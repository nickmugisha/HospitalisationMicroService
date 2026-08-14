from __future__ import annotations
import logging
from concurrent import futures
import grpc
from auth.v1 import auth_pb2_grpc
from services.auth.config import AUTH_GRPC_HOST, AUTH_GRPC_PORT
from services.auth.runtime_service import RuntimeAuthService
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger=logging.getLogger('projectx.auth')
def serve() -> None:
    server=grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(RuntimeAuthService(),server)
    address=f'{AUTH_GRPC_HOST}:{AUTH_GRPC_PORT}'; bound_port=server.add_insecure_port(address)
    if bound_port==0: raise RuntimeError(f'Unable to bind AuthService to {address}')
    server.start(); logger.info('PROJECTX AuthService started on %s',address); logger.info('Auth gRPC port: %s',bound_port)
    try: server.wait_for_termination()
    except KeyboardInterrupt: logger.info('Stopping PROJECTX AuthService...'); server.stop(grace=5); logger.info('PROJECTX AuthService stopped.')
if __name__=='__main__': serve()
