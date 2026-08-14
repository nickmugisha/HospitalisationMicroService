from __future__ import annotations

import logging
from concurrent import futures

import grpc

from accueil.v1 import accueil_pb2_grpc
from services.accueil.config import ACCUEIL_GRPC_HOST, ACCUEIL_GRPC_PORT
from services.accueil.service import AccueilService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("projectx.accueil")


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    accueil_pb2_grpc.add_AccueilServiceServicer_to_server(AccueilService(), server)

    address = f"{ACCUEIL_GRPC_HOST}:{ACCUEIL_GRPC_PORT}"
    bound_port = server.add_insecure_port(address)
    if bound_port == 0:
        raise RuntimeError(f"Unable to bind AccueilService to {address}")

    server.start()
    logger.info("PROJECTX AccueilService started on %s", address)
    logger.info("Accueil gRPC port: %s", bound_port)

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping PROJECTX AccueilService...")
        server.stop(grace=5)
        logger.info("PROJECTX AccueilService stopped.")


if __name__ == "__main__":
    serve()
