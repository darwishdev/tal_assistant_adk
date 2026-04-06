"""
Example: Using Redis Interview Context Storage
-----------------------------------------------
Demonstrates how to store and retrieve interview data in Redis
for use in agent executors.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to Python path so imports work
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from pkg.ats_api import AtsApiClient
from pkg.redis.redis_publisher import (
    store_interview_context,
    get_interview_context,
    clear_signal_history,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def example_store_and_retrieve():
    """
    Example: Store interview data from ATS API in Redis and retrieve it later.
    
    This pattern should be used:
    1. At session initialization - fetch from ATS and store in Redis
    2. In agent executors - retrieve from Redis to get interview context
    """
    print("\n" + "=" * 70)
    print("EXAMPLE: Store and Retrieve Interview Context from Redis")
    print("=" * 70)
    
    # Session identifiers
    session_id = "session-12345"
    interview_id = "HR-INT-2026-0001"
    
    # Step 1: Clear any old signal history for this session
    await clear_signal_history(session_id)
    print(f"\n✓ Cleared signal history for session: {session_id}")
    
    # Step 2: Fetch interview data from ATS API
    print(f"\nFetching interview data from ATS API...")
    async with AtsApiClient(base_url="http://localhost:8000") as client:
        try:
            interview_data = await client.get_interview_details(interview_id)
            print(f"✓ Fetched interview: {interview_data.interview.name}")
            print(f"  Job: {interview_data.job_opening.job_title}")
            print(f"  Candidate: {interview_data.applicant.applicant_name}")
            
        except Exception as e:
            print(f"✗ Failed to fetch from ATS: {e}")
            return
    
    # Step 3: Store interview data in Redis
    print(f"\nStoring interview context in Redis...")
    await store_interview_context(session_id, interview_id, interview_data)
    print(f"✓ Stored in Redis with TTL=8 hours")
    print(f"  Key: interview_context:{session_id}")
    
    # Step 4: Later, retrieve the interview data (as agent executor would)
    print(f"\nRetrieving interview context from Redis...")
    retrieved_data = await get_interview_context(session_id)
    
    if retrieved_data:
        print(f"✓ Retrieved interview context successfully")
        print(f"\n{'─' * 70}")
        print("RETRIEVED DATA")
        print('─' * 70)
        print(f"Interview: {retrieved_data.interview.name}")
        print(f"Job: {retrieved_data.job_opening.job_title}")
        print(f"Candidate: {retrieved_data.applicant.applicant_name}")
        print(f"Round: {retrieved_data.interview_round.round_name}")
        print(f"Type: {retrieved_data.interview_type.name}")
        print(f"Expected Skills: {', '.join(retrieved_data.get_expected_skills())}")
        
        # Use helper methods
        print(f"\n{'─' * 70}")
        print("HELPER METHODS")
        print('─' * 70)
        print(f"Recruiter: {retrieved_data.get_recruiter_name()}")
        print(f"\nJob Description:\n{retrieved_data.get_job_description()[:200]}...")
        print(f"\nCandidate Resume:\n{retrieved_data.get_candidate_resume()[:200]}...")
    else:
        print(f"✗ Failed to retrieve interview context")


async def example_agent_executor_usage():
    """
    Example: How to use get_interview_context in an agent executor.
    
    This shows the pattern for retrieving interview context in
    agent_executor_next_question.py or agent_executor.py
    """
    print("\n" + "=" * 70)
    print("EXAMPLE: Using Interview Context in Agent Executor")
    print("=" * 70)
    
    # Simulating what happens in agent executor when processing a request
    session_id = "session-12345"
    
    print(f"\nProcessing request for session: {session_id}")
    
    # Retrieve interview context
    interview_data = await get_interview_context(session_id)
    
    if not interview_data:
        print("✗ No interview context found - session may not be initialized")
        print("  Solution: Call store_interview_context at session start")
        return
    
    print(f"✓ Interview context loaded from Redis")
    
    # Now you can use this data to enhance agent system prompt or context
    print(f"\n{'─' * 70}")
    print("CONTEXT FOR AGENT")
    print('─' * 70)
    
    # Example: Building enhanced system prompt with interview data
    context_text = f"""
Interview Round: {interview_data.interview_round.round_name}
Interview Type: {interview_data.interview_type.name}
Expected Skills: {', '.join(interview_data.get_expected_skills())}

Job Opening: {interview_data.job_opening.job_title}
Candidate: {interview_data.applicant.applicant_name}
Candidate Email: {interview_data.applicant.email_id}

This context can be added to your agent's system prompt or passed
as additional context when invoking the agent.
"""
    print(context_text)
    
    # In actual agent executor, you would:
    # 1. Get interview_data = await get_interview_context(session_id)
    # 2. Build enhanced system prompt with interview_data
    # 3. Pass to agent via runner.run(...)


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("REDIS INTERVIEW CONTEXT - USAGE EXAMPLES")
    print("=" * 70)
    print("\nThese examples show how to store and retrieve interview data")
    print("in Redis for use across agent executors.\n")
    
    # Run examples
    await example_store_and_retrieve()
    await example_agent_executor_usage()
    
    print("\n" + "=" * 70)
    print("INTEGRATION PATTERN")
    print("=" * 70)
    print("""
STEP 1: At Session Start (e.g., in main.py or session init endpoint)
----------------------------------------------------------------------
from pkg.ats_api import AtsApiClient
from pkg.redis.redis_publisher import store_interview_context, clear_signal_history

# Clear old data
await clear_signal_history(session_id)

# Fetch from ATS
async with AtsApiClient() as client:
    interview_data = await client.get_interview_details(interview_id)

# Store in Redis
await store_interview_context(session_id, interview_id, interview_data)


STEP 2: In Agent Executors (agent_executor.py, agent_executor_next_question.py)
--------------------------------------------------------------------------------
from pkg.redis.redis_publisher import get_interview_context

# Retrieve interview context
interview_data = await get_interview_context(session_id)

if interview_data:
    # Use in system prompt or agent context
    skills = ', '.join(interview_data.get_expected_skills())
    job_title = interview_data.job_opening.job_title
    # ... add to agent prompt ...
""")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        log.error(f"Unexpected error: {e}", exc_info=True)
