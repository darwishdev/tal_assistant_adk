"""
redis_publisher.py — publish NQI results and signals to Redis pub/sub channels
"""
import json
import logging
import os
from typing import Optional

import redis.asyncio as aioredis
from pkg.ats_api.models import InterviewData

log = logging.getLogger(__name__)

REDIS_URL      = os.environ.get("REDIS_URL", "redis://localhost:6379")
NQI_CHANNEL    = os.environ.get("NQI_CHANNEL", "nqi:results")
SIGNAL_CHANNEL = os.environ.get("SIGNAL_CHANNEL", "signal:results")

# How many recent signals to keep per session and send to NQI
SIGNAL_HISTORY_LEN = int(os.environ.get("SIGNAL_HISTORY_LEN", "10"))
# Redis key TTL for signal history (seconds) — default 4 hours
SIGNAL_HISTORY_TTL = int(os.environ.get("SIGNAL_HISTORY_TTL", "14400"))
# Redis key TTL for interview context (seconds) — default 8 hours
INTERVIEW_CONTEXT_TTL = int(os.environ.get("INTERVIEW_CONTEXT_TTL", "28800"))
_redis: aioredis.Redis | None = None



def _signal_history_key(session_id: str) -> str:
    return f"signal_history:{session_id}"


def _interview_context_key(session_id: str) -> str:
    return f"interview_context:{session_id}"


def _personalized_interview_key(interview_id: str) -> str:
    """Redis key for personalized interview data (from Question Bank Personalizer)."""
    return f"personalized_interview:{interview_id}"


async def append_signal(session_id: str, signal_data: dict) -> None:
    """
    Append a detected signal to the session's history list in Redis.
    Keeps only the last SIGNAL_HISTORY_LEN entries. Refreshes TTL on every write.
    """
    try:
        r   = await get_redis()
        key = _signal_history_key(session_id)
        entry = json.dumps({
            "type":      signal_data.get("type", ""),
            "text":      signal_data.get("text", ""),
            "timestamp": signal_data.get("timestamp", ""),
        }, ensure_ascii=False)
        pipe = r.pipeline()
        pipe.rpush(key, entry)
        pipe.ltrim(key, -SIGNAL_HISTORY_LEN, -1)   # keep only the last N
        pipe.expire(key, SIGNAL_HISTORY_TTL)
        await pipe.execute()
        log.info("appended signal session=%s type=%s history_key=%s",
                 session_id, signal_data.get("type"), key)
    except Exception as e:
        log.warning("append_signal failed session=%s: %s", session_id, e)


async def get_signal_history(session_id: str) -> list[dict]:
    """
    Return all stored signals for the session, oldest first.
    """
    try:
        r       = await get_redis()
        key     = _signal_history_key(session_id)
        entries = await r.lrange(key, 0, -1)
        return [json.loads(e) for e in entries]
    except Exception as e:
        log.warning("get_signal_history failed session=%s: %s", session_id, e)
        return []

async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def publish_nqi_result(session_id: str, nqi_data: dict) -> None:
    """
    Publish an NQI result to NQI_CHANNEL.
    Payload: {"session_id": "...", "next_question": "...", "rationale": "..."}
    """
    try:
        r = await get_redis()
        payload = json.dumps({
            "session_id":    session_id,
            "next_question": nqi_data.get("next_question", ""),
            "rationale":     nqi_data.get("rationale", ""),
        }, ensure_ascii=False)
        await r.publish(NQI_CHANNEL, payload)
        log.info("published NQI result session=%s channel=%s", session_id, NQI_CHANNEL)
    except Exception as e:
        log.warning("Redis publish failed (NQI) session=%s: %s", session_id, e)


async def publish_signal(session_id: str, signal_data: dict) -> None:
    """
    Publish a detected signal (question or answer) to SIGNAL_CHANNEL.
    Payload: {"session_id": "...", "type": "question|answer", "text": "...", "timestamp": "..."}
    """
    try:
        r = await get_redis()
        payload = json.dumps({
            "session_id": session_id,
            "type":       signal_data.get("type", ""),
            "text":       signal_data.get("text", ""),
            "timestamp":  signal_data.get("timestamp", ""),
        }, ensure_ascii=False)
        await r.publish(SIGNAL_CHANNEL, payload)
        log.info("published signal session=%s type=%s channel=%s",
                 session_id, signal_data.get("type"), SIGNAL_CHANNEL)
    except Exception as e:
        log.warning("Redis publish failed (signal) session=%s: %s", session_id, e)


async def clear_signal_history(session_id: str) -> None:
    """
    Delete the signal history list for a session.
    Call this at the start of each new session to prevent stale data bleeding in.
    """
    try:
        r   = await get_redis()
        key = _signal_history_key(session_id)
        await r.delete(key)
        log.info("cleared signal history session=%s key=%s", session_id, key)
    except Exception as e:
        log.warning("clear_signal_history failed session=%s: %s", session_id, e)


async def store_interview_context(
    session_id: str, 
    interview_id: str, 
    interview_data: InterviewData
) -> None:
    """
    Store interview data in Redis for a session.
    
    Args:
        session_id: Unique session identifier
        interview_id: Interview ID (e.g., "HR-INT-2026-0001")
        interview_data: Complete interview data from ATS API
    
    The data is stored with a TTL (default 8 hours) and can be retrieved
    using get_interview_context().
    """
    try:
        r = await get_redis()
        key = _interview_context_key(session_id)
        
        # Store as JSON with interview_id metadata
        context = {
            "interview_id": interview_id,
            "session_id": session_id,
            "data": interview_data.model_dump(mode="json")
        }
        
        await r.set(key, json.dumps(context, ensure_ascii=False), ex=INTERVIEW_CONTEXT_TTL)
        log.info(
            "stored interview context session=%s interview=%s key=%s ttl=%ds",
            session_id, interview_id, key, INTERVIEW_CONTEXT_TTL
        )
    except Exception as e:
        log.error(
            "store_interview_context failed session=%s interview=%s: %s",
            session_id, interview_id, e, exc_info=True
        )


async def get_interview_context(session_id: str) -> Optional[InterviewData]:
    """
    Retrieve interview data for a session from Redis.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        InterviewData object if found, None if not found or error
    
    This should be called in agent executors to get the interview context
    needed for generating questions.
    """
    try:
        r = await get_redis()
        key = _interview_context_key(session_id)
        data = await r.get(key)
        
        if not data:
            log.warning("interview context not found session=%s key=%s", session_id, key)
            return None
        
        context = json.loads(data)
        interview_data = InterviewData.model_validate(context["data"])
        
        log.info(
            "retrieved interview context session=%s interview=%s",
            session_id, context.get("interview_id")
        )
        return interview_data
        
    except Exception as e:
        log.error(
            "get_interview_context failed session=%s: %s",
            session_id, e, exc_info=True
        )
        return None


async def store_personalized_interview_data(
    interview_id: str,
    personalized_data: dict,
    interview_data: Optional[InterviewData] = None
) -> None:
    """
    Store personalized interview data from Question Bank Personalizer in Redis.
    
    Args:
        interview_id: Interview ID (e.g., "HR-INT-2026-0001")
        personalized_data: Dict containing personalized_question_bank and summarized_resume
        interview_data: Optional full interview data from ATS API (job opening, applicant, resume, etc.)
    
    The data is stored with the interview_id as the key and a TTL (default 8 hours).
    This allows the personalized context to be retrieved during the interview session.
    """
    try:
        r = await get_redis()
        key = _personalized_interview_key(interview_id)
        
        # Store the personalized data with interview_id metadata
        context = {
            "interview_id": interview_id,
            "personalized_question_bank": personalized_data.get("personalized_question_bank", {}),
            "summarized_resume": personalized_data.get("summarized_resume", ""),
            "timestamp": personalized_data.get("timestamp")  # optional
        }
        
        # Include full interview data if provided
        if interview_data:
            context["interview_data"] = interview_data.model_dump(mode="json")
        
        await r.set(key, json.dumps(context, ensure_ascii=False), ex=INTERVIEW_CONTEXT_TTL)
        log.info(
            "stored personalized interview data interview=%s key=%s ttl=%ds categories=%d has_interview_data=%s",
            interview_id, key, INTERVIEW_CONTEXT_TTL,
            len(context["personalized_question_bank"].get("categories", [])),
            interview_data is not None
        )
    except Exception as e:
        log.error(
            "store_personalized_interview_data failed interview=%s: %s",
            interview_id, e, exc_info=True
        )


async def get_personalized_interview_data(interview_id: str) -> Optional[dict]:
    """
    Retrieve personalized interview data for an interview from Redis.
    
    Args:
        interview_id: Interview ID (e.g., "HR-INT-2026-0001")
    
    Returns:
        Dict with personalized_question_bank, summarized_resume, and optionally interview_data if found,
        None if not found or error
    
    This should be called in agent executors to get the personalized context
    (personalized questions, resume summary, and full interview data) during the interview.
    """
    try:
        r = await get_redis()
        key = _personalized_interview_key(interview_id)
        data = await r.get(key)
        
        if not data:
            log.warning(
                "personalized interview data not found interview=%s key=%s",
                interview_id, key
            )
            return None
        
        context = json.loads(data)
        
        result = {
            "personalized_question_bank": context.get("personalized_question_bank", {}),
            "summarized_resume": context.get("summarized_resume", ""),
            "timestamp": context.get("timestamp")
        }
        
        # Include interview_data if it was stored
        if "interview_data" in context:
            result["interview_data"] = InterviewData.model_validate(context["interview_data"])
        
        log.info(
            "retrieved personalized interview data interview=%s categories=%d has_interview_data=%s",
            interview_id,
            len(context.get("personalized_question_bank", {}).get("categories", [])),
            "interview_data" in context
        )
        
        return result
        
    except Exception as e:
        log.error(
            "get_personalized_interview_data failed interview=%s: %s",
            interview_id, e, exc_info=True
        )
        return None
