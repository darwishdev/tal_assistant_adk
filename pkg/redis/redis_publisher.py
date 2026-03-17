"""
redis_publisher.py — publish NQI results and signals to Redis pub/sub channels
"""
import json
import logging
import os

import redis.asyncio as aioredis

log = logging.getLogger(__name__)

REDIS_URL      = os.environ.get("REDIS_URL", "redis://localhost:6379")
NQI_CHANNEL    = os.environ.get("NQI_CHANNEL", "nqi:results")
SIGNAL_CHANNEL = os.environ.get("SIGNAL_CHANNEL", "signal:results")

# How many recent signals to keep per session and send to NQI
SIGNAL_HISTORY_LEN = int(os.environ.get("SIGNAL_HISTORY_LEN", "10"))
# Redis key TTL for signal history (seconds) — default 4 hours
SIGNAL_HISTORY_TTL = int(os.environ.get("SIGNAL_HISTORY_TTL", "14400"))
_redis: aioredis.Redis | None = None



def _signal_history_key(session_id: str) -> str:
    return f"signal_history:{session_id}"


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