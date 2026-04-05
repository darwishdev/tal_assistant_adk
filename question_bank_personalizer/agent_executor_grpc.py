"""
agent_executor_grpc.py — QuestionBankPersonalizerExecutor
----------------------------------------------------------
gRPC-compatible executor for the Question Bank Personalizer agent.
This executor is used in the main.py gRPC server.

Input Format:
    interview_id (e.g., "HR-INT-2026-0001")

Output Format:
    JSON with personalized_question_bank and summarized_resume
"""
import json
import logging
import os
from typing_extensions import override

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from question_bank_personalizer.agent_executor import personalize_question_bank
from pkg.redis.redis_publisher import store_personalized_interview_data

log = logging.getLogger(__name__)

ATS_BASE_URL = os.environ.get("ATS_BASE_URL", "http://localhost:8000")


class QuestionBankPersonalizerExecutor(AgentExecutor):
    """
    gRPC executor for Question Bank Personalizer agent.
    
    This is a stateless, pre-interview agent that doesn't require
    session management or streaming. It simply:
    1. Receives an interview_id
    2. Fetches data from ATS
    3. Personalizes questions and summarizes resume
    4. Returns structured JSON
    """

    @override
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute the question bank personalization.
        
        Args:
            context: Request context containing the interview_id
            event_queue: Event queue for sending responses
        """
        user_input = context.get_user_input()
        if not user_input:
            error_msg = "ERROR: No interview_id provided"
            log.warning(error_msg)
            await event_queue.enqueue_event(new_agent_text_message(error_msg))
            return

        interview_id = user_input.strip()
        
        log.info(f"Starting question bank personalization for interview: {interview_id}")
        
        try:
            # Call the personalization function
            result = await personalize_question_bank(
                interview_id=interview_id,
                ats_base_url=ATS_BASE_URL
            )
            
            # Store the personalized data in Redis for later use during the interview
            # Includes both personalized content and full ATS interview data
            await store_personalized_interview_data(
                interview_id=interview_id,
                personalized_data=result.to_dict(),
                interview_data=result.interview_data
            )
            
            # Convert result to JSON
            output = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
            
            log.info(
                f"✓ Personalization complete for {interview_id}\n"
                f"  - Categories: {len(result.personalized_question_bank.get('categories', []))}\n"
                f"  - Resume summary: {len(result.summarized_resume)} chars\n"
                f"  - Stored in Redis with full interview data for later retrieval"
            )
            
            # Send the response
            await event_queue.enqueue_event(new_agent_text_message(output))
            
        except Exception as e:
            error_msg = f"ERROR: Failed to personalize question bank: {str(e)}"
            log.error(error_msg, exc_info=True)
            await event_queue.enqueue_event(new_agent_text_message(error_msg))

    @override
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Cancel the personalization request.
        
        Since this is a stateless agent without session management,
        cancellation is a no-op. We just log the cancellation request.
        """
        interview_id = context.get_user_input() or "unknown"
        log.info(f"Question Bank Personalizer cancelled for interview: {interview_id}")
        await event_queue.enqueue_event(new_agent_text_message("Cancelled"))
