from __future__ import annotations

import logging
from concurrent import futures

import grpc

from laboratoire.v1 import laboratoire_pb2_grpc
from services.laboratoire.config import LABORATOIRE_GRPC_HOST, LABORATOIRE_GRPC_PORT
from services.laboratoire.service import LaboratoireService


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("projectx.laboratoire")


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    laboratoire_pb2_grpc.add_LaboratoireServiceServicer_to_server(LaboratoireService(), server)
    address = f"{LABORATOIRE_GRPC_HOST}:{LABORATOIRE_GRPC_PORT}"
    bound_port = server.add_insecure_port(address)
    if bound_port == 0:
        raise RuntimeError(f"Unable to bind LaboratoireService to {address}")
    server.start()
    logger.info("PROJECTX LaboratoireService started on %s", address)
    logger.info("Laboratoire gRPC port: %s", bound_port)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping PROJECTX LaboratoireService...")
        server.stop(grace=5)
        logger.info("PROJECTX LaboratoireService stopped.")


if __name__ == "__main__":
    serve()
