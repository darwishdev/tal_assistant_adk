"""
Test Question Bank Personalizer via gRPC
-----------------------------------------
Simple script to test the Question Bank Personalizer gRPC service.

Prerequisites:
    - main.py must be running
    - ATS API must be accessible
    
Usage:
    python test_qbp_grpc.py [interview_id]
"""
import asyncio
import sys
import grpc
from a2a.grpc import a2a_pb2, a2a_pb2_grpc


async def test_question_bank_personalizer(interview_id: str = "HR-INT-2026-0001"):
    """
    Test the Question Bank Personalizer via gRPC.
    
    Args:
        interview_id: Interview identifier to personalize
    """
    print(f"\n{'='*70}")
    print(f"Testing Question Bank Personalizer via gRPC")
    print(f"{'='*70}")
    print(f"Interview ID: {interview_id}")
    print(f"Connecting to: localhost:50053")
    print(f"{'='*70}\n")
    
    try:
        # Create gRPC channel
        async with grpc.aio.insecure_channel("localhost:50053") as channel:
            stub = a2a_pb2_grpc.A2AServiceStub(channel)
            
            # Create message request
            message = a2a_pb2.Message(
                role=a2a_pb2.Role.ROLE_USER,
                context_id=f"qbp-test-{interview_id}",
                message_id=f"msg-test-{id(interview_id)}",
                content=[a2a_pb2.Part(text=interview_id)],
            )
            
            request = a2a_pb2.SendMessageRequest(request=message)
            
            print("Sending request...")
            print(f"Context ID: {message.context_id}")
            print(f"User Input: {interview_id}\n")
            
            # Execute request
            print("Waiting for response...\n")
            response = await stub.SendMessage(request)
            
            full_response = ""
            if response.HasField("msg"):
                for part in response.msg.content:
                    if part.text:
                        full_response += part.text
                        print(part.text, end='', flush=True)
            
            print(f"\n\n{'='*70}")
            print("✓ Response received successfully!")
            print(f"{'='*70}\n")
            
            # Try to parse as JSON to verify structure
            if full_response:
                import json
                try:
                    data = json.loads(full_response)
                    print("Response structure:")
                    print(f"  - Has personalized_question_bank: {'personalized_question_bank' in data}")
                    print(f"  - Has summarized_resume: {'summarized_resume' in data}")
                    
                    if 'personalized_question_bank' in data:
                        categories = data['personalized_question_bank'].get('categories', [])
                        print(f"  - Number of question categories: {len(categories)}")
                        total_questions = sum(len(cat.get('questions', [])) for cat in categories)
                        print(f"  - Total questions: {total_questions}")
                    
                    if 'summarized_resume' in data:
                        resume_len = len(data['summarized_resume'])
                        print(f"  - Resume summary length: {resume_len} characters")
                    
                    print(f"\n{'='*70}")
                    print("✓ Test completed successfully!")
                    print(f"{'='*70}\n")
                    
                except json.JSONDecodeError as e:
                    print(f"\n⚠ Warning: Could not parse response as JSON: {e}")
                    print("Raw response received (may be an error message)")
            
            return full_response
            
    except grpc.aio.AioRpcError as e:
        print(f"\n✗ gRPC Error:")
        print(f"  Status: {e.code()}")
        print(f"  Details: {e.details()}")
        print(f"\nTroubleshooting:")
        print(f"  1. Ensure main.py is running")
        print(f"  2. Check that port 50053 is accessible")
        print(f"  3. Verify the ATS server is running")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Get interview_id from command line or use default
    interview_id = sys.argv[1] if len(sys.argv) > 1 else "HR-INT-2026-0001"
    
    asyncio.run(test_question_bank_personalizer(interview_id))
