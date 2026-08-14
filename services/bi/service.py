from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import text

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2_grpc
from bi.v1 import bi_pb2, bi_pb2_grpc
from billing.v1 import billing_pb2, billing_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat, health_category
from consultation.v1 import consultation_pb2, consultation_pb2_grpc
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
from laboratoire.v1 import laboratoire_pb2, laboratoire_pb2_grpc
from maternite.v1 import maternite_pb2, maternite_pb2_grpc
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc
from rendezvous.v1 import rendezvous_pb2, rendezvous_pb2_grpc

from database.bi_session import BISessionLocal, engine
from services.bi.config import (
    ACCUEIL_GRPC_TARGET, AUTH_GRPC_TARGET, BILLING_GRPC_TARGET, BI_GRPC_TARGET,
    BI_MAX_MEDICINE_SCAN, BI_MAX_PATIENT_SCAN, CHATBOT_GRPC_TARGET,
    CONSULTATION_GRPC_TARGET, HOSPITALISATION_GRPC_TARGET, LABORATOIRE_GRPC_TARGET,
    MATERNITE_GRPC_TARGET, PHARMACIE_GRPC_TARGET, RENDEZVOUS_GRPC_TARGET,
    SERVICE_VERSION,
)
from services.bi.models import MetricSnapshot, ReportRun
from services.common.auth_guard import require_permission

logger=logging.getLogger('projectx.bi.service')

QUALITY_COMPLETE=bi_pb2.DATA_QUALITY_COMPLETE
QUALITY_PARTIAL=bi_pb2.DATA_QUALITY_PARTIAL
QUALITY_UNAVAILABLE=bi_pb2.DATA_QUALITY_UNAVAILABLE


def now_utc(): return datetime.now(timezone.utc)
def ts(value=None):
    out=Timestamp(); out.FromDatetime((value or now_utc()).astimezone(timezone.utc)); return out

def downstream_md(context):
    for item in context.invocation_metadata():
        if item.key.lower()=='authorization' and item.value.strip():
            return (('authorization',item.value.strip()),)
    return tuple()

def parse_date(raw, field, context):
    raw=raw.strip()
    if not raw: return None
    try: return datetime.strptime(raw,'%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError: context.abort(grpc.StatusCode.INVALID_ARGUMENT,f'{field} must use YYYY-MM-DD.')

def request_range(request, context):
    start=parse_date(request.date_from,'date_from',context)
    end=parse_date(request.date_to,'date_to',context)
    if end: end=end+timedelta(days=1)
    if start and end and start>=end: context.abort(grpc.StatusCode.INVALID_ARGUMENT,'date_from must not be after date_to.')
    return start,end

def money_currency(value):
    fields=value.DESCRIPTOR.fields_by_name
    if 'currency_code' in fields: return value.currency_code or 'BIF'
    if 'currency' in fields: return value.currency or 'BIF'
    return 'BIF'

def health_status_from_common(response):
    category = health_category(response)
    if category == "ONLINE":
        return bi_pb2.SERVICE_STATUS_ONLINE
    if category == "OFFLINE":
        return bi_pb2.SERVICE_STATUS_OFFLINE
    return bi_pb2.SERVICE_STATUS_DEGRADED

def build_health(status,message):
    return build_health_response_compat("bi", status, message, SERVICE_VERSION)

def metric(code,label,value,unit,source,note='',available=True):
    return bi_pb2.Metric(code=code,label=label,value=int(value),unit=unit,available=available,source_service=source,note=note)

def quality(warnings, unavailable=False):
    if unavailable: return QUALITY_UNAVAILABLE
    return QUALITY_PARTIAL if warnings else QUALITY_COMPLETE

class BIService(bi_pb2_grpc.BIServiceServicer):
    def _patients(self,context):
        warnings=[]
        try:
            with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as ch:
                r=accueil_pb2_grpc.AccueilServiceStub(ch).SearchPatients(accueil_pb2.SearchPatientsRequest(query='',limit=BI_MAX_PATIENT_SCAN,offset=0),metadata=downstream_md(context),timeout=3)
            patients=list(r.patients)
            if r.total>len(patients): warnings.append(f'Patient scan limited to {len(patients)} of {r.total}; derived patient-level KPIs are partial.')
            return patients,int(r.total),warnings
        except grpc.RpcError as e:
            warnings.append(f'Accueil unavailable for patient aggregation: {e.code().name}')
            return [],0,warnings

    def _hospital_stats(self,context):
        patients,total_patients,warnings=self._patients(context)
        consultations=0; active_admissions=0
        md=downstream_md(context)
        for p in patients:
            try:
                with grpc.insecure_channel(CONSULTATION_GRPC_TARGET) as ch:
                    r=consultation_pb2_grpc.ConsultationServiceStub(ch).ListPatientConsultations(consultation_pb2.ListPatientConsultationsRequest(patient_id=p.id,limit=1,offset=0),metadata=md,timeout=3)
                consultations+=int(r.total)
            except grpc.RpcError as e:
                warnings.append(f'Consultation aggregation partial: {e.code().name}'); break
        for p in patients:
            try:
                with grpc.insecure_channel(HOSPITALISATION_GRPC_TARGET) as ch:
                    hospitalisation_pb2_grpc.HospitalisationServiceStub(ch).GetCurrentAdmission(hospitalisation_pb2.GetCurrentAdmissionRequest(patient_id=p.id),metadata=md,timeout=3)
                active_admissions+=1
            except grpc.RpcError as e:
                if e.code()!=grpc.StatusCode.NOT_FOUND:
                    warnings.append(f'Hospitalisation aggregation partial: {e.code().name}'); break
        pending=0
        try:
            with grpc.insecure_channel(LABORATOIRE_GRPC_TARGET) as ch:
                r=laboratoire_pb2_grpc.LaboratoireServiceStub(ch).ListPendingOrders(laboratoire_pb2.ListPendingOrdersRequest(limit=1,offset=0),metadata=md,timeout=3)
            pending=int(r.total)
        except grpc.RpcError as e: warnings.append(f'Laboratoire pending-order KPI unavailable: {e.code().name}')
        return total_patients,consultations,active_admissions,pending,warnings

    def _revenue_stats(self,context):
        patients,_,warnings=self._patients(context); md=downstream_md(context)
        charges=paid=balance=0; currency='BIF'
        for p in patients:
            try:
                with grpc.insecure_channel(BILLING_GRPC_TARGET) as ch:
                    r=billing_pb2_grpc.BillingServiceStub(ch).GetPatientBalance(billing_pb2.GetPatientBalanceRequest(patient_id=p.id),metadata=md,timeout=3)
                charges+=int(r.total_charges.amount_minor); paid+=int(r.total_paid.amount_minor); balance+=int(r.balance.amount_minor); currency=money_currency(r.balance)
            except grpc.RpcError as e:
                if e.code()==grpc.StatusCode.NOT_FOUND: continue
                warnings.append(f'Billing aggregation partial: {e.code().name}'); break
        return charges,paid,balance,currency,warnings

    def _occupancy_stats(self,context):
        warnings=[]
        try:
            with grpc.insecure_channel(HOSPITALISATION_GRPC_TARGET) as ch:
                r=hospitalisation_pb2_grpc.HospitalisationServiceStub(ch).GetBedAvailability(hospitalisation_pb2.GetBedAvailabilityRequest(ward_code='',available_only=False),metadata=downstream_md(context),timeout=3)
            return int(r.total),int(r.available),int(r.occupied),int(r.out_of_service),warnings
        except grpc.RpcError as e:
            warnings.append(f'Hospitalisation occupancy unavailable: {e.code().name}'); return 0,0,0,0,warnings

    def _stock_stats(self,context):
        warnings=[]; md=downstream_md(context); medicines=0; units=0; alerts=0
        try:
            with grpc.insecure_channel(PHARMACIE_GRPC_TARGET) as ch:
                stub=pharmacie_pb2_grpc.PharmacieServiceStub(ch)
                r=stub.SearchMedicines(pharmacie_pb2.SearchMedicinesRequest(query='',active_only=False,limit=BI_MAX_MEDICINE_SCAN,offset=0),metadata=md,timeout=3)
                medicines=int(r.total)
                for med in r.medicines:
                    try: units+=int(stub.GetStock(pharmacie_pb2.GetStockRequest(medicine_ref=med.code),metadata=md,timeout=3).stock.total_available)
                    except grpc.RpcError as e: warnings.append(f'Stock detail partial for {med.code}: {e.code().name}')
                if r.total>len(r.medicines): warnings.append(f'Medicine scan limited to {len(r.medicines)} of {r.total}; stock units are partial.')
                alerts=int(stub.ListStockAlerts(pharmacie_pb2.ListStockAlertsRequest(days_to_expiry=30),metadata=md,timeout=3).total)
        except grpc.RpcError as e: warnings.append(f'Pharmacie KPI unavailable: {e.code().name}')
        return medicines,units,alerts,warnings

    def _maternity_stats(self,context):
        patients,_,warnings=self._patients(context); md=downstream_md(context)
        records=in_labor=delivered=newborns=0
        for p in patients:
            try:
                with grpc.insecure_channel(MATERNITE_GRPC_TARGET) as ch:
                    record=maternite_pb2_grpc.MaterniteServiceStub(ch).GetMaternityRecord(maternite_pb2.GetMaternityRecordRequest(patient_id=p.id),metadata=md,timeout=3).record
                records+=1; newborns+=len(record.newborns)
                if record.pregnancy.status==maternite_pb2.PREGNANCY_STATUS_IN_LABOR: in_labor+=1
                if record.pregnancy.status==maternite_pb2.PREGNANCY_STATUS_DELIVERED: delivered+=1
            except grpc.RpcError as e:
                if e.code()==grpc.StatusCode.NOT_FOUND: continue
                warnings.append(f'Maternite aggregation partial: {e.code().name}'); break
        return records,in_labor,delivered,newborns,warnings

    def _appointment_stats(self,request,context):
        warnings=[]; start,end=request_range(request,context)
        req=rendezvous_pb2.ListAgendaRequest(provider_id='',service=request.service.strip(),limit=300,offset=0)
        if start: req.from_at.CopyFrom(ts(start))
        if end: req.to_at.CopyFrom(ts(end))
        try:
            with grpc.insecure_channel(RENDEZVOUS_GRPC_TARGET) as ch:
                r=rendezvous_pb2_grpc.RendezvousServiceStub(ch).ListAgenda(req,metadata=downstream_md(context),timeout=3)
            counts={'BOOKED':0,'CONFIRMED':0,'CHECKED_IN':0,'COMPLETED':0,'CANCELLED':0,'NO_SHOW':0}
            for item in r.appointments:
                name=rendezvous_pb2.AppointmentStatus.Name(item.status).replace('APPOINTMENT_STATUS_','')
                if name in counts: counts[name]+=1
            if r.total>len(r.appointments): warnings.append(f'Agenda scan limited to {len(r.appointments)} of {r.total}; status breakdown is partial.')
            return int(r.total),counts,warnings
        except grpc.RpcError as e:
            warnings.append(f'Rendezvous KPI unavailable: {e.code().name}'); return 0,{k:0 for k in ['BOOKED','CONFIRMED','CHECKED_IN','COMPLETED','CANCELLED','NO_SHOW']},warnings

    def _one_health(self,name,target,stub_factory):
        start=time.perf_counter(); checked=now_utc()
        try:
            with grpc.insecure_channel(target) as ch:
                response=stub_factory(ch).HealthCheck(common_pb2.HealthRequest(),timeout=2)
            latency=int((time.perf_counter()-start)*1000)
            return bi_pb2.ServiceHealth(service=name,target=target,status=health_status_from_common(response),latency_ms=latency,checked_at=ts(checked),message=getattr(response,'message',''))
        except Exception as e:
            latency=int((time.perf_counter()-start)*1000)
            detail=e.code().name if isinstance(e,grpc.RpcError) else type(e).__name__
            status=bi_pb2.SERVICE_STATUS_DEGRADED if isinstance(e,grpc.RpcError) and e.code()==grpc.StatusCode.UNIMPLEMENTED else bi_pb2.SERVICE_STATUS_OFFLINE
            message=('Reachable but HealthCheck is not implemented yet.' if status==bi_pb2.SERVICE_STATUS_DEGRADED else f'Unavailable: {detail}')
            return bi_pb2.ServiceHealth(service=name,target=target,status=status,latency_ms=latency,checked_at=ts(checked),message=message)

    def _service_health(self):
        specs=[
            ('auth',AUTH_GRPC_TARGET,lambda ch: auth_pb2_grpc.AuthServiceStub(ch)),
            ('accueil',ACCUEIL_GRPC_TARGET,lambda ch: accueil_pb2_grpc.AccueilServiceStub(ch)),
            ('hospitalisation',HOSPITALISATION_GRPC_TARGET,lambda ch: hospitalisation_pb2_grpc.HospitalisationServiceStub(ch)),
            ('billing',BILLING_GRPC_TARGET,lambda ch: billing_pb2_grpc.BillingServiceStub(ch)),
            ('consultation',CONSULTATION_GRPC_TARGET,lambda ch: consultation_pb2_grpc.ConsultationServiceStub(ch)),
            ('laboratoire',LABORATOIRE_GRPC_TARGET,lambda ch: laboratoire_pb2_grpc.LaboratoireServiceStub(ch)),
            ('pharmacie',PHARMACIE_GRPC_TARGET,lambda ch: pharmacie_pb2_grpc.PharmacieServiceStub(ch)),
            ('maternite',MATERNITE_GRPC_TARGET,lambda ch: maternite_pb2_grpc.MaterniteServiceStub(ch)),
            ('rendezvous',RENDEZVOUS_GRPC_TARGET,lambda ch: rendezvous_pb2_grpc.RendezvousServiceStub(ch)),
        ]
        results=[]
        with ThreadPoolExecutor(max_workers=9) as pool:
            futs=[pool.submit(self._one_health,*s) for s in specs]
            for f in as_completed(futs): results.append(f.result())
        try:
            with engine.connect() as c: c.execute(text('SELECT 1'))
            results.append(bi_pb2.ServiceHealth(service='bi',target=BI_GRPC_TARGET,status=bi_pb2.SERVICE_STATUS_ONLINE,latency_ms=0,checked_at=ts(),message='BI service and MySQL are available.'))
        except Exception:
            results.append(bi_pb2.ServiceHealth(service='bi',target=BI_GRPC_TARGET,status=bi_pb2.SERVICE_STATUS_DEGRADED,latency_ms=0,checked_at=ts(),message='BI service is running but MySQL is unavailable.'))
        # Chatbot is intentionally probed without importing its contract; LOT K will install the real contract.
        start=time.perf_counter()
        try:
            ch=grpc.insecure_channel(CHATBOT_GRPC_TARGET); grpc.channel_ready_future(ch).result(timeout=0.35); ch.close()
            results.append(bi_pb2.ServiceHealth(service='chatbot',target=CHATBOT_GRPC_TARGET,status=bi_pb2.SERVICE_STATUS_ONLINE,latency_ms=int((time.perf_counter()-start)*1000),checked_at=ts(),message='Port reachable. Chatbot HealthCheck contract will be used after LOT K.'))
        except Exception:
            results.append(bi_pb2.ServiceHealth(service='chatbot',target=CHATBOT_GRPC_TARGET,status=bi_pb2.SERVICE_STATUS_OFFLINE,latency_ms=int((time.perf_counter()-start)*1000),checked_at=ts(),message='Chatbot is not running yet.'))
        return sorted(results,key=lambda x:x.service)

    def _persist(self,actor,request,metrics,q,warnings):
        s=BISessionLocal()
        try:
            qname=bi_pb2.DataQuality.Name(q)
            s.add(ReportRun(requested_by=actor.id,date_from=request.date_from.strip() or None,date_to=request.date_to.strip() or None,service_filter=request.service.strip() or None,quality=qname,warnings=json.dumps(warnings,ensure_ascii=False) if warnings else None))
            for m in metrics:
                if m.available:
                    s.add(MetricSnapshot(metric_code=m.code,period_start=request.date_from.strip() or None,period_end=request.date_to.strip() or None,value=m.value,dimensions=json.dumps({'unit':m.unit,'note':m.note},ensure_ascii=False),source_service=m.source_service))
            s.commit()
        except Exception:
            s.rollback(); logger.exception('BI snapshot persistence failed')
        finally: s.close()

    def GetHospitalStats(self,request,context):
        require_permission(context,'bi.dashboard.read'); p,c,a,l,w=self._hospital_stats(context)
        return bi_pb2.HospitalStatsResponse(patients=p,consultations=c,active_admissions=a,pending_lab_orders=l,quality=quality(w),warnings=w)

    def GetRevenueStats(self,request,context):
        require_permission(context,'bi.dashboard.read'); ch,pa,ba,cur,w=self._revenue_stats(context)
        return bi_pb2.RevenueStatsResponse(total_charges_minor=ch,total_paid_minor=pa,balance_minor=ba,currency_code=cur,quality=quality(w),warnings=w)

    def GetOccupancyStats(self,request,context):
        require_permission(context,'bi.dashboard.read'); t,a,o,x,w=self._occupancy_stats(context)
        return bi_pb2.OccupancyStatsResponse(total_beds=t,available_beds=a,occupied_beds=o,out_of_service_beds=x,quality=quality(w),warnings=w)

    def GetStockStats(self,request,context):
        require_permission(context,'bi.dashboard.read'); m,u,a,w=self._stock_stats(context)
        return bi_pb2.StockStatsResponse(medicines=m,total_units_available=u,stock_alerts=a,quality=quality(w),warnings=w)

    def GetMaternityStats(self,request,context):
        require_permission(context,'bi.dashboard.read'); r,l,d,n,w=self._maternity_stats(context)
        return bi_pb2.MaternityStatsResponse(maternity_records=r,in_labor=l,delivered=d,newborns=n,quality=quality(w),warnings=w)

    def GetAppointmentStats(self,request,context):
        require_permission(context,'bi.dashboard.read'); total,c,w=self._appointment_stats(request,context)
        return bi_pb2.AppointmentStatsResponse(appointments=total,booked=c['BOOKED'],confirmed=c['CONFIRMED'],checked_in=c['CHECKED_IN'],completed=c['COMPLETED'],cancelled=c['CANCELLED'],no_show=c['NO_SHOW'],quality=quality(w),warnings=w)

    def GetServiceHealth(self,request,context):
        require_permission(context,'bi.dashboard.read'); services=self._service_health(); warnings=[]
        offline=[s.service for s in services if s.status==bi_pb2.SERVICE_STATUS_OFFLINE]
        degraded=[s.service for s in services if s.status==bi_pb2.SERVICE_STATUS_DEGRADED]
        if offline: warnings.append('Offline services: '+', '.join(offline))
        if degraded: warnings.append('Degraded services: '+', '.join(degraded))
        filtered=services if request.include_offline else [s for s in services if s.status!=bi_pb2.SERVICE_STATUS_OFFLINE]
        return bi_pb2.ServiceHealthResponse(services=filtered,quality=quality(warnings),warnings=warnings,checked_at=ts())

    def GetDashboard(self,request,context):
        actor=require_permission(context,'bi.dashboard.read')
        p,c,a,l,w1=self._hospital_stats(context)
        charges,paid,balance,currency,w2=self._revenue_stats(context)
        total_beds,available,occupied,out_service,w3=self._occupancy_stats(context)
        meds,units,alerts,w4=self._stock_stats(context)
        mat_records,in_labor,delivered,newborns,w5=self._maternity_stats(context)
        appts,ac,w6=self._appointment_stats(request,context)
        services=self._service_health()
        warnings=w1+w2+w3+w4+w5+w6
        offline=[s.service for s in services if s.status==bi_pb2.SERVICE_STATUS_OFFLINE]
        if offline: warnings.append('Service health is partial; offline: '+', '.join(offline))
        metrics=[
            metric('patients.total','Patients',p,'count','accueil'),
            metric('consultations.total','Consultations',c,'count','consultation','Aggregated through patient histories.'),
            metric('admissions.active','Active admissions',a,'count','hospitalisation'),
            metric('beds.available','Available beds',available,'count','hospitalisation'),
            metric('beds.occupied','Occupied beds',occupied,'count','hospitalisation'),
            metric('revenue.charges','Charges',charges,currency,'billing'),
            metric('revenue.paid','Paid',paid,currency,'billing'),
            metric('revenue.balance','Outstanding balance',balance,currency,'billing'),
            metric('lab.pending','Pending lab orders',l,'count','laboratoire'),
            metric('stock.units','Stock units available',units,'units','pharmacie'),
            metric('stock.alerts','Stock alerts',alerts,'count','pharmacie'),
            metric('maternity.records','Maternity records',mat_records,'count','maternite'),
            metric('maternity.delivered','Delivered maternity cases',delivered,'count','maternite'),
            metric('maternity.newborns','Registered newborns',newborns,'count','maternite'),
            metric('appointments.total','Appointments',appts,'count','rendezvous'),
            metric('appointments.completed','Completed appointments',ac['COMPLETED'],'count','rendezvous'),
        ]
        q=quality(warnings)
        self._persist(actor,request,metrics,q,warnings)
        logger.info('rpc=GetDashboard peer=%s actor=%s metrics=%s quality=%s outcome=OK',context.peer(),actor.id,len(metrics),bi_pb2.DataQuality.Name(q))
        return bi_pb2.DashboardResponse(metrics=metrics,services=services,quality=q,warnings=warnings,generated_at=ts())

    def HealthCheck(self,request,context):
        try:
            with engine.connect() as c: c.execute(text('SELECT 1'))
            return build_health('ONLINE','BI service and MySQL are available.')
        except Exception:
            logger.exception('rpc=HealthCheck peer=%s outcome=DEGRADED',context.peer()); return build_health('DEGRADED','BI service is running but MySQL is unavailable.')
