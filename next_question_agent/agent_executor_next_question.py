"""
agent_executor_next_question.py — NextQuestionExecutor
-------------------------------------------------------
Handles three trigger modes:
  1. INIT   — initializes the session with interview context from Redis.
               Input format: "INIT|<interview_id>"
               Fetches personalized interview data and sends FORMAT A to agent.
  2. AUTO   — called by the signal detector after a Q/A pair is complete.
               Input format: "AUTO|<json with question+answer+optional context>"
  3. MANUAL — called directly by a user/client.
               Input format: "MANUAL|<user prompt>|<optional transcript snippet>"

Maintains a rolling conversation history in Redis so the agent remembers
all Q/A pairs seen so far within a session.
"""
import json
import logging
import os
import re
from typing_extensions import override

from google.adk.runners import Runner
from google.genai.types import Content, Part

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from next_question_agent.agent_next_question import next_question_inferrer
from pkg.redis.redis_session_service import RedisSessionService
from pkg.redis.redis_publisher import publish_nqi_result, get_personalized_interview_data, get_redis

log = logging.getLogger(__name__)

APP_NAME  = "next_question_inferrer"
USER_ID   = "go-client"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

_JSON_RE = re.compile(r'\{[^{}]+\}', re.DOTALL)

session_service = RedisSessionService(redis_url=REDIS_URL)

runner = Runner(
    app_name=APP_NAME,
    agent=next_question_inferrer,
    session_service=session_service,
)


def _parse_suggestion(raw: str) -> dict | None:
    """Extract {"next_question": ..., "rationale": ...} from model output.
    
    Returns:
        - Dict with next_question and rationale (FOLLOW_UP or CHANGE_QUESTION)
        - Dict with only rationale and strategy (PREDEFINED - no next_question)
        - None if parsing failed
    """
    idx = raw.find("{")
    if idx == -1:
        return None
    clean = raw[idx:]
    try:
        result = json.loads(clean)
        # Valid response can have next_question OR be PREDEFINED strategy without it
        if result.get("next_question") or result.get("strategy") == "PREDEFINED":
            return result
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(clean)
    if m:
        try:
            result = json.loads(m.group())
            if result.get("next_question") or result.get("strategy") == "PREDEFINED":
                return result
        except json.JSONDecodeError:
            pass
    return None

def _build_auto_payload(data: dict) -> str:
    """
    Build the prompt sent to the LLM for an AUTO trigger.
    data keys: history (list of {type, text, timestamp})
    """
    history: list[dict] = data.get("history", [])

    if not history:
        return "No signal history available."

    lines = []
    for entry in history:
        sig_type  = entry.get("type", "unknown").upper()
        sig_text  = entry.get("text", "").strip()
        sig_ts    = entry.get("timestamp", "")
        prefix    = f"[{sig_ts}] " if sig_ts else ""
        lines.append(f"{prefix}{sig_type}: {sig_text}")

    return "\n".join(lines)


def _build_manual_payload(user_prompt: str, transcript: str) -> str:
    lines = [
        "MANUAL_TRIGGER",
        f"PROMPT: {user_prompt.strip()}",
    ]
    if transcript.strip():
        lines.append(f"TRANSCRIPT_CONTEXT: {transcript.strip()}")
    return "\n".join(lines)


def _build_init_payload(personalized_data: dict) -> str:
    """
    Build FORMAT A initialization payload from personalized interview data.
    This is sent as the FIRST message to initialize the agent with interview context.
    
    Expected response from agent: null (acknowledging context loaded)
    """
    # Extract interview data
    interview_data = personalized_data.get("interview_data")
    if not interview_data:
        return "ERROR: No interview data found in Redis. Run Question Bank Personalizer first."
    
    # Extract recruiter info (if available)
    recruiter_info = "Name: Not specified\nEmail: Not specified"
    # TODO: Add recruiter info to interview_data if needed
    
    # Extract job description
    job_opening = interview_data.job_opening
    job_description = f"""Role: {job_opening.job_title}
Designation: {job_opening.designation}
Company: {job_opening.company or 'Not specified'}
Location: {job_opening.location or 'Not specified'}
Employment Type: {job_opening.employment_type or 'Full-time'}

{job_opening.description or 'No description available'}"""
    
    # Extract candidate resume (use summarized version)
    candidate_resume = personalized_data.get("summarized_resume", "No resume summary available")
    
    # Extract personalized question bank
    question_bank_data = personalized_data.get("personalized_question_bank", {})
    question_bank_lines = []
    
    for category in question_bank_data.get("categories", []):
        category_name = category.get("category_name", "Uncategorized")
        question_bank_lines.append(f"\n─── {category_name} {'─' * max(0, 60 - len(category_name))}")
        
        for q in category.get("questions", []):
            question_text = q.get("question_text", "")
            difficulty = q.get("difficulty", "medium").upper()
            question_bank_lines.append(f"- [{difficulty}] {question_text}")
    
    question_bank = "\n".join(question_bank_lines) if question_bank_lines else "No personalized questions available"
    
    # Build FORMAT A payload
    payload = f"""RECRUITER:
{recruiter_info}

JOB_DESCRIPTION:
{job_description}

CANDIDATE_RESUME:
{candidate_resume}

QUESTION_BANK:
{question_bank}"""
    
    return payload


async def _get_question_index_key(session_id: str) -> str:
    """Get Redis key for tracking question bank index."""
    return f"question_index:{session_id}"


async def _get_current_question_index(session_id: str) -> int:
    """Get current question index from Redis (0-based)."""
    try:
        r = await get_redis()
        key = await _get_question_index_key(session_id)
        index = await r.get(key)
        return int(index) if index else 0
    except Exception as e:
        log.warning(f"Failed to get question index for session {session_id}: {e}")
        return 0


async def _increment_question_index(session_id: str) -> int:
    """Increment and return the new question index."""
    try:
        r = await get_redis()
        key = await _get_question_index_key(session_id)
        new_index = await r.incr(key)
        # Set TTL of 8 hours on the index key
        await r.expire(key, 28800)
        return int(new_index)
    except Exception as e:
        log.error(f"Failed to increment question index for session {session_id}: {e}")
        return 0


async def _get_next_predefined_question(session_id: str) -> dict | None:
    """Get next question from personalized question bank.
    
    Returns:
        Dict with next_question, rationale, and strategy, or None if no more questions
    """
    try:
        # Get current index
        current_index = await _get_current_question_index(session_id)
        
        # Get interview_id from session (assuming it's stored during INIT)
        # For now, we'll try to extract from session data or use a convention
        # TODO: Store interview_id mapping during INIT
        r = await get_redis()
        interview_id_key = f"session_interview_id:{session_id}"
        interview_id = await r.get(interview_id_key)
        
        if not interview_id:
            log.warning(f"No interview_id found for session {session_id}")
            return None
        
        # Get personalized data from Redis
        personalized_data = await get_personalized_interview_data(interview_id)
        if not personalized_data:
            log.error(f"No personalized data found for interview {interview_id}")
            return None
        
        # Extract all questions from all categories
        question_bank = personalized_data.get("personalized_question_bank", {})
        categories = question_bank.get("categories", [])
        
        all_questions = []
        for category in categories:
            for q in category.get("questions", []):
                all_questions.append({
                    "question_text": q.get("question_text", ""),
                    "category": category.get("category_name", "Uncategorized"),
                    "difficulty": q.get("difficulty", "medium"),
                    "rationale": q.get("rationale", "")
                })
        
        if not all_questions:
            log.warning("No questions available in personalized question bank")
            return None
        
        # Check if we've exhausted all questions
        if current_index >= len(all_questions):
            log.info(f"All {len(all_questions)} questions have been asked")
            return {
                "next_question": None,
                "rationale": "All personalized questions have been asked. Consider wrapping up the interview or exploring topics in more depth.",
                "strategy": "PREDEFINED"
            }
        
        # Get the question at current index
        question = all_questions[current_index]
        
        # Increment index for next time
        await _increment_question_index(session_id)
        
        log.info(f"Returning predefined question {current_index + 1}/{len(all_questions)} from category '{question['category']}'")
        
        return {
            "next_question": question["question_text"],
            "rationale": question.get("rationale") or f"Predefined question from category: {question['category']} [Difficulty: {question['difficulty'].upper()}]",
            "strategy": "PREDEFINED",
            "metadata": {
                "category": question["category"],
                "difficulty": question["difficulty"],
                "question_number": current_index + 1,
                "total_questions": len(all_questions)
            }
        }
        
    except Exception as e:
        log.error(f"Failed to get next predefined question: {e}", exc_info=True)
        return None


async def _store_interview_id_mapping(session_id: str, interview_id: str):
    """Store interview_id mapping for session."""
    try:
        r = await get_redis()
        key = f"session_interview_id:{session_id}"
        await r.set(key, interview_id, ex=28800)  # 8 hours TTL
        log.info(f"Stored interview_id mapping: {session_id} -> {interview_id}")
    except Exception as e:
        log.error(f"Failed to store interview_id mapping: {e}")


async def _ensure_session(session_id: str):
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
        )
        log.info("new NQI session: %s", session_id)
    return session


class NextQuestionExecutor(AgentExecutor):

    @override
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_input = context.get_user_input()
        if not user_input:
            await event_queue.enqueue_event(new_agent_text_message(""))
            return

        parts = user_input.split("|", 2)
        mode  = parts[0].strip().upper() if parts else ""

        # ── INIT mode ────────────────────────────────────────────────────────
        if mode == "INIT":
            if len(parts) < 2:
                log.warning("INIT trigger missing interview_id")
                await event_queue.enqueue_event(new_agent_text_message("ERROR: missing interview_id"))
                return
            
            interview_id = parts[1].strip()
            session_id = context.context_id or "nqi-default"
            log.info("INIT trigger session=%s interview_id=%s", session_id, interview_id)
            
            # Store interview_id mapping for this session
            await _store_interview_id_mapping(session_id, interview_id)
            
            # Fetch personalized interview data from Redis
            try:
                personalized_data = await get_personalized_interview_data(interview_id)
                if not personalized_data:
                    error_msg = f"ERROR: No personalized data found for interview {interview_id}. Run Question Bank Personalizer first."
                    log.error(error_msg)
                    await event_queue.enqueue_event(new_agent_text_message(error_msg))
                    return
                
                payload = _build_init_payload(personalized_data)
                log.info("Built INIT payload for interview=%s (length=%d chars)", interview_id, len(payload))
                
            except Exception as e:
                error_msg = f"ERROR: Failed to fetch personalized data: {str(e)}"
                log.error(error_msg, exc_info=True)
                await event_queue.enqueue_event(new_agent_text_message(error_msg))
                return

        # ── AUTO mode ────────────────────────────────────────────────────────
        elif mode == "AUTO":
            if len(parts) < 2:
                log.warning("AUTO trigger missing payload")
                await event_queue.enqueue_event(new_agent_text_message("ERROR: missing JSON payload"))
                return
            try:
                data = json.loads(parts[1])
            except json.JSONDecodeError as e:
                log.warning("AUTO trigger bad JSON: %s", e)
                await event_queue.enqueue_event(new_agent_text_message("ERROR: bad JSON"))
                return
            payload = _build_auto_payload(data)
            log.info("AUTO trigger session=%s q=%r", context.context_id, data.get("question", "")[:60])

        # ── MANUAL mode ──────────────────────────────────────────────────────
        elif mode == "MANUAL":
            user_prompt = parts[1].strip() if len(parts) > 1 else ""
            transcript  = parts[2].strip() if len(parts) > 2 else ""
            if not user_prompt:
                await event_queue.enqueue_event(new_agent_text_message("ERROR: empty prompt"))
                return
            payload = _build_manual_payload(user_prompt, transcript)
            log.info("MANUAL trigger session=%s prompt=%r", context.context_id, user_prompt[:60])

        else:
            log.warning("unknown mode: %r", mode)
            await event_queue.enqueue_event(
                new_agent_text_message("ERROR: expected INIT|interview_id or AUTO|... or MANUAL|prompt|transcript")
            )
            return

        session_id = context.context_id or "nqi-default"
        await _ensure_session(session_id)

        raw = ""
        try:
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session_id,
                new_message=Content(role="user", parts=[Part(text=payload)]),
            ):
                if event.content and event.content.parts:
                    candidate = "".join(
                        p.text for p in event.content.parts if p.text
                    ).strip()
                    if candidate:
                        raw = candidate

        except Exception as e:
            error_str = str(e)
            if "Session not found" in error_str or "NOT_FOUND" in error_str:
                log.warning("session gone [%s], recreating", session_id)
                await session_service.create_session(
                    app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
                )
            else:
                log.error("NQI runner error [%s]: %s", session_id, e)
            await event_queue.enqueue_event(new_agent_text_message(""))
            return

        log.debug("NQI session=%s raw=%r", session_id, raw[:120])

        result = _parse_suggestion(raw)
        if not result:
            log.warning("NQI could not parse suggestion from: %r", raw[:120])
            await event_queue.enqueue_event(new_agent_text_message(""))
            return

        # ── Handle PREDEFINED strategy (no next_question in response) ───────
        if result.get("strategy") == "PREDEFINED" and not result.get("next_question"):
            log.info("Agent chose PREDEFINED strategy, fetching from question bank...")
            predefined_result = await _get_next_predefined_question(session_id)
            
            if predefined_result:
                # Merge agent's rationale with predefined question
                if result.get("rationale"):
                    predefined_result["agent_rationale"] = result["rationale"]
                result = predefined_result
                log.info(f"Using predefined question: {result['next_question'][:80] if result.get('next_question') else 'No more questions'}")
            else:
                log.warning("Failed to get predefined question from bank")
                result["next_question"] = None
                result["rationale"] = "Unable to retrieve predefined question from question bank."

        log.info("NQI suggestion session=%s strategy=%s: %r", 
                 session_id, 
                 result.get("strategy", "UNKNOWN"),
                 result.get("next_question", "null")[:80] if result.get("next_question") else "null")

        # ── Publish to Redis — NQI agent always owns this ────────────────────
        await publish_nqi_result(session_id, result)

        await event_queue.enqueue_event(
            new_agent_text_message(json.dumps(result, ensure_ascii=False))
        )

    @override
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        session_id = context.context_id or "nqi-default"
        try:
            await session_service.delete_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
            )
        except Exception as e:
            log.warning("NQI delete session error: %s", e)
        log.info("NQI cancelled: %s", session_id)