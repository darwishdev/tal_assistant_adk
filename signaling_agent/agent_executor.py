import asyncio
import json
import logging
import os
import re
from typing_extensions import override

import grpc
from google.adk.runners import Runner
from google.genai.types import Content, Part

from a2a.grpc import a2a_pb2, a2a_pb2_grpc
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from signaling_agent.agent import signal_detector
from pkg.redis.redis_session_service import RedisSessionService
from pkg.redis.redis_publisher import publish_signal

log = logging.getLogger(__name__)

APP_NAME  = "signal_detector"
USER_ID   = "go-client"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

NQI_ADDR        = os.environ.get("NQI_ADDR", "localhost:50052")
NQI_INLINE      = os.environ.get("NQI_INLINE", "true").lower() == "true"
SIGNAL_HIST_MAX = int(os.environ.get("SIGNAL_HISTORY_LEN", "20"))

_JSON_RE = re.compile(r'\{[^{}]+\}', re.DOTALL)

session_service = RedisSessionService(redis_url=REDIS_URL)

runner = Runner(
    app_name=APP_NAME,
    agent=signal_detector,
    session_service=session_service,
)


def _parse_signal(raw: str) -> dict | None:
    idx = raw.find("{")
    if idx == -1:
        return None
    clean = raw[idx:]
    try:
        result = json.loads(clean)
        if result.get("type") in ("question", "answer") and result.get("text"):
            return result
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(clean)
    if m:
        try:
            result = json.loads(m.group())
            if result.get("type") in ("question", "answer") and result.get("text"):
                return result
        except json.JSONDecodeError:
            pass
    return None


async def _get_or_create_session(session_id: str):
    """
    Get existing session or create a fresh one.
    Session state schema:
      { "signals": [ {"type": "...", "text": "...", "timestamp": "..."}, ... ] }
    """
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
            state={"signals": []},
        )
        log.info("new session created: %s", session_id)
    elif "signals" not in session.state:
        session.state["signals"] = []
    return session


async def _append_signal_to_session(session_id: str, signal: dict) -> list[dict]:
    """
    Load the session, append the new signal to state["signals"], persist, and
    return the full updated history (capped at SIGNAL_HIST_MAX).
    """
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
    )
    if session is None:
        log.warning("session gone when appending signal: %s", session_id)
        return [signal]

    history: list[dict] = session.state.get("signals", [])
    history.append({
        "type":      signal.get("type", ""),
        "text":      signal.get("text", ""),
        "timestamp": signal.get("timestamp", ""),
    })

    # cap history
    if len(history) > SIGNAL_HIST_MAX:
        history = history[-SIGNAL_HIST_MAX:]

    session.state["signals"] = history

    # persist updated state back to Redis
    from pkg.redis.redis_session_service import _session_key, SESSION_TTL
    import json as _json
    r = await session_service._r()
    await r.set(
        _session_key(APP_NAME, USER_ID, session_id),
        _json.dumps({
            "app_name": APP_NAME,
            "user_id":  USER_ID,
            "id":       session_id,
            "state":    session.state,
        }),
        ex=SESSION_TTL,
    )
    log.info("session state updated session=%s signals_count=%d",
             session_id, len(history))
    return history


async def _call_nqi(session_id: str, history: list[dict]) -> None:
    payload_json = json.dumps({"history": history}, ensure_ascii=False)
    nqi_input    = f"AUTO|{payload_json}"

    log.info("NQI call START session=%s history_len=%d", session_id, len(history))
    log.debug("NQI full payload: %s", nqi_input)

    try:
        async with grpc.aio.insecure_channel(NQI_ADDR) as channel:
            stub = a2a_pb2_grpc.A2AServiceStub(channel)
            send_request = a2a_pb2.SendMessageRequest(
                request=a2a_pb2.Message(
                    role=a2a_pb2.Role.ROLE_USER,
                    content=[a2a_pb2.Part(text=nqi_input)],
                    context_id=f"nqi-{session_id}",
                )
            )
            log.info("NQI gRPC sending to %s context_id=nqi-%s", NQI_ADDR, session_id)
            response = await stub.SendMessage(send_request)

            if response.HasField("msg"):
                raw = "".join(p.text for p in response.msg.content).strip()
                log.info("NQI response text=%r session=%s", raw[:200], session_id)
            else:
                log.warning("NQI response has no msg field session=%s", session_id)

    except grpc.aio.AioRpcError as e:
        log.error("NQI gRPC error session=%s status=%s details=%s",
                  session_id, e.code(), e.details())
    except Exception:
        log.exception("NQI unexpected error session=%s", session_id)


class SignalDetectorExecutor(AgentExecutor):

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

        parts_split = user_input.split("|", 2)
        if len(parts_split) != 3:
            log.warning("bad format: %r", user_input)
            await event_queue.enqueue_event(
                new_agent_text_message("ERROR: expected SPEAKER|TIMESTAMP|TEXT")
            )
            return

        speaker, timestamp, text = parts_split
        session_id = context.context_id or "default"
        log.info("execute session=%s speaker=%s ts=%s text=%r",
                 session_id, speaker, timestamp, text)

        await _get_or_create_session(session_id)

        payload = f"[{speaker} @ {timestamp}]: {text}"
        raw     = ""

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
                    app_name=APP_NAME,
                    user_id=USER_ID,
                    session_id=session_id,
                    state={"signals": []},
                )
            else:
                log.error("runner error [%s]: %s", session_id, e)
            await event_queue.enqueue_event(new_agent_text_message(""))
            return

        log.debug("session=%s raw=%r", session_id, raw[:120])

        if not raw or raw.strip().upper() == "NONE":
            await event_queue.enqueue_event(new_agent_text_message(""))
            return

        result = _parse_signal(raw)
        if not result:
            await event_queue.enqueue_event(new_agent_text_message(""))
            return

        log.info("signal session=%s type=%s text=%r",
                 session_id, result["type"], result["text"][:60])

        # ── Store signal in session state + publish to Redis channel ─────────
        history = await _append_signal_to_session(session_id, result)
        await publish_signal(session_id, result)

        # ── Trigger NQI on every answer, passing full session history ────────
        if result["type"] == "answer":
            log.info("answer detected, triggering NQI session=%s history_len=%d",
                     session_id, len(history))
            if NQI_INLINE:
                await _call_nqi(session_id, history)
            else:
                asyncio.create_task(_call_nqi(session_id, history))
                log.info("NQI fire-and-forget triggered session=%s", session_id)
        else:
            log.info("question detected, skipping NQI session=%s", session_id)

        await event_queue.enqueue_event(
            new_agent_text_message(json.dumps(result, ensure_ascii=False))
        )

    @override
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        session_id = context.context_id or "default"
        try:
            await session_service.delete_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
            )
        except Exception as e:
            log.warning("delete session error: %s", e)
        log.info("cancelled: %s", session_id)