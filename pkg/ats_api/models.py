"""
ATS API Data Models
-------------------
Pydantic models for parsing ATS API responses.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class InterviewDetail(BaseModel):
    """Individual interviewer detail."""
    interviewer: str
    idx: int


class Interview(BaseModel):
    """Interview information."""
    name: str
    designation: str
    interview_round: str
    job_applicant: str
    custom_job_opening: Optional[str] = None
    scheduled_on: Optional[str] = None
    from_time: Optional[str] = None
    to_time: Optional[str] = None
    status: str
    interview_details: List[InterviewDetail] = Field(default_factory=list)


class Applicant(BaseModel):
    """Job applicant information."""
    name: str
    applicant_name: str
    email_id: str
    phone_number: Optional[str] = None
    designation: str
    status: str
    applicant_rating: float = 0.0


class PipelineStep(BaseModel):
    """Pipeline step in job opening."""
    step_code: str
    step_name: str
    step_type: str


class JobOpeningApplicant(BaseModel):
    """Applicant in job opening."""
    job_applicant: str
    applicant_resume: str
    step_code: str
    invalidated_at: Optional[str] = None


class JobOpening(BaseModel):
    """Job opening information."""
    name: str
    job_title: str
    designation: str
    status: str
    company: Optional[str] = None
    department: Optional[str] = None
    employment_type: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    custom_pipeline_steps: List[PipelineStep] = Field(default_factory=list)
    custom_applicants: List[JobOpeningApplicant] = Field(default_factory=list)


class Experience(BaseModel):
    """Work experience entry."""
    company: Optional[str] = None
    position: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    """Education entry."""
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    year: Optional[str] = None


class Project(BaseModel):
    """Project entry."""
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[str] = None


class ApplicantResume(BaseModel):
    """Applicant resume with parsed details."""
    name: str
    summary: Optional[str] = None
    skills: Optional[str] = None
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)


class ExpectedSkillSet(BaseModel):
    """Expected skill for interview round."""
    skill: str
    description: Optional[str] = None


class Interviewer(BaseModel):
    """Interviewer in interview round."""
    user: str
    idx: int


class InterviewRound(BaseModel):
    """Interview round information."""
    round_name: str
    interview_type: str
    expected_average_rating: float
    designation: str
    interviewers: List[Interviewer] = Field(default_factory=list)
    expected_skill_set: List[ExpectedSkillSet] = Field(default_factory=list)


class InterviewType(BaseModel):
    """Interview type information."""
    name: str
    description: Optional[str] = None


class Question(BaseModel):
    """Individual question in the question bank."""
    question_text: str
    category: Optional[str] = None
    difficulty: Optional[str] = None  # e.g., "easy", "medium", "hard"
    expected_answer_points: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class QuestionBank(BaseModel):
    """Question bank for the interview."""
    name: Optional[str] = None
    description: Optional[str] = None
    questions: List[Question] = Field(default_factory=list)


class InterviewData(BaseModel):
    """
    Complete interview data returned from ATS API.
    This is the top-level response object.
    """
    interview: Interview
    applicant: Applicant
    job_opening: JobOpening
    applicant_resume: ApplicantResume
    interview_round: InterviewRound
    interview_type: InterviewType
    question_bank: Optional[QuestionBank] = None

    def get_recruiter_name(self) -> str:
        """Extract the first interviewer's email as recruiter name."""
        if self.interview.interview_details:
            return self.interview.interview_details[0].interviewer
        return "Unknown"

    def get_job_description(self) -> str:
        """Get formatted job description."""
        return f"""Role: {self.job_opening.job_title}
Designation: {self.job_opening.designation}
Company: {self.job_opening.company or 'N/A'}
Location: {self.job_opening.location or 'N/A'}
Employment Type: {self.job_opening.employment_type or 'N/A'}

Description:
{self.job_opening.description or 'No description available'}"""

    def get_candidate_resume(self) -> str:
        """Get formatted candidate resume."""
        resume = f"""Name: {self.applicant.applicant_name}
Email: {self.applicant.email_id}
Phone: {self.applicant.phone_number or 'N/A'}
Designation: {self.applicant.designation}

Summary:
{self.applicant_resume.summary or 'No summary available'}

Skills:
{self.applicant_resume.skills or 'No skills listed'}
"""
        
        if self.applicant_resume.experience:
            resume += "\n\nExperience:\n"
            for exp in self.applicant_resume.experience:
                resume += f"- {exp.position or 'Position'} at {exp.company or 'Company'}\n"
                if exp.description:
                    resume += f"  {exp.description}\n"
        
        if self.applicant_resume.education:
            resume += "\n\nEducation:\n"
            for edu in self.applicant_resume.education:
                resume += f"- {edu.degree or 'Degree'} in {edu.field or 'Field'} from {edu.institution or 'Institution'}\n"
        
        return resume

    def get_expected_skills(self) -> List[str]:
        """Get list of expected skills for the interview."""
        return [skill.skill for skill in self.interview_round.expected_skill_set]

    def get_question_bank(self) -> str:
        """Get formatted question bank if available."""
        if not self.question_bank or not self.question_bank.questions:
            return "No predefined questions available."
        
        result = ""
        if self.question_bank.name:
            result += f"Question Bank: {self.question_bank.name}\n"
        if self.question_bank.description:
            result += f"Description: {self.question_bank.description}\n"
        
        result += f"\nPredefined Questions ({len(self.question_bank.questions)}):\n"
        for i, q in enumerate(self.question_bank.questions, 1):
            result += f"\n{i}. {q.question_text}"
            if q.category:
                result += f" [{q.category}]"
            if q.difficulty:
                result += f" (Difficulty: {q.difficulty})"
            if q.expected_answer_points:
                result += f"\n   Expected Answer Points: {q.expected_answer_points}"
            if q.tags:
                result += f"\n   Tags: {', '.join(q.tags)}"
            result += "\n"
        
        return result
