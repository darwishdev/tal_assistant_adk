# Next Question Inferrer Agent

Real-time interview coaching agent that suggests the most relevant follow-up questions during technical interviews.

## Overview

The Next Question Inferrer (NQI) observes the interview transcript in real-time and intelligently suggests the single best follow-up question the recruiter should ask next. It uses three strategic approaches:
1. **Follow-up Questions** - Probes vague or incomplete answers
2. **Contextual New Questions** - Generates new questions based on conversation flow
3. **Predefined Questions** - Draws from personalized question bank

## Trigger Modes

### 1. INIT Mode (Session Initialization)

**Purpose**: Initialize the NQI session with complete interview context at the start of the interview.

**Input Format**: 
```
INIT|{interview_id}
```

**Workflow**:
1. Receives `interview_id` (e.g., "HR-INT-2026-0001")
2. Fetches personalized interview data from Redis:
   - Personalized question bank
   - Summarized candidate resume
   - Full interview data (job description, applicant details, etc.)
3. Formats data as FORMAT A (interview context initialization)
4. Sends to agent to load context into memory
5. Agent responds with `null` to acknowledge

**Expected Response**: 
```
null
```

**Example**:
```python
# Initialize NQI session before interview starts
request = "INIT|HR-INT-2026-0001"
response = await nqi_executor.execute(request)
# Response: null (context loaded)
```

**Prerequisites**:
- Question Bank Personalizer must have been run for the interview
- Personalized data must exist in Redis: `personalized_interview:{interview_id}`

### 2. AUTO Mode (Real-time Q/A Detection)

**Purpose**: Automatically triggered after each Q/A pair is detected by the Signal Detector.

**Input Format**:
```
AUTO|{"history": [{"type": "question", "text": "...", "timestamp": "..."}, {"type": "answer", "text": "...", "timestamp": "..."}]}
```

**Workflow**:
1. Signal Detector identifies question and answer in transcript
2. Sends Q/A pair with signal history to NQI
3. NQI analyzes the answer quality and conversation flow
4. Suggests next question using appropriate strategy
5. Publishes result to Redis for consumption by UI/clients

**Expected Response**:
```json
{
  "next_question": "Can you walk me through a specific example of when you used LoRA for fine-tuning?",
  "rationale": "Candidate mentioned using LoRA but provided no concrete implementation details. This follow-up probes for hands-on experience.",
  "strategy": "FOLLOW_UP"
}
```

### 3. MANUAL Mode (Recruiter-Triggered)

**Purpose**: Allows recruiter to manually guide the questioning with custom prompts.

**Input Format**:
```
MANUAL|{prompt}|{optional transcript context}
```

**Workflow**:
1. Recruiter provides instruction (e.g., "challenge the answer", "go deeper on distributed training")
2. Optionally includes recent transcript snippet for context
3. NQI generates question aligned with the prompt
4. Returns tailored suggestion

**Expected Response**:
```json
{
  "next_question": "What specific challenges did you face when scaling your training to multiple nodes?",
  "rationale": "Following recruiter's guidance to probe deeper into distributed training expertise.",
  "strategy": "MANUAL"
}
```

## Complete Interview Workflow

### Step 1: Pre-Interview (Run Once Per Interview)

```bash
# 1. Personalize question bank
python examples/example_question_bank_personalizer.py HR-INT-2026-0001

# This stores in Redis:
# - personalized_interview:{interview_id}
#   - personalized_question_bank
#   - summarized_resume
#   - interview_data
```

### Step 2: Initialize NQI Session (Start of Interview)

```bash
# 2. Initialize NQI with interview context
python examples/example_nqi_init.py HR-INT-2026-0001 session-123

# Request: "INIT|HR-INT-2026-0001"
# Response: null (context loaded)
```

### Step 3: During Interview (Automated)

```
Transcript → Signal Detector → AUTO trigger → NQI → Next Question Suggestion
```

The Signal Detector automatically:
1. Listens to transcript stream
2. Detects questions and answers
3. Triggers NQI with AUTO mode
4. NQI suggests next question
5. Result published to Redis

### Step 4: Manual Intervention (As Needed)

```bash
# Recruiter can override with manual prompts
MANUAL|Ask about model deployment challenges|[recent transcript]
```

## Question Strategy Selection

The agent intelligently chooses between three strategies:

### Strategy A: FOLLOW_UP (Preferred for incomplete answers)
Used when the last answer contains:
- Vague statements without examples
- Unverified claims (e.g., "30% improvement")
- Technical terms without explanation
- Contradictions with resume
- Incomplete thoughts

**Example**:
```
Answer: "I worked with distributed training on large clusters."
Follow-up: "What specific framework did you use, and how many nodes were in your largest cluster?"
```

### Strategy B: CHANGE_QUESTION (Preferred for natural pivots)
Used when:
- Last answer was thorough and complete
- Conversation has natural momentum in a new direction
- Want to explore adjacent skills revealed by answer
- Moving to predefined question would break flow

**Example**:
```
After detailed scaling story → "How do you typically approach architectural trade-offs between cost and performance?"
```

### Strategy C: PREDEFINED (Use question bank)
Used when:
- First question of the interview
- Need to move to completely new topic
- Neither FOLLOW_UP nor CHANGE_QUESTION apply

**How it works**:
1. Agent returns JSON with `strategy: "PREDEFINED"` but **no** `next_question` key
2. Executor detects this and fetches the next question from the personalized question bank in Redis
3. Question index is tracked per session, so questions are served sequentially
4. When all questions are exhausted, returns `next_question: null`

**Example Agent Response** (PREDEFINED):
```json
{
  "rationale": "Moving to a new topic area to assess different skills",
  "strategy": "PREDEFINED"
}
```

**Example Final Output** (after executor fetches from bank):
```json
{
  "next_question": "Can you explain how you would handle Arabic dialect variations in your NLP pipeline?",
  "rationale": "Predefined question from category: Arabic NLP [Difficulty: HARD]",
  "strategy": "PREDEFINED",
  "metadata": {
    "category": "Arabic NLP",
    "difficulty": "hard",
    "question_number": 3,
    "total_questions": 22
  }
}
```

## Output Format

All NQI responses (except INIT) follow this structure:

```json
{
  "next_question": "Question text that recruiter should ask",
  "rationale": "Why this question is the best choice right now",
  "strategy": "FOLLOW_UP | CHANGE_QUESTION | PREDEFINED"
}
```

**For PREDEFINED strategy**, additional metadata is included:
```json
{
  "next_question": "Question from personalized bank",
  "rationale": "Predefined question from category: Category Name [Difficulty: LEVEL]",
  "strategy": "PREDEFINED",
  "metadata": {
    "category": "Category Name",
    "difficulty": "easy | medium | hard",
    "question_number": 5,
    "total_questions": 22
  }
}
```

**Note**: 
- For PREDEFINED strategy with no question selected, `next_question` may be `null`
- When all questions are exhausted, `next_question` will be `null` with appropriate rationale

## Redis Integration

### Data Read
- **Key**: `personalized_interview:{interview_id}`
- **Data**: Interview context loaded during INIT

### Data Write
- **Channel**: `nqi:results`
- **Payload**: Next question suggestions published for real-time consumption

### State Management
The executor tracks the current question index for PREDEFINED strategy:

- **Key Pattern**: `question_index:{session_id}`
- **Type**: Integer counter (0-based)
- **TTL**: 8 hours
- **Behavior**: 
  - Increments each time a PREDEFINED question is served
  - Ensures questions are asked sequentially without repetition
  - Resets when session expires or is cleared

**Session-Interview Mapping**:
- **Key Pattern**: `session_interview_id:{session_id}`
- **Data**: interview_id associated with the session
- **TTL**: 8 hours
- **Purpose**: Links session to personalized question bank

## Architecture

```
next_question_agent/
├── __init__.py
├── agent_next_question.py          # LLM agent with system prompt
└── agent_executor_next_question.py # gRPC executor with three modes
```

## Error Handling

### INIT Mode Errors
- **No interview_id**: Returns `ERROR: missing interview_id`
- **No personalized data in Redis**: Returns `ERROR: No personalized data found for interview {id}. Run Question Bank Personalizer first.`
- **Redis connection error**: Returns `ERROR: Failed to fetch personalized data: {error}`

### AUTO Mode Errors
- **Missing payload**: Returns `ERROR: missing JSON payload`
- **Invalid JSON**: Returns `ERROR: bad JSON`

### MANUAL Mode Errors
- **Empty prompt**: Returns `ERROR: empty prompt`

## Testing

### Test INIT Mode
```bash
# Ensure main.py is running
python main.py &

# Initialize session
python examples/example_nqi_init.py HR-INT-2026-0001

# Expected output:
# Response: null
# ✅ SUCCESS: Next Question Inferrer is ready!
```

### Test AUTO Mode
```bash
# Send AUTO trigger with Q/A history
# (Usually done by Signal Detector)
```

### Test MANUAL Mode
```bash
# Send MANUAL trigger with custom prompt
# MANUAL|Ask about MLOps experience|Recent discussion about model deployment
```

## Configuration

Environment variables:
- `REDIS_URL` - Redis connection URL (default: `redis://localhost:6379`)
- `NQI_GRPC_PORT` - gRPC port for NQI (default: `50052`)
- `NQI_CHANNEL` - Redis pub/sub channel for results (default: `nqi:results`)

## Dependencies

- Google ADK (Agent Development Kit)
- Redis (session storage, signal history, pub/sub)
- gRPC (inter-agent communication)
- ATS API (via Question Bank Personalizer)

## Logging

Enable debug logging to see detailed agent behavior:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Logs include:
- Mode detection (INIT/AUTO/MANUAL)
- Payload construction
- Redis data retrieval
- Agent invocation
- Response parsing
- Strategy selection
