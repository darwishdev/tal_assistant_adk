"""
test_ws.py — tests the signal agent via WebSocket
Run: uv run python test_ws.py
"""
import asyncio
import json
import websockets

SERVER = "ws://localhost:8000"

SEGMENTS = [
    ("Interviewer", "00:00:03,000", "Tell me about yourself."),
    ("Candidate",   "00:00:08,000", "Sure, I have 5 years of backend experience."),
    ("Interviewer", "00:00:15,000", "Where do you see yourself in five years?"),
    ("Candidate",   "00:00:22,000", "I see myself leading a team and driving architecture decisions."),
    ("Interviewer", "00:00:30,000", "What is your biggest weakness?"),
    ("Candidate",   "00:00:36,000", "I sometimes focus too much on details, but I am working on it."),
]

async def main():
    session_id = "test-session-001"
    url = f"{SERVER}/ws/{session_id}"
    print(f"Connecting to {url}")

    async with websockets.connect(url) as ws:
        print("Connected\n")

        for speaker, timestamp, text in SEGMENTS:
            msg = {
                "type":      "transcript",
                "speaker":   speaker,
                "timestamp": timestamp,
                "text":      text,
            }
            print(f"→ [{speaker}] {text}")
            await ws.send(json.dumps(msg))

            resp = json.loads(await ws.recv())
            if resp["type"] == "signal":
                print(f"← SIGNAL: {resp['signal']}\n")
            else:
                print(f"← (no signal)\n")

            await asyncio.sleep(0.5)

        await ws.send(json.dumps({"type": "close"}))
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())