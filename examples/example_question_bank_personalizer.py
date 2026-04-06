"""
Example: Question Bank Personalizer
------------------------------------
Demonstrates how to use the question bank personalizer agent
to generate personalized questions and resume summaries.

Usage:
    python examples/example_question_bank_personalizer.py

Environment Variables:
    ATS_BASE_URL: Base URL of the ATS API (default: http://localhost:8000)
    INTERVIEW_ID: Interview identifier to personalize (default: HR-INT-2026-0001)
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to Python path so imports work
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Import the personalizer
from question_bank_personalizer.agent_executor import (
    personalize_question_bank,
    personalize_and_print
)


async def main():
    """Run the question bank personalizer example."""
    
    # Get configuration from environment
    ats_base_url = os.environ.get("ATS_BASE_URL", "http://localhost:8000")
    interview_id = os.environ.get("INTERVIEW_ID", "HR-INT-2026-0002")
    
    print("\n" + "="*70)
    print("QUESTION BANK PERSONALIZER - EXAMPLE")
    print("="*70)
    print(f"ATS URL: {ats_base_url}")
    print(f"Interview ID: {interview_id}")
    print("="*70 + "\n")
    
    try:
        # Option 1: Use the friendly print version
        result = await personalize_and_print(interview_id, ats_base_url)
        
        # Option 2: Access the structured data
        print("\n" + "="*70)
        print("ACCESSING STRUCTURED DATA")
        print("="*70 + "\n")
        
        print("Number of question categories:", 
              len(result.personalized_question_bank.get("categories", [])))
        
        # Count total questions
        total_questions = sum(
            len(cat.get("questions", []))
            for cat in result.personalized_question_bank.get("categories", [])
        )
        print("Total personalized questions:", total_questions)
        
        print("\nResume summary preview:")
        print(result.summarized_resume[:200] + "..." 
              if len(result.summarized_resume) > 200 
              else result.summarized_resume)
        
        # Option 3: Export to dict for further processing
        data_dict = result.to_dict()
        print("\n✓ Data can be exported as dict for integration with other systems")
        
        return result
        
    except Exception as e:
        log.error(f"Failed to personalize question bank: {e}", exc_info=True)
        print(f"\n✗ ERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure the ATS server is running")
        print(f"2. Verify the interview ID '{interview_id}' exists")
        print(f"3. Check that the ATS API is accessible at {ats_base_url}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
