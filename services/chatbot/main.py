from concurrent import futures
import logging, grpc
from chatbot.v1 import chatbot_pb2_grpc
from services.chatbot.config import CHATBOT_GRPC_HOST, CHATBOT_GRPC_PORT
from services.chatbot.service import ChatbotService
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger=logging.getLogger('projectx.chatbot')
def serve():
    server=grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    chatbot_pb2_grpc.add_ChatbotServiceServicer_to_server(ChatbotService(),server)
    address=f'{CHATBOT_GRPC_HOST}:{CHATBOT_GRPC_PORT}'; port=server.add_insecure_port(address)
    if port==0: raise RuntimeError(f'Unable to bind ChatbotService to {address}')
    server.start(); logger.info('PROJECTX ChatbotService started on %s',address); logger.info('Chatbot gRPC port: %s',port)
    try: server.wait_for_termination()
    except KeyboardInterrupt: logger.info('Stopping PROJECTX ChatbotService...'); server.stop(grace=5); logger.info('PROJECTX ChatbotService stopped.')
if __name__=='__main__': serve()
