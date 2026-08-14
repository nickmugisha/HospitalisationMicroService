from __future__ import annotations

import logging, re, uuid
from datetime import datetime, timezone, timedelta
import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import delete, func, select, text

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from bi.v1 import bi_pb2, bi_pb2_grpc
from billing.v1 import billing_pb2, billing_pb2_grpc
from chatbot.v1 import chatbot_pb2, chatbot_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc
from rendezvous.v1 import rendezvous_pb2, rendezvous_pb2_grpc

from database.chatbot_session import ChatbotSessionLocal, engine
from services.chatbot.config import (
    ACCUEIL_GRPC_TARGET, AUTH_GRPC_TARGET, BILLING_GRPC_TARGET, BI_GRPC_TARGET,
    HOSPITALISATION_GRPC_TARGET, PHARMACIE_GRPC_TARGET, RENDEZVOUS_GRPC_TARGET,
    SERVICE_VERSION,
)
from services.chatbot.models import ChatMessage, ChatSession, ToolCall

logger=logging.getLogger('projectx.chatbot.service')

def now_utc(): return datetime.now(timezone.utc)
def ts(value=None):
    out=Timestamp(); v=value or now_utc()
    if v.tzinfo is None: v=v.replace(tzinfo=timezone.utc)
    out.FromDatetime(v.astimezone(timezone.utc)); return out

def build_health(status,message):
    return build_health_response_compat("chatbot", status, message, SERVICE_VERSION)

def bearer(context):
    for item in context.invocation_metadata():
        if item.key.lower()=='authorization' and item.value.strip():
            value=item.value.strip()
            if value.lower().startswith('bearer '): return value[7:].strip()
    context.abort(grpc.StatusCode.UNAUTHENTICATED,'Missing Bearer authorization metadata.')

def auth_user(context):
    token=bearer(context)
    try:
        with grpc.insecure_channel(AUTH_GRPC_TARGET) as ch:
            r=auth_pb2_grpc.AuthServiceStub(ch).ValidateToken(auth_pb2.ValidateTokenRequest(access_token=token),timeout=3)
    except grpc.RpcError as e:
        context.abort(grpc.StatusCode.UNAVAILABLE,f'Authentication service unavailable: {e.code().name}')
    if not r.valid: context.abort(grpc.StatusCode.UNAUTHENTICATED,'Invalid or expired access token.')
    if 'chatbot.ask' not in set(r.user.permissions): context.abort(grpc.StatusCode.PERMISSION_DENIED,'Missing permission: chatbot.ask')
    return r.user, token

def require_intent(user, permission, context):
    if permission and permission not in set(user.permissions):
        context.abort(grpc.StatusCode.PERMISSION_DENIED,f'Missing permission: {permission}')

def md(token): return (('authorization',f'Bearer {token}'),)

def session_proto(s): return chatbot_pb2.ChatSession(id=s.id,user_id=s.user_id,started_at=ts(s.started_at),updated_at=ts(s.updated_at))
def message_proto(m):
    role=chatbot_pb2.MESSAGE_ROLE_USER if m.role=='USER' else chatbot_pb2.MESSAGE_ROLE_ASSISTANT
    return chatbot_pb2.ChatMessage(id=m.id,session_id=m.session_id,role=role,content=m.content,created_at=ts(m.created_at))

def source(service,rpc,corr,success,message):
    return chatbot_pb2.Source(service=service,rpc=rpc,correlation_id=corr,success=success,message=message,checked_at=ts())

def identify(question):
    q=question.lower()
    checks=[
        ('service_health',0.98,['service health','health service','status service','service status','services online','services offline','santé des services','etat des services','état des services']),
        ('kpi',0.95,['kpi','dashboard','statistics','statistique','indicateur','indicators','hospital stats','résumé hôpital']),
        ('beds',0.95,['bed','beds','lit','lits','chambre disponible','available bed']),
        ('stock',0.95,['stock','medicine','medicament','médicament','pharmacy','pharmacie']),
        ('agenda',0.93,['agenda','appointment','appointments','rendez-vous','rendezvous','rdv']),
        ('payment',0.93,['payment','paiement','billing','facture','invoice','balance','solde']),
        ('patient',0.90,['patient','pat-']),
    ]
    for name,conf,words in checks:
        if any(w in q for w in words): return name,conf
    return 'help',0.55

CAPS=[
 ('patient','Rechercher une identité patient via Accueil.','accueil.patient.read',['patient PAT-20260813-XXXX','find patient Ndayizeye']),
 ('beds','Afficher la disponibilité des lits.','hospitalisation.read',['lits disponibles','available beds']),
 ('stock','Rechercher un médicament et son stock.','pharmacy.stock.read',['stock paracetamol','medicine amoxicillin']),
 ('agenda','Consulter les rendez-vous récents/à venir.','appointment.read',['agenda','rendez-vous cette semaine']),
 ('payment','Consulter le solde d’un patient.','billing.read',['solde PAT-...','patient balance PAT-...']),
 ('kpi','Afficher les KPI consolidés via BI.','bi.dashboard.read',['KPI hôpital','dashboard']),
 ('service_health','Afficher l’état des microservices via BI.','bi.dashboard.read',['service health','état des services']),
 ('help','Afficher les capacités autorisées.','chatbot.ask',['aide','help']),
]

class ChatbotService(chatbot_pb2_grpc.ChatbotServiceServicer):
    def _owned_session(self,s,user,context):
        row=s.get(ChatSession,user and getattr(user,'_session_id',None)) if False else None

    def _get_session(self,s,session_id,user_id,context):
        row=s.get(ChatSession,session_id)
        if row is None: context.abort(grpc.StatusCode.NOT_FOUND,'Chat session not found.')
        if row.user_id!=user_id: context.abort(grpc.StatusCode.PERMISSION_DENIED,'This session belongs to another user.')
        return row

    def _record_tool(self,s,session_id,message_id,service_name,rpc,corr,outcome,detail):
        s.add(ToolCall(session_id=session_id,message_id=message_id,service=service_name,rpc=rpc,correlation_id=corr,outcome=outcome,detail=detail))

    def StartSession(self,request,context):
        user,_=auth_user(context); s=ChatbotSessionLocal()
        try:
            key=request.client_request_id.strip()
            if key:
                existing=s.scalar(select(ChatSession).where(ChatSession.client_request_id==key))
                if existing:
                    if existing.user_id!=user.id: context.abort(grpc.StatusCode.ALREADY_EXISTS,'client_request_id already belongs to another user.')
                    return chatbot_pb2.SessionResponse(session=session_proto(existing))
            row=ChatSession(user_id=user.id,client_request_id=key or None); s.add(row); s.commit()
            return chatbot_pb2.SessionResponse(session=session_proto(row))
        finally: s.close()

    def GetCapabilities(self,request,context):
        user,_=auth_user(context); perms=set(user.permissions); out=[]
        for intent,desc,perm,examples in CAPS:
            if perm=='chatbot.ask' or perm in perms:
                out.append(chatbot_pb2.Capability(intent=intent,description=desc,required_permission=perm,examples=examples))
        return chatbot_pb2.GetCapabilitiesResponse(capabilities=out)

    def AskAssistant(self,request,context):
        user,token=auth_user(context); q=request.question.strip()
        if not q: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'Question is required.')
        corr=request.correlation_id.strip() or str(uuid.uuid4())
        intent,confidence=identify(q)
        perm={c[0]:c[2] for c in CAPS}.get(intent,'chatbot.ask'); require_intent(user,perm,context)
        s=ChatbotSessionLocal()
        try:
            sess=self._get_session(s,request.session_id.strip(),user.id,context)
            user_msg=ChatMessage(session_id=sess.id,role='USER',content=q); s.add(user_msg); s.flush()
            answer=''; sources=[]
            try:
                if intent=='service_health':
                    with grpc.insecure_channel(BI_GRPC_TARGET) as ch:
                        r=bi_pb2_grpc.BIServiceStub(ch).GetServiceHealth(bi_pb2.ServiceHealthRequest(include_offline=True),metadata=md(token),timeout=10)
                    online=[x.service for x in r.services if x.status==bi_pb2.SERVICE_STATUS_ONLINE]
                    degraded=[x.service for x in r.services if x.status==bi_pb2.SERVICE_STATUS_DEGRADED]
                    offline=[x.service for x in r.services if x.status==bi_pb2.SERVICE_STATUS_OFFLINE]
                    answer=f"Services online: {len(online)}. Degraded: {', '.join(degraded) if degraded else 'none'}. Offline: {', '.join(offline) if offline else 'none'}."
                    sources.append(source('bi','GetServiceHealth',corr,True,'Service health obtained from BI.'))
                    self._record_tool(s,sess.id,user_msg.id,'bi','GetServiceHealth',corr,'OK',answer)
                elif intent=='kpi':
                    with grpc.insecure_channel(BI_GRPC_TARGET) as ch:
                        r=bi_pb2_grpc.BIServiceStub(ch).GetDashboard(bi_pb2.DashboardRequest(),metadata=md(token),timeout=10)
                    wanted={'patients.total','consultations.total','admissions.active','revenue.paid','revenue.balance','beds.available','stock.units','appointments.total'}
                    vals=[f'{m.label}: {m.value} {m.unit}' for m in r.metrics if m.code in wanted]
                    quality=bi_pb2.DataQuality.Name(r.quality)
                    answer='Hospital KPI ('+quality+'): '+('; '.join(vals) if vals else 'No KPI values available.')
                    if r.warnings: answer+=' Warnings: '+' | '.join(list(r.warnings)[:3])
                    sources.append(source('bi','GetDashboard',corr,True,f'Dashboard quality: {quality}.'))
                    self._record_tool(s,sess.id,user_msg.id,'bi','GetDashboard',corr,'OK',quality)
                elif intent=='beds':
                    with grpc.insecure_channel(HOSPITALISATION_GRPC_TARGET) as ch:
                        r=hospitalisation_pb2_grpc.HospitalisationServiceStub(ch).GetBedAvailability(hospitalisation_pb2.GetBedAvailabilityRequest(available_only=True),metadata=md(token),timeout=3)
                    answer=f'Beds: {r.available} available, {r.occupied} occupied, {r.out_of_service} out of service, {r.total} total.'
                    sources.append(source('hospitalisation','GetBedAvailability',corr,True,'Bed availability obtained.'))
                    self._record_tool(s,sess.id,user_msg.id,'hospitalisation','GetBedAvailability',corr,'OK',answer)
                elif intent=='patient':
                    match=re.search(r'PAT-[A-Z0-9-]+',q,re.I)
                    with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as ch:
                        stub=accueil_pb2_grpc.AccueilServiceStub(ch)
                        if match:
                            r=stub.GetPatient(accueil_pb2.GetPatientRequest(patient_number=match.group(0).upper()),metadata=md(token),timeout=3)
                            p=r.patient; answer=f'Patient {p.patient_number}: {p.first_name} {p.last_name}, phone {p.phone or "not provided"}.'
                            rpc='GetPatient'
                        else:
                            cleaned=re.sub(r'(?i)patient|find|search|chercher|rechercher',' ',q).strip()
                            r=stub.SearchPatients(accueil_pb2.SearchPatientsRequest(query=cleaned,limit=5,offset=0),metadata=md(token),timeout=3)
                            answer=f'{r.total} patient(s) found. '+', '.join(f'{p.patient_number} {p.first_name} {p.last_name}' for p in r.patients[:5])
                            rpc='SearchPatients'
                    sources.append(source('accueil',rpc,corr,True,'Patient data obtained from Accueil.'))
                    self._record_tool(s,sess.id,user_msg.id,'accueil',rpc,corr,'OK',answer)
                elif intent=='stock':
                    cleaned=re.sub(r'(?i)stock|medicine|medicament|médicament|pharmacy|pharmacie|of|de|du|des',' ',q).strip()
                    with grpc.insecure_channel(PHARMACIE_GRPC_TARGET) as ch:
                        stub=pharmacie_pb2_grpc.PharmacieServiceStub(ch)
                        r=stub.SearchMedicines(pharmacie_pb2.SearchMedicinesRequest(query=cleaned,active_only=True,limit=5,offset=0),metadata=md(token),timeout=3)
                        if not r.medicines: answer='No active medicine matched the request.'
                        else:
                            med=r.medicines[0]
                            stock=stub.GetStock(pharmacie_pb2.GetStockRequest(medicine_ref=med.code),metadata=md(token),timeout=3).stock
                            answer=f'{med.name} {med.strength}: {stock.total_available} {med.unit}(s) available across {len(stock.batches)} batch(es).'
                    sources.append(source('pharmacie','SearchMedicines/GetStock',corr,True,'Stock obtained from Pharmacie.'))
                    self._record_tool(s,sess.id,user_msg.id,'pharmacie','SearchMedicines/GetStock',corr,'OK',answer)
                elif intent=='agenda':
                    start=Timestamp(); start.FromDatetime(now_utc()); end=Timestamp(); end.FromDatetime(now_utc()+timedelta(days=7))
                    provider=''; m=re.search(r'DOC-[A-Z0-9_-]+',q,re.I)
                    if m: provider=m.group(0).upper()
                    with grpc.insecure_channel(RENDEZVOUS_GRPC_TARGET) as ch:
                        r=rendezvous_pb2_grpc.RendezvousServiceStub(ch).ListAgenda(rendezvous_pb2.ListAgendaRequest(provider_id=provider,from_at=start,to_at=end,limit=20,offset=0),metadata=md(token),timeout=3)
                    answer=f'{r.total} appointment(s) in the next 7 days'+(f' for {provider}' if provider else '')+'.'
                    sources.append(source('rendezvous','ListAgenda',corr,True,'Agenda obtained from Rendez-vous.'))
                    self._record_tool(s,sess.id,user_msg.id,'rendezvous','ListAgenda',corr,'OK',answer)
                elif intent=='payment':
                    match=re.search(r'PAT-[A-Z0-9-]+',q,re.I)
                    if not match:
                        answer='Please include a patient number such as PAT-20260813-XXXX so I can retrieve the balance securely.'
                    else:
                        with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as ch:
                            p=accueil_pb2_grpc.AccueilServiceStub(ch).GetPatient(accueil_pb2.GetPatientRequest(patient_number=match.group(0).upper()),metadata=md(token),timeout=3).patient
                        with grpc.insecure_channel(BILLING_GRPC_TARGET) as ch:
                            r=billing_pb2_grpc.BillingServiceStub(ch).GetPatientBalance(billing_pb2.GetPatientBalanceRequest(patient_id=p.id),metadata=md(token),timeout=3)
                        currency='BIF'; f=r.balance.DESCRIPTOR.fields_by_name
                        if 'currency_code' in f: currency=r.balance.currency_code or 'BIF'
                        elif 'currency' in f: currency=r.balance.currency or 'BIF'
                        answer=f'Patient {p.patient_number} balance: {r.balance.amount_minor} {currency}; total charges {r.total_charges.amount_minor}, paid {r.total_paid.amount_minor}.'
                        sources.append(source('accueil','GetPatient',corr,True,'Patient identity resolved.'))
                        sources.append(source('billing','GetPatientBalance',corr,True,'Financial balance obtained.'))
                        self._record_tool(s,sess.id,user_msg.id,'billing','GetPatientBalance',corr,'OK',answer)
                else:
                    allowed=[c[0] for c in CAPS if c[2]=='chatbot.ask' or c[2] in set(user.permissions)]
                    answer='I can help with: '+', '.join(allowed)+'. I use hospital microservices and do not diagnose or invent unavailable results.'
            except grpc.RpcError as e:
                svc={'service_health':'bi','kpi':'bi','beds':'hospitalisation','patient':'accueil','stock':'pharmacie','agenda':'rendezvous','payment':'billing'}.get(intent,'unknown')
                answer=f'I could not complete this request because {svc} returned {e.code().name}. No success was invented.'
                sources.append(source(svc,'downstream',corr,False,f'{e.code().name}: {e.details()}'))
                self._record_tool(s,sess.id,user_msg.id,svc,'downstream',corr,f'ERROR:{e.code().name}',e.details())
            assistant_msg=ChatMessage(session_id=sess.id,role='ASSISTANT',content=answer); s.add(assistant_msg); sess.updated_at=datetime.now(timezone.utc).replace(tzinfo=None); s.commit()
            logger.info('rpc=AskAssistant peer=%s actor=%s session=%s intent=%s correlation_id=%s outcome=OK',context.peer(),user.id,sess.id,intent,corr)
            return chatbot_pb2.AskAssistantResponse(session=session_proto(sess),answer_message=message_proto(assistant_msg),answer=answer,intent=intent,confidence=confidence,sources=sources)
        finally: s.close()

    def GetConversation(self,request,context):
        user,_=auth_user(context); s=ChatbotSessionLocal()
        try:
            sess=self._get_session(s,request.session_id.strip(),user.id,context); limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
            total=s.scalar(select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id==sess.id)) or 0
            rows=s.scalars(select(ChatMessage).where(ChatMessage.session_id==sess.id).order_by(ChatMessage.created_at.asc()).limit(limit).offset(offset)).all()
            return chatbot_pb2.GetConversationResponse(session=session_proto(sess),messages=[message_proto(x) for x in rows],total=int(total))
        finally: s.close()

    def ClearSession(self,request,context):
        user,_=auth_user(context); s=ChatbotSessionLocal()
        try:
            sess=self._get_session(s,request.session_id.strip(),user.id,context)
            tools=s.scalar(select(func.count()).select_from(ToolCall).where(ToolCall.session_id==sess.id)) or 0
            msgs=s.scalar(select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id==sess.id)) or 0
            s.execute(delete(ToolCall).where(ToolCall.session_id==sess.id)); s.execute(delete(ChatMessage).where(ChatMessage.session_id==sess.id)); sess.updated_at=datetime.now(timezone.utc).replace(tzinfo=None); s.commit()
            return chatbot_pb2.ClearSessionResponse(session_id=sess.id,deleted_messages=int(msgs),deleted_tool_calls=int(tools))
        finally: s.close()

    def HealthCheck(self,request,context):
        try:
            with engine.connect() as c: c.execute(text('SELECT 1'))
            return build_health('ONLINE','Chatbot service and MySQL are available.')
        except Exception:
            logger.exception('Chatbot HealthCheck degraded')
            return build_health('DEGRADED','Chatbot service is running but MySQL is unavailable.')
