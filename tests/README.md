# Tests

This directory contains test scripts and test data for validating the TAL Assistant agents.

## Test Scripts

### gRPC Service Tests

- **`test_qbp_grpc.py`** - Tests the Question Bank Personalizer agent via gRPC
  ```bash
  # Ensure main.py is running first
  python main.py &
  
  # Then run the test
  python tests/test_qbp_grpc.py HR-INT-2026-0001
  ```
  
  This test:
  - Connects to the gRPC server on port 50053
  - Sends an interview_id
  - Validates the JSON response structure
  - Verifies personalized questions and resume summary are returned

- **`test_servers.py`** - Integration tests for Signal Detector and Next Question Inferrer
  ```bash
  python tests/test_servers.py
  ```
  
  This test suite validates:
  - Signal detection from transcript segments
  - Question/answer identification
  - Next question inference
  - Integration between agents

## Test Data

JSON files containing sample data for testing:

- **`test_data_conversation_flow.json`** - Full conversation flow test data
- **`test_data_shallow_answers.json`** - Test data for detecting shallow/vague answers
- **`test_data_thorough_answers.json`** - Test data for detecting thorough/detailed answers  
- **`test_request.json`** - Sample request payloads

## Prerequisites

Before running tests:

1. **Start required services:**
   ```bash
   # Start Redis
   redis-server
   
   # Start ATS API (if testing against real data)
   # See ATS documentation
   
   # Start main.py for gRPC tests
   python main.py
   ```

2. **Set environment variables:**
   ```bash
   export ATS_BASE_URL=http://localhost:8000
   export REDIS_URL=redis://localhost:6379
   export GRPC_PORT=50051
   export NQI_GRPC_PORT=50052
   export QBP_GRPC_PORT=50053
   ```

## Running Tests

### Individual Tests

```bash
# Test Question Bank Personalizer gRPC service
python tests/test_qbp_grpc.py HR-INT-2026-0001

# Test Signal Detector and Next Question Inferrer
python tests/test_servers.py
```

### With Different Interview IDs

```bash
# Pass interview ID as argument
python tests/test_qbp_grpc.py HR-INT-2026-0002
```

### With Debug Logging

```python
# Add to test script or run with:
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Test Output

Successful tests will show:
- ✓ Connection established
- ✓ Request sent
- ✓ Response received
- ✓ JSON validation passed
- ✓ Expected fields present

Failed tests will show:
- ✗ Error details
- Troubleshooting suggestions
- Stack traces (with debug logging)

## Troubleshooting

**gRPC connection errors:**
- Ensure main.py is running
- Check port numbers (50051, 50052, 50053)
- Verify firewall settings

**ATS API errors:**
- Confirm ATS server is running
- Verify ATS_BASE_URL is correct
- Check interview_id exists in ATS

**Redis errors:**
- Ensure Redis server is running
- Verify REDIS_URL is correct
- Check Redis connection logs

**JSON parsing errors:**
- Check agent response format
- Enable debug logging to see raw responses
- Verify agent instructions are correct

## Adding New Tests

When adding new test scripts:

1. Follow the naming convention: `test_<feature>.py`
2. Include docstring explaining what's tested
3. Add command-line argument support when appropriate
4. Provide clear error messages and troubleshooting tips
5. Update this README with the new test

Example test structure:
```python
"""
Test <Feature Name>
-------------------
Description of what this test validates.

Prerequisites:
    - Service X must be running
    - Environment variable Y must be set

Usage:
    python tests/test_<feature>.py [args]
"""
import asyncio
import sys

async def test_feature():
    # Test implementation
    pass

if __name__ == "__main__":
    asyncio.run(test_feature())
```
