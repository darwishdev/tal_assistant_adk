"""
Example: Question Bank Mock Data
---------------------------------
Demonstrates how to create and use question bank data in InterviewData.
"""
import json
from pkg.ats_api.models import (
    InterviewData,
    Interview,
    Applicant,
    JobOpening,
    ApplicantResume,
    InterviewRound,
    InterviewType,
    QuestionBank,
    Question,
)


def create_mock_interview_data_with_questions():
    """
    Create a mock InterviewData object with a question bank.
    This shows the structure you would receive from the ATS API.
    """
    # Create mock question bank
    question_bank = QuestionBank(
        name="Python Backend Developer - Technical Round",
        description="Standard questions for Python backend interviews",
        questions=[
            Question(
                question_text="Can you explain the difference between a list and a tuple in Python?",
                category="Python Fundamentals",
                difficulty="easy",
                expected_answer_points="Mutability, performance, use cases",
                tags=["python", "data-structures", "fundamentals"]
            ),
            Question(
                question_text="How would you implement caching in a REST API to improve performance?",
                category="System Design",
                difficulty="medium",
                expected_answer_points="Redis/Memcached, cache invalidation strategies, TTL",
                tags=["caching", "performance", "redis"]
            ),
            Question(
                question_text="Explain the concept of async/await in Python and when you would use it.",
                category="Concurrency",
                difficulty="medium",
                expected_answer_points="Event loop, I/O bound operations, asyncio library",
                tags=["python", "async", "concurrency"]
            ),
            Question(
                question_text="Design a URL shortener service. What would be your approach?",
                category="System Design",
                difficulty="hard",
                expected_answer_points="Hash function, database schema, scalability, collision handling",
                tags=["system-design", "architecture", "databases"]
            ),
            Question(
                question_text="Tell me about a time you had to optimize a slow database query.",
                category="Behavioral",
                difficulty="medium",
                expected_answer_points="Problem identification, indexing, query analysis, result",
                tags=["behavioral", "databases", "optimization"]
            ),
        ]
    )
    
    # Create minimal mock interview data
    interview_data = InterviewData(
        interview=Interview(
            name="HR-INT-2026-0001",
            designation="Python Backend Developer",
            interview_round="Technical Round 1",
            job_applicant="John Doe",
            status="Scheduled",
            interview_details=[]
        ),
        applicant=Applicant(
            name="John Doe",
            applicant_name="John Doe",
            email_id="john.doe@example.com",
            designation="Senior Developer",
            status="Active"
        ),
        job_opening=JobOpening(
            name="JO-2026-0001",
            job_title="Python Backend Developer",
            designation="Senior Developer",
            status="Open",
            description="Looking for experienced Python developer"
        ),
        applicant_resume=ApplicantResume(
            name="John Doe Resume",
            summary="5+ years of Python development experience",
            skills="Python, Django, FastAPI, PostgreSQL, Redis"
        ),
        interview_round=InterviewRound(
            round_name="Technical Round 1",
            interview_type="Technical",
            expected_average_rating=4.0,
            designation="Senior Developer",
            expected_skill_set=[]
        ),
        interview_type=InterviewType(
            name="Technical Interview",
            description="Technical assessment"
        ),
        question_bank=question_bank  # Add the question bank here
    )
    
    return interview_data


def main():
    """Demonstrate question bank usage."""
    print("\n" + "=" * 70)
    print("QUESTION BANK - MOCK DATA EXAMPLE")
    print("=" * 70)
    
    # Create mock data
    interview_data = create_mock_interview_data_with_questions()
    
    # Show formatted question bank
    print("\n" + "─" * 70)
    print("FORMATTED QUESTION BANK")
    print("─" * 70)
    print(interview_data.get_question_bank())
    
    # Show JSON structure
    print("\n" + "─" * 70)
    print("QUESTION BANK - JSON STRUCTURE")
    print("─" * 70)
    if interview_data.question_bank:
        print(json.dumps(
            interview_data.question_bank.model_dump(),
            indent=2,
            ensure_ascii=False
        ))
    
    # Show how it would be used in session initializer
    print("\n" + "─" * 70)
    print("USAGE IN SESSION INITIALIZER")
    print("─" * 70)
    print("""
When the ATS API returns interview data with a question_bank field:

from pkg.ats_api import AtsApiClient
from pkg.ats_api.session_initializer import SessionInitializer

# Initialize and fetch from ATS
initializer = SessionInitializer()
interview_data = await initializer.initialize_session("HR-INT-2026-0001")

# Get question bank context (will use actual questions if available)
question_context = initializer.get_question_bank_context()

# This will be included in agent context automatically
agent_context = initializer.prepare_agent_context()
# agent_context["question_bank"] contains the formatted questions
""")
    
    # Show example when no question bank is available
    print("\n" + "─" * 70)
    print("FALLBACK BEHAVIOR (No Question Bank)")
    print("─" * 70)
    
    # Create data without question bank
    interview_data_no_qb = create_mock_interview_data_with_questions()
    interview_data_no_qb.question_bank = None
    
    result = interview_data_no_qb.get_question_bank()
    print(result)
    
    print("\n" + "=" * 70)
    print("INTEGRATION NOTES")
    print("=" * 70)
    print("""
1. The ATS API should return question_bank in the response (optional field)
2. If present, questions will be automatically included in agent context
3. If not present, placeholder questions are generated based on skills
4. Questions can be filtered by category, difficulty, or tags if needed

Question Model Fields:
- question_text: The actual question (required)
- category: Category/topic (optional)
- difficulty: easy/medium/hard (optional)
- expected_answer_points: Key points to look for (optional)
- tags: List of relevant tags (optional)
""")


if __name__ == "__main__":
    main()
