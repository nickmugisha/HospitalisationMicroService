from __future__ import annotations
import logging
from concurrent import futures
import grpc
from hospitalisation.v1 import hospitalisation_pb2_grpc
from services.hospitalisation.config import HOSPITALISATION_GRPC_HOST, HOSPITALISATION_GRPC_PORT
from services.hospitalisation.service import HospitalisationService

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("projectx.hospitalisation")

def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    hospitalisation_pb2_grpc.add_HospitalisationServiceServicer_to_server(HospitalisationService(), server)
    address = f"{HOSPITALISATION_GRPC_HOST}:{HOSPITALISATION_GRPC_PORT}"
    bound = server.add_insecure_port(address)
    if bound == 0:
        raise RuntimeError(f"Unable to bind HospitalisationService to {address}")
    server.start(); logger.info("PROJECTX HospitalisationService started on %s", address); logger.info("Hospitalisation gRPC port: %s", bound)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping PROJECTX HospitalisationService..."); server.stop(grace=5); logger.info("PROJECTX HospitalisationService stopped.")

if __name__ == "__main__":
    serve()
