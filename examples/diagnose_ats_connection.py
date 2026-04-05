"""
ATS Connection Diagnostics
---------------------------
Quick diagnostics to check ATS server connectivity and troubleshoot issues.
"""
import asyncio
import httpx
import socket


async def test_connection():
    """Test connection to ATS server with detailed diagnostics."""
    
    print("=" * 70)
    print("ATS SERVER CONNECTION DIAGNOSTICS")
    print("=" * 70)
    
    base_url = "http://localhost:8000"
    interview_name = "HR-INT-2026-0001"
    endpoint = f"{base_url}/api/method/mawhub.api.interview_interview_api.interview_find"
    full_url = f"{endpoint}?name={interview_name}"
    
    # Test 1: Check if port is open
    print("\n[1] Testing if port 8000 is open...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        
        if result == 0:
            print("    ✓ Port 8000 is OPEN")
        else:
            print("    ✗ Port 8000 is CLOSED or not reachable")
            print(f"      Error code: {result}")
            print("\n    → Is the ATS server running?")
            print("      Try starting it with: python manage.py runserver 8000")
            return
    except Exception as e:
        print(f"    ✗ Socket test failed: {e}")
        return
    
    # Test 2: Try basic HTTP request to root
    print("\n[2] Testing HTTP connection to root...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/")
            print(f"    ✓ Connected! Status: {response.status_code}")
            print(f"      Response length: {len(response.text)} bytes")
    except httpx.ConnectError as e:
        print(f"    ✗ Connection failed: {e}")
        print("\n    Possible causes:")
        print("      - Server not running")
        print("      - Wrong port (check if it's 8000)")
        print("      - Firewall blocking connection")
        return
    except Exception as e:
        print(f"    ✗ Error: {type(e).__name__}: {e}")
        return
    
    # Test 3: Try the actual interview endpoint
    print("\n[3] Testing interview API endpoint...")
    print(f"    URL: {full_url}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint, params={"name": interview_name})
            print(f"    ✓ Request succeeded! Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    print("    ✓ Response format is correct")
                    interview_data = data.get("message", {}).get("interview", {})
                    if interview_data:
                        print(f"    ✓ Interview found: {interview_data.get('name')}")
                        print(f"      Candidate: {data.get('message', {}).get('applicant', {}).get('applicant_name')}")
                        print(f"      Job: {data.get('message', {}).get('job_opening', {}).get('job_title')}")
                    else:
                        print("    ⚠ Interview data is empty")
                else:
                    print("    ⚠ Response missing 'message' field")
                    print(f"      Response keys: {list(data.keys())}")
            elif response.status_code == 404:
                print(f"    ⚠ Interview not found: {interview_name}")
                print("      → Check if the interview ID is correct")
            else:
                print(f"    ⚠ Unexpected status code")
                print(f"      Response: {response.text[:200]}")
                
    except httpx.ConnectError as e:
        print(f"    ✗ Connection error: {e}")
        print("\n    Details:")
        print(f"      Error type: {type(e).__name__}")
        print(f"      Message: {str(e)}")
        
        # Check for specific error patterns
        error_str = str(e).lower()
        if "connection refused" in error_str:
            print("\n    → Connection refused - server not listening on port 8000")
        elif "timeout" in error_str:
            print("\n    → Connection timeout - server too slow or unreachable")
        elif "name or service not known" in error_str or "nodename nor servname" in error_str:
            print("\n    → DNS/hostname resolution failed")
        
    except httpx.HTTPStatusError as e:
        print(f"    ✗ HTTP error: {e.response.status_code}")
        print(f"      Response: {e.response.text[:200]}")
    except httpx.TimeoutException as e:
        print(f"    ✗ Request timeout: {e}")
        print("      → Server is too slow or not responding")
    except Exception as e:
        print(f"    ✗ Unexpected error: {type(e).__name__}")
        print(f"      Message: {str(e)}")
        import traceback
        print(f"\n    Full traceback:")
        print(f"    {traceback.format_exc()}")
    
    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 70)
    print("\nIf you're seeing connection errors, check:")
    print("  1. Is the ATS server running? (python manage.py runserver)")
    print("  2. Is it listening on the correct port? (default: 8000)")
    print("  3. Are there firewall rules blocking localhost connections?")
    print("  4. Try accessing in browser: http://localhost:8000")
    print()


async def main():
    await test_connection()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted")
