from __future__ import annotations
import logging
from concurrent import futures
import grpc
from hr.v1 import hr_pb2_grpc
from services.hr.config import HR_GRPC_HOST, HR_GRPC_PORT
from services.hr.service import HRService

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("projectx.hr")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    hr_pb2_grpc.add_HRServiceServicer_to_server(HRService(), server)
    address = f"{HR_GRPC_HOST}:{HR_GRPC_PORT}"
    bound = server.add_insecure_port(address)
    if bound == 0: raise RuntimeError(f"Unable to bind HRService to {address}")
    server.start(); logger.info("PROJECTX HRService started on %s", address)
    try: server.wait_for_termination()
    except KeyboardInterrupt: server.stop(grace=5)

if __name__ == "__main__": serve()
