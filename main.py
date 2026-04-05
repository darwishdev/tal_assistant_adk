# main.py — Unified gRPC server for Signal Detector + NQI + Question Bank Personalizer
import asyncio
import logging
import os

import grpc
from grpc_reflection.v1alpha import reflection
from dotenv import load_dotenv

from a2a.grpc import a2a_pb2, a2a_pb2_grpc
from a2a.server.request_handlers import DefaultRequestHandler, GrpcHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from signaling_agent.agent_executor import SignalDetectorExecutor
from next_question_agent.agent_executor_next_question import NextQuestionExecutor
from question_bank_personalizer.agent_executor_grpc import QuestionBankPersonalizerExecutor

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.INFO)
log = logging.getLogger(__name__)

# ── Ports ────────────────────────────────────────────────────────────────
SIGNAL_GRPC_PORT = int(os.environ.get("GRPC_PORT", "50051"))
NQI_GRPC_PORT    = int(os.environ.get("NQI_GRPC_PORT", "50052"))
QBP_GRPC_PORT    = int(os.environ.get("QBP_GRPC_PORT", "50053"))

# ── Agent card builders ───────────────────────────────────────────────────
def build_signal_detector_card() -> AgentCard:
    return AgentCard(
        name="Signal Detector",
        description="Detects conversation structure signals from live transcript segments.",
        url=f"grpc://localhost:{SIGNAL_GRPC_PORT}",
        version="1.0.0",
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="detect_signals",
                name="Detect Conversation Signals",
                description="Emits [QUESTION_START] [QUESTION_END] [ANSWER_START] [ANSWER_END]",
                tags=["signals", "interview", "transcript"],
                inputModes=["text/plain"],
                outputModes=["text/plain"],
            )
        ],
    )


def build_next_question_card() -> AgentCard:
    return AgentCard(
        name="Next Question Inferrer",
        description=(
            "Analyses completed Q/A pairs from a live transcript and suggests "
            "the most relevant follow-up question. Can be triggered automatically "
            "by the Signal Detector or manually by a user."
        ),
        url=f"grpc://localhost:{NQI_GRPC_PORT}",
        version="1.0.0",
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="infer_next_question",
                name="Infer Next Question",
                description=(
                    "Given a Q/A pair or a transcript snippet + user prompt, "
                    "returns the best follow-up question as JSON: "
                    '{"next_question": "...", "rationale": "..."}'
                ),
                tags=["interview", "followup", "transcript", "question"],
                inputModes=["text/plain"],
                outputModes=["text/plain"],
            )
        ],
    )


def build_question_bank_personalizer_card() -> AgentCard:
    return AgentCard(
        name="Question Bank Personalizer",
        description=(
            "Pre-interview agent that analyzes interview context from ATS and generates "
            "personalized question banks and concise resume summaries tailored to the "
            "candidate's background and job requirements."
        ),
        url=f"grpc://localhost:{QBP_GRPC_PORT}",
        version="1.0.0",
        defaultInputModes=["text/plain"],
        defaultOutputModes=["application/json"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="personalize_questions",
                name="Personalize Question Bank",
                description=(
                    "Given an interview_id, fetches data from ATS and returns "
                    "personalized question bank and summarized resume as JSON: "
                    '{"personalized_question_bank": {...}, "summarized_resume": "..."}'
                ),
                tags=["interview", "questions", "personalization", "pre-interview"],
                inputModes=["text/plain"],
                outputModes=["application/json"],
            )
        ],
    )

# ── Server starter ───────────────────────────────────────────────────────
async def start_grpc_server(executor, agent_card: AgentCard, port: int):
    """Start a gRPC server for a given agent executor and port."""
    request_handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())
    grpc_handler = GrpcHandler(agent_card=agent_card, request_handler=request_handler)

    server = grpc.aio.server()
    a2a_pb2_grpc.add_A2AServiceServicer_to_server(grpc_handler, server)

    # Enable reflection for grpcurl
    service_names = (
        a2a_pb2.DESCRIPTOR.services_by_name["A2AService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)
    log.info("gRPC server listening on %s for %s", listen_addr, agent_card.name)
    await server.start()
    return server

# ── Main ────────────────────────────────────────────────────────────────
async def main() -> None:
    load_dotenv()

    # Create executor instances
    signal_executor = SignalDetectorExecutor()
    nqi_executor    = NextQuestionExecutor()
    qbp_executor    = QuestionBankPersonalizerExecutor()

    # Build agent cards
    signal_card = build_signal_detector_card()
    nqi_card    = build_next_question_card()
    qbp_card    = build_question_bank_personalizer_card()

    # Start all servers concurrently
    signal_server = await start_grpc_server(signal_executor, signal_card, SIGNAL_GRPC_PORT)
    nqi_server    = await start_grpc_server(nqi_executor, nqi_card, NQI_GRPC_PORT)
    qbp_server    = await start_grpc_server(qbp_executor, qbp_card, QBP_GRPC_PORT)

    # Wait for all servers
    await asyncio.gather(
        signal_server.wait_for_termination(),
        nqi_server.wait_for_termination(),
        qbp_server.wait_for_termination(),
    )

if __name__ == "__main__":
    asyncio.run(main())