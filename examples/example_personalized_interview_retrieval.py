"""
Example: Retrieve Personalized Interview Data from Redis
---------------------------------------------------------
This example demonstrates how to retrieve personalized interview data
that was stored by the Question Bank Personalizer agent.

During an actual interview, agents like Next Question Inferrer can call
get_personalized_interview_data() to access the personalized question bank
and resume summary.

Prerequisites:
    - Redis must be running
    - Question Bank Personalizer must have been run for the interview
    
Usage:
    python examples/example_personalized_interview_retrieval.py HR-INT-2026-0001
"""
import asyncio
import sys
import json
import logging

from pkg.redis.redis_publisher import get_personalized_interview_data

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def main():
    """Retrieve and display personalized interview data."""
    
    # Get interview_id from command line or use default
    interview_id = sys.argv[1] if len(sys.argv) > 1 else "HR-INT-2026-0001"
    
    log.info(f"Retrieving personalized interview data for: {interview_id}")
    
    # Retrieve the personalized data from Redis
    personalized_data = await get_personalized_interview_data(interview_id)
    
    if not personalized_data:
        log.error(f"No personalized data found for interview: {interview_id}")
        log.info("Make sure the Question Bank Personalizer has been run first:")
        log.info(f"  python examples/example_question_bank_personalizer.py {interview_id}")
        return
    
    # Display the retrieved data
    print("\n" + "="*80)
    print(f"PERSONALIZED INTERVIEW DATA: {interview_id}")
    print("="*80)
    
    # Display full interview data if available
    if "interview_data" in personalized_data and personalized_data["interview_data"]:
        interview_data = personalized_data["interview_data"]
        print("\n📊 FULL INTERVIEW DATA (from ATS)")
        print("-" * 80)
        print(f"Job Title: {interview_data.job_opening.job_title}")
        print(f"Company: {interview_data.job_opening.company or 'N/A'}")
        print(f"Applicant: {interview_data.applicant.applicant_name}")
        print(f"Email: {interview_data.applicant.email_id}")
        print(f"Rating: {interview_data.applicant.applicant_rating}")
        print(f"Round: {interview_data.interview_round.round_name}")
        print(f"Interview Type: {interview_data.interview_round.interview_type}")
    
    # Display resume summary
    print("\n📋 RESUME SUMMARY")
    print("-" * 80)
    print(personalized_data["summarized_resume"])
    
    # Display personalized question bank
    print("\n❓ PERSONALIZED QUESTION BANK")
    print("-" * 80)
    
    question_bank = personalized_data["personalized_question_bank"]
    categories = question_bank.get("categories", [])
    
    total_questions = 0
    for category in categories:
        category_name = category.get("category_name", "Uncategorized")
        questions = category.get("questions", [])
        total_questions += len(questions)
        
        print(f"\n📁 {category_name}")
        for i, q in enumerate(questions, 1):
            difficulty = q.get("difficulty", "medium").upper()
            question_text = q.get("question_text", "")
            print(f"   {i}. [{difficulty}] {question_text}")
    
    print("\n" + "="*80)
    print(f"Total Categories: {len(categories)}")
    print(f"Total Questions: {total_questions}")
    print("="*80)
    
    # Show how to access specific data programmatically
    print("\n💡 PROGRAMMATIC ACCESS EXAMPLE")
    print("-" * 80)
    print("# Access resume summary:")
    print(f'resume_summary = personalized_data["summarized_resume"]')
    print(f"\n# Access question bank:")
    print(f'question_bank = personalized_data["personalized_question_bank"]')
    print(f'\n# Access full interview data (if available):')
    print(f'if "interview_data" in personalized_data:')
    print(f'    interview_data = personalized_data["interview_data"]')
    print(f'    job_title = interview_data.job_opening.job_title')
    print(f'    applicant_name = interview_data.applicant.applicant_name')
    print(f'    # Access any ATS data...')
    print(f'\n# Iterate through categories:')
    print(f'for category in question_bank["categories"]:')
    print(f'    category_name = category["category_name"]')
    print(f'    questions = category["questions"]')
    print(f'    # Process questions...')
    
    print("\n✓ Retrieval complete!")


if __name__ == "__main__":
    asyncio.run(main())
