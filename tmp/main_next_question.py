"""
main_next_question.py — Next Question Inferrer A2A gRPC server
--------------------------------------------------------------
Runs on port 50052 (signal detector stays on 50051).
Run:
    uv run python main_next_question.py
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
import grpc
from grpc_reflection.v1alpha import reflection

from a2a.grpc import a2a_pb2, a2a_pb2_grpc
from a2a.server.request_handlers import DefaultRequestHandler, GrpcHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor_next_question import NextQuestionExecutor

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.INFO)

log = logging.getLogger(__name__)

GRPC_PORT = int(os.environ.get("NQI_GRPC_PORT", "50052"))


def build_agent_card() -> AgentCard:
    return AgentCard(
        name="Next Question Inferrer",
        description=(
            "Analyses completed Q/A pairs from a live transcript and suggests "
            "the most relevant follow-up question. Can be triggered automatically "
            "by the Signal Detector or manually by a user."
        ),
        url=f"grpc://localhost:{GRPC_PORT}",
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


async def main() -> None:
    load_dotenv()
    executor        = NextQuestionExecutor()
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

    service_names = (
        a2a_pb2.DESCRIPTOR.services_by_name["A2AService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    listen_addr = f"[::]:{GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    log.info("NQI gRPC server listening on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(main())