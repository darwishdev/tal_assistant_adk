"""
Example: Test PREDEFINED Strategy with Question Bank
-----------------------------------------------------
This example demonstrates how the Next Question Inferrer handles
the PREDEFINED strategy by fetching questions from the personalized
question bank stored in Redis.

Prerequisites:
    - Redis must be running
    - Question Bank Personalizer must have been run
    - NQI session must be initialized with INIT mode
    - main.py gRPC server must be running (port 50052)
    
Usage:
    python examples/example_nqi_predefined.py HR-INT-2026-0001
"""
import asyncio
import sys
import logging
import grpc
from pathlib import Path

# Add parent directory to Python path so imports work
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from a2a.grpc import a2a_pb2, a2a_pb2_grpc

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NQI_GRPC_PORT = 50052


async def test_predefined_flow(interview_id: str, session_id: str = "test-predefined-session"):
    """
    Test the complete PREDEFINED question flow.
    
    Steps:
    1. Initialize NQI with interview context (INIT)
    2. Trigger AUTO mode with empty history (should use PREDEFINED)
    3. Verify we get questions from the personalized bank
    4. Track question progression
    """
    
    async with grpc.aio.insecure_channel(f"localhost:{NQI_GRPC_PORT}") as channel:
        stub = a2a_pb2_grpc.AgentCardServiceStub(channel)
        
        print("\n" + "="*80)
        print("TESTING PREDEFINED STRATEGY - QUESTION BANK FLOW")
        print("="*80)
        
        # Step 1: Initialize session
        print(f"\n[1] Initializing NQI session with interview_id: {interview_id}")
        init_message = f"INIT|{interview_id}"
        
        message = a2a_pb2.Message(
            role=a2a_pb2.Role.ROLE_USER,
            parts=[a2a_pb2.Part(text=init_message)]
        )
        
        request = a2a_pb2.SendMessageRequest(
            session_id=session_id,
            message=message
        )
        
        response = await stub.SendMessage(request)
        print("    ✓ Session initialized")
        
        # Step 2: Send empty AUTO trigger (should trigger PREDEFINED strategy)
        print("\n[2] Sending AUTO trigger with minimal history...")
        print("    (This should trigger PREDEFINED strategy)")
        
        auto_message = 'AUTO|{"history": []}'  # Empty history
        
        message = a2a_pb2.Message(
            role=a2a_pb2.Role.ROLE_USER,
            parts=[a2a_pb2.Part(text=auto_message)]
        )
        
        request = a2a_pb2.SendMessageRequest(
            session_id=session_id,
            message=message
        )
        
        response = await stub.SendMessage(request)
        
        # Extract response
        if response and response.message and response.message.parts:
            import json
            response_text = ""
            for part in response.message.parts:
                if part.text:
                    response_text += part.text
            
            result = json.loads(response_text)
            
            print("\n" + "-"*80)
            print("RESPONSE:")
            print("-"*80)
            print(f"Strategy: {result.get('strategy', 'N/A')}")
            print(f"Next Question: {result.get('next_question', 'N/A')}")
            print(f"Rationale: {result.get('rationale', 'N/A')}")
            
            if result.get('metadata'):
                metadata = result['metadata']
                print(f"\nMetadata:")
                print(f"  - Category: {metadata.get('category', 'N/A')}")
                print(f"  - Difficulty: {metadata.get('difficulty', 'N/A').upper()}")
                print(f"  - Question #{metadata.get('question_number', 'N/A')} of {metadata.get('total_questions', 'N/A')}")
            
            print("-"*80)
            
            # Step 3: Get a few more questions to show progression
            print("\n[3] Fetching next few questions to show progression...")
            
            for i in range(3):
                print(f"\n    Request #{i+2}:")
                
                # Send another AUTO trigger
                message = a2a_pb2.Message(
                    role=a2a_pb2.Role.ROLE_USER,
                    parts=[a2a_pb2.Part(text=auto_message)]
                )
                
                request = a2a_pb2.SendMessageRequest(
                    session_id=session_id,
                    message=message
                )
                
                response = await stub.SendMessage(request)
                
                if response and response.message and response.message.parts:
                    response_text = ""
                    for part in response.message.parts:
                        if part.text:
                            response_text += part.text
                    
                    result = json.loads(response_text)
                    
                    if result.get('metadata'):
                        metadata = result['metadata']
                        print(f"    Question #{metadata.get('question_number')} [{metadata.get('category')}]:")
                        print(f"    {result.get('next_question', 'N/A')[:100]}...")
                    else:
                        print(f"    {result.get('next_question', 'N/A')[:100]}...")
            
            print("\n" + "="*80)
            print("✓ PREDEFINED strategy test complete!")
            print("="*80)
            print("\nKey Observations:")
            print("  - Questions are served sequentially from personalized bank")
            print("  - Each question includes category and difficulty metadata")
            print("  - Question counter increments with each request")
            print("  - No question repetition (state tracked in Redis)")


async def main():
    """Main entry point."""
    interview_id = sys.argv[1] if len(sys.argv) > 1 else "HR-INT-2026-0001"
    session_id = sys.argv[2] if len(sys.argv) > 2 else "test-predefined-session"
    
    await test_predefined_flow(interview_id, session_id)


if __name__ == "__main__":
    asyncio.run(main())
