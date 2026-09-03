from __future__ import annotations
import logging,uuid
from datetime import datetime,timezone
import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import func,select,text
from sqlalchemy.exc import IntegrityError,SQLAlchemyError
from accueil.v1 import accueil_pb2,accueil_pb2_grpc
from billing.v1 import billing_pb2,billing_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from services.common.notifications import list_role_recipients, send_system_notification
from maternite.v1 import maternite_pb2,maternite_pb2_grpc
from database.maternite_session import MaterniteSessionLocal,engine
from services.common.auth_guard import require_permission
from services.maternite.config import AUTH_GRPC_TARGET, ACCUEIL_GRPC_TARGET,BILLING_GRPC_TARGET,MATERNITE_CURRENCY_CODE,MATERNITE_DELIVERY_CHARGE_MINOR,SERVICE_VERSION
from services.maternite.models import BillingOutbox,Delivery,LaborEvent,Newborn,Pregnancy,PrenatalVisit
from services.maternite.repository import get_active_by_patient,get_delivery,get_latest_by_patient,get_pregnancy
logger=logging.getLogger('projectx.maternite.service')

PREG_PROTO_TO_DB={maternite_pb2.PREGNANCY_STATUS_ACTIVE:'ACTIVE',maternite_pb2.PREGNANCY_STATUS_IN_LABOR:'IN_LABOR',maternite_pb2.PREGNANCY_STATUS_DELIVERED:'DELIVERED',maternite_pb2.PREGNANCY_STATUS_CLOSED:'CLOSED'}
PREG_DB_TO_PROTO={'ACTIVE':maternite_pb2.PREGNANCY_STATUS_ACTIVE,'IN_LABOR':maternite_pb2.PREGNANCY_STATUS_IN_LABOR,'DELIVERED':maternite_pb2.PREGNANCY_STATUS_DELIVERED,'CLOSED':maternite_pb2.PREGNANCY_STATUS_CLOSED}
RISK_PROTO_TO_DB={maternite_pb2.RISK_LEVEL_LOW:'LOW',maternite_pb2.RISK_LEVEL_MODERATE:'MODERATE',maternite_pb2.RISK_LEVEL_HIGH:'HIGH',maternite_pb2.RISK_LEVEL_CRITICAL:'CRITICAL'}
RISK_DB_TO_PROTO={v:k for k,v in RISK_PROTO_TO_DB.items()}
LABOR_PROTO_TO_DB={maternite_pb2.LABOR_EVENT_TYPE_ADMISSION:'ADMISSION',maternite_pb2.LABOR_EVENT_TYPE_CERVICAL_EXAM:'CERVICAL_EXAM',maternite_pb2.LABOR_EVENT_TYPE_CONTRACTION:'CONTRACTION',maternite_pb2.LABOR_EVENT_TYPE_FETAL_HEART:'FETAL_HEART',maternite_pb2.LABOR_EVENT_TYPE_NOTE:'NOTE',maternite_pb2.LABOR_EVENT_TYPE_OTHER:'OTHER'}
LABOR_DB_TO_PROTO={v:k for k,v in LABOR_PROTO_TO_DB.items()}
MODE_PROTO_TO_DB={maternite_pb2.DELIVERY_MODE_VAGINAL:'VAGINAL',maternite_pb2.DELIVERY_MODE_CESAREAN:'CESAREAN',maternite_pb2.DELIVERY_MODE_ASSISTED:'ASSISTED',maternite_pb2.DELIVERY_MODE_OTHER:'OTHER'}
MODE_DB_TO_PROTO={v:k for k,v in MODE_PROTO_TO_DB.items()}
OUTCOME_PROTO_TO_DB={maternite_pb2.DELIVERY_OUTCOME_LIVE_BIRTH:'LIVE_BIRTH',maternite_pb2.DELIVERY_OUTCOME_STILLBIRTH:'STILLBIRTH',maternite_pb2.DELIVERY_OUTCOME_OTHER:'OTHER'}
OUTCOME_DB_TO_PROTO={v:k for k,v in OUTCOME_PROTO_TO_DB.items()}
SEX_PROTO_TO_DB={maternite_pb2.NEWBORN_SEX_MALE:'MALE',maternite_pb2.NEWBORN_SEX_FEMALE:'FEMALE',maternite_pb2.NEWBORN_SEX_INTERSEX:'INTERSEX',maternite_pb2.NEWBORN_SEX_UNKNOWN:'UNKNOWN'}
SEX_DB_TO_PROTO={v:k for k,v in SEX_PROTO_TO_DB.items()}
NEWBORN_PROTO_TO_DB={maternite_pb2.NEWBORN_STATUS_STABLE:'STABLE',maternite_pb2.NEWBORN_STATUS_OBSERVATION:'OBSERVATION',maternite_pb2.NEWBORN_STATUS_CRITICAL:'CRITICAL',maternite_pb2.NEWBORN_STATUS_DECEASED:'DECEASED'}
NEWBORN_DB_TO_PROTO={v:k for k,v in NEWBORN_PROTO_TO_DB.items()}
BILLING_DB_TO_PROTO={'PENDING_DELIVERY':maternite_pb2.BILLING_CHARGE_STATUS_PENDING_DELIVERY,'DELIVERED':maternite_pb2.BILLING_CHARGE_STATUS_DELIVERED,'FAILED':maternite_pb2.BILLING_CHARGE_STATUS_FAILED}

def utc_now(): return datetime.now(timezone.utc).replace(tzinfo=None)
def num(prefix): return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
def ts(value):
    out=Timestamp()
    if value is not None:
        aware=value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc); out.FromDatetime(aware)
    return out
def from_ts(value,default=None):
    if value is None or (value.seconds==0 and value.nanos==0): return default
    return value.ToDatetime(tzinfo=timezone.utc).replace(tzinfo=None)
def md(context):
    for x in context.invocation_metadata():
        if x.key.lower()=='authorization' and x.value.strip(): return (('authorization',x.value.strip()),)
    return tuple()
def valid_date(value,field,context):
    if not value: return None
    try: datetime.strptime(value,'%Y-%m-%d')
    except ValueError: context.abort(grpc.StatusCode.INVALID_ARGUMENT,f'{field} must use YYYY-MM-DD.')
    return value

def patient_exists(context,patient_id):
    try:
        with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as ch:
            return accueil_pb2_grpc.AccueilServiceStub(ch).GetPatient(accueil_pb2.GetPatientRequest(patient_id=patient_id),metadata=md(context),timeout=3).patient
    except grpc.RpcError as e:
        if e.code()==grpc.StatusCode.NOT_FOUND: context.abort(grpc.StatusCode.NOT_FOUND,'Mother patient not found in Accueil.')
        if e.code() in (grpc.StatusCode.UNAUTHENTICATED,grpc.StatusCode.PERMISSION_DENIED): context.abort(e.code(),e.details() or 'Patient validation denied.')
        context.abort(grpc.StatusCode.UNAVAILABLE,f'Accueil service unavailable: {e.code().name}')

def pregnancy_proto(x):
    return maternite_pb2.Pregnancy(id=x.id,pregnancy_number=x.pregnancy_number,patient_id=x.patient_id,consultation_id=x.consultation_id or '',gravida=x.gravida,para=x.para,lmp_date=x.lmp_date or '',edd=x.edd or '',risk_level=RISK_DB_TO_PROTO.get(x.risk_level,maternite_pb2.RISK_LEVEL_UNSPECIFIED),risk_factors=x.risk_factors or '',referral_reason=x.referral_reason or '',status=PREG_DB_TO_PROTO.get(x.status,maternite_pb2.PREGNANCY_STATUS_UNSPECIFIED),correlation_id=x.correlation_id,created_by=x.created_by,created_at=ts(x.created_at),updated_at=ts(x.updated_at),labor_admitted_at=ts(x.labor_admitted_at))
def visit_proto(x): return maternite_pb2.PrenatalVisit(id=x.id,pregnancy_id=x.pregnancy_id,visit_at=ts(x.visit_at),gestational_age_weeks=x.gestational_age_weeks,observations=x.observations or '',systolic_bp=x.systolic_bp,diastolic_bp=x.diastolic_bp,weight_kg=x.weight_kg_x100/100.0,fetal_heart_bpm=x.fetal_heart_bpm,recorded_by=x.recorded_by)
def labor_proto(x): return maternite_pb2.LaborEvent(id=x.id,pregnancy_id=x.pregnancy_id,event_type=LABOR_DB_TO_PROTO.get(x.event_type,maternite_pb2.LABOR_EVENT_TYPE_UNSPECIFIED),event_at=ts(x.event_at),description=x.description or '',cervical_dilation_cm=x.cervical_dilation_x10/10.0,fetal_heart_bpm=x.fetal_heart_bpm,recorded_by=x.recorded_by)
def delivery_proto(x): return maternite_pb2.Delivery(id=x.id,delivery_number=x.delivery_number,pregnancy_id=x.pregnancy_id,patient_id=x.patient_id,delivered_at=ts(x.delivered_at),mode=MODE_DB_TO_PROTO.get(x.mode,maternite_pb2.DELIVERY_MODE_UNSPECIFIED),outcome=OUTCOME_DB_TO_PROTO.get(x.outcome,maternite_pb2.DELIVERY_OUTCOME_UNSPECIFIED),complications=x.complications or '',attendant_id=x.attendant_id,billing_status=BILLING_DB_TO_PROTO.get(x.billing_status,maternite_pb2.BILLING_CHARGE_STATUS_UNSPECIFIED),billing_charge_id=x.billing_charge_id or '',billed_amount_minor=x.billed_amount_minor,currency_code=x.currency_code,created_at=ts(x.created_at))
def newborn_proto(x): return maternite_pb2.Newborn(id=x.id,newborn_number=x.newborn_number,delivery_id=x.delivery_id,mother_patient_id=x.mother_patient_id,sex=SEX_DB_TO_PROTO.get(x.sex,maternite_pb2.NEWBORN_SEX_UNSPECIFIED),weight_g=x.weight_g,apgar_1=x.apgar_1,apgar_5=x.apgar_5,status=NEWBORN_DB_TO_PROTO.get(x.status,maternite_pb2.NEWBORN_STATUS_UNSPECIFIED),registered_by=x.registered_by,created_at=ts(x.created_at))
def record_proto(x):
    delivery=x.deliveries[-1] if x.deliveries else None
    payload={
        'pregnancy':pregnancy_proto(x),
        'prenatal_visits':[visit_proto(v) for v in x.prenatal_visits],
        'labor_events':[labor_proto(e) for e in x.labor_events],
        'newborns':[newborn_proto(n) for n in (delivery.newborns if delivery else [])],
    }
    if delivery is not None:
        payload['delivery']=delivery_proto(delivery)
    return maternite_pb2.MaternityRecord(**payload)
def health(status,message):
    return build_health_response_compat("maternite", status, message, SERVICE_VERSION)

def try_billing(session,delivery,context):
    outbox=session.scalar(select(BillingOutbox).where(BillingOutbox.delivery_id==delivery.id))
    if outbox is None:
        outbox=BillingOutbox(delivery_id=delivery.id,patient_id=delivery.patient_id,amount_minor=MATERNITE_DELIVERY_CHARGE_MINOR,currency_code=MATERNITE_CURRENCY_CODE,correlation_id=str(uuid.uuid4()),idempotency_key=f'maternity-delivery:{delivery.id}')
        session.add(outbox); session.commit(); session.refresh(outbox)
    if outbox.status=='DELIVERED': return
    try:
        with grpc.insecure_channel(BILLING_GRPC_TARGET) as ch:
            response=billing_pb2_grpc.BillingServiceStub(ch).CreateCharge(billing_pb2.CreateChargeRequest(source_type='MATERNITY_DELIVERY',source_id=delivery.id,patient_id=delivery.patient_id,amount_minor=outbox.amount_minor,currency_code=outbox.currency_code,description=f'Accouchement {delivery.delivery_number}',idempotency_key=outbox.idempotency_key,correlation_id=outbox.correlation_id),metadata=md(context),timeout=5)
        outbox.status='DELIVERED'; outbox.billing_charge_id=response.charge.id; outbox.last_error=None
        delivery.billing_status='DELIVERED'; delivery.billing_charge_id=response.charge.id; delivery.billed_amount_minor=outbox.amount_minor; delivery.currency_code=outbox.currency_code
        session.commit()
    except grpc.RpcError as e:
        if e.code() in (grpc.StatusCode.UNAVAILABLE,grpc.StatusCode.DEADLINE_EXCEEDED):
            outbox.status='PENDING_DELIVERY'; outbox.last_error=e.code().name; delivery.billing_status='PENDING_DELIVERY'; session.commit()
        else:
            outbox.status='FAILED'; outbox.last_error=(e.details() or e.code().name)[:1000]; delivery.billing_status='FAILED'; session.commit()


def notify_maternity_role(notification_type: str, title: str, body: str) -> None:
    for recipient in sorted(set(list_role_recipients(auth_target=AUTH_GRPC_TARGET, role_code="SAGE_FEMME"))):
        send_system_notification(auth_target=AUTH_GRPC_TARGET, recipient_id=recipient, notification_type=notification_type, title=title, body=body, source_service="maternite")

class MaterniteService(maternite_pb2_grpc.MaterniteServiceServicer):
    def CreateMaternityCase(self,request,context):
        actor=require_permission(context,'maternity.case.create')
        patient_id=request.patient_id.strip(); idem=request.idempotency_key.strip() or request.correlation_id.strip() or str(uuid.uuid4())
        if not patient_id: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'patient_id is required.')
        if request.gravida<0 or request.para<0 or request.para>request.gravida: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'gravida/para values are invalid.')
        patient_exists(context,patient_id)
        session=MaterniteSessionLocal()
        try:
            existing=session.scalar(select(Pregnancy).where(Pregnancy.idempotency_key==idem))
            if existing: return maternite_pb2.MaternityRecordResponse(record=record_proto(get_pregnancy(session,existing.id)),replayed=True)
            active=get_active_by_patient(session,patient_id)
            if active: context.abort(grpc.StatusCode.FAILED_PRECONDITION,'Patient already has an active maternity case.')
            risk=RISK_PROTO_TO_DB.get(request.risk_level,'LOW')
            item=Pregnancy(pregnancy_number=num('MAT'),patient_id=patient_id,active_patient_key=patient_id,consultation_id=request.consultation_id.strip() or None,gravida=request.gravida,para=request.para,lmp_date=valid_date(request.lmp_date,'lmp_date',context),edd=valid_date(request.edd,'edd',context),risk_level=risk,risk_factors=request.risk_factors.strip() or None,referral_reason=request.referral_reason.strip() or None,correlation_id=request.correlation_id.strip() or str(uuid.uuid4()),idempotency_key=idem,created_by=actor.id)
            session.add(item); session.commit(); saved=get_pregnancy(session,item.id)
            logger.info('rpc=CreateMaternityCase peer=%s actor=%s pregnancy=%s patient=%s outcome=OK',context.peer(),actor.id,item.id,patient_id)
            return maternite_pb2.MaternityRecordResponse(record=record_proto(saved),replayed=False)
        except IntegrityError: session.rollback(); context.abort(grpc.StatusCode.FAILED_PRECONDITION,'Active maternity case already exists.')
        finally: session.close()

    def AddPrenatalVisit(self,request,context):
        actor=require_permission(context,'maternity.manage'); pid=request.pregnancy_id.strip(); idem=request.idempotency_key.strip()
        if not pid or not idem: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'pregnancy_id and idempotency_key are required.')
        if request.gestational_age_weeks<0 or request.gestational_age_weeks>45: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'gestational_age_weeks is invalid.')
        session=MaterniteSessionLocal()
        try:
            old=session.scalar(select(PrenatalVisit).where(PrenatalVisit.idempotency_key==idem))
            if old: return maternite_pb2.PrenatalVisitResponse(visit=visit_proto(old),replayed=True)
            preg=get_pregnancy(session,pid)
            if not preg: context.abort(grpc.StatusCode.NOT_FOUND,'Maternity case not found.')
            if preg.status!='ACTIVE': context.abort(grpc.StatusCode.FAILED_PRECONDITION,'Prenatal visits require an ACTIVE pregnancy.')
            v=PrenatalVisit(pregnancy_id=pid,visit_at=from_ts(request.visit_at,utc_now()),gestational_age_weeks=request.gestational_age_weeks,observations=request.observations.strip() or None,systolic_bp=request.systolic_bp,diastolic_bp=request.diastolic_bp,weight_kg_x100=round(request.weight_kg*100),fetal_heart_bpm=request.fetal_heart_bpm,recorded_by=actor.id,idempotency_key=idem)
            session.add(v); session.commit(); session.refresh(v); return maternite_pb2.PrenatalVisitResponse(visit=visit_proto(v),replayed=False)
        finally: session.close()

    def AdmitForLabor(self,request,context):
        actor=require_permission(context,'maternity.manage'); pid=request.pregnancy_id.strip(); idem=request.idempotency_key.strip()
        if not pid or not idem: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'pregnancy_id and idempotency_key are required.')
        session=MaterniteSessionLocal()
        try:
            preg=session.scalar(select(Pregnancy).where(Pregnancy.id==pid).with_for_update())
            if not preg: context.abort(grpc.StatusCode.NOT_FOUND,'Maternity case not found.')
            if preg.status=='IN_LABOR' and preg.labor_admit_key==idem: return maternite_pb2.MaternityRecordResponse(record=record_proto(get_pregnancy(session,pid)),replayed=True)
            if preg.status!='ACTIVE': context.abort(grpc.StatusCode.FAILED_PRECONDITION,'Only ACTIVE pregnancy can be admitted for labor.')
            preg.status='IN_LABOR'; preg.labor_admitted_at=from_ts(request.admitted_at,utc_now()); preg.labor_admit_key=idem; preg.updated_at=utc_now()
            session.add(LaborEvent(pregnancy_id=pid,event_type='ADMISSION',event_at=preg.labor_admitted_at,description=request.reason.strip() or 'Admission en travail',recorded_by=actor.id,idempotency_key=f'{idem}:event'))
            session.commit(); return maternite_pb2.MaternityRecordResponse(record=record_proto(get_pregnancy(session,pid)),replayed=False)
        finally: session.close()

    def RecordLaborEvent(self,request,context):
        actor=require_permission(context,'maternity.manage'); pid=request.pregnancy_id.strip(); idem=request.idempotency_key.strip(); et=LABOR_PROTO_TO_DB.get(request.event_type)
        if not pid or not idem or not et: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'pregnancy_id, event_type and idempotency_key are required.')
        if request.cervical_dilation_cm<0 or request.cervical_dilation_cm>10: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'cervical_dilation_cm is invalid.')
        session=MaterniteSessionLocal()
        try:
            old=session.scalar(select(LaborEvent).where(LaborEvent.idempotency_key==idem))
            if old: return maternite_pb2.LaborEventResponse(event=labor_proto(old),replayed=True)
            preg=get_pregnancy(session,pid)
            if not preg: context.abort(grpc.StatusCode.NOT_FOUND,'Maternity case not found.')
            if preg.status!='IN_LABOR': context.abort(grpc.StatusCode.FAILED_PRECONDITION,'Labor events require IN_LABOR status.')
            ev=LaborEvent(pregnancy_id=pid,event_type=et,event_at=from_ts(request.event_at,utc_now()),description=request.description.strip() or None,cervical_dilation_x10=round(request.cervical_dilation_cm*10),fetal_heart_bpm=request.fetal_heart_bpm,recorded_by=actor.id,idempotency_key=idem)
            session.add(ev); session.commit(); session.refresh(ev); return maternite_pb2.LaborEventResponse(event=labor_proto(ev),replayed=False)
        finally: session.close()

    def RecordDelivery(self,request,context):
        actor=require_permission(context,'maternity.manage'); pid=request.pregnancy_id.strip(); idem=request.idempotency_key.strip(); mode=MODE_PROTO_TO_DB.get(request.mode); outcome=OUTCOME_PROTO_TO_DB.get(request.outcome)
        if not pid or not idem or not mode or not outcome: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'pregnancy_id, mode, outcome and idempotency_key are required.')
        session=MaterniteSessionLocal()
        try:
            existing=session.scalar(select(Delivery).where(Delivery.idempotency_key==idem))
            if existing:
                try_billing(session,existing,context); return maternite_pb2.DeliveryResponse(delivery=delivery_proto(existing),replayed=True)
            preg=session.scalar(select(Pregnancy).where(Pregnancy.id==pid).with_for_update())
            if not preg: context.abort(grpc.StatusCode.NOT_FOUND,'Maternity case not found.')
            if preg.status!='IN_LABOR': context.abort(grpc.StatusCode.FAILED_PRECONDITION,'Delivery requires IN_LABOR status.')
            d=Delivery(delivery_number=num('DEL'),pregnancy_id=pid,patient_id=preg.patient_id,delivered_at=from_ts(request.delivered_at,utc_now()),mode=mode,outcome=outcome,complications=request.complications.strip() or None,attendant_id=actor.id,idempotency_key=idem,billing_status='PENDING_DELIVERY',billed_amount_minor=MATERNITE_DELIVERY_CHARGE_MINOR,currency_code=MATERNITE_CURRENCY_CODE)
            preg.status='DELIVERED'; preg.active_patient_key=None; preg.updated_at=utc_now(); session.add(d); session.commit(); session.refresh(d)
            try_billing(session,d,context); session.refresh(d)
            notify_maternity_role('MATERNITY_DELIVERY_RECORDED','Accouchement enregistré / Delivery recorded',f'Accouchement / delivery {d.delivery_number} enregistré. Dossier / case {pid}.')
            logger.info('rpc=RecordDelivery peer=%s actor=%s delivery=%s pregnancy=%s billing=%s outcome=OK',context.peer(),actor.id,d.id,pid,d.billing_status)
            return maternite_pb2.DeliveryResponse(delivery=delivery_proto(d),replayed=False)
        finally: session.close()

    def RegisterNewborn(self,request,context):
        actor=require_permission(context,'maternity.manage'); did=request.delivery_id.strip(); idem=request.idempotency_key.strip(); sex=SEX_PROTO_TO_DB.get(request.sex); status=NEWBORN_PROTO_TO_DB.get(request.status)
        if not did or not idem or not sex or not status: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'delivery_id, sex, status and idempotency_key are required.')
        if request.weight_g<=0 or request.apgar_1<0 or request.apgar_1>10 or request.apgar_5<0 or request.apgar_5>10: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'Newborn measurements are invalid.')
        session=MaterniteSessionLocal()
        try:
            old=session.scalar(select(Newborn).where(Newborn.idempotency_key==idem))
            if old: return maternite_pb2.NewbornResponse(newborn=newborn_proto(old),replayed=True)
            delivery=get_delivery(session,did)
            if not delivery: context.abort(grpc.StatusCode.NOT_FOUND,'Delivery not found.')
            if delivery.outcome!='LIVE_BIRTH': context.abort(grpc.StatusCode.FAILED_PRECONDITION,'Newborn can only be registered for LIVE_BIRTH delivery.')
            n=Newborn(newborn_number=num('NB'),delivery_id=did,mother_patient_id=delivery.patient_id,sex=sex,weight_g=request.weight_g,apgar_1=request.apgar_1,apgar_5=request.apgar_5,status=status,registered_by=actor.id,idempotency_key=idem)
            session.add(n); session.commit(); session.refresh(n)
            notify_maternity_role('MATERNITY_NEWBORN_REGISTERED','Nouveau-né enregistré / Newborn registered',f'Nouveau-né / newborn {n.newborn_number} enregistré pour delivery {did}.')
            return maternite_pb2.NewbornResponse(newborn=newborn_proto(n),replayed=False)
        finally: session.close()

    def GetMaternityRecord(self,request,context):
        require_permission(context,'maternity.read'); session=MaterniteSessionLocal()
        try:
            item=get_pregnancy(session,request.pregnancy_id.strip()) if request.pregnancy_id.strip() else get_latest_by_patient(session,request.patient_id.strip())
            if not item: context.abort(grpc.StatusCode.NOT_FOUND,'Maternity record not found.')
            return maternite_pb2.MaternityRecordResponse(record=record_proto(item),replayed=False)
        finally: session.close()

    def ListMaternityCases(self,request,context):
        actor=require_permission(context,'maternity.read'); limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
        session=MaterniteSessionLocal()
        try:
            filters=[]
            if request.patient_id.strip(): filters.append(Pregnancy.patient_id==request.patient_id.strip())
            if request.status != maternite_pb2.PREGNANCY_STATUS_UNSPECIFIED:
                desired=PREG_PROTO_TO_DB.get(request.status)
                if not desired: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'Invalid maternity status.')
                filters.append(Pregnancy.status==desired)
            total=session.scalar(select(func.count()).select_from(Pregnancy).where(*filters)) or 0
            stmt=select(Pregnancy).where(*filters).order_by(Pregnancy.created_at.desc()).limit(limit).offset(offset)
            from services.maternite.repository import pregnancy_options
            items=session.scalars(pregnancy_options(stmt)).all()
            logger.info('rpc=ListMaternityCases peer=%s actor=%s count=%s outcome=OK',context.peer(),actor.id,len(items))
            return maternite_pb2.ListMaternityCasesResponse(records=[record_proto(x) for x in items],total=int(total))
        finally: session.close()

    def CloseMaternityCase(self,request,context):
        actor=require_permission(context,'maternity.manage'); pid=request.pregnancy_id.strip(); reason=request.reason.strip()
        if not pid or not reason: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'pregnancy_id and reason are required.')
        session=MaterniteSessionLocal()
        try:
            item=session.scalar(select(Pregnancy).where(Pregnancy.id==pid).with_for_update())
            if not item: context.abort(grpc.StatusCode.NOT_FOUND,'Maternity case not found.')
            if item.status=='CLOSED':
                item=get_pregnancy(session,pid); return maternite_pb2.MaternityRecordResponse(record=record_proto(item),replayed=True)
            if item.status!='DELIVERED': context.abort(grpc.StatusCode.FAILED_PRECONDITION,'Only a DELIVERED maternity case can be closed.')
            item.status='CLOSED'; item.active_patient_key=None; item.updated_at=utc_now(); session.commit()
            saved=get_pregnancy(session,pid)
            logger.info('rpc=CloseMaternityCase peer=%s actor=%s pregnancy=%s reason=%s outcome=OK',context.peer(),actor.id,pid,reason)
            return maternite_pb2.MaternityRecordResponse(record=record_proto(saved),replayed=False)
        finally: session.close()

    def HealthCheck(self,request,context):
        try:
            with engine.connect() as c: c.execute(text('SELECT 1'))
            return health('ONLINE','Maternite service and MySQL are available.')
        except Exception:
            logger.exception('rpc=HealthCheck peer=%s outcome=DEGRADED',context.peer()); return health('DEGRADED','Maternite service is running but MySQL is unavailable.')
