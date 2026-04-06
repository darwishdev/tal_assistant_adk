"""
Example: Initialize Next Question Inferrer with Interview Context
-----------------------------------------------------------------
This example demonstrates how to initialize the Next Question Inferrer (NQI)
agent with personalized interview data at the start of an interview session.

The INIT mode:
1. Receives interview_id
2. Fetches personalized data from Redis (Question Bank Personalizer response)
3. Sends FORMAT A (interview context) to the agent
4. Agent responds with "null" to acknowledge context loaded

Prerequisites:
    - Redis must be running
    - Question Bank Personalizer must have been run for the interview
    - main.py gRPC server must be running (port 50052 for NQI)
    
Usage:
    python examples/example_nqi_init.py HR-INT-2026-0001
"""
import asyncio
import sys
import logging
import grpc

from a2a.grpc import a2a_pb2, a2a_pb2_grpc

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NQI_GRPC_PORT = 50052


async def init_nqi_session(interview_id: str, session_id: str = "test-session-001"):
    """
    Initialize Next Question Inferrer session with interview context.
    
    Args:
        interview_id: Interview ID (e.g., "HR-INT-2026-0001")
        session_id: Unique session identifier for this interview session
    """
    log.info(f"Initializing NQI session: {session_id} for interview: {interview_id}")
    
    # Connect to NQI gRPC server
    async with grpc.aio.insecure_channel(f"localhost:{NQI_GRPC_PORT}") as channel:
        stub = a2a_pb2_grpc.A2AServiceStub(channel)
        
        # Build INIT request
        # Format: "INIT|{interview_id}"
        init_message = f"INIT|{interview_id}"
        
        log.info(f"Sending INIT message: {init_message}")
        
        # Create gRPC request
        message = a2a_pb2.Message(
            role=a2a_pb2.Role.ROLE_USER,
            context_id=session_id,
            message_id=f"msg-init-{id(init_message)}",
            content=[a2a_pb2.Part(text=init_message)]
        )
        
        request = a2a_pb2.SendMessageRequest(
            request=message
        )
        
        # Send request
        try:
            response = await stub.SendMessage(request)
            
            # Extract response text
            if response and response.msg and response.msg.content:
                response_text = ""
                for part in response.msg.content:
                    if part.text:
                        response_text += part.text
                
                response_text = response_text.strip()
                
                print("\n" + "="*80)
                print(f"NQI INITIALIZATION RESPONSE")
                print("="*80)
                print(f"Session ID: {session_id}")
                print(f"Interview ID: {interview_id}")
                print(f"Response: {response_text}")
                print("="*80)
                
                if response_text.lower() == "null" or response_text == "":
                    log.info("✓ NQI session initialized successfully!")
                    log.info("  - Interview context loaded")
                    log.info("  - Agent ready for Q/A interaction")
                    print("\n✅ SUCCESS: Next Question Inferrer is ready!")
                    print("   You can now send AUTO or MANUAL triggers with Q/A data.")
                else:
                    log.warning(f"Unexpected response: {response_text}")
                    print(f"\n⚠️  WARNING: Expected 'null', got: {response_text}")
            else:
                log.error("No response received from NQI")
                print("\n❌ ERROR: No response from Next Question Inferrer")
                
        except grpc.RpcError as e:
            log.error(f"gRPC error: {e.code()} - {e.details()}")
            print(f"\n❌ ERROR: {e.details()}")
            raise
        except Exception as e:
            log.error(f"Initialization failed: {e}", exc_info=True)
            print(f"\n❌ ERROR: {str(e)}")
            raise


async def main():
    """Main entry point."""
    # Get interview_id from command line or use default
    interview_id = sys.argv[1] if len(sys.argv) > 1 else "HR-INT-2026-0001"
    session_id = sys.argv[2] if len(sys.argv) > 2 else "test-session-001"
    
    print("\n" + "="*80)
    print("NEXT QUESTION INFERRER - INITIALIZATION")
    print("="*80)
    print(f"Interview ID: {interview_id}")
    print(f"Session ID: {session_id}")
    print(f"NQI gRPC Port: {NQI_GRPC_PORT}")
    print("="*80)
    
    # Initialize session
    await init_nqi_session(interview_id, session_id)
    
    print("\n💡 NEXT STEPS:")
    print("   1. Session is initialized with interview context")
    print("   2. Send AUTO triggers with Q/A data during interview")
    print("   3. Or send MANUAL triggers with custom prompts")
    print("\n   Example AUTO trigger:")
    print(f'      AUTO|{{"history": [{{"type": "question", "text": "..."}}]}}')
    print("\n   Example MANUAL trigger:")
    print('      MANUAL|Ask about distributed training|[transcript context]')


if __name__ == "__main__":
    asyncio.run(main())
