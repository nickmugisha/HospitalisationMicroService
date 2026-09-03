from __future__ import annotations

from auth.v1 import auth_pb2
from billing.v1 import billing_pb2
from hospitalisation.v1 import hospitalisation_pb2
from hr.v1 import hr_pb2
from laboratoire.v1 import laboratoire_pb2
from maternite.v1 import maternite_pb2
from pharmacie.v1 import pharmacie_pb2
from rendezvous.v1 import rendezvous_pb2


def methods(descriptor, service):
    return {m.name for m in descriptor.services_by_name[service].methods}


def require_methods(descriptor, service, expected):
    actual=methods(descriptor,service); missing=set(expected)-actual
    assert not missing, f"{service} missing RPCs: {sorted(missing)}"


def require_fields(message, expected):
    actual=set(message.DESCRIPTOR.fields_by_name)
    missing=set(expected)-actual
    assert not missing, f"{message.DESCRIPTOR.full_name} missing fields: {sorted(missing)}"


def main():
    require_methods(auth_pb2.DESCRIPTOR,'AuthService',[
        'UpdateStaffProfile','SyncStaffEmploymentStatus','ListStaffDirectory','GetStaffDirectoryEntry',
        'SendSystemNotification','ListSystemRecipientsByRole',
    ])
    require_methods(laboratoire_pb2.DESCRIPTOR,'LaboratoireService',['ListLabTests','GetLabTest'])
    require_methods(pharmacie_pb2.DESCRIPTOR,'PharmacieService',[
        'CreateMedicine','UpdateMedicine','ListPrescriptionInbox','GetPrescriptionInbox','CreateSupplier','UpdateSupplier',
        'ListSuppliers','GetPurchaseOrder','ListPurchaseOrders','DispatchStockAlertNotifications',
    ])
    require_methods(hospitalisation_pb2.DESCRIPTOR,'HospitalisationService',[
        'ListWards','CreateWard','UpdateWard','ListRooms','CreateRoom','UpdateRoom','CreateBed','SetBedStatus',
        'ApproveAdmission','ListAdmissions','ListDoctors','AssignDoctor','ListDoctorAssignments','CompleteDoctorAssignment',
    ])
    require_methods(hr_pb2.DESCRIPTOR,'HRService',[
        'UpdateShift','GetMyAttendanceToday','ListMyAttendance','ListMyShifts','ListMyLeaveRequests','CancelMyLeaveRequest','ListHrAuditLogs',
    ])
    require_methods(rendezvous_pb2.DESCRIPTOR,'RendezvousService',[
        'UpdateScheduleSlot','BlockScheduleSlot','ListPatientAppointments','MarkNoShow',
    ])
    require_methods(maternite_pb2.DESCRIPTOR,'MaterniteService',['ListMaternityCases','CloseMaternityCase'])
    require_fields(billing_pb2.RecordPaymentRequest,['notification_recipient_user_id'])
    require_fields(billing_pb2.ReversePaymentRequest,['notification_recipient_user_id'])
    require_fields(rendezvous_pb2.Appointment,['reminder_due_at','reminder_sent_at'])
    require_fields(hr_pb2.Shift,['overnight'])
    require_fields(hr_pb2.HrDashboardResponse,['not_started_today'])
    require_fields(hospitalisation_pb2.Admission,['approved_at','approved_by','approval_reason'])
    require_fields(pharmacie_pb2.CreateMedicineRequest,['active'])
    assert pharmacie_pb2.CreateMedicineRequest.DESCRIPTOR.fields_by_name['active'].has_presence, 'CreateMedicineRequest.active must preserve omitted-vs-false presence'

    # Regression guard for MySQL/MariaDB deployments with a 1000-byte index-key limit.
    # A 255-char utf8mb4 fingerprint can exceed that limit when combined with dispatched_on.
    from types import SimpleNamespace
    from services.pharmacie.models import StockAlertDispatch
    from services.pharmacie.service import stock_alert_fingerprint
    fp_column = StockAlertDispatch.__table__.c.fingerprint
    assert fp_column.type.length == 64, f"Stock alert fingerprint column must be 64 chars, got {fp_column.type.length}"
    sample_fp = stock_alert_fingerprint(SimpleNamespace(type=1, medicine_id="m"*36, batch_id="b"*36, message="é"*500))
    assert len(sample_fp) == 64 and all(ch in "0123456789abcdef" for ch in sample_fp), "Stock alert fingerprint must be SHA-256 hex"

    # Service class coverage: every declared RPC in the changed domains has a Python implementation.
    from services.auth.runtime_service import RuntimeAuthService
    from services.billing.service import BillingService
    from services.hospitalisation.service import HospitalisationService
    from services.hr.service import HRService
    from services.laboratoire.service import LaboratoireService
    from services.maternite.service import MaterniteService
    from services.pharmacie.service import PharmacieService
    from services.rendezvous.service import RendezvousService
    pairs=[
        (auth_pb2.DESCRIPTOR,'AuthService',RuntimeAuthService),(billing_pb2.DESCRIPTOR,'BillingService',BillingService),
        (hospitalisation_pb2.DESCRIPTOR,'HospitalisationService',HospitalisationService),(hr_pb2.DESCRIPTOR,'HRService',HRService),
        (laboratoire_pb2.DESCRIPTOR,'LaboratoireService',LaboratoireService),(maternite_pb2.DESCRIPTOR,'MaterniteService',MaterniteService),
        (pharmacie_pb2.DESCRIPTOR,'PharmacieService',PharmacieService),(rendezvous_pb2.DESCRIPTOR,'RendezvousService',RendezvousService),
    ]
    for desc,name,cls in pairs:
        missing=[rpc for rpc in methods(desc,name) if not hasattr(cls,rpc)]
        assert not missing, f"{name} proto/service implementation mismatch: {missing}"
    print('PROJECTX BACKEND COMPLETION V3 CONTRACT CHECK: PASS')

if __name__=='__main__': main()
