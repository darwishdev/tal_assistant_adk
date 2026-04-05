# Question Bank Personalizer Agent

Pre-interview agent that personalizes question banks and generates concise resume summaries based on interview context from the ATS API.

## Overview

The Question Bank Personalizer is designed to run in the **pre-interview phase** to prepare tailored interview materials. It:

1. **Fetches interview data** from the ATS API using an interview ID
2. **Analyzes** job requirements, candidate resume, and original question bank
3. **Generates** two key outputs:
   - **Personalized Question Bank**: 15-25 tailored questions organized by category
   - **Summarized Resume**: Concise 300-500 word summary highlighting relevant experience

## Architecture

Following the existing agent architecture pattern:

```
question_bank_personalizer/
├── __init__.py           # Package exports
├── agent.py              # LLM agent definition with system prompt
└── agent_executor.py     # Orchestration logic (ATS fetch → agent → parse)
```

## Components

### `agent.py`
Defines the `question_bank_personalizer` LLM agent with instructions to:
- Analyze candidate background and role requirements
- Adapt original question bank to candidate's specific experience
- Add questions targeting resume claims and projects
- Generate concise resume summary

### `agent_executor.py`
Orchestrates the personalization workflow:
- `personalize_question_bank()` - Main async function
- `QuestionBankPersonalizerResult` - Structured result class
- Formatting helpers for agent input
- JSON parsing and validation

## Usage

### Basic Usage

```python
from question_bank_personalizer.agent_executor import personalize_question_bank

# Personalize for a specific interview
result = await personalize_question_bank(
    interview_id="HR-INT-2026-0001",
    ats_base_url="http://localhost:8000"
)

# Access results
print(result.summarized_resume)
print(result.get_formatted_question_bank())
```

### Using the Example Script

```bash
# Run with defaults
python example_question_bank_personalizer.py

# Or with custom configuration
ATS_BASE_URL=http://localhost:8000 INTERVIEW_ID=HR-INT-2026-0001 \
python example_question_bank_personalizer.py
```

### Integration Example

```python
# In your pre-interview workflow
async def prepare_interview(interview_id: str):
    # Personalize questions and resume
    result = await personalize_question_bank(interview_id)
    
    # Export to dict for storage or API response
    data = result.to_dict()
    
    # Save to database, send to frontend, etc.
    await store_personalized_data(interview_id, data)
    
    return data
```

## Redis Storage (Persistent Context)

The Question Bank Personalizer **automatically stores** its results in Redis when run via the gRPC server. This allows other agents to retrieve the personalized context during the actual interview.

### Automatic Storage (gRPC)

When called via gRPC ([main.py](../main.py) on port 50053), the personalized data is automatically stored in Redis:

```python
# Stored in Redis with key: personalized_interview:{interview_id}
# Data includes:
# - personalized_question_bank
# - summarized_resume
# - timestamp
```

### Retrieving During Interview

Other agents can retrieve the personalized data during the interview:

```python
from pkg.redis.redis_publisher import get_personalized_interview_data

# In your agent executor
async def execute(self, context, event_queue):
    interview_id = get_interview_id_from_session()  # your logic
    
    # Retrieve personalized context
    personalized_data = await get_personalized_interview_data(interview_id)
    
    if personalized_data:
        question_bank = personalized_data["personalized_question_bank"]
        resume_summary = personalized_data["summarized_resume"]
        
        # Access full interview data if needed
        if "interview_data" in personalized_data:
            interview_data = personalized_data["interview_data"]
            job_title = interview_data.job_opening.job_title
            applicant_name = interview_data.applicant.applicant_name
            # ... use any ATS data
        
        # Use this context for generating interview questions
        # e.g., pick next question from personalized bank
```

### Example: Retrieve Personalized Data

```bash
# Run the retrieval example
python examples/example_personalized_interview_retrieval.py HR-INT-2026-0001
```

### Storage Details
- **Key Pattern**: `personalized_interview:{interview_id}`
- **TTL**: 8 hours (configurable via `INTERVIEW_CONTEXT_TTL`)
- **Scope**: Interview-wide (not session-specific)
- **Format**: JSON with:
  - `personalized_question_bank` - Personalized questions organized by category
  - `summarized_resume` - Concise resume summary (300-500 words)
  - `interview_data` - Full ATS interview data (job opening, applicant, resume, round details, original question bank)

## Input

The agent receives structured interview data from the ATS API containing:
- **Job Opening**: Title, description, requirements, responsibilities
- **Applicant**: Name, email, rating, status
- **Resume**: Experience, education, skills, projects
- **Interview Round**: Round details, expected skills
- **Original Question Bank**: Base questions for this interview type

## Output

### Structured JSON Response

```json
{
  "personalized_question_bank": {
    "categories": [
      {
        "category_name": "Distributed Training & Scalability",
        "questions": [
          {
            "question_text": "You mentioned fine-tuning VLMs on A100/H100 clusters...",
            "rationale": "Verifies hands-on experience with multi-node training",
            "difficulty": "hard"
          }
        ]
      }
    ]
  },
  "summarized_resume": "Senior AI Engineer with 3+ years experience..."
}
```

### Using the Result

```python
result = await personalize_question_bank(interview_id)

# Get formatted question bank string
formatted_questions = result.get_formatted_question_bank()

# Get resume summary
resume_summary = result.summarized_resume

# Get structured data
data_dict = result.to_dict()

# Access categories and questions
for category in result.personalized_question_bank["categories"]:
    print(f"Category: {category['category_name']}")
    for q in category["questions"]:
        print(f"  - {q['question_text']}")
```

## Question Personalization Strategy

The agent personalizes questions by:

1. **Verification Questions**: Target specific resume claims
   - "You mentioned 30% performance boost - how did you measure that?"

2. **Deep-Dive Questions**: Explore listed projects and experiences
   - "Walk me through your Recommendation Engine architecture"

3. **Gap Assessment**: Test areas between candidate background and job requirements
   - Probes skills required by role but not emphasized in resume

4. **Difficulty Matching**: Adjusts question complexity to candidate seniority
   - More architectural questions for senior roles
   - More implementation details for mid-level

5. **Context-Aware**: References their actual tech stack and projects
   - "Given your experience with PyTorch DDP on A100 clusters..."

## Resume Summarization Strategy

The summarized resume:
- Opens with one-sentence professional summary
- Highlights 3-5 most relevant experiences with quantified achievements
- Lists key technical skills matching job requirements
- Notes years of experience in relevant domains
- Written in third person, professional tone
- 300-500 words focused on THIS specific interview

## Error Handling

The agent handles various failure scenarios:
- ATS API connection errors
- Invalid interview IDs
- Missing or incomplete data
- JSON parsing failures
- Invalid agent responses

Check logs for detailed error information:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Configuration

Environment variables:
- `ATS_BASE_URL` - Base URL of ATS API (default: `http://localhost:8000`)
- `INTERVIEW_ID` - Interview identifier for testing

## Testing

```bash
# Test with real ATS data
python example_question_bank_personalizer.py

# Or create custom test
python -c "
import asyncio
from question_bank_personalizer.agent_executor import personalize_and_print
asyncio.run(personalize_and_print('YOUR-INTERVIEW-ID'))
"
```

## Integration with Next Question Agent

The personalized outputs are designed to be used with the Next Question Inferrer Agent:

```python
# 1. Pre-interview: Personalize questions
personalized = await personalize_question_bank(interview_id)

# 2. During interview: Initialize Next Question Agent with personalized data
initial_context = f"""
RECRUITER
{recruiter_info}

JOB_DESCRIPTION
{job_description}

CANDIDATE_RESUME
{personalized.summarized_resume}

QUESTION_BANK
{personalized.get_formatted_question_bank()}
"""

# Send to Next Question Agent (it will respond with null to acknowledge)
await next_question_agent.run(initial_context)
```

## Logging

The executor logs key events:
- Interview data fetching
- Formatting steps
- Agent invocation
- Response parsing
- Success metrics (categories count, resume length)

Enable debug logging for full details:
```python
logging.getLogger('question_bank_personalizer').setLevel(logging.DEBUG)
```

## Future Enhancements

Potential improvements:
- [ ] Cache personalized results to avoid re-generation
- [ ] Support for multiple interview rounds
- [ ] Question difficulty validation against candidate level
- [ ] Integration with question bank versioning
- [ ] Resume keyword extraction and matching scores
