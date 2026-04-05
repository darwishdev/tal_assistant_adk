"""
Session Initializer
-------------------
Handles fetching interview data at session start and preparing context.
"""
import logging
from typing import Optional
from .client import AtsApiClient
from .models import InterviewData


log = logging.getLogger(__name__)


class SessionInitializer:
    """
    Manages session initialization by fetching interview data from ATS.
    
    This class is responsible for:
    - Fetching interview details from ATS API
    - Extracting and formatting data for agent context
    - Storing session state
    """

    def __init__(self, ats_base_url: str = "http://localhost:8000"):
        """
        Initialize session initializer.
        
        Args:
            ats_base_url: Base URL of the ATS API
        """
        self.ats_base_url = ats_base_url
        self.interview_data: Optional[InterviewData] = None

    async def initialize_session(self, interview_name: str) -> InterviewData:
        """
        Initialize a new interview session by fetching data from ATS.
        
        Args:
            interview_name: Interview identifier (e.g., "HR-INT-2026-0001")
            
        Returns:
            InterviewData object containing all interview information
            
        Raises:
            Exception: If fetching or parsing interview data fails
        """
        log.info(f"Initializing session for interview: {interview_name}")
        
        try:
            async with AtsApiClient(base_url=self.ats_base_url) as client:
                self.interview_data = await client.get_interview_details(interview_name)
            
            log.info(f"Session initialized successfully for {interview_name}")
            log.debug(f"  - Job: {self.interview_data.job_opening.job_title}")
            log.debug(f"  - Candidate: {self.interview_data.applicant.applicant_name}")
            log.debug(f"  - Round: {self.interview_data.interview_round.round_name}")
            
            return self.interview_data
            
        except Exception as e:
            log.error(
                f"Failed to initialize session for {interview_name}:\n"
                f"  ATS Base URL: {self.ats_base_url}\n"
                f"  Error Type: {type(e).__name__}\n"
                f"  Error Message: {str(e)}",
                exc_info=True
            )
            raise

    def get_recruiter_context(self) -> str:
        """Get formatted recruiter information for agent context."""
        if not self.interview_data:
            return "Recruiter: Unknown"
        
        recruiter_email = self.interview_data.get_recruiter_name()
        return f"Recruiter: {recruiter_email}"

    def get_job_description_context(self) -> str:
        """Get formatted job description for agent context."""
        if not self.interview_data:
            return "Job Description: Not available"
        
        return self.interview_data.get_job_description()

    def get_candidate_resume_context(self) -> str:
        """Get formatted candidate resume for agent context."""
        if not self.interview_data:
            return "Candidate Resume: Not available"
        
        return self.interview_data.get_candidate_resume()

    def get_question_bank_context(self) -> str:
        """
        Get question bank from interview data or generate placeholder.
        
        Returns predefined questions if available in the interview data,
        otherwise generates a placeholder based on expected skills.
        """
        if not self.interview_data:
            return "Question Bank: Not available"
        
        # Try to get question bank from interview data first
        if self.interview_data.question_bank and self.interview_data.question_bank.questions:
            return self.interview_data.get_question_bank()
        
        # Fallback to placeholder if no question bank in data
        skills = self.interview_data.get_expected_skills()
        
        # Placeholder - you would fetch actual questions based on skills
        question_bank = f"""Question Bank (based on skills: {', '.join(skills)}):
        
─── Technical Skills ───────────────────────────────────────────
- Can you describe your experience with {skills[0] if skills else 'relevant technologies'}?
- Walk me through a challenging project you've worked on.
- How do you approach problem-solving in your work?
- What tools and technologies are you most comfortable with?

─── Behavioral ─────────────────────────────────────────────────
- Tell me about a time when you had to deal with a difficult team member.
- How do you prioritize your work when you have multiple deadlines?
- Describe a situation where you had to learn a new technology quickly.
"""
        return question_bank

    def prepare_agent_context(self) -> dict:
        """
        Prepare complete context dictionary for agents.
        
        Returns:
            Dictionary containing all formatted context data
        """
        return {
            "interview_name": self.interview_data.interview.name if self.interview_data else "Unknown",
            "recruiter": self.get_recruiter_context(),
            "job_description": self.get_job_description_context(),
            "candidate_resume": self.get_candidate_resume_context(),
            "question_bank": self.get_question_bank_context(),
            "expected_skills": self.interview_data.get_expected_skills() if self.interview_data else [],
            "interview_round": self.interview_data.interview_round.round_name if self.interview_data else "Unknown",
            "interview_type": self.interview_data.interview_type.name if self.interview_data else "Unknown",
        }
