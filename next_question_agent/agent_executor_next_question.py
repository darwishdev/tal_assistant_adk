"""
agent_executor_next_question.py — NextQuestionExecutor
-------------------------------------------------------
Handles two trigger modes:
  1. AUTO   — called by the signal detector after a Q/A pair is complete.
               Input format: "AUTO|<json with question+answer+optional context>"
  2. MANUAL — called directly by a user/client.
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
from pkg.redis.redis_publisher import publish_nqi_result

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
    """Extract {"next_question": ..., "rationale": ...} from model output."""
    idx = raw.find("{")
    if idx == -1:
        return None
    clean = raw[idx:]
    try:
        result = json.loads(clean)
        if result.get("next_question"):
            return result
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(clean)
    if m:
        try:
            result = json.loads(m.group())
            if result.get("next_question"):
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

        # ── AUTO mode ────────────────────────────────────────────────────────
        if mode == "AUTO":
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
                new_agent_text_message("ERROR: expected AUTO|... or MANUAL|prompt|transcript")
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

        log.info("NQI suggestion session=%s: %r", session_id, result["next_question"][:80])

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