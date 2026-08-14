from __future__ import annotations

import logging
from concurrent import futures

import grpc

from consultation.v1 import consultation_pb2_grpc
from services.consultation.config import CONSULTATION_GRPC_HOST, CONSULTATION_GRPC_PORT
from services.consultation.service import ConsultationService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("projectx.consultation")


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    consultation_pb2_grpc.add_ConsultationServiceServicer_to_server(ConsultationService(), server)

    address = f"{CONSULTATION_GRPC_HOST}:{CONSULTATION_GRPC_PORT}"
    bound_port = server.add_insecure_port(address)
    if bound_port == 0:
        raise RuntimeError(f"Unable to bind ConsultationService to {address}")

    server.start()
    logger.info("PROJECTX ConsultationService started on %s", address)
    logger.info("Consultation gRPC port: %s", bound_port)

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping PROJECTX ConsultationService...")
        server.stop(grace=5)
        logger.info("PROJECTX ConsultationService stopped.")


if __name__ == "__main__":
    serve()
