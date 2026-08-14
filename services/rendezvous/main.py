from __future__ import annotations
import logging
from concurrent import futures
import grpc
from rendezvous.v1 import rendezvous_pb2_grpc
from services.rendezvous.config import RENDEZVOUS_GRPC_HOST, RENDEZVOUS_GRPC_PORT
from services.rendezvous.service import RendezvousService

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger=logging.getLogger("projectx.rendezvous")

def serve() -> None:
    server=grpc.server(futures.ThreadPoolExecutor(max_workers=12))
    rendezvous_pb2_grpc.add_RendezvousServiceServicer_to_server(RendezvousService(),server)
    address=f"{RENDEZVOUS_GRPC_HOST}:{RENDEZVOUS_GRPC_PORT}"
    bound_port=server.add_insecure_port(address)
    if bound_port==0: raise RuntimeError(f"Unable to bind RendezvousService to {address}")
    server.start(); logger.info("PROJECTX RendezvousService started on %s",address); logger.info("Rendezvous gRPC port: %s",bound_port)
    try: server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping PROJECTX RendezvousService..."); server.stop(grace=5); logger.info("PROJECTX RendezvousService stopped.")

if __name__=="__main__": serve()
