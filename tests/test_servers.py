"""
test_servers.py — interactive test script for Signal Detector + NQI servers
Usage: python test_servers.py
"""
import asyncio
import json
import logging
import os
import sys
import uuid

import grpc
from a2a.grpc import a2a_pb2, a2a_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
)
log = logging.getLogger(__name__)

SIGNAL_ADDR = os.environ.get("SIGNAL_ADDR", "localhost:50051")
NQI_ADDR    = os.environ.get("NQI_ADDR",    "localhost:50052")

# ── Sample data ──────────────────────────────────────────────────────────────

SAMPLE_SIGNALS = [
    ("INTERVIEWER", "00:00:10,000", "Can you tell me about your background in backend development?"),
    ("CANDIDATE",   "00:00:15,000", "Sure, I have 5 years of experience building REST APIs with Python and Go."),
    ("INTERVIEWER", "00:00:30,000", "What databases have you worked with?"),
    ("CANDIDATE",   "00:00:35,000", "Mostly PostgreSQL and Redis, but I also have experience with MongoDB."),
    ("INTERVIEWER", "00:01:00,000", "How do you handle authentication in your APIs?"),
    ("CANDIDATE",   "00:01:10,000", "I use JWT tokens with short expiry and refresh token rotation stored in Redis."),
]

SAMPLE_NQI_HISTORY = [
    {"type": "question", "text": "Can you tell me about your background?",          "timestamp": "00:00:10,000"},
    {"type": "answer",   "text": "I have 5 years of backend experience with Python.", "timestamp": "00:00:15,000"},
    {"type": "question", "text": "What databases have you worked with?",              "timestamp": "00:00:30,000"},
    {"type": "answer",   "text": "Mostly PostgreSQL and Redis.",                      "timestamp": "00:00:35,000"},
]

# ── Test scenarios for NQI strategy validation ──────────────────────────────

# Scenarios where agent should generate FOLLOW_UP (answer is incomplete/shallow)
SHALLOW_ANSWER_SCENARIOS = [
    {
        "name": "Vague statement without examples",
        "history": [
            {"type": "question", "text": "Tell me about your experience with deep learning frameworks.", "timestamp": "00:00:10,000"},
            {"type": "answer", "text": "I have worked with various ML models and frameworks.", "timestamp": "00:00:15,000"},
        ],
        "expected_strategy": "FOLLOW_UP",
        "reason": "Answer is too vague, lacks concrete examples"
    },
    {
        "name": "Unverified performance claim",
        "history": [
            {"type": "question", "text": "Have you optimized model performance before?", "timestamp": "00:01:00,000"},
            {"type": "answer", "text": "Yes, I improved our model accuracy by 30% through optimization.", "timestamp": "00:01:05,000"},
        ],
        "expected_strategy": "FOLLOW_UP",
        "reason": "Claims need verification - how was 30% measured?"
    },
    {
        "name": "Technical term without explanation",
        "history": [
            {"type": "question", "text": "How have you fine-tuned large language models?", "timestamp": "00:02:00,000"},
            {"type": "answer", "text": "I used LoRA and PEFT techniques for fine-tuning.", "timestamp": "00:02:10,000"},
        ],
        "expected_strategy": "FOLLOW_UP",
        "reason": "Technical terms mentioned but not explained"
    },
    {
        "name": "Incomplete thought with trailing ellipsis",
        "history": [
            {"type": "question", "text": "What programming languages are you proficient in?", "timestamp": "00:03:00,000"},
            {"type": "answer", "text": "I'm proficient in Python, SQL, and some other languages...", "timestamp": "00:03:05,000"},
        ],
        "expected_strategy": "FOLLOW_UP",
        "reason": "Incomplete answer, needs specifics"
    },
    {
        "name": "Surface-level skills mention",
        "history": [
            {"type": "question", "text": "What experience do you have with distributed training?", "timestamp": "00:04:00,000"},
            {"type": "answer", "text": "I have experience with distributed systems and parallel processing.", "timestamp": "00:04:08,000"},
        ],
        "expected_strategy": "FOLLOW_UP",
        "reason": "Too general, lacks technical depth"
    },
]

# Scenarios where agent should use PREDEFINED (answer is complete/thorough)
THOROUGH_ANSWER_SCENARIOS = [
    {
        "name": "Detailed technical implementation",
        "history": [
            {"type": "question", "text": "Describe your experience with distributed training.", "timestamp": "00:00:10,000"},
            {"type": "answer", "text": "I implemented distributed training using PyTorch DDP across 8 A100 GPUs. We used gradient accumulation with a global batch size of 512, implemented overlapped communication to avoid bottlenecks, and used local batch normalization. This reduced training time from 72 hours to 11 hours while maintaining model convergence.", "timestamp": "00:00:20,000"},
        ],
        "expected_strategy": "PREDEFINED",
        "reason": "Answer provides specific technical details, metrics, and outcomes"
    },
    {
        "name": "Complete project narrative with challenges",
        "history": [
            {"type": "question", "text": "Tell me about a challenging ML project you worked on.", "timestamp": "00:01:00,000"},
            {"type": "answer", "text": "I built a recommendation engine for our platform that serves 2 million users. The main challenge was cold-start problem for new users. I implemented a hybrid approach combining collaborative filtering with content-based features using user demographics and implicit signals. We used matrix factorization with ALS in PySpark for scalability. After A/B testing, we saw 23% increase in user engagement and 15% increase in conversion rate. The system processes 50K recommendations per second with 99.9% uptime.", "timestamp": "00:01:30,000"},
        ],
        "expected_strategy": "PREDEFINED",
        "reason": "Comprehensive answer with problem, solution, technologies, and measurable results"
    },
    {
        "name": "Verified technical specifications",
        "history": [
            {"type": "question", "text": "How have you worked with large datasets?", "timestamp": "00:02:00,000"},
            {"type": "answer", "text": "At SDAIA, I built ETL pipelines using PySpark to process terabytes of structured and unstructured data daily. We ingested data from multiple sources into Hive tables, performed data quality checks with Great Expectations, and built predictive models over billions of records achieving over 80% accuracy. The pipeline handled approximately 5TB of data per day with fault tolerance and automatic recovery mechanisms.", "timestamp": "00:02:20,000"},
        ],
        "expected_strategy": "PREDEFINED",
        "reason": "Specific quantifiable details with technologies and outcomes"
    },
    {
        "name": "Detailed architectural decision",
        "history": [
            {"type": "question", "text": "How do you approach model deployment?", "timestamp": "00:03:00,000"},
            {"type": "answer", "text": "I containerize models using Docker with multi-stage builds to minimize image size. For serving, I use FastAPI with async endpoints and implement request batching for throughput optimization. I deploy to Kubernetes with horizontal pod autoscaling based on CPU and custom metrics. For monitoring, I track prediction latency, model drift using Evidently, and business metrics. We use blue-green deployments for zero-downtime updates and maintain model versioning in MLflow for rollback capability.", "timestamp": "00:03:25,000"},
        ],
        "expected_strategy": "PREDEFINED",
        "reason": "Comprehensive technical approach covering multiple aspects with specific tools"
    },
]

# Mixed conversation flow - alternating shallow and thorough answers
CONVERSATION_FLOW_SCENARIO = [
    {
        "turn": 1,
        "history": [
            {"type": "question", "text": "Tell me about your experience with NLP.", "timestamp": "00:00:10,000"},
            {"type": "answer", "text": "I have worked on several NLP projects.", "timestamp": "00:00:15,000"},
        ],
        "expected_strategy": "FOLLOW_UP",
        "reason": "First answer is vague - needs follow-up"
    },
    {
        "turn": 2,
        "history": [
            {"type": "question", "text": "Tell me about your experience with NLP.", "timestamp": "00:00:10,000"},
            {"type": "answer", "text": "I have worked on several NLP projects.", "timestamp": "00:00:15,000"},
            {"type": "question", "text": "Can you describe a specific NLP project in detail?", "timestamp": "00:00:20,000"},
            {"type": "answer", "text": "I built a multilingual clinical text classification system for pharmaceutical companies. Used ensemble of BERT-based models fine-tuned on medical domain data achieving 92% F1-score across 5 languages. The system processes 10K documents per hour and integrates with their existing workflow via REST API. We handled class imbalance using focal loss and implemented active learning for continuous improvement.", "timestamp": "00:00:35,000"},
        ],
        "expected_strategy": "PREDEFINED",
        "reason": "Thorough answer with details - ready to move to next topic"
    },
    {
        "turn": 3,
        "history": [
            {"type": "question", "text": "Tell me about your experience with NLP.", "timestamp": "00:00:10,000"},
            {"type": "answer", "text": "I have worked on several NLP projects.", "timestamp": "00:00:15,000"},
            {"type": "question", "text": "Can you describe a specific NLP project in detail?", "timestamp": "00:00:20,000"},
            {"type": "answer", "text": "I built a multilingual clinical text classification system for pharmaceutical companies. Used ensemble of BERT-based models fine-tuned on medical domain data achieving 92% F1-score across 5 languages. The system processes 10K documents per hour and integrates with their existing workflow via REST API. We handled class imbalance using focal loss and implemented active learning for continuous improvement.", "timestamp": "00:00:35,000"},
            {"type": "question", "text": "Have you worked with model monitoring in production?", "timestamp": "00:00:50,000"},
            {"type": "answer", "text": "Yes, I have experience with production monitoring.", "timestamp": "00:00:55,000"},
        ],
        "expected_strategy": "FOLLOW_UP",
        "reason": "New topic but shallow answer - needs follow-up"
    },
]


# ── gRPC helpers ─────────────────────────────────────────────────────────────

def _make_message(text: str, context_id: str) -> a2a_pb2.Message:
    return a2a_pb2.Message(
        role=a2a_pb2.Role.ROLE_USER,
        context_id=context_id,
        message_id=f"msg-test-{id(text)}",
        content=[a2a_pb2.Part(text=text)],
    )
async def send_message(stub: a2a_pb2_grpc.A2AServiceStub,
                       text: str,
                       context_id: str) -> str | None:
    req = a2a_pb2.SendMessageRequest(request=_make_message(text, context_id))
    try:
        resp = await stub.SendMessage(req)
        if resp.HasField("msg"):
            raw = "".join(p.text for p in resp.msg.content).strip()
            return raw or None
    except grpc.aio.AioRpcError as e:
        log.error("gRPC error: status=%s details=%s", e.code(), e.details())
    return None


async def ping(stub: a2a_pb2_grpc.A2AServiceStub, label: str) -> bool:
    """Check that the server is reachable."""
    try:
        req = a2a_pb2.GetAgentCardRequest()
        await stub.GetAgentCard(req)
        log.info("%-20s ✓ reachable", label)
        return True
    except grpc.aio.AioRpcError as e:
        log.error("%-20s ✗ unreachable: %s %s", label, e.code(), e.details())
        return False


# ── Individual tests ─────────────────────────────────────────────────────────

async def test_signal_no_signal(stub: a2a_pb2_grpc.A2AServiceStub):
    """Filler speech should return empty — no signal."""
    print("\n── test: signal / no signal ────────────────────────────────")
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    text    = "INTERVIEWER|00:00:01,000|Hmm, let me think about that for a second."
    raw     = await send_message(stub, text, session_id)
    result  = f"EMPTY (correct)" if not raw else f"got: {raw}"
    print(f"  input : {text}")
    print(f"  result: {result}")


async def test_signal_question(stub: a2a_pb2_grpc.A2AServiceStub):
    """A clear question should return a question signal."""
    print("\n── test: signal / question ─────────────────────────────────")
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    text = "INTERVIEWER|00:00:10,000|Can you walk me through how you designed the caching layer?"
    raw  = await send_message(stub, text, session_id)
    print(f"  input : {text}")
    if raw:
        try:
            parsed = json.loads(raw)
            print(f"  type  : {parsed.get('type')}")
            print(f"  text  : {parsed.get('text')}")
        except json.JSONDecodeError:
            print(f"  raw   : {raw}")
    else:
        print("  result: EMPTY")


async def test_signal_answer(stub: a2a_pb2_grpc.A2AServiceStub):
    """A clear answer should return an answer signal."""
    print("\n── test: signal / answer ───────────────────────────────────")
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    text = "CANDIDATE|00:00:20,000|We used Redis with a write-through strategy and a 5-minute TTL on all keys."
    raw  = await send_message(stub, text, session_id)
    print(f"  input : {text}")
    if raw:
        try:
            parsed = json.loads(raw)
            print(f"  type  : {parsed.get('type')}")
            print(f"  text  : {parsed.get('text')}")
        except json.JSONDecodeError:
            print(f"  raw   : {raw}")
    else:
        print("  result: EMPTY")


async def test_signal_sequence(stub: a2a_pb2_grpc.A2AServiceStub):
    """Run through the full sample sequence and print each result."""
    print("\n── test: signal / full sequence ────────────────────────────")
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    ctx = session_id
    for speaker, ts, text in SAMPLE_SIGNALS:
        payload = f"{speaker}|{ts}|{text}"
        raw     = await send_message(stub, payload, ctx)
        if raw:
            try:
                parsed = json.loads(raw)
                print(f"  [{ts}] {speaker:<12} → {parsed.get('type'):8}  {parsed.get('text', '')[:60]}")
            except json.JSONDecodeError:
                print(f"  [{ts}] {speaker:<12} → (unparseable) {raw[:60]}")
        else:
            print(f"  [{ts}] {speaker:<12} → (no signal)")
        await asyncio.sleep(0.1)   # small gap between calls


async def test_nqi_auto(stub: a2a_pb2_grpc.A2AServiceStub):
    """AUTO trigger with a history list."""
    print("\n── test: NQI / AUTO ────────────────────────────────────────")
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    payload = "AUTO|" + json.dumps({"history": SAMPLE_NQI_HISTORY}, ensure_ascii=False)
    raw     = await send_message(stub, payload, session_id)
    print(f"  history entries: {len(SAMPLE_NQI_HISTORY)}")
    if raw:
        try:
            parsed = json.loads(raw)
            print(f"  next_question: {parsed.get('next_question')}")
            print(f"  rationale    : {parsed.get('rationale')}")
        except json.JSONDecodeError:
            print(f"  raw: {raw}")
    else:
        print("  result: EMPTY")


async def test_nqi_manual(stub: a2a_pb2_grpc.A2AServiceStub):
    """MANUAL trigger with a user prompt and transcript snippet."""
    print("\n── test: NQI / MANUAL ──────────────────────────────────────")
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    transcript = "\n".join(
        f"[{e['timestamp']}] {e['type'].upper()}: {e['text']}"
        for e in SAMPLE_NQI_HISTORY
    )
    payload = f"MANUAL|Dig deeper into the candidate's Redis experience|{transcript}"
    raw     = await send_message(stub, payload, session_id)
    print(f"  prompt: Dig deeper into the candidate's Redis experience")
    if raw:
        try:
            parsed = json.loads(raw)
            print(f"  next_question: {parsed.get('next_question')}")
            print(f"  rationale    : {parsed.get('rationale')}")
        except json.JSONDecodeError:
            print(f"  raw: {raw}")
    else:
        print("  result: EMPTY")


async def test_nqi_bad_input(stub: a2a_pb2_grpc.A2AServiceStub):
    """Bad input should return an error string, not crash."""
    print("\n── test: NQI / bad input ───────────────────────────────────")
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    for bad in ["", "GARBAGE", "AUTO|not-json", "MANUAL|"]:
        raw = await send_message(stub, bad, session_id)
        print(f"  input={bad!r:25}  response={raw!r}")


# ── NQI Strategy Validation Tests ────────────────────────────────────────────

def assert_nqi_strategy(response: str | None, expected_strategy: str, 
                        scenario_name: str) -> tuple[bool, dict | None]:
    """
    Assert that NQI response contains the expected strategy.
    Returns (passed, parsed_response)
    """
    if not response:
        log.error("  ✗ %s: No response received", scenario_name)
        return False, None
    
    try:
        parsed = json.loads(response)
        actual_strategy = parsed.get("strategy", "").upper()
        expected_strategy = expected_strategy.upper()
        
        if actual_strategy == expected_strategy:
            log.info("  ✓ %s: strategy=%s", scenario_name, actual_strategy)
            return True, parsed
        else:
            log.error("  ✗ %s: expected strategy=%s but got=%s", 
                     scenario_name, expected_strategy, actual_strategy)
            log.error("     question: %s", parsed.get("next_question", "")[:80])
            log.error("     rationale: %s", parsed.get("rationale", "")[:80])
            return False, parsed
    except json.JSONDecodeError as e:
        log.error("  ✗ %s: Failed to parse JSON: %s", scenario_name, str(e))
        log.error("     raw response: %s", response[:100])
        return False, None


async def test_nqi_follow_up_scenarios(stub: a2a_pb2_grpc.A2AServiceStub):
    """
    Test that agent generates FOLLOW_UP strategy for shallow/incomplete answers.
    """
    print("\n" + "=" * 70)
    print("TEST: NQI FOLLOW_UP Detection (Shallow Answers)")
    print("=" * 70)
    print("Testing scenarios where answers are incomplete and need follow-up...\n")
    
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    results = []
    for scenario in SHALLOW_ANSWER_SCENARIOS:
        print(f"Scenario: {scenario['name']}")
        print(f"  Reason: {scenario['reason']}")
        
        # Build payload
        payload = "AUTO|" + json.dumps({"history": scenario["history"]}, ensure_ascii=False)
        
        # Send to NQI
        raw = await send_message(stub, payload, session_id)
        print("\n" + "=" * 40)
        print(f"  Raw: {raw}")
        print("\n" + "=" * 40)
        
        # Validate strategy
        passed, parsed = assert_nqi_strategy(
            raw, 
            scenario["expected_strategy"], 
            scenario["name"]
        )
        
        results.append({
            "scenario": scenario["name"],
            "expected": scenario["expected_strategy"],
            "passed": passed,
            "response": parsed
        })
        
        if parsed and passed:
            print("\n" + f"  → Agent Follow-up Q: {parsed.get('next_question', '')}")
        
        print()
        await asyncio.sleep(0.2)  # Small delay between requests
    
    # Summary
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"\n{'-' * 70}")
    print(f"FOLLOW_UP Detection: {passed_count}/{total_count} passed")
    print(f"{'-' * 70}\n")
    
    return results


async def test_nqi_next_question_scenarios(stub: a2a_pb2_grpc.A2AServiceStub):
    """
    Test that agent generates PREDEFINED strategy for thorough/complete answers.
    """
    print("\n" + "=" * 70)
    print("TEST: NQI PREDEFINED Detection (Thorough Answers)")
    print("=" * 70)
    print("Testing scenarios where answers are complete and ready for next topic...\n")
    
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    results = []
    for scenario in THOROUGH_ANSWER_SCENARIOS:
        print(f"Scenario: {scenario['name']}")
        print(f"  Reason: {scenario['reason']}")
        
        # Build payload
        payload = "AUTO|" + json.dumps({"history": scenario["history"]}, ensure_ascii=False)
        
        # Send to NQI
        raw = await send_message(stub, payload, session_id)
        print("\n" + "=" * 40)
        print(f"  Raw: {raw}")
        print("\n" + "=" * 40)
        # Validate strategy
        passed, parsed = assert_nqi_strategy(
            raw, 
            scenario["expected_strategy"], 
            scenario["name"]
        )
        
        results.append({
            "scenario": scenario["name"],
            "expected": scenario["expected_strategy"],
            "passed": passed,
            "response": parsed
        })
        
        if parsed and passed:
            print("\n" + f"  → Agent Next Q: {parsed.get('next_question', '')}")
        
        print()
        await asyncio.sleep(0.2)  # Small delay between requests
    
    # Summary
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"\n{'-' * 70}")
    print(f"PREDEFINED Detection: {passed_count}/{total_count} passed")
    print(f"{'-' * 70}\n")
    
    return results


async def test_nqi_conversation_flow(stub: a2a_pb2_grpc.A2AServiceStub):
    """
    Test realistic conversation flow with alternating shallow and thorough answers.
    Validates that agent adapts strategy based on answer quality.
    """
    print("\n" + "=" * 70)
    print("TEST: NQI Conversation Flow (Mixed Answer Quality)")
    print("=" * 70)
    print("Testing multi-turn conversation with varying answer depth...\n")
    
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    results = []
    for turn_data in CONVERSATION_FLOW_SCENARIO:
        turn = turn_data["turn"]
        print(f"Turn {turn}: {turn_data['reason']}")
        
        # Show the latest Q&A
        history = turn_data["history"]
        if len(history) >= 2:
            latest_q = history[-2]["text"]
            latest_a = history[-1]["text"]
            print(f"  Q: {latest_q[:70]}...")
            print(f"  A: {latest_a[:70]}...")
        
        # Build payload
        payload = "AUTO|" + json.dumps({"history": history}, ensure_ascii=False)
        
        # Send to NQI
        raw = await send_message(stub, payload, session_id)
        
        # Validate strategy
        passed, parsed = assert_nqi_strategy(
            raw, 
            turn_data["expected_strategy"], 
            f"Turn {turn}"
        )
        
        results.append({
            "turn": turn,
            "expected": turn_data["expected_strategy"],
            "passed": passed,
            "response": parsed
        })
        
        if parsed:
            print(f"  → Strategy: {parsed.get('strategy', 'UNKNOWN')}")
            print(f"  → Next Q: {parsed.get('next_question', '')[:80]}...")
        
        print()
        await asyncio.sleep(0.2)
    
    # Summary
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"\n{'-' * 70}")
    print(f"Conversation Flow: {passed_count}/{total_count} turns passed")
    print(f"{'-' * 70}\n")
    
    return results


async def test_nqi_edge_cases(stub: a2a_pb2_grpc.A2AServiceStub):
    """
    Test edge cases: empty answers, very short answers, first question, etc.
    """
    print("\n" + "=" * 70)
    print("TEST: NQI Edge Cases")
    print("=" * 70)
    
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    edge_cases = [
        {
            "name": "Very short answer",
            "history": [
                {"type": "question", "text": "What's your experience with Python?", "timestamp": "00:00:10,000"},
                {"type": "answer", "text": "A lot.", "timestamp": "00:00:12,000"},
            ],
            "expected_strategy": "FOLLOW_UP",
            "reason": "Too brief to be complete"
        },
        {
            "name": "First question (no history)",
            "history": [],
            "expected_strategy": "PREDEFINED",
            "reason": "First question should come from question bank"
        },
        {
            "name": "Single word answer",
            "history": [
                {"type": "question", "text": "Do you have experience with Docker?", "timestamp": "00:00:10,000"},
                {"type": "answer", "text": "Yes.", "timestamp": "00:00:11,000"},
            ],
            "expected_strategy": "FOLLOW_UP",
            "reason": "Needs elaboration"
        },
    ]
    
    results = []
    for case in edge_cases:
        print(f"\nEdge Case: {case['name']}")
        print(f"  Reason: {case['reason']}")
        
        payload = "AUTO|" + json.dumps({"history": case["history"]}, ensure_ascii=False)
        raw = await send_message(stub, payload, session_id)
        
        passed, parsed = assert_nqi_strategy(raw, case["expected_strategy"], case["name"])
        
        results.append({
            "case": case["name"],
            "expected": case["expected_strategy"],
            "passed": passed,
            "response": parsed
        })
        
        if parsed and passed:
            print(f"  → Next Q: {parsed.get('next_question', '')[:100]}...")
        
        await asyncio.sleep(0.2)
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"\n{'-' * 70}")
    print(f"Edge Cases: {passed_count}/{total_count} passed")
    print(f"{'-' * 70}\n")
    
    return results


async def run_all_nqi_strategy_tests(stub: a2a_pb2_grpc.A2AServiceStub):
    """
    Run all NQI strategy validation tests and provide comprehensive summary.
    """
    print("\n" + "=" * 70)
    print("COMPREHENSIVE NQI STRATEGY VALIDATION TEST SUITE")
    print("=" * 70)
    print("This test suite validates that the Next Question Inferrer correctly")
    print("decides between FOLLOW_UP (for incomplete answers) and PREDEFINED")
    print("(for thorough answers ready to move to next topic).\n")
    
    all_results = {
        "follow_up": [],
        "predefined": [],
        "conversation_flow": [],
        "edge_cases": []
    }
    
    # Run all test categories
    all_results["follow_up"] = await test_nqi_follow_up_scenarios(stub)
    all_results["predefined"] = await test_nqi_next_question_scenarios(stub)
    all_results["conversation_flow"] = await test_nqi_conversation_flow(stub)
    all_results["edge_cases"] = await test_nqi_edge_cases(stub)
    
    # Overall summary
    print("\n" + "=" * 70)
    print("OVERALL TEST SUMMARY")
    print("=" * 70)
    
    total_tests = 0
    total_passed = 0
    
    for category, results in all_results.items():
        category_passed = sum(1 for r in results if r.get("passed", False))
        category_total = len(results)
        total_tests += category_total
        total_passed += category_passed
        
        status = "✓" if category_passed == category_total else "✗"
        print(f"{status} {category.replace('_', ' ').title():25} {category_passed}/{category_total} passed")
    
    print(f"\n{'=' * 70}")
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"FINAL RESULT: {total_passed}/{total_tests} tests passed ({pass_rate:.1f}%)")
    print(f"{'=' * 70}\n")
    
    return all_results


# ── Interactive menu ─────────────────────────────────────────────────────────

MENU = """
Commands:
  1   ping both servers
  2   signal: no-signal (filler)
  3   signal: question
  4   signal: answer
  5   signal: full sequence
  6   NQI: AUTO trigger
  7   NQI: MANUAL trigger
  8   NQI: bad input handling
  9   run all tests
  ──────────────────────────────────────────────
  10  NQI: test FOLLOW_UP detection (shallow answers)
  11  NQI: test PREDEFINED detection (thorough answers)
  12  NQI: test conversation flow (mixed quality)
  13  NQI: test edge cases
  14  NQI: run ALL strategy validation tests
  ──────────────────────────────────────────────
  s   custom signal   →  prompts for SPEAKER|TIMESTAMP|TEXT
  n   custom NQI AUTO →  prompts for question + answer
  q   quit
"""


async def custom_signal(stub: a2a_pb2_grpc.A2AServiceStub):
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    speaker = input("  speaker (e.g. INTERVIEWER): ").strip() or "INTERVIEWER"
    ts      = input("  timestamp (e.g. 00:01:00,000): ").strip() or "00:01:00,000"
    text    = input("  text: ").strip()
    if not text:
        print("  (empty text, skipped)")
        return
    payload = f"{speaker}|{ts}|{text}"
    raw     = await send_message(stub, payload, session_id)
    print(f"  raw response: {raw!r}")
    if raw:
        try:
            print(f"  parsed: {json.loads(raw)}")
        except json.JSONDecodeError:
            pass


async def custom_nqi_auto(stub: a2a_pb2_grpc.A2AServiceStub):
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    question = input("  question: ").strip()
    answer   = input("  answer  : ").strip()
    if not question or not answer:
        print("  (empty input, skipped)")
        return
    history  = [
        {"type": "question", "text": question, "timestamp": "00:00:00,000"},
        {"type": "answer",   "text": answer,   "timestamp": "00:00:05,000"},
    ]
    payload  = "AUTO|" + json.dumps({"history": history}, ensure_ascii=False)
    raw      = await send_message(stub, payload, session_id)
    print(f"  raw response: {raw!r}")
    if raw:
        try:
            print(f"  parsed: {json.loads(raw)}")
        except json.JSONDecodeError:
            pass


async def main():
    print(f"connecting to signal server @ {SIGNAL_ADDR}")
    print(f"connecting to NQI server    @ {NQI_ADDR}")

    async with (
        grpc.aio.insecure_channel(SIGNAL_ADDR) as sig_chan,
        grpc.aio.insecure_channel(NQI_ADDR)    as nqi_chan,
    ):
        sig_stub = a2a_pb2_grpc.A2AServiceStub(sig_chan)
        nqi_stub = a2a_pb2_grpc.A2AServiceStub(nqi_chan)

        print(MENU)
        while True:
            try:
                cmd = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nbye")
                break

            if cmd == "q":
                print("bye")
                break
            elif cmd == "1":
                await ping(sig_stub, "signal-detector")
                await ping(nqi_stub, "nqi")
            elif cmd == "2":
                await test_signal_no_signal(sig_stub)
            elif cmd == "3":
                await test_signal_question(sig_stub)
            elif cmd == "4":
                await test_signal_answer(sig_stub)
            elif cmd == "5":
                await test_signal_sequence(sig_stub)
            elif cmd == "6":
                await test_nqi_auto(nqi_stub)
            elif cmd == "7":
                await test_nqi_manual(nqi_stub)
            elif cmd == "8":
                await test_nqi_bad_input(nqi_stub)
            elif cmd == "9":
                await ping(sig_stub, "signal-detector")
                await ping(nqi_stub, "nqi")
                await test_signal_no_signal(sig_stub)
                await test_signal_question(sig_stub)
                await test_signal_answer(sig_stub)
                await test_signal_sequence(sig_stub)
                await test_nqi_auto(nqi_stub)
                await test_nqi_manual(nqi_stub)
                await test_nqi_bad_input(nqi_stub)
                print("\n── all tests done ──────────────────────────────────────")
            elif cmd == "10":
                await test_nqi_follow_up_scenarios(nqi_stub)
            elif cmd == "11":
                await test_nqi_next_question_scenarios(nqi_stub)
            elif cmd == "12":
                await test_nqi_conversation_flow(nqi_stub)
            elif cmd == "13":
                await test_nqi_edge_cases(nqi_stub)
            elif cmd == "14":
                await run_all_nqi_strategy_tests(nqi_stub)
            elif cmd == "s":
                await custom_signal(sig_stub)
            elif cmd == "n":
                await custom_nqi_auto(nqi_stub)
            elif cmd == "":
                continue
            else:
                print(f"  unknown command: {cmd!r}")
                print(MENU)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nbye")
        sys.exit(0)
    except EOFError:
        print("\nbye (EOF)")
        sys.exit(0)
    except Exception as e:
        log.error("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)