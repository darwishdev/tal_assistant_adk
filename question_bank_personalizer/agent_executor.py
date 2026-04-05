"""
agent_executor.py — Question Bank Personalizer Executor
--------------------------------------------------------
Orchestrates the question bank personalization workflow:
1. Fetches interview data from ATS API
2. Formats data for the agent
3. Invokes the personalizer agent
4. Parses and returns structured output
"""
import json
import logging
import os
import re
from typing import Dict, Any, Optional

from google.adk.runners import Runner
from google.genai.types import Content, Part

from question_bank_personalizer.agent import question_bank_personalizer
from pkg.ats_api.client import AtsApiClient
from pkg.ats_api.models import InterviewData, QuestionBank

log = logging.getLogger(__name__)

# Regex to extract JSON from agent response
_JSON_RE = re.compile(r'\{.*\}', re.DOTALL)


class QuestionBankPersonalizerResult:
    """Result from the question bank personalizer agent."""
    
    def __init__(
        self,
        personalized_question_bank: Dict[str, Any],
        summarized_resume: str,
        interview_data: Optional[InterviewData] = None,
        raw_response: str = ""
    ):
        self.personalized_question_bank = personalized_question_bank
        self.summarized_resume = summarized_resume
        self.interview_data = interview_data
        self.raw_response = raw_response
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "personalized_question_bank": self.personalized_question_bank,
            "summarized_resume": self.summarized_resume
        }
    
    def get_formatted_question_bank(self) -> str:
        """Get formatted question bank as string."""
        output = []
        categories = self.personalized_question_bank.get("categories", [])
        
        for category in categories:
            category_name = category.get("category_name", "Uncategorized")
            output.append(f"\n─── {category_name} {'─' * (60 - len(category_name))}")
            
            questions = category.get("questions", [])
            for q in questions:
                question_text = q.get("question_text", "")
                difficulty = q.get("difficulty", "medium")
                output.append(f"- [{difficulty.upper()}] {question_text}")
        
        return "\n".join(output)


def _format_question_bank(question_bank: Optional[QuestionBank]) -> str:
    """Format question bank for agent input."""
    if not question_bank or not question_bank.questions:
        return "No original question bank provided."
    
    output = []
    if question_bank.name:
        output.append(f"Question Bank: {question_bank.name}")
    if question_bank.description:
        output.append(f"Description: {question_bank.description}")
    output.append("")
    
    # Group questions by category if available
    categorized: Dict[str, list] = {}
    uncategorized = []
    
    for q in question_bank.questions:
        category = q.category or "General"
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(q)
    
    for category, questions in categorized.items():
        output.append(f"─── {category} ───")
        for q in questions:
            line = f"- {q.question_text}"
            if q.difficulty:
                line += f" [{q.difficulty.upper()}]"
            output.append(line)
        output.append("")
    
    return "\n".join(output)


def _format_interview_data_for_agent(interview_data: InterviewData) -> str:
    """Format interview data into agent input prompt."""
    
    # Format job opening
    job_description = f"""JOB_OPENING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Job Title: {interview_data.job_opening.job_title}
Designation: {interview_data.job_opening.designation}
Company: {interview_data.job_opening.company or 'N/A'}
Location: {interview_data.job_opening.location or 'N/A'}
Employment Type: {interview_data.job_opening.employment_type or 'N/A'}
Status: {interview_data.job_opening.status}

Description:
{interview_data.job_opening.description or 'No description available'}
"""
    
    # Format applicant
    applicant_info = f"""APPLICANT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: {interview_data.applicant.applicant_name}
Email: {interview_data.applicant.email_id}
Phone: {interview_data.applicant.phone_number or 'N/A'}
Designation: {interview_data.applicant.designation}
Status: {interview_data.applicant.status}
Rating: {interview_data.applicant.applicant_rating}
"""
    
    # Format resume
    resume = f"""APPLICANT_RESUME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Summary:
{interview_data.applicant_resume.summary or 'No summary available'}

Skills:
{interview_data.applicant_resume.skills or 'No skills listed'}
"""
    
    # Add experience
    if interview_data.applicant_resume.experience:
        resume += "\n\nExperience:\n"
        for exp in interview_data.applicant_resume.experience:
            resume += f"- {exp.position or 'Position'} at {exp.company or 'Company'}"
            if exp.duration:
                resume += f" ({exp.duration})"
            resume += "\n"
            if exp.description:
                resume += f"  {exp.description}\n"
    
    # Add education
    if interview_data.applicant_resume.education:
        resume += "\n\nEducation:\n"
        for edu in interview_data.applicant_resume.education:
            resume += f"- {edu.degree or 'Degree'}"
            if edu.field:
                resume += f" in {edu.field}"
            if edu.institution:
                resume += f" from {edu.institution}"
            if edu.year:
                resume += f" ({edu.year})"
            resume += "\n"
    
    # Add projects
    if interview_data.applicant_resume.projects:
        resume += "\n\nProjects:\n"
        for proj in interview_data.applicant_resume.projects:
            resume += f"- {proj.name or 'Project'}\n"
            if proj.description:
                resume += f"  Description: {proj.description}\n"
            if proj.technologies:
                resume += f"  Technologies: {proj.technologies}\n"
    
    # Format interview round
    interview_round_info = f"""INTERVIEW_ROUND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Round Name: {interview_data.interview_round.round_name}
Interview Type: {interview_data.interview_round.interview_type}
Expected Average Rating: {interview_data.interview_round.expected_average_rating}
Designation: {interview_data.interview_round.designation}

Expected Skill Set:
"""
    for skill in interview_data.interview_round.expected_skill_set:
        interview_round_info += f"- {skill.skill}"
        if skill.description:
            interview_round_info += f": {skill.description}"
        interview_round_info += "\n"
    
    # Format question bank
    question_bank_text = f"""ORIGINAL_QUESTION_BANK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_format_question_bank(interview_data.question_bank)}
"""
    
    # Combine all sections
    full_prompt = f"""
{job_description}

{applicant_info}

{resume}

{interview_round_info}

{question_bank_text}
"""
    
    return full_prompt.strip()


def _parse_agent_response(raw_response: str) -> Dict[str, Any]:
    """Parse JSON from agent response."""
    # Try to find and parse JSON
    log.debug(f"Raw agent response: {raw_response[:500]}...")
    
    # First try direct JSON parse
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON using regex
    match = _JSON_RE.search(raw_response)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse extracted JSON: {e}")
            log.debug(f"Extracted text: {match.group()[:500]}...")
    
    raise ValueError(f"Could not parse JSON from agent response: {raw_response[:200]}...")


async def personalize_question_bank(
    interview_id: str,
    ats_base_url: str = "http://localhost:8000"
) -> QuestionBankPersonalizerResult:
    """
    Personalize question bank for an interview.
    
    Args:
        interview_id: Interview identifier (e.g., "HR-INT-2026-0001")
        ats_base_url: Base URL of the ATS API server
        
    Returns:
        QuestionBankPersonalizerResult with personalized question bank and resume summary
        
    Raises:
        Exception: If ATS API call fails or agent response cannot be parsed
    """
    log.info(f"Starting question bank personalization for interview: {interview_id}")
    
    # Step 1: Fetch interview data from ATS
    log.info(f"Fetching interview data from ATS at {ats_base_url}")
    async with AtsApiClient(base_url=ats_base_url) as client:
        interview_data = await client.get_interview_details(interview_id)
    
    log.info(f"Successfully fetched interview data for {interview_data.applicant.applicant_name}")
    
    # Step 2: Format data for agent
    log.info("Formatting interview data for agent")
    agent_input = _format_interview_data_for_agent(interview_data)
    log.debug(f"Agent input length: {len(agent_input)} characters")
    
    # Step 3: Invoke agent directly (stateless, no session needed  )
    log.info("Invoking question bank personalizer agent")
    
    try:
        # Call the agent's LLM directly without Runner/session infrastructure
        # This is a stateless operation that doesn't need persistence
        from google.genai import Client
        
        client = Client()
        
        # Combine the agent's system instruction with the user input
        full_prompt = f"{question_bank_personalizer.instruction}\n\n{agent_input}"
        
        # Invoke the model asynchronously
        response = await client.aio.models.generate_content(
            model=question_bank_personalizer.model,
            contents=full_prompt
        )
        
        raw_response = ""
        if response and hasattr(response, 'text') and response.text:
            raw_response = response.text
        elif response and hasattr(response, 'candidates') and response.candidates:
            # Extract text from candidates
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                raw_response += part.text
        
        log.info(f"Received agent response (length: {len(raw_response)})")
        
        # Step 4: Parse response
        log.info("Parsing agent response")
        result_data = _parse_agent_response(raw_response)
        
        # Validate structure
        if "personalized_question_bank" not in result_data:
            raise ValueError("Response missing 'personalized_question_bank' field")
        if "summarized_resume" not in result_data:
            raise ValueError("Response missing 'summarized_resume' field")
        
        result = QuestionBankPersonalizerResult(
            personalized_question_bank=result_data["personalized_question_bank"],
            summarized_resume=result_data["summarized_resume"],
            interview_data=interview_data,  # Include the full ATS interview data
            raw_response=raw_response
        )
        
        log.info("✓ Successfully personalized question bank")
        log.info(f"  - Generated {len(result.personalized_question_bank.get('categories', []))} question categories")
        log.info(f"  - Resume summary length: {len(result.summarized_resume)} characters")
        
        return result
        
    except Exception as e:
        log.error(f"Error during question bank personalization: {e}", exc_info=True)
        raise


# Convenience function for testing
async def personalize_and_print(interview_id: str, ats_base_url: str = "http://localhost:8000"):
    """
    Personalize question bank and print results in a friendly format.
    Useful for testing and debugging.
    """
    print(f"\n{'='*70}")
    print(f"PERSONALIZING QUESTION BANK FOR: {interview_id}")
    print(f"{'='*70}\n")
    
    try:
        result = await personalize_question_bank(interview_id, ats_base_url)
        
        print("✓ PERSONALIZATION COMPLETE\n")
        
        print(f"{'─'*70}")
        print("SUMMARIZED RESUME")
        print(f"{'─'*70}")
        print(result.summarized_resume)
        print()
        
        print(f"{'─'*70}")
        print("PERSONALIZED QUESTION BANK")
        print(f"{'─'*70}")
        print(result.get_formatted_question_bank())
        print()
        
        return result
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        raise
