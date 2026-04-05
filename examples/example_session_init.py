"""
Example: Session Initialization with ATS API
---------------------------------------------
Demonstrates how to initialize a session by fetching interview data
from the ATS API at the start of an interview.
"""
import asyncio
import logging
import json
import traceback
import httpx
from pkg.ats_api import AtsApiClient
from pkg.ats_api.session_initializer import SessionInitializer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def example_basic_usage():
    """
    Example 1: Basic usage - fetch interview details directly.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Usage - Fetch Interview Details")
    print("=" * 70)
    
    interview_name = "HR-INT-2026-0001"
    
    async with AtsApiClient(base_url="http://localhost:8000") as client:
        try:
            interview_data = await client.get_interview_details(interview_name)
            
            print(f"\n✓ Successfully fetched interview: {interview_data.interview.name}")
            print(f"  Job Title: {interview_data.job_opening.job_title}")
            print(f"  Candidate: {interview_data.applicant.applicant_name}")
            print(f"  Email: {interview_data.applicant.email_id}")
            print(f"  Round: {interview_data.interview_round.round_name}")
            print(f"  Type: {interview_data.interview_type.name}")
            print(f"  Expected Skills: {', '.join(interview_data.get_expected_skills())}")
            
        except httpx.ConnectError as e:
            print(f"\n✗ Connection Error:")
            print(f"  Cannot connect to ATS server at http://localhost:8000")
            print(f"  Error: {type(e).__name__}: {str(e)}")
            print(f"\n  Troubleshooting:")
            print(f"    1. Is the ATS server running?")
            print(f"    2. Check the URL: http://localhost:8000")
            print(f"    3. Verify firewall/network settings")
        except httpx.TimeoutException as e:
            print(f"\n✗ Timeout Error:")
            print(f"  The request took too long (> 30s)")
            print(f"  Error: {str(e)}")
        except Exception as e:
            print(f"\n✗ Error fetching interview:")
            print(f"  Type: {type(e).__name__}")
            print(f"  Message: {str(e)}")
            print(f"\n  Full traceback:")
            print(f"  {traceback.format_exc()}")


async def example_session_initialization():
    """
    Example 2: Session initialization with formatted context.
    This is the recommended approach for starting an interview session.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Session Initialization (Recommended)")
    print("=" * 70)
    
    interview_name = "HR-INT-2026-0001"
    
    # Initialize session
    initializer = SessionInitializer(ats_base_url="http://localhost:8000")
    
    try:
        # Fetch interview data from ATS
        interview_data = await initializer.initialize_session(interview_name)
        
        print(f"\n✓ Session initialized for: {interview_data.interview.name}")
        print(f"\n{'─' * 70}")
        print("RECRUITER CONTEXT")
        print('─' * 70)
        print(initializer.get_recruiter_context())
        
        print(f"\n{'─' * 70}")
        print("JOB DESCRIPTION CONTEXT")
        print('─' * 70)
        print(initializer.get_job_description_context())
        
        print(f"\n{'─' * 70}")
        print("CANDIDATE RESUME CONTEXT")
        print('─' * 70)
        print(initializer.get_candidate_resume_context())
        
        print(f"\n{'─' * 70}")
        print("QUESTION BANK CONTEXT")
        print('─' * 70)
        print(initializer.get_question_bank_context())
        
        # Get complete context for agents
        agent_context = initializer.prepare_agent_context()
        print(f"\n{'─' * 70}")
        print("COMPLETE AGENT CONTEXT (JSON)")
        print('─' * 70)
        print(json.dumps({
            "interview_name": agent_context["interview_name"],
            "interview_round": agent_context["interview_round"],
            "interview_type": agent_context["interview_type"],
            "expected_skills": agent_context["expected_skills"],
        }, indent=2))
        
    except httpx.ConnectError as e:
        print(f"\n✗ Connection Error:")
        print(f"  Cannot connect to ATS server at http://localhost:8000")
        print(f"  Error: {type(e).__name__}: {str(e)}")
    except Exception as e:
        print(f"\n✗ Error initializing session:")
        print(f"  Type: {type(e).__name__}")
        print(f"  Message: {str(e)}")


async def example_integration_with_agent():
    """
    Example 3: How to integrate with the Next Question Agent.
    Shows how to pass ATS context to the agent system prompt.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Integration with Next Question Agent")
    print("=" * 70)
    
    interview_name = "HR-INT-2026-0001"
    
    # Initialize session
    initializer = SessionInitializer(ats_base_url="http://localhost:8000")
    
    try:
        await initializer.initialize_session(interview_name)
        agent_context = initializer.prepare_agent_context()
        
        # Build system prompt with ATS data
        system_prompt = f"""You are an expert technical interview coach assisting a recruiter
in a live interview session. You observe the transcript in real time and suggest the
single best follow-up question the recruiter should ask next.

═══════════════════════════════════════════════════════
INTERVIEW CONTEXT (from ATS)
═══════════════════════════════════════════════════════

INTERVIEW: {agent_context['interview_name']}
ROUND: {agent_context['interview_round']}
TYPE: {agent_context['interview_type']}

{agent_context['recruiter']}

JOB DESCRIPTION
{agent_context['job_description']}

CANDIDATE RESUME
{agent_context['candidate_resume']}

EXPECTED SKILLS
{', '.join(agent_context['expected_skills'])}

{agent_context['question_bank']}

═══════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════
[Rest of the agent instructions...]
"""
        
        print("\n✓ System prompt generated with ATS data")
        print(f"\nPrompt preview (first 500 chars):")
        print("─" * 70)
        print(system_prompt[:500] + "...")
        print("─" * 70)
    except httpx.ConnectError as e:
        print(f"\n✗ Connection Error:")
        print(f"  Cannot connect to ATS server")
        print(f"  Error: {str(e)}")
    except Exception as e:
        print(f"\n✗ Error in integration example:")
        print(f"  Type: {type(e).__name__}")
        print(f"  Message: {str(e)}")
        print("  1. Pass this system_prompt to your LlmAgent")
        print("  2. Store interview_name in session context")
        print("  3. Use context_id = interview_name for message routing")
        
    except Exception as e:
        print(f"\n✗ Error in integration example: {e}")


async def example_error_handling():
    """
    Example 4: Error handling for missing or invalid interviews.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Error Handling")
    print("=" * 70)
    
    invalid_interview_name = "HR-INT-9999-9999"
    
    async with AtsApiClient(base_url="http://localhost:8000") as client:
        try:
            await client.get_interview_details(invalid_interview_name)
            print(f"\n✓ Fetched interview (unexpected)")
            
        except httpx.HTTPStatusError as e:
            print(f"\n✓ HTTP Error handled gracefully:")
            print(f"  Status Code: {e.response.status_code}")
            print(f"  Error type: {type(e).__name__}")
            print(f"  Message: {str(e)}")
            print(f"\n  Response body (first 200 chars):")
            print(f"  {e.response.text[:200]}")
        except httpx.ConnectError as e:
            print(f"\n✓ Connection Error handled gracefully:")
            print(f"  Error type: {type(e).__name__}")
            print(f"  Message: {str(e)}")
            print(f"  → Cannot reach ATS server at http://localhost:8000")
        except Exception as e:
            print(f"\n✓ Error handled gracefully:")
            print(f"  Error type: {type(e).__name__}")
            print(f"  Message: {str(e)}")
            print(f"\nℹ In production, you might:")
            print("  - Return a default context")
            print("  - Prompt user to enter valid interview ID")
            print("  - Log error and alert admin")


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("ATS API CLIENT - SESSION INITIALIZATION EXAMPLES")
    print("=" * 70)
    print("\nThese examples demonstrate how to fetch interview data from")
    print("the ATS API at the start of an interview session.\n")
    
    # Run examples
    await example_basic_usage()
    await example_session_initialization()
    await example_integration_with_agent()
    await example_error_handling()
    
    print("\n" + "=" * 70)
    print("EXAMPLES COMPLETE")
    print("=" * 70)
    print("\nTo use in your application:")
    print("  1. Import: from pkg.ats_api.session_initializer import SessionInitializer")
    print("  2. Initialize: initializer = SessionInitializer()")
    print("  3. Fetch data: await initializer.initialize_session('HR-INT-2026-0001')")
    print("  4. Get context: agent_context = initializer.prepare_agent_context()")
    print("  5. Pass to agent system prompt")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        log.error(f"Unexpected error: {e}", exc_info=True)
