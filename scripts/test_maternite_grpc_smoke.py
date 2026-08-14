from __future__ import annotations
import getpass,uuid
from datetime import datetime,timezone,timedelta
import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from accueil.v1 import accueil_pb2,accueil_pb2_grpc
from auth.v1 import auth_pb2,auth_pb2_grpc
from consultation.v1 import consultation_pb2,consultation_pb2_grpc
from maternite.v1 import maternite_pb2,maternite_pb2_grpc

def md(t): return (('authorization',f'Bearer {t}'),)
def ts(d): x=Timestamp(); x.FromDatetime(d.astimezone(timezone.utc)); return x
def patient(accueil,token,label):
    s=datetime.now(timezone.utc).strftime('%H%M%S%f')[-10:]
    return accueil.CreatePatient(accueil_pb2.CreatePatientRequest(first_name=label,last_name=f'MaternitySmoke{s}',sex=accueil_pb2.SEX_FEMALE,birth_date='1995-04-12',phone=f'+25779{s}',address='Bujumbura'),metadata=md(token),timeout=5).patient

def main():
    username=input('Username: ').strip(); password=getpass.getpass('Password: ')
    with grpc.insecure_channel('127.0.0.1:50051') as ch: login=auth_pb2_grpc.AuthServiceStub(ch).Login(auth_pb2.LoginRequest(username=username,password=password),timeout=5)
    token=login.access_token
    with grpc.insecure_channel('127.0.0.1:50052') as ch:
        accueil=accueil_pb2_grpc.AccueilServiceStub(ch); mother=patient(accueil,token,'Aline'); referral_patient=patient(accueil,token,'Brigitte')
    with grpc.insecure_channel('127.0.0.1:50058') as ch:
        mat=maternite_pb2_grpc.MaterniteServiceStub(ch); m=md(token)
        create_key=f'mat-{uuid.uuid4()}'
        case=mat.CreateMaternityCase(maternite_pb2.CreateMaternityCaseRequest(patient_id=mother.id,gravida=2,para=1,lmp_date='2025-12-01',edd='2026-09-07',risk_level=maternite_pb2.RISK_LEVEL_MODERATE,risk_factors='Surveillance tensionnelle',referral_reason='Suivi prénatal',idempotency_key=create_key,correlation_id=str(uuid.uuid4())),metadata=m,timeout=5)
        replay=mat.CreateMaternityCase(maternite_pb2.CreateMaternityCaseRequest(patient_id=mother.id,gravida=2,para=1,lmp_date='2025-12-01',edd='2026-09-07',risk_level=maternite_pb2.RISK_LEVEL_MODERATE,risk_factors='Surveillance tensionnelle',referral_reason='Suivi prénatal',idempotency_key=create_key,correlation_id=case.record.pregnancy.correlation_id),metadata=m,timeout=5)
        visit=mat.AddPrenatalVisit(maternite_pb2.AddPrenatalVisitRequest(pregnancy_id=case.record.pregnancy.id,visit_at=ts(datetime.now(timezone.utc)),gestational_age_weeks=36,observations='Evolution favorable',systolic_bp=118,diastolic_bp=76,weight_kg=68.4,fetal_heart_bpm=142,idempotency_key=f'visit-{uuid.uuid4()}'),metadata=m,timeout=5)
        labor=mat.AdmitForLabor(maternite_pb2.AdmitForLaborRequest(pregnancy_id=case.record.pregnancy.id,admitted_at=ts(datetime.now(timezone.utc)),reason='Contractions régulières',idempotency_key=f'labor-{uuid.uuid4()}'),metadata=m,timeout=5)
        event=mat.RecordLaborEvent(maternite_pb2.RecordLaborEventRequest(pregnancy_id=case.record.pregnancy.id,event_type=maternite_pb2.LABOR_EVENT_TYPE_CERVICAL_EXAM,event_at=ts(datetime.now(timezone.utc)),description='Progression du travail',cervical_dilation_cm=6.0,fetal_heart_bpm=138,idempotency_key=f'event-{uuid.uuid4()}'),metadata=m,timeout=5)
        delivery=mat.RecordDelivery(maternite_pb2.RecordDeliveryRequest(pregnancy_id=case.record.pregnancy.id,delivered_at=ts(datetime.now(timezone.utc)),mode=maternite_pb2.DELIVERY_MODE_VAGINAL,outcome=maternite_pb2.DELIVERY_OUTCOME_LIVE_BIRTH,complications='',idempotency_key=f'delivery-{uuid.uuid4()}'),metadata=m,timeout=5)
        newborn=mat.RegisterNewborn(maternite_pb2.RegisterNewbornRequest(delivery_id=delivery.delivery.id,sex=maternite_pb2.NEWBORN_SEX_FEMALE,weight_g=3180,apgar_1=8,apgar_5=9,status=maternite_pb2.NEWBORN_STATUS_STABLE,idempotency_key=f'newborn-{uuid.uuid4()}'),metadata=m,timeout=5)
        record=mat.GetMaternityRecord(maternite_pb2.GetMaternityRecordRequest(pregnancy_id=case.record.pregnancy.id),metadata=m,timeout=5).record
        post_delivery_guard='NOT_TESTED'
        try:
            mat.RecordLaborEvent(maternite_pb2.RecordLaborEventRequest(pregnancy_id=case.record.pregnancy.id,event_type=maternite_pb2.LABOR_EVENT_TYPE_NOTE,event_at=ts(datetime.now(timezone.utc)),description='Should be blocked',idempotency_key=f'late-{uuid.uuid4()}'),metadata=m,timeout=5); post_delivery_guard='FAILED'
        except grpc.RpcError as e: post_delivery_guard=e.code().name
    # Prove Consultation -> Maternite on a separate patient, so it does not collide with the full-case test.
    with grpc.insecure_channel('127.0.0.1:50055') as ch:
        cons=consultation_pb2_grpc.ConsultationServiceStub(ch); m=md(token)
        c=cons.CreateConsultation(consultation_pb2.CreateConsultationRequest(patient_id=referral_patient.id,reason='Evaluation obstétricale',symptoms='Douleurs pelviennes'),metadata=m,timeout=5).consultation
        referral=cons.RequestHospitalization(consultation_pb2.RequestHospitalizationRequest(consultation_id=c.id,reason='Orientation maternité',target=consultation_pb2.HOSPITALIZATION_TARGET_MATERNITE),metadata=m,timeout=5).request
    print(); print('===================================='); print(' PROJECTX MATERNITE SMOKE SUCCESS'); print('====================================')
    print('Mother patient number :',mother.patient_number)
    print('Pregnancy number      :',case.record.pregnancy.pregnancy_number)
    print('Create replay         :',replay.replayed)
    print('Prenatal visit        :',bool(visit.visit.id))
    print('Labor status          :',maternite_pb2.PregnancyStatus.Name(labor.record.pregnancy.status))
    print('Labor event           :',maternite_pb2.LaborEventType.Name(event.event.event_type))
    print('Delivery number       :',delivery.delivery.delivery_number)
    print('Delivery status       :',maternite_pb2.PregnancyStatus.Name(record.pregnancy.status))
    print('Billing charge status :',maternite_pb2.BillingChargeStatus.Name(delivery.delivery.billing_status))
    print('Newborn number        :',newborn.newborn.newborn_number)
    print('Mother-child linked   :',newborn.newborn.mother_patient_id==mother.id)
    print('Record newborn total  :',len(record.newborns))
    print('Post-delivery guard   :',post_delivery_guard)
    print('Consult -> Maternity  :',consultation_pb2.ExternalRequestStatus.Name(referral.status))
    print('JWT printed           : False')
if __name__=='__main__':
    try: main()
    except grpc.RpcError as e: print('PROJECTX MATERNITE SMOKE FAILED'); print('STATUS :',e.code().name); print('DETAIL :',e.details())
    except Exception as e: print('PROJECTX MATERNITE SMOKE FAILED'); print('DETAIL :',str(e))
