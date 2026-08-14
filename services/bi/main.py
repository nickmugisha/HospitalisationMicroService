from concurrent import futures
import logging,grpc
from bi.v1 import bi_pb2_grpc
from services.bi.config import BI_GRPC_HOST,BI_GRPC_PORT
from services.bi.service import BIService
logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger=logging.getLogger('projectx.bi')
def serve():
    server=grpc.server(futures.ThreadPoolExecutor(max_workers=16)); bi_pb2_grpc.add_BIServiceServicer_to_server(BIService(),server)
    address=f'{BI_GRPC_HOST}:{BI_GRPC_PORT}'; port=server.add_insecure_port(address)
    if port==0: raise RuntimeError(f'Unable to bind BIService to {address}')
    server.start(); logger.info('PROJECTX BIService started on %s',address); logger.info('BI gRPC port: %s',port)
    try: server.wait_for_termination()
    except KeyboardInterrupt: logger.info('Stopping PROJECTX BIService...'); server.stop(grace=5); logger.info('PROJECTX BIService stopped.')
if __name__=='__main__': serve()
