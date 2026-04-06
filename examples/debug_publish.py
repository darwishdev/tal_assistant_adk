"""
debug_publish.py — interactive CLI to publish test messages to Redis channels
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to Python path so imports work
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from pkg.redis.redis_publisher import get_redis

NQI_CHANNEL    = os.environ.get("NQI_CHANNEL", "nqi:results")
SIGNAL_CHANNEL = os.environ.get("SIGNAL_CHANNEL", "signal:results")


def make_nqi_payload(session_id: str) -> dict:
    return {
        "session_id":    session_id,
        "next_question": "Can you elaborate on the timeline of events?",
        "rationale":     "The answer was vague about timing.",
    }


def make_signal_payload(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "type":       "question",
        "text":       "What were the main challenges you faced?",
        "timestamp":  "00:01:23,456",
    }


async def main():
    r = await get_redis()
    print("Redis pub/sub debug publisher")
    print(f"  NQI channel    → {NQI_CHANNEL}")
    print(f"  Signal channel → {SIGNAL_CHANNEL}")
    print()
    print("Commands:")
    print("  n <session_id>   publish a test NQI result")
    print("  s <session_id>   publish a test signal")
    print("  q                quit")
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd   = parts[0].lower()
        sid   = parts[1] if len(parts) > 1 else "debug-session-1"

        if cmd == "q":
            print("bye")
            break

        elif cmd == "n":
            payload = json.dumps(make_nqi_payload(sid), ensure_ascii=False)
            await r.publish(NQI_CHANNEL, payload)
            print(f"  published NQI → {NQI_CHANNEL}  session={sid}")
            print(f"  payload: {payload}")

        elif cmd == "s":
            payload = json.dumps(make_signal_payload(sid), ensure_ascii=False)
            await r.publish(SIGNAL_CHANNEL, payload)
            print(f"  published signal → {SIGNAL_CHANNEL}  session={sid}")
            print(f"  payload: {payload}")

        else:
            print(f"  unknown command: {cmd!r}")


if __name__ == "__main__":
    asyncio.run(main())