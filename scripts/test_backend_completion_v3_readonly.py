from __future__ import annotations

import getpass
from datetime import date, timedelta
import grpc

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from bi.v1 import bi_pb2, bi_pb2_grpc
from common.v1 import common_pb2
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
from hr.v1 import hr_pb2, hr_pb2_grpc
from laboratoire.v1 import laboratoire_pb2, laboratoire_pb2_grpc
from maternite.v1 import maternite_pb2, maternite_pb2_grpc
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc
from rendezvous.v1 import rendezvous_pb2, rendezvous_pb2_grpc


def md(token): return (("authorization",f"Bearer {token}"),)
def ok(label, extra=''): print(f"[OK] {label}" + (f" — {extra}" if extra else ''))


def main():
    user=input('Admin username: ').strip(); password=getpass.getpass('Admin password: ')
    with grpc.insecure_channel('127.0.0.1:50051') as ch:
        auth=auth_pb2_grpc.AuthServiceStub(ch); login=auth.Login(auth_pb2.LoginRequest(username=user,password=password),timeout=5)
        token=login.access_token; metadata=md(token); ok('Admin login')
        directory=auth.ListStaffDirectory(auth_pb2.ListStaffDirectoryRequest(active_only=True,page=common_pb2.PageRequest(page=1,page_size=5)),metadata=metadata,timeout=5)
        ok('Auth staff directory',f'{len(directory.entries)} entries sampled')

    with grpc.insecure_channel('127.0.0.1:50056') as ch:
        lab=laboratoire_pb2_grpc.LaboratoireServiceStub(ch); r=lab.ListLabTests(laboratoire_pb2.ListLabTestsRequest(active_only=True,limit=20),metadata=metadata,timeout=5)
        assert r.total>=0; ok('Laboratory catalogue',f'{r.total} tests')
        if r.tests:
            detail=lab.GetLabTest(laboratoire_pb2.GetLabTestRequest(test_ref=r.tests[0].code),metadata=metadata,timeout=5)
            assert detail.test.code==r.tests[0].code; ok('Laboratory catalogue detail',detail.test.code)

    with grpc.insecure_channel('127.0.0.1:50057') as ch:
        ph=pharmacie_pb2_grpc.PharmacieServiceStub(ch)
        meds=ph.SearchMedicines(pharmacie_pb2.SearchMedicinesRequest(query='',active_only=True,limit=10),metadata=metadata,timeout=5); ok('Pharmacy medicine catalogue',f'{meds.total} medicines')
        inbox=ph.ListPrescriptionInbox(pharmacie_pb2.ListPrescriptionInboxRequest(limit=10),metadata=metadata,timeout=5); ok('Pharmacy prescription inbox',f'{inbox.total} prescriptions')
        suppliers=ph.ListSuppliers(pharmacie_pb2.ListSuppliersRequest(limit=10),metadata=metadata,timeout=5); ok('Pharmacy suppliers read',f'{suppliers.total} suppliers')
        pos=ph.ListPurchaseOrders(pharmacie_pb2.ListPurchaseOrdersRequest(limit=10),metadata=metadata,timeout=5); ok('Pharmacy purchase orders read',f'{pos.total} purchase orders')
        if pos.purchase_orders:
            detail=ph.GetPurchaseOrder(pharmacie_pb2.GetPurchaseOrderRequest(purchase_order_id=pos.purchase_orders[0].id),metadata=metadata,timeout=5)
            assert detail.purchase_order.id==pos.purchase_orders[0].id; ok('Pharmacy purchase order detail',detail.purchase_order.order_number)

    with grpc.insecure_channel('127.0.0.1:50053') as ch:
        hosp=hospitalisation_pb2_grpc.HospitalisationServiceStub(ch)
        wards=hosp.ListWards(hospitalisation_pb2.ListWardsRequest(active_only=False),metadata=metadata,timeout=5); ok('Hospitalisation wards',f'{wards.total} wards')
        rooms=hosp.ListRooms(hospitalisation_pb2.ListRoomsRequest(),metadata=metadata,timeout=5); ok('Hospitalisation rooms',f'{rooms.total} rooms')
        beds=hosp.GetBedAvailability(hospitalisation_pb2.GetBedAvailabilityRequest(available_only=False),metadata=metadata,timeout=5); ok('Hospitalisation bed availability',f'{beds.total} beds')
        doctors=hosp.ListDoctors(hospitalisation_pb2.ListDoctorsRequest(active_only=True),metadata=metadata,timeout=5); ok('Hospitalisation doctor directory/workload',f'{doctors.total} doctors')
        admissions=hosp.ListAdmissions(hospitalisation_pb2.ListAdmissionsRequest(limit=10),metadata=metadata,timeout=5); ok('Hospitalisation admission history/read',f'{admissions.total} admissions')

    with grpc.insecure_channel('127.0.0.1:50062') as ch:
        hr=hr_pb2_grpc.HRServiceStub(ch)
        logs=hr.ListHrAuditLogs(hr_pb2.ListHrAuditLogsRequest(limit=10),metadata=metadata,timeout=5); ok('HR audit exposure',f'{logs.total} audit records')
        dashboard=hr.GetHrDashboard(hr_pb2.HrDashboardRequest(work_date=date.today().isoformat()),metadata=metadata,timeout=5); ok('HR dashboard compatibility',f'not_started={dashboard.not_started_today}')

    patient_id=''
    with grpc.insecure_channel('127.0.0.1:50052') as ch:
        accueil=accueil_pb2_grpc.AccueilServiceStub(ch); patients=accueil.SearchPatients(accueil_pb2.SearchPatientsRequest(query='',limit=1,offset=0),metadata=metadata,timeout=5)
        if patients.patients: patient_id=patients.patients[0].id
    with grpc.insecure_channel('127.0.0.1:50059') as ch:
        rv=rendezvous_pb2_grpc.RendezvousServiceStub(ch)
        if patient_id:
            r=rv.ListPatientAppointments(rendezvous_pb2.ListPatientAppointmentsRequest(patient_id=patient_id,limit=10),metadata=metadata,timeout=5); ok('Patient appointment history',f'{r.total} appointments')
        else: ok('Patient appointment history','no patient fixture; RPC not exercised')

    with grpc.insecure_channel('127.0.0.1:50058') as ch:
        mat=maternite_pb2_grpc.MaterniteServiceStub(ch); r=mat.ListMaternityCases(maternite_pb2.ListMaternityCasesRequest(limit=10),metadata=metadata,timeout=5); ok('Maternity case list/search',f'{r.total} cases')

    with grpc.insecure_channel('127.0.0.1:50060') as ch:
        bi=bi_pb2_grpc.BIServiceStub(ch)
        today=date.today(); start=(today-timedelta(days=7)).isoformat()
        r=bi.GetDashboard(bi_pb2.DashboardRequest(date_from=start,date_to=today.isoformat(),service='pharmacie'),metadata=metadata,timeout=10)
        assert all(m.source_service=='pharmacie' for m in r.metrics); ok('BI service filter',f'{len(r.metrics)} pharmacie metrics, quality={bi_pb2.DataQuality.Name(r.quality)}')
        health=bi.GetServiceHealth(bi_pb2.ServiceHealthRequest(include_offline=True),metadata=metadata,timeout=12); assert len(health.services)==12; ok('BI 12-service topology')

    print('\nPROJECTX BACKEND COMPLETION V3 READ-ONLY REGRESSION: PASS')

if __name__=='__main__':
    try: main()
    except grpc.RpcError as e:
        print('PROJECTX BACKEND COMPLETION V3 READ-ONLY REGRESSION: FAIL'); print('STATUS:',e.code().name); print('DETAIL:',e.details()); raise
