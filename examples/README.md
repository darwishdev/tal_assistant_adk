# Examples

This directory contains example scripts and utilities for working with the TAL Assistant agents.

## Example Scripts

### Question Bank Personalization
- **`example_question_bank_personalizer.py`** - Demonstrates how to use the Question Bank Personalizer agent to generate personalized questions and resume summaries
  ```bash
  python examples/example_question_bank_personalizer.py
  ```

- **`example_personalized_interview_retrieval.py`** - Shows how to retrieve personalized interview data from Redis during an interview
  ```bash
  python examples/example_personalized_interview_retrieval.py HR-INT-2026-0001
  ```

### Integration Examples
- **`example_integration_main.py`** - Full workflow integration example showing how agents work together
  ```bash
  python examples/example_integration_main.py
  ```

- **`example_session_init.py`** - Example of initializing an interview session with ATS data
  ```bash
  python examples/example_session_init.py
  ```

- **`example_redis_interview_context.py`** - Example of using Redis for interview context management
  ```bash
  python examples/example_redis_interview_context.py
  ```

- **`example_question_bank.py`** - Example of working with question banks
  ```bash
  python examples/example_question_bank.py
  ```

## Utility Scripts

### Debugging & Diagnostics
- **`debug_publish.py`** - Debug utility for testing Redis publishing
  ```bash
  python examples/debug_publish.py
  ```

- **`diagnose_ats_connection.py`** - Diagnostic tool to test ATS API connectivity
  ```bash
  python examples/diagnose_ats_connection.py
  ```

## Environment Variables

Most examples use these environment variables:

```bash
# ATS API
export ATS_BASE_URL=http://localhost:8000

# Redis
export REDIS_URL=redis://localhost:6379

# Interview ID for testing
export INTERVIEW_ID=HR-INT-2026-0001
```

## Usage Pattern

1. **Ensure services are running:**
   - ATS API server
   - Redis server
   - main.py (for gRPC examples)

2. **Set environment variables** (optional - scripts use defaults)

3. **Run the example:**
   ```bash
   python examples/<script_name>.py
   ```

## Tips

- Check the script's docstring for specific usage instructions
- Enable debug logging for more details:
  ```python
  import logging
  logging.basicConfig(level=logging.DEBUG)
  ```
- Most scripts can be imported and used programmatically in your own code
