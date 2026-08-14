from __future__ import annotations
import getpass
from datetime import datetime,timezone,timedelta
import grpc
from auth.v1 import auth_pb2,auth_pb2_grpc
from bi.v1 import bi_pb2,bi_pb2_grpc
from common.v1 import common_pb2

def md(token): return (('authorization',f'Bearer {token}'),)

def main():
    username=input('Username: ').strip(); password=getpass.getpass('Password: ')
    with grpc.insecure_channel('127.0.0.1:50051') as ch:
        login=auth_pb2_grpc.AuthServiceStub(ch).Login(auth_pb2.LoginRequest(username=username,password=password),timeout=5)
    token=login.access_token; m=md(token)
    with grpc.insecure_channel('127.0.0.1:50060') as ch:
        stub=bi_pb2_grpc.BIServiceStub(ch)
        health=stub.HealthCheck(common_pb2.HealthRequest(),timeout=5)
        today=datetime.now(timezone.utc).date(); start=today-timedelta(days=30)
        req=bi_pb2.DashboardRequest(date_from=start.isoformat(),date_to=today.isoformat())
        dashboard=stub.GetDashboard(req,metadata=m,timeout=30)
        hospital=stub.GetHospitalStats(req,metadata=m,timeout=30)
        revenue=stub.GetRevenueStats(req,metadata=m,timeout=30)
        occupancy=stub.GetOccupancyStats(req,metadata=m,timeout=10)
        stock=stub.GetStockStats(req,metadata=m,timeout=15)
        maternity=stub.GetMaternityStats(req,metadata=m,timeout=30)
        appointments=stub.GetAppointmentStats(req,metadata=m,timeout=10)
        service_health=stub.GetServiceHealth(bi_pb2.ServiceHealthRequest(include_offline=True),metadata=m,timeout=10)
    online=sum(1 for s in service_health.services if s.status==bi_pb2.SERVICE_STATUS_ONLINE)
    offline=[s.service for s in service_health.services if s.status==bi_pb2.SERVICE_STATUS_OFFLINE]
    print(); print('===================================='); print(' PROJECTX BI SMOKE SUCCESS'); print('====================================')
    print('BI health             :',health.message)
    print('Dashboard quality     :',bi_pb2.DataQuality.Name(dashboard.quality))
    print('Dashboard metrics     :',len(dashboard.metrics))
    print('Patients              :',hospital.patients)
    print('Consultations         :',hospital.consultations)
    print('Active admissions     :',hospital.active_admissions)
    print('Pending lab orders    :',hospital.pending_lab_orders)
    print('Revenue paid          :',revenue.total_paid_minor,revenue.currency_code)
    print('Outstanding balance   :',revenue.balance_minor,revenue.currency_code)
    print('Beds available        :',occupancy.available_beds,'/',occupancy.total_beds)
    print('Stock units           :',stock.total_units_available)
    print('Stock alerts          :',stock.stock_alerts)
    print('Maternity records     :',maternity.maternity_records)
    print('Registered newborns   :',maternity.newborns)
    print('Appointments 30d      :',appointments.appointments)
    print('Service health count  :',len(service_health.services))
    print('Services online       :',online)
    print('Services offline      :',offline)
    print('Partial is truthful   :',dashboard.quality in (bi_pb2.DATA_QUALITY_COMPLETE,bi_pb2.DATA_QUALITY_PARTIAL))
    print('JWT printed           : False')
if __name__=='__main__':
    try: main()
    except grpc.RpcError as e: print('PROJECTX BI SMOKE FAILED'); print('STATUS :',e.code().name); print('DETAIL :',e.details())
    except Exception as e: print('PROJECTX BI SMOKE FAILED'); print('DETAIL :',str(e))
