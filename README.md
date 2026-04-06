# TAL Assistant ADK

Technical AI-powered Live interview assistant built with Google ADK (Agent Development Kit).

## Overview

This project provides AI agents for automating and enhancing technical interview workflows:
- **Pre-interview**: Personalize question banks and summarize resumes
- **During interview**: Detect Q&A signals and suggest next questions in real-time
- **Integration**: Connects to Mawhub ATS and Redis for session management

## Architecture

The system consists of three main agents:

### 1. Question Bank Personalizer Agent
**Phase**: Pre-interview  
**Purpose**: Analyzes interview context and generates personalized materials

- Fetches interview data from ATS API
- Generates 15-25 personalized questions based on candidate background
- Creates concise resume summary (300-500 words)
- Output used to initialize the Next Question Inferrer

📖 [Full Documentation](question_bank_personalizer/README.md)

### 2. Signal Detector Agent
**Phase**: During interview  
**Purpose**: Monitors live transcript and detects complete questions/answers

- Receives transcript segments in real-time
- Identifies when a complete question or answer has been spoken
- Publishes detected signals to Redis
- Triggers Next Question Inferrer after each answer

### 3. Next Question Inferrer Agent
**Phase**: During interview  
**Purpose**: Suggests the best follow-up question after each answer

**Three Trigger Modes**:
- **INIT**: Initializes session with interview context from Redis (first call)
- **AUTO**: Automatically triggered after each answer is detected
- **MANUAL**: Recruiter-triggered with custom prompts

**Three Response Strategies**:
- **FOLLOW_UP**: Probes deeper when answer is vague or incomplete
- **CHANGE_QUESTION**: Generates contextual new question when pivoting is valuable
- **PREDEFINED**: Fetches sequential questions from personalized bank (state-tracked in Redis)

Initialized with personalized context from Question Bank Personalizer via INIT mode.

📖 [Full Documentation](next_question_agent/README.md)

## Project Structure

```
tal_assistant_adk/
├── question_bank_personalizer/    # Pre-interview question personalization
│   ├── agent.py                   # LLM agent definition
│   ├── agent_executor.py          # Orchestration logic
│   ├── agent_executor_grpc.py     # gRPC executor
│   └── README.md                  # Detailed documentation
├── signaling_agent/               # Live transcript signal detection
│   ├── agent.py                   # Signal detector agent
│   └── agent_executor.py          # gRPC server + Redis publisher
├── next_question_agent/           # Next question suggestion
│   ├── agent_next_question.py     # Production agent
│   ├── agent_nqi_test.py          # Test/development agent
│   └── agent_executor_next_question.py
├── pkg/
│   ├── ats_api/                   # ATS API client
│   │   ├── client.py              # HTTP client for interview data
│   │   └── models.py              # Pydantic data models
│   └── redis/                     # Redis integration
│       ├── redis_publisher.py     # Signal publishing
│       └── redis_session_service.py
├── examples/                      # Example scripts and utilities
│   ├── example_question_bank_personalizer.py
│   ├── example_integration_main.py
│   ├── example_session_init.py
│   ├── example_redis_interview_context.py
│   ├── example_question_bank.py
│   ├── debug_publish.py
│   └── diagnose_ats_connection.py
├── tests/                         # Test scripts and data
│   ├── test_qbp_grpc.py
│   ├── test_servers.py
│   └── test_data_*.json
├── main.py                        # Unified gRPC server entry point
└── README.md                      # This file
```

## Quick Start

### Prerequisites

- Python 3.10+
- Redis server running
- Mawhub ATS API accessible

### Installation

```bash
# Clone repository
cd tal_assistant_adk

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Set environment variables:

```bash
# ATS API
export ATS_BASE_URL=http://localhost:8000

# Redis
export REDIS_URL=redis://localhost:6379

# gRPC Ports
export GRPC_PORT=50051          # Signal Detector
export NQI_GRPC_PORT=50052      # Next Question Inferrer
export QBP_GRPC_PORT=50053      # Question Bank Personalizer
```

### Running the gRPC Server

The main.py file runs all three agents as gRPC services:

```bash
python main.py
```

This will start:
- **Signal Detector** on port 50051
- **Next Question Inferrer** on port 50052
- **Question Bank Personalizer** on port 50053

### Usage Examples

#### 1. Personalize Question Bank (Pre-interview)

**Via Python API:**
```bash
python examples/example_question_bank_personalizer.py
```

Or programmatically:

```python
from question_bank_personalizer.agent_executor import personalize_question_bank

result = await personalize_question_bank("HR-INT-2026-0001")
print(result.summarized_resume)
print(result.get_formatted_question_bank())
```

**Via gRPC (when main.py is running):**
```bash
# Using the test script
python tests/test_qbp_grpc.py HR-INT-2026-0001

# Or using grpcurl
grpcurl -plaintext -d '{"interview_id": "HR-INT-2026-0001"}' \
  localhost:50053 \
  a2a.A2AService/Execute
```

#### 2. Initialize Next Question Inferrer (Interview Start)

**Via Example Script:**
```bash
python examples/example_nqi_init.py HR-INT-2026-0001 session-123
```

Or programmatically via gRPC:

```python
# Send INIT request to load interview context
message = "INIT|HR-INT-2026-0001"
# Agent fetches personalized data from Redis
# Response: null (context loaded successfully)
```

**Prerequisites**: Question Bank Personalizer must have been run first.

#### 3. Run Full Integration

```bash
python examples/example_integration_main.py
```

#### 4. Test ATS Connection

```bash
python examples/diagnose_ats_connection.py
```

## Complete Interview Workflow

### Pre-Interview Phase

1. **Fetch Interview Data**: ATS API provides job description, candidate resume, original question bank
2. **Personalize**: Question Bank Personalizer generates tailored questions and resume summary
3. **Store in Redis**: Personalized data saved with key `personalized_interview:{interview_id}`

```bash
# Step 1: Personalize question bank (run once per interview)
python examples/example_question_bank_personalizer.py HR-INT-2026-0001

# This stores in Redis:
# - personalized_question_bank (15-25 tailored questions)
# - summarized_resume (300-500 word summary)
# - interview_data (full ATS data)
```

### Interview Start Phase

4. **Initialize NQI Session**: Load interview context into Next Question Inferrer

```bash
# Step 2: Initialize Next Question Inferrer (start of interview)
python examples/example_nqi_init.py HR-INT-2026-0001 session-123

# Request: "INIT|HR-INT-2026-0001"
# - Fetches personalized data from Redis
# - Sends FORMAT A (interview context) to agent
# - Agent responds: null (context loaded)
```

### During Interview Phase

5. **Transcript Monitoring**: Signal Detector monitors live transcript from WebSocket/gRPC
6. **Signal Detection**: Identifies complete questions and answers
7. **Publish to Redis**: Detected signals stored and published
8. **Question Suggestion**: Next Question Inferrer suggests follow-up question (AUTO mode)
9. **Display to Recruiter**: Frontend shows suggested question

```
Transcript Stream → Signal Detector → Redis → Next Question Inferrer → UI
                                        ↓              ↑
                                 Signal History   Personalized Context
                                                 (from Redis: INIT mode)
```

**Manual Override**: Recruiter can send custom prompts anytime:
```
MANUAL|Ask about model deployment challenges|[recent transcript]
```

## API Integration

### ATS API

Fetch interview details:

```python
from pkg.ats_api.client import AtsApiClient

async with AtsApiClient(base_url="http://localhost:8000") as client:
    data = await client.get_interview_details("HR-INT-2026-0001")
    
print(data.applicant.applicant_name)
print(data.job_opening.job_title)
print(data.question_bank.questions)
```

### Redis Session Management

```python
from pkg.redis.redis_session_service import RedisSessionService

service = RedisSessionService(redis_url="redis://localhost:6379")
session = await service.get_or_create_session("app", "user", "session_id")
```

## Development

### Running Tests

```bash
# Test question bank personalizer
python examples/example_question_bank_personalizer.py

# Test ATS connection
python examples/diagnose_ats_connection.py

# Test Redis integration
python tests/test_servers.py

# Test Question Bank Personalizer via gRPC
python tests/test_qbp_grpc.py HR-INT-2026-0001
```

### Adding New Agents

Follow the established pattern:

1. Create directory: `new_agent/`
2. Define agent: `new_agent/agent.py` with system prompt
3. Create executor: `new_agent/agent_executor.py` with orchestration logic
4. Add `__init__.py` for exports
5. Create example: `example_new_agent.py`

See [question_bank_personalizer](question_bank_personalizer/) as reference.

## Logging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Each agent logs:
- Input/output sizes
- API call results
- Parsing status
- Error details

## Dependencies

Key libraries:
- `google-adk` - Agent Development Kit
- `httpx` - Async HTTP client for ATS API
- `redis` - Redis client
- `pydantic` - Data validation and parsing
- `grpc` - Inter-agent communication

See [requirements.txt](requirements.txt) for full list.

## Contributing

When adding features:
1. Follow existing agent architecture patterns
2. Add comprehensive logging
3. Create example scripts
4. Document in README
5. Handle errors gracefully

## License

[Add license information]

## Support

For issues or questions:
- Check agent-specific README files
- Review example scripts
- Enable debug logging
- Check ATS API connectivity
