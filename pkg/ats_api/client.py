"""
ATS API Client
--------------
HTTP client for fetching interview data from Mawhub ATS.
"""
import logging
import os
from typing import Optional
import httpx
from .models import InterviewData, QuestionBank, Question


log = logging.getLogger(__name__)


def _create_mock_question_bank() -> QuestionBank:
    """
    Create a mock question bank for testing purposes.
    This will be used until the ATS API returns the actual question bank.
    """
    questions = [
        Question(
            question_text="How would you approach building a sentiment analysis model that distinguishes between Egyptian, Gulf, and Levantine dialects?",
            category="Arabic / Dialect NLP",
            difficulty="hard",
            tags=["NLP", "Arabic", "Dialects", "Sentiment Analysis"]
        ),
        Question(
            question_text="Explain the trade-offs between using root-based stemming vs. lemmatization for an Arabic search engine",
            category="Arabic / Dialect NLP",
            difficulty="medium",
            tags=["NLP", "Arabic", "Preprocessing"]
        ),
        Question(
            question_text='What are "Stop Words," and why might you remove them (or keep them) when processing Arabic text?',
            category="NLP Basics",
            difficulty="easy",
            tags=["NLP", "Fundamentals", "Arabic"]
        ),
        Question(
            question_text="What are three common techniques to prevent a neural network from overfitting?",
            category="ML Fundamentals",
            difficulty="medium",
            tags=["Machine Learning", "Neural Networks", "Optimization"]
        ),
        Question(
            question_text="In PyTorch or TensorFlow, what is the purpose of a DataLoader, and how does it help with memory management?",
            category="ML Frameworks",
            difficulty="easy",
            tags=["PyTorch", "TensorFlow", "Data Pipeline"]
        ),
        Question(
            question_text="If your model has high bias, would you add more data or increase model complexity? Why?",
            category="ML Fundamentals",
            difficulty="medium",
            tags=["Machine Learning", "Bias-Variance", "Model Selection"]
        ),
        Question(
            question_text="How would you architect a system to perform real-time sentiment analysis on 5,000 tweets per second?",
            category="System Design",
            difficulty="hard",
            tags=["System Design", "Scalability", "Real-time Processing"]
        ),
        Question(
            question_text='Your model\'s performance has dropped two months after deployment. How do you automate the detection of "Data Drift"?',
            category="MLOps",
            difficulty="hard",
            tags=["MLOps", "Monitoring", "Data Drift", "Production"]
        ),
    ]
    
    return QuestionBank(
        name="AI Engineer Technical Interview - Mock Question Bank",
        description="Mock question bank for testing until ATS API returns actual questions",
        questions=questions
    )


class AtsApiClient:
    """
    Client for interacting with the Mawhub ATS API.
    
    Usage:
        client = AtsApiClient(base_url="http://localhost:8000")
        data = await client.get_interview_details("HR-INT-2026-0001")
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        """
        Initialize ATS API client.
        
        Args:
            base_url: Base URL of the ATS API server (defaults to ATS_BASE_URL env var or http://localhost:8000)
            timeout: Request timeout in seconds
        """
        if base_url is None:
            base_url = os.environ.get("ATS_BASE_URL", "http://localhost:8000")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def get_interview_details(self, interview_name: str) -> InterviewData:
        """
        Fetch interview details from ATS API.
        
        Args:
            interview_name: Interview identifier (e.g., "HR-INT-2026-0001")
            
        Returns:
            InterviewData object with all interview information
            
        Raises:
            httpx.HTTPError: If the API request fails
            ValueError: If the response cannot be parsed
        """
        endpoint = f"{self.base_url}/api/method/mawhub.api.interview_interview_api.interview_find"
        params = {"name": interview_name}
        full_url = f"{endpoint}?name={interview_name}"

        log.info(f"Fetching interview details for: {interview_name}")
        log.debug(f"Request URL: {full_url}")
        
        try:
            client = await self._get_client()
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # The API returns {"message": {...}}
            if "message" not in data:
                raise ValueError("Invalid API response: missing 'message' field")
            
            interview_data = InterviewData(**data["message"])
            
            # TODO: Remove this mock once ATS API returns actual question bank
            # Add mock question bank if not present in response
            if interview_data.question_bank is None or not interview_data.question_bank.questions:
                log.info("Question bank not present in API response - using mock data")
                interview_data.question_bank = _create_mock_question_bank()
            
            log.info(f"Successfully fetched interview data for {interview_name}")
            
            return interview_data
            
        except httpx.HTTPStatusError as e:
            log.error(
                f"HTTP error fetching interview {interview_name}:\n"
                f"  Status Code: {e.response.status_code}\n"
                f"  URL: {full_url}\n"
                f"  Response: {e.response.text[:500]}\n"
                f"  Error: {str(e)}"
            )
            raise
        except httpx.ConnectError as e:
            log.error(
                f"Connection error fetching interview {interview_name}:\n"
                f"  URL: {full_url}\n"
                f"  Error Type: Connection Failed\n"
                f"  Details: {str(e)}\n"
                f"  → Is the ATS server running at {self.base_url}?"
            )
            raise
        except httpx.TimeoutException as e:
            log.error(
                f"Timeout error fetching interview {interview_name}:\n"
                f"  URL: {full_url}\n"
                f"  Timeout: {self.timeout}s\n"
                f"  Error: {str(e)}\n"
                f"  → Try increasing timeout or check server response time"
            )
            raise
        except httpx.RequestError as e:
            log.error(
                f"Request error fetching interview {interview_name}:\n"
                f"  URL: {full_url}\n"
                f"  Error Type: {type(e).__name__}\n"
                f"  Details: {str(e)}\n"
                f"  Full Exception:", exc_info=True
            )
            raise
        except ValueError as e:
            log.error(f"Error parsing interview data: {e}", exc_info=True)
            raise
        except Exception as e:
            log.error(
                f"Unexpected error fetching interview {interview_name}:\n"
                f"  URL: {full_url}\n"
                f"  Error Type: {type(e).__name__}\n"
                f"  Details: {str(e)}",
                exc_info=True
            )
            raise

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Convenience function for one-off requests
async def fetch_interview(interview_name: str, base_url: str | None = None) -> InterviewData:
    """
    Fetch interview details using a one-off client.
    
    Args:
        interview_name: Interview identifier (e.g., "HR-INT-2026-0001")
        base_url: Base URL of the ATS API server (defaults to ATS_BASE_URL env var or http://localhost:8000)
        
    Returns:
        InterviewData object with all interview information
    """
    async with AtsApiClient(base_url=base_url) as client:
        return await client.get_interview_details(interview_name)
