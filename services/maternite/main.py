from concurrent import futures
import logging,grpc
from maternite.v1 import maternite_pb2_grpc
from services.maternite.config import MATERNITE_GRPC_HOST,MATERNITE_GRPC_PORT
from services.maternite.service import MaterniteService
logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger=logging.getLogger('projectx.maternite')
def serve():
    server=grpc.server(futures.ThreadPoolExecutor(max_workers=12)); maternite_pb2_grpc.add_MaterniteServiceServicer_to_server(MaterniteService(),server)
    address=f'{MATERNITE_GRPC_HOST}:{MATERNITE_GRPC_PORT}'; port=server.add_insecure_port(address)
    if port==0: raise RuntimeError(f'Unable to bind MaterniteService to {address}')
    server.start(); logger.info('PROJECTX MaterniteService started on %s',address); logger.info('Maternite gRPC port: %s',port)
    try: server.wait_for_termination()
    except KeyboardInterrupt: logger.info('Stopping PROJECTX MaterniteService...'); server.stop(grace=5); logger.info('PROJECTX MaterniteService stopped.')
if __name__=='__main__': serve()
