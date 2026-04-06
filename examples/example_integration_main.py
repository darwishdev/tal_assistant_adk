"""
Example Integration - Session Initialization in Main Application
-----------------------------------------------------------------
This example shows how to integrate the ATS API client into your main
application to fetch interview context at session start.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to Python path so imports work
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import grpc
from grpc_reflection.v1alpha import reflection
from dotenv import load_dotenv

from a2a.grpc import a2a_pb2, a2a_pb2_grpc
from a2a.server.request_handlers import DefaultRequestHandler, GrpcHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from signaling_agent.agent_executor import SignalDetectorExecutor
from next_question_agent.agent_executor_next_question import NextQuestionExecutor
from pkg.ats_api.session_initializer import SessionInitializer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


# ── Global session storage ───────────────────────────────────────────────────
# In production, use Redis or a proper session store
ACTIVE_SESSIONS = {}


# ── Session Manager ──────────────────────────────────────────────────────────

class InterviewSessionManager:
    """
    Manages interview sessions with ATS data.
    
    When a new interview session starts:
    1. Fetch interview data from ATS API
    2. Store the context for the session
    3. Use it to build agent system prompts
    """
    
    def __init__(self, ats_base_url: str = "http://localhost:8000"):
        self.ats_base_url = ats_base_url
        self.sessions = {}  # interview_name -> SessionInitializer
    
    async def start_session(self, interview_name: str) -> dict:
        """
        Start a new interview session by fetching data from ATS.
        
        Args:
            interview_name: Interview ID (e.g., "HR-INT-2026-0001")
            
        Returns:
            Agent context dictionary
        """
        if interview_name in self.sessions:
            log.info(f"Session {interview_name} already exists, returning cached data")
            return self.sessions[interview_name].prepare_agent_context()
        
        log.info(f"Starting new session: {interview_name}")
        
        # Initialize session with ATS data
        initializer = SessionInitializer(ats_base_url=self.ats_base_url)
        
        try:
            await initializer.initialize_session(interview_name)
            self.sessions[interview_name] = initializer
            
            context = initializer.prepare_agent_context()
            log.info(f"✓ Session {interview_name} started successfully")
            log.info(f"  - Candidate: {initializer.interview_data.applicant.applicant_name}")
            log.info(f"  - Job: {initializer.interview_data.job_opening.job_title}")
            
            return context
            
        except Exception as e:
            log.error(f"✗ Failed to start session {interview_name}: {e}")
            raise
    
    def get_session_context(self, interview_name: str) -> Optional[dict]:
        """Get context for an active session."""
        if interview_name not in self.sessions:
            return None
        return self.sessions[interview_name].prepare_agent_context()
    
    def end_session(self, interview_name: str):
        """End an interview session."""
        if interview_name in self.sessions:
            log.info(f"Ending session: {interview_name}")
            del self.sessions[interview_name]


# ── Enhanced Request Handler with Session Context ────────────────────────────

class SessionAwareRequestHandler(DefaultRequestHandler):
    """
    Request handler that fetches ATS context on first message.
    """
    
    def __init__(self, agent_executor, task_store, session_manager: InterviewSessionManager):
        super().__init__(agent_executor, task_store)
        self.session_manager = session_manager
        self.initialized_contexts = set()  # Track which contexts have been initialized
    
    async def handle_send_message(self, request: a2a_pb2.Message) -> a2a_pb2.Message:
        """
        Handle incoming message, initializing session if needed.
        """
        context_id = request.context_id
        
        # Check if this is a new context that needs ATS initialization
        if context_id and context_id not in self.initialized_contexts:
            # Check if context_id is an interview name (starts with "HR-INT-")
            if context_id.startswith("HR-INT-"):
                interview_name = context_id
                log.info(f"New interview context detected: {interview_name}")
                
                try:
                    # Fetch interview data from ATS
                    context = await self.session_manager.start_session(interview_name)
                    
                    # Mark this context as initialized
                    self.initialized_contexts.add(context_id)
                    
                    # Store context globally (in production, use Redis)
                    ACTIVE_SESSIONS[context_id] = context
                    
                    log.info(f"✓ Session initialized and ready for {interview_name}")
                    
                except Exception as e:
                    log.error(f"Failed to initialize session for {interview_name}: {e}")
                    # Continue with default handling even if ATS fetch fails
        
        # Call parent handler
        return await super().handle_send_message(request)


# ── Example Usage in Server Startup ──────────────────────────────────────────

async def start_nqi_server_with_session_support():
    """
    Example: Start NQI server with session initialization support.
    """
    port = 50052
    ats_base_url = os.environ.get("ATS_BASE_URL", "http://localhost:8000")
    
    # Create session manager
    session_manager = InterviewSessionManager(ats_base_url=ats_base_url)
    
    # Create agent card
    agent_card = AgentCard(
        name="Next Question Inferrer",
        description="Suggests follow-up questions based on interview context from ATS",
        url=f"grpc://localhost:{port}",
        version="1.0.0",
    )
    
    # Create executor and request handler with session support
    executor = NextQuestionExecutor()
    task_store = InMemoryTaskStore()
    request_handler = SessionAwareRequestHandler(
        agent_executor=executor,
        task_store=task_store,
        session_manager=session_manager
    )
    
    # Create gRPC handler and server
    grpc_handler = GrpcHandler(agent_card=agent_card, request_handler=request_handler)
    server = grpc.aio.server()
    a2a_pb2_grpc.add_A2AServiceServicer_to_server(grpc_handler, server)
    
    # Enable reflection
    service_names = (
        a2a_pb2.DESCRIPTOR.services_by_name["A2AService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)
    
    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)
    
    log.info(f"Starting NQI server with ATS session support on {listen_addr}")
    await server.start()
    
    # Keep server running
    await server.wait_for_termination()


# ── Standalone Example: Manual Session Initialization ────────────────────────

async def example_manual_session_init():
    """
    Example: Manually initialize session before starting interview.
    This approach is useful if you want to pre-fetch data.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE: Manual Session Initialization")
    print("=" * 70)
    
    interview_name = "HR-INT-2026-0001"
    session_manager = InterviewSessionManager()
    
    try:
        # Start session (fetches from ATS)
        context = await session_manager.start_session(interview_name)
        
        print(f"\n✓ Session ready: {interview_name}")
        print(f"\nContext summary:")
        print(f"  - Interview: {context['interview_name']}")
        print(f"  - Round: {context['interview_round']}")
        print(f"  - Type: {context['interview_type']}")
        print(f"  - Expected Skills: {', '.join(context['expected_skills'])}")
        
        # In your application, you would:
        # 1. Pass this context to your agent's system prompt
        # 2. Use interview_name as context_id for messages
        # 3. Start processing messages
        
        print(f"\nℹ Next steps:")
        print(f"  1. Use context_id='{interview_name}' in messages")
        print(f"  2. Context will be available via session_manager.get_session_context()")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")


async def main():
    """Run examples."""
    load_dotenv()
    
    print("\n" + "=" * 70)
    print("ATS API INTEGRATION EXAMPLES")
    print("=" * 70)
    
    # Example 1: Manual session initialization
    await example_manual_session_init()
    
    # Example 2: Server with auto-initialization (commented out)
    # Uncomment to run the full server
    # await start_nqi_server_with_session_support()
    
    print("\n" + "=" * 70)
    print("INTEGRATION COMPLETE")
    print("=" * 70)
    print("\nKey Points:")
    print("  ✓ Session manager fetches ATS data automatically")
    print("  ✓ Use interview name (HR-INT-xxx) as context_id")
    print("  ✓ Context is cached for the session lifetime")
    print("  ✓ Agent receives full interview context from ATS")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
