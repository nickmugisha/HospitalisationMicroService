from __future__ import annotations

import logging
from concurrent import futures

import grpc

from pharmacie.v1 import pharmacie_pb2_grpc
from services.pharmacie.config import PHARMACIE_GRPC_HOST, PHARMACIE_GRPC_PORT
from services.pharmacie.service import PharmacieService


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("projectx.pharmacie")


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=12))
    pharmacie_pb2_grpc.add_PharmacieServiceServicer_to_server(PharmacieService(), server)
    address = f"{PHARMACIE_GRPC_HOST}:{PHARMACIE_GRPC_PORT}"
    bound_port = server.add_insecure_port(address)
    if bound_port == 0:
        raise RuntimeError(f"Unable to bind PharmacieService to {address}")
    server.start()
    logger.info("PROJECTX PharmacieService started on %s", address)
    logger.info("Pharmacie gRPC port: %s", bound_port)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping PROJECTX PharmacieService...")
        server.stop(grace=5)
        logger.info("PROJECTX PharmacieService stopped.")


if __name__ == "__main__":
    serve()
