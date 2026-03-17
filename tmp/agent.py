from google.adk.agents import LlmAgent

SYSTEM_PROMPT = """You are observing a live conversation transcript segment by segment.
Detect when a COMPLETE question or COMPLETE answer has been spoken.

Input format: [Speaker @ timestamp]: text

Rules:
- Observe silently until a full question or full answer is complete.
- A question is complete when fully asked (ends with "?" or clearly rhetorical).
- An answer is complete when the speaker finishes their response.
- When complete, respond with ONLY this exact JSON on one line, nothing else before or after:
  {"type": "question", "text": "the full question", "timestamp": "HH:MM:SS,mmm"}
  {"type": "answer", "text": "the full answer", "timestamp": "HH:MM:SS,mmm"}
- Use the timestamp from the FIRST segment of the detected Q or A.
- If not complete yet, respond with exactly: NONE
- Do NOT repeat or echo the input text.
- Do NOT add markdown, code fences, or any explanation."""

signal_detector = LlmAgent(
    name="signal_detector",
    model="gemini-2.0-flash",
    instruction=SYSTEM_PROMPT,
)