"""
main.py — Signal Detector A2A server, gRPC transport only
----------------------------------------------------------
No HTTP, no JSON-RPC, no Starlette — pure gRPC on port 50051.

Run:
    uv run python main.py
"""
import asyncio
import logging
import os

import grpc
# Add to imports
from grpc_reflection.v1alpha import reflection
from a2a.grpc import a2a_pb2

from a2a.grpc import a2a_pb2_grpc
from a2a.server.request_handlers import DefaultRequestHandler, GrpcHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from dotenv import load_dotenv
from agent_executor import SignalDetectorExecutor

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

GRPC_PORT = int(os.environ.get("GRPC_PORT", "50051"))

# ← log everything including grpc internals
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# tone down noisy libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.INFO)

log = logging.getLogger(__name__)
GRPC_PORT = int(os.environ.get("GRPC_PORT", "50051"))

 
def build_agent_card() -> AgentCard:
    return AgentCard(
        name="Signal Detector",
        description="Detects conversation structure signals from live transcript segments.",
        url=f"grpc://localhost:{GRPC_PORT}",  # informational only
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

async def main() -> None:
    load_dotenv()
    executor        = SignalDetectorExecutor()
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )
    agent_card   = build_agent_card()
    grpc_handler = GrpcHandler(
        agent_card=agent_card,
        request_handler=request_handler,
    )

    server = grpc.aio.server()
    a2a_pb2_grpc.add_A2AServiceServicer_to_server(grpc_handler, server)

    # Enable reflection so grpcurl can discover services
    service_names = (
        a2a_pb2.DESCRIPTOR.services_by_name["A2AService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    listen_addr = f"[::]:{GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    log.info("gRPC server listening on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(main())