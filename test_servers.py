"""
test_servers.py — interactive test script for Signal Detector + NQI servers
Usage: python test_servers.py
"""
import asyncio
import json
import logging
import os
import sys

import grpc
from a2a.grpc import a2a_pb2, a2a_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
)
log = logging.getLogger(__name__)

SIGNAL_ADDR = os.environ.get("SIGNAL_ADDR", "localhost:50051")
NQI_ADDR    = os.environ.get("NQI_ADDR",    "localhost:50052")

# ── Sample data ──────────────────────────────────────────────────────────────

SAMPLE_SIGNALS = [
    ("INTERVIEWER", "00:00:10,000", "Can you tell me about your background in backend development?"),
    ("CANDIDATE",   "00:00:15,000", "Sure, I have 5 years of experience building REST APIs with Python and Go."),
    ("INTERVIEWER", "00:00:30,000", "What databases have you worked with?"),
    ("CANDIDATE",   "00:00:35,000", "Mostly PostgreSQL and Redis, but I also have experience with MongoDB."),
    ("INTERVIEWER", "00:01:00,000", "How do you handle authentication in your APIs?"),
    ("CANDIDATE",   "00:01:10,000", "I use JWT tokens with short expiry and refresh token rotation stored in Redis."),
]

SAMPLE_NQI_HISTORY = [
    {"type": "question", "text": "Can you tell me about your background?",          "timestamp": "00:00:10,000"},
    {"type": "answer",   "text": "I have 5 years of backend experience with Python.", "timestamp": "00:00:15,000"},
    {"type": "question", "text": "What databases have you worked with?",              "timestamp": "00:00:30,000"},
    {"type": "answer",   "text": "Mostly PostgreSQL and Redis.",                      "timestamp": "00:00:35,000"},
]


# ── gRPC helpers ─────────────────────────────────────────────────────────────

def _make_message(text: str, context_id: str) -> a2a_pb2.Message:
    return a2a_pb2.Message(
        role=a2a_pb2.Role.ROLE_USER,
        context_id=context_id,
        message_id=f"msg-test-{id(text)}",
        content=[a2a_pb2.Part(text=text)],
    )
async def send_message(stub: a2a_pb2_grpc.A2AServiceStub,
                       text: str,
                       context_id: str) -> str | None:
    req = a2a_pb2.SendMessageRequest(request=_make_message(text, context_id))
    try:
        resp = await stub.SendMessage(req)
        if resp.HasField("msg"):
            raw = "".join(p.text for p in resp.msg.content).strip()
            return raw or None
    except grpc.aio.AioRpcError as e:
        log.error("gRPC error: status=%s details=%s", e.code(), e.details())
    return None


async def ping(stub: a2a_pb2_grpc.A2AServiceStub, label: str) -> bool:
    """Check that the server is reachable."""
    try:
        req = a2a_pb2.GetAgentCardRequest()
        await stub.GetAgentCard(req)
        log.info("%-20s ✓ reachable", label)
        return True
    except grpc.aio.AioRpcError as e:
        log.error("%-20s ✗ unreachable: %s %s", label, e.code(), e.details())
        return False


# ── Individual tests ─────────────────────────────────────────────────────────

async def test_signal_no_signal(stub: a2a_pb2_grpc.A2AServiceStub):
    """Filler speech should return empty — no signal."""
    print("\n── test: signal / no signal ────────────────────────────────")
    text    = "INTERVIEWER|00:00:01,000|Hmm, let me think about that for a second."
    raw     = await send_message(stub, text, "test-nosignal")
    result  = f"EMPTY (correct)" if not raw else f"got: {raw}"
    print(f"  input : {text}")
    print(f"  result: {result}")


async def test_signal_question(stub: a2a_pb2_grpc.A2AServiceStub):
    """A clear question should return a question signal."""
    print("\n── test: signal / question ─────────────────────────────────")
    text = "INTERVIEWER|00:00:10,000|Can you walk me through how you designed the caching layer?"
    raw  = await send_message(stub, text, "test-question")
    print(f"  input : {text}")
    if raw:
        try:
            parsed = json.loads(raw)
            print(f"  type  : {parsed.get('type')}")
            print(f"  text  : {parsed.get('text')}")
        except json.JSONDecodeError:
            print(f"  raw   : {raw}")
    else:
        print("  result: EMPTY")


async def test_signal_answer(stub: a2a_pb2_grpc.A2AServiceStub):
    """A clear answer should return an answer signal."""
    print("\n── test: signal / answer ───────────────────────────────────")
    text = "CANDIDATE|00:00:20,000|We used Redis with a write-through strategy and a 5-minute TTL on all keys."
    raw  = await send_message(stub, text, "test-answer")
    print(f"  input : {text}")
    if raw:
        try:
            parsed = json.loads(raw)
            print(f"  type  : {parsed.get('type')}")
            print(f"  text  : {parsed.get('text')}")
        except json.JSONDecodeError:
            print(f"  raw   : {raw}")
    else:
        print("  result: EMPTY")


async def test_signal_sequence(stub: a2a_pb2_grpc.A2AServiceStub):
    """Run through the full sample sequence and print each result."""
    print("\n── test: signal / full sequence ────────────────────────────")
    ctx = "test-sequence"
    for speaker, ts, text in SAMPLE_SIGNALS:
        payload = f"{speaker}|{ts}|{text}"
        raw     = await send_message(stub, payload, ctx)
        if raw:
            try:
                parsed = json.loads(raw)
                print(f"  [{ts}] {speaker:<12} → {parsed.get('type'):8}  {parsed.get('text', '')[:60]}")
            except json.JSONDecodeError:
                print(f"  [{ts}] {speaker:<12} → (unparseable) {raw[:60]}")
        else:
            print(f"  [{ts}] {speaker:<12} → (no signal)")
        await asyncio.sleep(0.1)   # small gap between calls


async def test_nqi_auto(stub: a2a_pb2_grpc.A2AServiceStub):
    """AUTO trigger with a history list."""
    print("\n── test: NQI / AUTO ────────────────────────────────────────")
    payload = "AUTO|" + json.dumps({"history": SAMPLE_NQI_HISTORY}, ensure_ascii=False)
    raw     = await send_message(stub, payload, "test-nqi-auto")
    print(f"  history entries: {len(SAMPLE_NQI_HISTORY)}")
    if raw:
        try:
            parsed = json.loads(raw)
            print(f"  next_question: {parsed.get('next_question')}")
            print(f"  rationale    : {parsed.get('rationale')}")
        except json.JSONDecodeError:
            print(f"  raw: {raw}")
    else:
        print("  result: EMPTY")


async def test_nqi_manual(stub: a2a_pb2_grpc.A2AServiceStub):
    """MANUAL trigger with a user prompt and transcript snippet."""
    print("\n── test: NQI / MANUAL ──────────────────────────────────────")
    transcript = "\n".join(
        f"[{e['timestamp']}] {e['type'].upper()}: {e['text']}"
        for e in SAMPLE_NQI_HISTORY
    )
    payload = f"MANUAL|Dig deeper into the candidate's Redis experience|{transcript}"
    raw     = await send_message(stub, payload, "test-nqi-manual")
    print(f"  prompt: Dig deeper into the candidate's Redis experience")
    if raw:
        try:
            parsed = json.loads(raw)
            print(f"  next_question: {parsed.get('next_question')}")
            print(f"  rationale    : {parsed.get('rationale')}")
        except json.JSONDecodeError:
            print(f"  raw: {raw}")
    else:
        print("  result: EMPTY")


async def test_nqi_bad_input(stub: a2a_pb2_grpc.A2AServiceStub):
    """Bad input should return an error string, not crash."""
    print("\n── test: NQI / bad input ───────────────────────────────────")
    for bad in ["", "GARBAGE", "AUTO|not-json", "MANUAL|"]:
        raw = await send_message(stub, bad, "test-nqi-bad")
        print(f"  input={bad!r:25}  response={raw!r}")


# ── Interactive menu ─────────────────────────────────────────────────────────

MENU = """
Commands:
  1   ping both servers
  2   signal: no-signal (filler)
  3   signal: question
  4   signal: answer
  5   signal: full sequence
  6   NQI: AUTO trigger
  7   NQI: MANUAL trigger
  8   NQI: bad input handling
  9   run all tests
  s   custom signal   →  prompts for SPEAKER|TIMESTAMP|TEXT
  n   custom NQI AUTO →  prompts for question + answer
  q   quit
"""


async def custom_signal(stub: a2a_pb2_grpc.A2AServiceStub):
    speaker = input("  speaker (e.g. INTERVIEWER): ").strip() or "INTERVIEWER"
    ts      = input("  timestamp (e.g. 00:01:00,000): ").strip() or "00:01:00,000"
    text    = input("  text: ").strip()
    if not text:
        print("  (empty text, skipped)")
        return
    payload = f"{speaker}|{ts}|{text}"
    raw     = await send_message(stub, payload, "custom-signal")
    print(f"  raw response: {raw!r}")
    if raw:
        try:
            print(f"  parsed: {json.loads(raw)}")
        except json.JSONDecodeError:
            pass


async def custom_nqi_auto(stub: a2a_pb2_grpc.A2AServiceStub):
    question = input("  question: ").strip()
    answer   = input("  answer  : ").strip()
    if not question or not answer:
        print("  (empty input, skipped)")
        return
    history  = [
        {"type": "question", "text": question, "timestamp": "00:00:00,000"},
        {"type": "answer",   "text": answer,   "timestamp": "00:00:05,000"},
    ]
    payload  = "AUTO|" + json.dumps({"history": history}, ensure_ascii=False)
    raw      = await send_message(stub, payload, "custom-nqi")
    print(f"  raw response: {raw!r}")
    if raw:
        try:
            print(f"  parsed: {json.loads(raw)}")
        except json.JSONDecodeError:
            pass


async def main():
    print(f"connecting to signal server @ {SIGNAL_ADDR}")
    print(f"connecting to NQI server    @ {NQI_ADDR}")

    async with (
        grpc.aio.insecure_channel(SIGNAL_ADDR) as sig_chan,
        grpc.aio.insecure_channel(NQI_ADDR)    as nqi_chan,
    ):
        sig_stub = a2a_pb2_grpc.A2AServiceStub(sig_chan)
        nqi_stub = a2a_pb2_grpc.A2AServiceStub(nqi_chan)

        print(MENU)
        while True:
            try:
                cmd = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nbye")
                break

            if cmd == "q":
                print("bye")
                break
            elif cmd == "1":
                await ping(sig_stub, "signal-detector")
                await ping(nqi_stub, "nqi")
            elif cmd == "2":
                await test_signal_no_signal(sig_stub)
            elif cmd == "3":
                await test_signal_question(sig_stub)
            elif cmd == "4":
                await test_signal_answer(sig_stub)
            elif cmd == "5":
                await test_signal_sequence(sig_stub)
            elif cmd == "6":
                await test_nqi_auto(nqi_stub)
            elif cmd == "7":
                await test_nqi_manual(nqi_stub)
            elif cmd == "8":
                await test_nqi_bad_input(nqi_stub)
            elif cmd == "9":
                await ping(sig_stub, "signal-detector")
                await ping(nqi_stub, "nqi")
                await test_signal_no_signal(sig_stub)
                await test_signal_question(sig_stub)
                await test_signal_answer(sig_stub)
                await test_signal_sequence(sig_stub)
                await test_nqi_auto(nqi_stub)
                await test_nqi_manual(nqi_stub)
                await test_nqi_bad_input(nqi_stub)
                print("\n── all tests done ──────────────────────────────────────")
            elif cmd == "s":
                await custom_signal(sig_stub)
            elif cmd == "n":
                await custom_nqi_auto(nqi_stub)
            elif cmd == "":
                continue
            else:
                print(f"  unknown command: {cmd!r}")
                print(MENU)


if __name__ == "__main__":
    asyncio.run(main())