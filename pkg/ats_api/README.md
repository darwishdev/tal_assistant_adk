# ATS API Client

This package provides HTTP client functionality for fetching interview data from the Mawhub ATS (Applicant Tracking System).

## Structure

```
pkg/ats_api/
├── __init__.py              # Package exports
├── client.py                # HTTP client for ATS API
├── models.py                # Pydantic models for data validation
└── session_initializer.py  # Session management & context preparation
```

## Features

- 🔄 **Async HTTP Client**: Built with `httpx` for efficient async operations
- ✅ **Data Validation**: Pydantic models ensure type safety
- 📦 **Context Preparation**: Formats data for agent system prompts
- 🔒 **Error Handling**: Graceful handling of network and parsing errors
- 🎯 **Session Management**: Track and manage interview sessions

## Installation

Install dependencies:

```bash
pip install httpx pydantic
```

Or using the project requirements:

```bash
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```python
from pkg.ats_api import AtsApiClient

async def fetch_interview_data():
    async with AtsApiClient(base_url="http://localhost:8000") as client:
        data = await client.get_interview_details("HR-INT-2026-0001")
        
        print(f"Job: {data.job_opening.job_title}")
        print(f"Candidate: {data.applicant.applicant_name}")
        print(f"Skills: {data.get_expected_skills()}")
```

### Session Initialization (Recommended)

```python
from pkg.ats_api.session_initializer import SessionInitializer

async def start_interview_session():
    initializer = SessionInitializer(ats_base_url="http://localhost:8000")
    
    # Fetch interview data
    interview_data = await initializer.initialize_session("HR-INT-2026-0001")
    
    # Get formatted context for agents
    context = initializer.prepare_agent_context()
    
    # Use context in your agent system prompt
    system_prompt = f"""You are an interview coach.
    
    RECRUITER: {context['recruiter']}
    JOB DESCRIPTION: {context['job_description']}
    CANDIDATE RESUME: {context['candidate_resume']}
    """
```

## API Reference

### AtsApiClient

HTTP client for the ATS API.

**Methods:**
- `async get_interview_details(interview_name: str) -> InterviewData`
  - Fetch complete interview data from ATS
  - Raises: `httpx.HTTPError`, `ValueError`

**Usage:**
```python
async with AtsApiClient(base_url="http://localhost:8000") as client:
    data = await client.get_interview_details("HR-INT-2026-0001")
```

### SessionInitializer

Manages session initialization and context preparation.

**Methods:**
- `async initialize_session(interview_name: str) -> InterviewData`
  - Fetch and store interview data
  
- `get_recruiter_context() -> str`
  - Returns formatted recruiter information
  
- `get_job_description_context() -> str`
  - Returns formatted job description
  
- `get_candidate_resume_context() -> str`
  - Returns formatted candidate resume
  
- `prepare_agent_context() -> dict`
  - Returns complete context dictionary for agents

**Usage:**
```python
initializer = SessionInitializer()
await initializer.initialize_session("HR-INT-2026-0001")
context = initializer.prepare_agent_context()
```

### InterviewData

Main data model containing all interview information.

**Properties:**
- `interview`: Interview details
- `applicant`: Candidate information
- `job_opening`: Job posting details
- `applicant_resume`: Parsed resume data
- `interview_round`: Round information
- `interview_type`: Type of interview

**Helper Methods:**
- `get_recruiter_name() -> str`: Extract recruiter email
- `get_job_description() -> str`: Formatted job description
- `get_candidate_resume() -> str`: Formatted resume
- `get_expected_skills() -> List[str]`: List of expected skills

## Integration with Main Application

### Automatic Session Initialization

```python
from pkg.ats_api.session_initializer import SessionInitializer

class InterviewSessionManager:
    def __init__(self):
        self.session_manager = SessionInitializer()
        self.sessions = {}
    
    async def start_session(self, interview_name: str):
        # Fetch from ATS
        await self.session_manager.initialize_session(interview_name)
        
        # Store context
        context = self.session_manager.prepare_agent_context()
        self.sessions[interview_name] = context
        
        return context
```

### Use Context in Agent System Prompt

```python
async def create_agent_with_context(interview_name: str):
    # Initialize session
    initializer = SessionInitializer()
    await initializer.initialize_session(interview_name)
    context = initializer.prepare_agent_context()
    
    # Build system prompt with ATS data
    system_prompt = f"""You are an expert interview coach.

INTERVIEW CONTEXT
═══════════════════════════════════════════════════════

{context['recruiter']}

JOB DESCRIPTION
{context['job_description']}

CANDIDATE RESUME
{context['candidate_resume']}

EXPECTED SKILLS
{', '.join(context['expected_skills'])}

{context['question_bank']}
"""
    
    # Create agent with this prompt
    from google.adk.agents import LlmAgent
    agent = LlmAgent(
        name="interview_coach",
        model="gemini-2.0-flash",
        instruction=system_prompt
    )
    
    return agent
```

## Examples

Run the examples to see the ATS API client in action:

### Basic Examples
```bash
python example_session_init.py
```

This demonstrates:
- ✅ Fetching interview details
- ✅ Session initialization
- ✅ Context preparation
- ✅ Error handling

### Integration Example
```bash
python example_integration_main.py
```

This demonstrates:
- ✅ Session manager implementation
- ✅ Automatic context initialization
- ✅ Integration with gRPC server
- ✅ Context-aware request handling

## API Endpoint

The ATS API endpoint used:

```
GET http://localhost:8000/api/method/mawhub.api.interview_interview_api.interview_find?name={interview_name}
```

**Response Format:**
```json
{
  "message": {
    "interview": {...},
    "applicant": {...},
    "job_opening": {...},
    "applicant_resume": {...},
    "interview_round": {...},
    "interview_type": {...}
  }
}
```

## Environment Variables

```bash
# ATS API base URL
ATS_BASE_URL=http://localhost:8000

# Request timeout (seconds)
ATS_TIMEOUT=30.0
```

## Error Handling

The client handles various error scenarios:

```python
try:
    data = await client.get_interview_details("HR-INT-9999-9999")
except httpx.HTTPStatusError as e:
    # Handle HTTP errors (404, 500, etc.)
    print(f"HTTP Error: {e.response.status_code}")
except httpx.RequestError as e:
    # Handle network errors
    print(f"Network Error: {e}")
except ValueError as e:
    # Handle parsing errors
    print(f"Parse Error: {e}")
```

## Best Practices

1. **Use Context Manager**: Always use `async with` to ensure proper cleanup
   ```python
   async with AtsApiClient() as client:
       data = await client.get_interview_details("HR-INT-2026-0001")
   ```

2. **Cache Session Context**: Avoid re-fetching data for the same interview
   ```python
   # Good: Cache context
   self.sessions[interview_name] = context
   
   # Bad: Fetch every time
   context = await fetch_context(interview_name)
   ```

3. **Use Interview Name as Context ID**: This enables automatic session initialization
   ```python
   context_id = "HR-INT-2026-0001"  # ✅ Interview name
   context_id = "random-uuid"        # ❌ Generic ID
   ```

4. **Handle Errors Gracefully**: Always provide fallback context
   ```python
   try:
       context = await initializer.initialize_session(interview_name)
   except Exception as e:
       log.error(f"Failed to fetch ATS data: {e}")
       context = get_default_context()
   ```

## Testing

To test with a running ATS instance:

```bash
# Make sure ATS is running on localhost:8000
python example_session_init.py
```

To test with mock data:

```python
from unittest.mock import AsyncMock, patch

async def test_session_init():
    with patch('pkg.ats_api.client.httpx.AsyncClient') as mock:
        mock.return_value.get = AsyncMock(return_value=mock_response)
        
        initializer = SessionInitializer()
        data = await initializer.initialize_session("HR-INT-2026-0001")
        
        assert data.interview.name == "HR-INT-2026-0001"
```

## Troubleshooting

### Connection Errors

**Problem**: Cannot connect to ATS API

**Solution**:
- Verify ATS is running: `curl http://localhost:8000/api/method/ping`
- Check base URL configuration
- Verify network connectivity

### Parse Errors

**Problem**: Response parsing fails

**Solution**:
- Check response format matches API documentation
- Verify all required fields are present
- Update Pydantic models if API changed

### Timeout Errors

**Problem**: Requests timing out

**Solution**:
- Increase timeout: `AtsApiClient(timeout=60.0)`
- Check ATS server performance
- Verify database connectivity on ATS side

## Contributing

To add new fields or endpoints:

1. Update `models.py` with new Pydantic models
2. Add new methods to `client.py`
3. Update `session_initializer.py` if needed for context
4. Add examples and tests
5. Update this README

## License

Same as parent project.
