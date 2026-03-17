"""
agent_executor.py — SignalDetectorExecutor (updated)
-----------------------------------------------------
After emitting a complete question OR answer signal, automatically calls
the Next Question Inferrer (NQI) agent on port 50052.

The NQI call is fire-and-forget within the same async context: the signal
detector replies immediately and does NOT wait for the NQI result (so latency
is unaffected). The NQI result is pushed separately to whoever is listening
on the NQI task stream.

If you want to WAIT for the NQI result and bundle it in the same response,
set NQI_INLINE=true in the environment.
"""
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

from agent import signal_detector
from redis_session_service import RedisSessionService

log = logging.getLogger(__name__)

APP_NAME  = "signal_detector"
USER_ID   = "go-client"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# ── NQI connection settings ──────────────────────────────────────────────────
# NQI_INLINE must be true so the result travels back to the Go client.
# Fire-and-forget has nowhere to deliver the result since the gRPC response
# is already closed. Default is now true.
NQI_ADDR   = os.environ.get("NQI_ADDR", "localhost:50052")
NQI_INLINE = os.environ.get("NQI_INLINE", "true").lower() == "true"

_JSON_RE = re.compile(r'\{[^{}]+\}', re.DOTALL)

session_service = RedisSessionService(redis_url=REDIS_URL)

runner = Runner(
    app_name=APP_NAME,
    agent=signal_detector,
    session_service=session_service,
)

# Rolling buffer: session_id → {"question": str | None, "answer": str | None}
_qa_buffer: dict[str, dict] = {}


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


async def _ensure_session(session_id: str):
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
        )
        log.info("new session: %s", session_id)
    return session


async def _call_nqi(session_id: str, question: str, answer: str) -> str | None:
    """
    Fire an AUTO trigger to the Next Question Inferrer agent over gRPC.
    Returns the raw JSON string from NQI, or None on failure.
    """
    payload_json = json.dumps({"question": question, "answer": answer}, ensure_ascii=False)
    nqi_input    = f"AUTO|{payload_json}"

    try:
        async with grpc.aio.insecure_channel(NQI_ADDR) as channel:
            stub = a2a_pb2_grpc.A2AServiceStub(channel)

            send_request = a2a_pb2.SendMessageRequest(
                message=a2a_pb2.Message(
                    role=a2a_pb2.Role.ROLE_USER,
                    content=[a2a_pb2.Part(text=a2a_pb2.TextPart(text=nqi_input))],
                    context_id=f"nqi-{session_id}",
                )
            )
            response = await stub.SendMessage(send_request)

            for part in (response.result.message.parts if response.result.HasField("message") else []):
                if part.HasField("text") and part.text.text.strip():
                    return part.text.text.strip()

    except Exception as e:
        log.warning("NQI call failed for session %s: %s", session_id, e)

    return None


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

        await _ensure_session(session_id)

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
                    app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
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

        # ── Update rolling Q/A buffer ────────────────────────────────────────
        buf = _qa_buffer.setdefault(session_id, {"question": None, "answer": None})
        if result["type"] == "question":
            buf["question"] = result["text"]
            buf["answer"]   = None          # reset answer for new Q
        elif result["type"] == "answer":
            buf["answer"] = result["text"]

        # ── Delete the signal-detector session (original behaviour) ──────────
        await session_service.delete_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
        )

        # ── Trigger NQI when we have a complete Q/A pair ─────────────────────
        if buf["question"] and buf["answer"]:
            q, a = buf["question"], buf["answer"]
            _qa_buffer[session_id] = {"question": None, "answer": None}

            if NQI_INLINE:
                nqi_raw = await _call_nqi(session_id, q, a)
                if nqi_raw:
                    log.info("NQI inline result session=%s: %r", session_id, nqi_raw[:80])
                    try:
                        nqi_data = json.loads(nqi_raw)
                        # Bundle NQI result into the signal payload so a single
                        # gRPC response carries everything back to the Go client.
                        result["next_question"] = nqi_data.get("next_question", "")
                        result["nqi_rationale"] = nqi_data.get("rationale", "")
                    except json.JSONDecodeError:
                        log.warning("NQI result not valid JSON: %r", nqi_raw[:80])
            else:
                asyncio.create_task(_call_nqi(session_id, q, a))
                log.info("NQI fire-and-forget triggered for session=%s", session_id)

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
        _qa_buffer.pop(session_id, None)
        try:
            await session_service.delete_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
            )
        except Exception as e:
            log.warning("delete session error: %s", e)
        log.info("cancelled: %s", session_id)