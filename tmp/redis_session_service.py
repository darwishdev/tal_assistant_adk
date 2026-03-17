"""
redis_session_service.py — ADK-compatible Redis session service
"""
import json
import logging
import os
from typing import Optional

import redis.asyncio as aioredis

from google.adk.sessions import BaseSessionService, Session
from google.adk.events import Event

log = logging.getLogger(__name__)

SESSION_TTL = int(os.environ.get("REDIS_SESSION_TTL_SECONDS", str(60 * 60 * 24)))


def _session_key(app_name: str, user_id: str, session_id: str) -> str:
    return f"adk:session:{app_name}:{user_id}:{session_id}"


def _events_key(app_name: str, user_id: str, session_id: str) -> str:
    return f"adk:events:{app_name}:{user_id}:{session_id}"


class RedisSessionService(BaseSessionService):

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def _r(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            log.info("[redis-session] connected to %s", self._redis_url)
        return self._redis

    async def create_session(self, *, app_name, user_id, session_id=None, state=None):
        import uuid
        sid = session_id or str(uuid.uuid4())
        session = Session(app_name=app_name, user_id=user_id, id=sid, state=state or {})
        r = await self._r()
        await r.set(
            _session_key(app_name, user_id, sid),
            json.dumps({"app_name": app_name, "user_id": user_id, "id": sid, "state": state or {}}),
            ex=SESSION_TTL,
        )
        log.debug("[redis-session] created %s", sid)
        return session

    async def get_session(self, *, app_name, user_id, session_id, config=None):
        r = await self._r()
        sk = _session_key(app_name, user_id, session_id)
        raw = await r.get(sk)
        if raw is None:
            return None
        data = json.loads(raw)
        session = Session(
            app_name=data["app_name"],
            user_id=data["user_id"],
            id=data["id"],
            state=data.get("state", {}),
        )
        ek = _events_key(app_name, user_id, session_id)
        event_jsons = await r.lrange(ek, 0, -1)
        events = []
        for ej in event_jsons:
            try:
                events.append(Event.model_validate_json(ej))
            except Exception as e:
                log.warning("[redis-session] bad event: %s", e)
        session.events = events
        await r.expire(sk, SESSION_TTL)
        await r.expire(ek, SESSION_TTL)
        return session

    async def list_sessions(self, *, app_name, user_id):
        r = await self._r()
        keys = await r.keys(_session_key(app_name, user_id, "*"))
        sessions = []
        for sk in keys:
            raw = await r.get(sk)
            if raw:
                try:
                    data = json.loads(raw)
                    sessions.append(Session(
                        app_name=data["app_name"],
                        user_id=data["user_id"],
                        id=data["id"],
                        state=data.get("state", {}),
                    ))
                except Exception as e:
                    log.warning("[redis-session] bad session %s: %s", sk, e)
        return sessions

    async def delete_session(self, *, app_name, user_id, session_id):
        r = await self._r()
        await r.delete(
            _session_key(app_name, user_id, session_id),
            _events_key(app_name, user_id, session_id),
        )
        log.debug("[redis-session] deleted %s", session_id)

    async def append_event(self, session: Session, event: Event) -> Event:
        r = await self._r()
        ek = _events_key(session.app_name, session.user_id, session.id)
        await r.rpush(ek, event.model_dump_json())
        await r.expire(ek, SESSION_TTL)
        await r.expire(_session_key(session.app_name, session.user_id, session.id), SESSION_TTL)
        return event