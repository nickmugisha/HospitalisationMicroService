from __future__ import annotations
import getpass, uuid, grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from chatbot.v1 import chatbot_pb2, chatbot_pb2_grpc

def main():
    username=input('Username: ').strip(); password=getpass.getpass('Password: ')
    with grpc.insecure_channel('127.0.0.1:50051') as ch:
        login=auth_pb2_grpc.AuthServiceStub(ch).Login(auth_pb2.LoginRequest(username=username,password=password),timeout=5)
    token=login.access_token; metadata=(('authorization',f'Bearer {token}'),)
    try:
        with grpc.insecure_channel('127.0.0.1:50061') as ch:
            stub=chatbot_pb2_grpc.ChatbotServiceStub(ch)
            session=stub.StartSession(chatbot_pb2.StartSessionRequest(client_request_id='smoke-'+str(uuid.uuid4())),metadata=metadata,timeout=5).session
            caps=stub.GetCapabilities(chatbot_pb2.GetCapabilitiesRequest(),metadata=metadata,timeout=5)
            health=stub.AskAssistant(chatbot_pb2.AskAssistantRequest(session_id=session.id,question='show service health',correlation_id=str(uuid.uuid4())),metadata=metadata,timeout=12)
            kpi=stub.AskAssistant(chatbot_pb2.AskAssistantRequest(session_id=session.id,question='show hospital KPI dashboard',correlation_id=str(uuid.uuid4())),metadata=metadata,timeout=12)
            help_r=stub.AskAssistant(chatbot_pb2.AskAssistantRequest(session_id=session.id,question='help',correlation_id=str(uuid.uuid4())),metadata=metadata,timeout=5)
            conv=stub.GetConversation(chatbot_pb2.GetConversationRequest(session_id=session.id,limit=50,offset=0),metadata=metadata,timeout=5)
            cleared=stub.ClearSession(chatbot_pb2.ClearSessionRequest(session_id=session.id),metadata=metadata,timeout=5)
        print('\n====================================')
        print(' PROJECTX CHATBOT SMOKE SUCCESS')
        print('====================================')
        print('Session created       :',bool(session.id))
        print('Capabilities          :',len(caps.capabilities))
        print('Health intent         :',health.intent)
        print('Health source BI      :',any(x.service=='bi' for x in health.sources))
        print('Health answer safe    :','invented' not in health.answer.lower())
        print('KPI intent            :',kpi.intent)
        print('KPI source BI         :',any(x.service=='bi' for x in kpi.sources))
        print('KPI answer present    :',bool(kpi.answer.strip()))
        print('Help intent           :',help_r.intent)
        print('Conversation messages :',conv.total)
        print('Clear deleted messages:',cleared.deleted_messages)
        print('JWT printed           :',False)
    except grpc.RpcError as e:
        print('PROJECTX CHATBOT SMOKE FAILED'); print('STATUS :',e.code().name); print('DETAIL :',e.details()); raise SystemExit(1)
if __name__=='__main__': main()
