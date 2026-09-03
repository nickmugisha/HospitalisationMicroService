from __future__ import annotations

import getpass
import secrets
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
from hr.v1 import hr_pb2, hr_pb2_grpc
from maternite.v1 import maternite_pb2, maternite_pb2_grpc
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc
from rendezvous.v1 import rendezvous_pb2, rendezvous_pb2_grpc

AUTH = "127.0.0.1:50051"
ACCUEIL = "127.0.0.1:50052"
HOSP = "127.0.0.1:50053"
PHARM = "127.0.0.1:50057"
MAT = "127.0.0.1:50058"
RDV = "127.0.0.1:50059"
HR = "127.0.0.1:50062"


def md(token: str):
    return (("authorization", f"Bearer {token}"),)


def ts(value: datetime) -> Timestamp:
    value = value.astimezone(timezone.utc)
    result = Timestamp()
    result.FromDatetime(value)
    return result


def ok(label: str, extra: str = ""):
    print(f"[OK] {label}" + (f" — {extra}" if extra else ""))


def expect(code: grpc.StatusCode, fn, label: str):
    try:
        fn()
    except grpc.RpcError as exc:
        if exc.code() != code:
            raise AssertionError(
                f"{label}: expected {code.name}, got {exc.code().name}: {exc.details()}"
            )
        ok(label)
        return
    raise AssertionError(label + ": unexpectedly succeeded")


def main():
    admin_username = input("Admin username: ").strip()
    admin_password = getpass.getpass("Admin password: ")
    suffix = uuid.uuid4().hex[:8].upper()
    low = suffix.lower()
    today = date.today()
    phone_tail = f"{int(suffix, 16) % 1000000:06d}"

    # Test-only identifiers. They intentionally remain recognizable in audit/history.
    doctor_username = f"v3doctor_{low}"
    doctor_password = secrets.token_urlsafe(14)
    employee_number = f"PXV3DOC-{suffix}"
    ward_code = f"V3W{suffix[:4]}"
    supplier_code = f"V3S{suffix[:5]}"
    medicine_code = f"V3M{suffix[:5]}"

    doctor_employee_id = ""
    doctor_user_id = ""
    ward_id = ""
    bed_ids: list[str] = []
    admission_ids: list[str] = []
    assignment_ids: list[str] = []
    supplier_created = False
    medicine_created = False
    future_appointment_id = ""
    future_slot_id = ""

    with (
        grpc.insecure_channel(AUTH) as auth_ch,
        grpc.insecure_channel(ACCUEIL) as accueil_ch,
        grpc.insecure_channel(HOSP) as hosp_ch,
        grpc.insecure_channel(PHARM) as pharm_ch,
        grpc.insecure_channel(MAT) as mat_ch,
        grpc.insecure_channel(RDV) as rdv_ch,
        grpc.insecure_channel(HR) as hr_ch,
    ):
        auth = auth_pb2_grpc.AuthServiceStub(auth_ch)
        accueil = accueil_pb2_grpc.AccueilServiceStub(accueil_ch)
        hosp = hospitalisation_pb2_grpc.HospitalisationServiceStub(hosp_ch)
        pharm = pharmacie_pb2_grpc.PharmacieServiceStub(pharm_ch)
        mat = maternite_pb2_grpc.MaterniteServiceStub(mat_ch)
        rdv = rendezvous_pb2_grpc.RendezvousServiceStub(rdv_ch)
        hr = hr_pb2_grpc.HRServiceStub(hr_ch)

        login = auth.Login(
            auth_pb2.LoginRequest(username=admin_username, password=admin_password), timeout=5
        )
        metadata = md(login.access_token)
        ok("Admin login")

        try:
            # -----------------------------------------------------------------
            # INTERNAL NOTIFICATION SECURITY
            # A normal user JWT must never authorize the private system RPC.
            # -----------------------------------------------------------------
            expect(
                grpc.StatusCode.UNAUTHENTICATED,
                lambda: auth.SendSystemNotification(
                    auth_pb2.SystemNotificationRequest(
                        recipient_id=login.user.id,
                        type="PXV3_TEST",
                        title="Should be rejected",
                        body="External callers must not use the internal notification route.",
                        source_service="regression-test",
                        correlation_id=f"pxv3-{low}",
                    ),
                    metadata=metadata,
                    timeout=5,
                ),
                "Internal notification RPC rejects a user JWT",
            )

            # -----------------------------------------------------------------
            # DOCTOR FIXTURE THROUGH REAL HR -> AUTH APPROVAL WORKFLOW
            # -----------------------------------------------------------------
            registration = hr.RegisterEmployee(
                hr_pb2.RegisterEmployeeRequest(
                    employee_number=employee_number,
                    first_name="Doctor",
                    last_name=f"V3{suffix[:4]}",
                    email=f"{doctor_username}@projectx.test",
                    phone="+25770000000",
                    department="Consultation",
                    job_title="Médecin test E2E",
                    hire_date=today.isoformat(),
                    employment_type="PERMANENT",
                    username=doctor_username,
                    temporary_password=doctor_password,
                ),
                metadata=metadata,
                timeout=8,
            )
            doctor_employee_id = registration.employee.id
            doctor_user_id = registration.employee.auth_user_id
            assert doctor_user_id
            auth.ApproveUser(
                auth_pb2.ApproveUserRequest(
                    user_id=doctor_user_id,
                    role_codes=["MEDECIN"],
                ),
                metadata=metadata,
                timeout=5,
            )
            ok("Test doctor registered by HR and approved by Admin", employee_number)

            doctors = hosp.ListDoctors(
                hospitalisation_pb2.ListDoctorsRequest(search=employee_number, active_only=True),
                metadata=metadata,
                timeout=5,
            )
            assert any(d.user_id == doctor_user_id for d in doctors.doctors)
            ok("Hospitalisation sees the newly approved doctor")

            # -----------------------------------------------------------------
            # TEST PATIENTS
            # -----------------------------------------------------------------
            p1 = accueil.CreatePatient(
                accueil_pb2.CreatePatientRequest(
                    first_name="PXV3",
                    last_name=f"HospitalA{suffix[:4]}",
                    sex=accueil_pb2.SEX_MALE,
                    birth_date="1990-01-01",
                    phone=f"+257711{phone_tail}",
                    address="ProjectX regression fixture",
                ),
                metadata=metadata,
                timeout=5,
            ).patient
            p2 = accueil.CreatePatient(
                accueil_pb2.CreatePatientRequest(
                    first_name="PXV3",
                    last_name=f"HospitalB{suffix[:4]}",
                    sex=accueil_pb2.SEX_FEMALE,
                    birth_date="1994-02-02",
                    phone=f"+257722{phone_tail}",
                    address="ProjectX regression fixture",
                ),
                metadata=metadata,
                timeout=5,
            ).patient
            p3 = accueil.CreatePatient(
                accueil_pb2.CreatePatientRequest(
                    first_name="PXV3",
                    last_name=f"Maternity{suffix[:4]}",
                    sex=accueil_pb2.SEX_FEMALE,
                    birth_date="1995-03-03",
                    phone=f"+257733{phone_tail}",
                    address="ProjectX regression fixture",
                ),
                metadata=metadata,
                timeout=5,
            ).patient
            ok("Three isolated PXV3 test patients created")

            # -----------------------------------------------------------------
            # HOSPITAL STRUCTURE + BEDS
            # -----------------------------------------------------------------
            ward = hosp.CreateWard(
                hospitalisation_pb2.CreateWardRequest(
                    code=ward_code,
                    name=f"PXV3 Test Ward {suffix}",
                    daily_rate_minor=1,
                    currency="BIF",
                ),
                metadata=metadata,
                timeout=5,
            ).ward
            ward_id = ward.id
            room = hosp.CreateRoom(
                hospitalisation_pb2.CreateRoomRequest(
                    ward_id=ward.id,
                    code="T01",
                    name="PXV3 Test Room",
                ),
                metadata=metadata,
                timeout=5,
            ).room
            for code in ("B01", "B02"):
                bed = hosp.CreateBed(
                    hospitalisation_pb2.CreateBedRequest(room_id=room.id, code=code),
                    metadata=metadata,
                    timeout=5,
                ).bed
                bed_ids.append(bed.id)
            ok("Ward, room and two beds created")

            oos = hosp.SetBedStatus(
                hospitalisation_pb2.SetBedStatusRequest(
                    bed_id=bed_ids[0],
                    status=hospitalisation_pb2.BED_STATUS_OUT_OF_SERVICE,
                    reason="PXV3 status guard test",
                ),
                metadata=metadata,
                timeout=5,
            ).bed
            assert oos.status == hospitalisation_pb2.BED_STATUS_OUT_OF_SERVICE
            back = hosp.SetBedStatus(
                hospitalisation_pb2.SetBedStatusRequest(
                    bed_id=bed_ids[0],
                    status=hospitalisation_pb2.BED_STATUS_AVAILABLE,
                    reason="PXV3 return test bed to service",
                ),
                metadata=metadata,
                timeout=5,
            ).bed
            assert back.status == hospitalisation_pb2.BED_STATUS_AVAILABLE
            ok("Bed OUT_OF_SERVICE -> AVAILABLE management")

            # -----------------------------------------------------------------
            # DOCTOR ASSIGNMENT + BUSY WARNING WITH TWO CONCURRENT PATIENTS
            # -----------------------------------------------------------------
            for idx, patient in enumerate((p1, p2), 1):
                admission = hosp.CreateAdmission(
                    hospitalisation_pb2.CreateAdmissionRequest(
                        patient_id=patient.id,
                        reason=f"PXV3 doctor workload patient {idx}",
                        preferred_ward=ward_code,
                        correlation_id=f"pxv3-adm-{low}-{idx}",
                        idempotency_key=f"pxv3-adm-{low}-{idx}",
                    ),
                    metadata=metadata,
                    timeout=5,
                ).admission
                admission_ids.append(admission.id)
                hosp.ApproveAdmission(
                    hospitalisation_pb2.ApproveAdmissionRequest(
                        admission_id=admission.id,
                        reason="PXV3 admin approval regression",
                    ),
                    metadata=metadata,
                    timeout=5,
                )
                hosp.AssignBed(
                    hospitalisation_pb2.AssignBedRequest(
                        admission_id=admission.id,
                        bed_id=bed_ids[idx - 1],
                        idempotency_key=f"pxv3-bed-{low}-{idx}",
                    ),
                    metadata=metadata,
                    timeout=5,
                )

            first = hosp.AssignDoctor(
                hospitalisation_pb2.AssignDoctorRequest(
                    admission_id=admission_ids[0],
                    doctor_user_id=doctor_user_id,
                    idempotency_key=f"pxv3-doc-{low}-1",
                ),
                metadata=metadata,
                timeout=5,
            )
            assignment_ids.append(first.assignment.id)
            assert not first.busy_warning
            ok("First doctor assignment has no busy warning")

            second = hosp.AssignDoctor(
                hospitalisation_pb2.AssignDoctorRequest(
                    admission_id=admission_ids[1],
                    doctor_user_id=doctor_user_id,
                    idempotency_key=f"pxv3-doc-{low}-2",
                ),
                metadata=metadata,
                timeout=5,
            )
            assignment_ids.append(second.assignment.id)
            assert second.busy_warning
            assert second.doctor.active_assignment_count >= 2
            ok("Second doctor assignment succeeds with busy warning", second.warning_message)

            current = hosp.ListDoctors(
                hospitalisation_pb2.ListDoctorsRequest(search=employee_number, active_only=True),
                metadata=metadata,
                timeout=5,
            )
            doctor = next(d for d in current.doctors if d.user_id == doctor_user_id)
            assert doctor.active_assignment_count >= 2 and doctor.busy
            ok("Doctor workload reports two active patients")

            # AssignDoctor uses the private Auth system-notification route internally.
            notes = auth.ListNotifications(
                auth_pb2.ListNotificationsRequest(recipient_id=doctor_user_id),
                metadata=metadata,
                timeout=5,
            )
            assert any(n.type == "HOSPITALISATION_ASSIGNMENT" for n in notes.notifications)
            ok("Internal service notification delivered to assigned doctor")

            for idx, assignment_id in enumerate(assignment_ids, 1):
                hosp.CompleteDoctorAssignment(
                    hospitalisation_pb2.CompleteDoctorAssignmentRequest(
                        assignment_id=assignment_id,
                        note=f"PXV3 assignment {idx} complete",
                    ),
                    metadata=metadata,
                    timeout=5,
                )
            after = hosp.ListDoctors(
                hospitalisation_pb2.ListDoctorsRequest(search=employee_number, active_only=True),
                metadata=metadata,
                timeout=5,
            )
            doctor_after = next(d for d in after.doctors if d.user_id == doctor_user_id)
            assert doctor_after.active_assignment_count == 0 and not doctor_after.busy
            ok("Doctor workload returns to zero after completing assignments")

            # Discharge both test admissions so no active admission or occupied test bed remains.
            for idx, admission_id in enumerate(admission_ids, 1):
                discharged = hosp.DischargePatient(
                    hospitalisation_pb2.DischargePatientRequest(
                        admission_id=admission_id,
                        discharge_summary="PXV3 regression discharge",
                        idempotency_key=f"pxv3-discharge-{low}-{idx}",
                    ),
                    metadata=metadata,
                    timeout=8,
                ).admission
                assert discharged.status == hospitalisation_pb2.ADMISSION_STATUS_DISCHARGED
            ok("Both PXV3 admissions discharged and test beds released")

            # -----------------------------------------------------------------
            # RENDEZ-VOUS: UPDATE/BLOCK + TIMED REMINDER + NO_SHOW
            # -----------------------------------------------------------------
            now = datetime.now(timezone.utc)
            slot = rdv.CreateScheduleSlot(
                rendezvous_pb2.CreateScheduleSlotRequest(
                    provider_id=doctor_user_id,
                    service="PXV3 TEST",
                    start_at=ts(now + timedelta(days=1, hours=1)),
                    end_at=ts(now + timedelta(days=1, hours=2)),
                    idempotency_key=f"pxv3-slot-{low}-future",
                ),
                metadata=metadata,
                timeout=5,
            ).slot
            future_slot_id = slot.id
            updated = rdv.UpdateScheduleSlot(
                rendezvous_pb2.UpdateScheduleSlotRequest(
                    slot_id=slot.id,
                    provider_id=doctor_user_id,
                    service="PXV3 TEST UPDATED",
                    start_at=ts(now + timedelta(days=1, hours=2)),
                    end_at=ts(now + timedelta(days=1, hours=3)),
                    reason="PXV3 update schedule regression",
                ),
                metadata=metadata,
                timeout=5,
            ).slot
            assert updated.service == "PXV3 TEST UPDATED"
            ok("Schedule slot update")

            future_appt = rdv.CreateAppointment(
                rendezvous_pb2.CreateAppointmentRequest(
                    patient_id=p1.id,
                    slot_id=slot.id,
                    reason="PXV3 timed reminder test",
                    idempotency_key=f"pxv3-appt-{low}-future",
                    correlation_id=f"pxv3-rdv-{low}",
                    request_reminder=True,
                    reminder_recipient_user_id=doctor_user_id,
                    reminder_lead_minutes=60,
                ),
                metadata=metadata,
                timeout=5,
            ).appointment
            future_appointment_id = future_appt.id
            assert future_appt.reminder_status == rendezvous_pb2.REMINDER_STATUS_PENDING
            assert future_appt.HasField("reminder_due_at")
            ok("Appointment reminder scheduled with a real due time")

            cancelled = rdv.CancelAppointment(
                rendezvous_pb2.CancelAppointmentRequest(
                    appointment_id=future_appt.id,
                    reason="PXV3 cleanup after reminder scheduling test",
                    idempotency_key=f"pxv3-cancel-{low}-future",
                ),
                metadata=metadata,
                timeout=5,
            ).appointment
            assert cancelled.status == rendezvous_pb2.APPOINTMENT_STATUS_CANCELLED
            blocked = rdv.BlockScheduleSlot(
                rendezvous_pb2.BlockScheduleSlotRequest(
                    slot_id=slot.id,
                    reason="PXV3 finalize test slot",
                ),
                metadata=metadata,
                timeout=5,
            ).slot
            assert blocked.status == rendezvous_pb2.SCHEDULE_SLOT_STATUS_BLOCKED
            ok("Cancelled appointment releases slot; slot can then be blocked")

            # Positive NO_SHOW transition with a short real-time slot.
            now2 = datetime.now(timezone.utc)
            short_slot = rdv.CreateScheduleSlot(
                rendezvous_pb2.CreateScheduleSlotRequest(
                    provider_id=doctor_user_id,
                    service="PXV3 NOSHOW",
                    start_at=ts(now2 + timedelta(seconds=8)),
                    end_at=ts(now2 + timedelta(seconds=10)),
                    idempotency_key=f"pxv3-slot-{low}-noshow",
                ),
                metadata=metadata,
                timeout=5,
            ).slot
            short_appt = rdv.CreateAppointment(
                rendezvous_pb2.CreateAppointmentRequest(
                    patient_id=p2.id,
                    slot_id=short_slot.id,
                    reason="PXV3 no-show transition",
                    idempotency_key=f"pxv3-appt-{low}-noshow",
                    correlation_id=f"pxv3-noshow-{low}",
                ),
                metadata=metadata,
                timeout=5,
            ).appointment
            expect(
                grpc.StatusCode.FAILED_PRECONDITION,
                lambda: rdv.MarkNoShow(
                    rendezvous_pb2.MarkNoShowRequest(
                        appointment_id=short_appt.id,
                        reason="too early",
                    ),
                    metadata=metadata,
                    timeout=5,
                ),
                "NO_SHOW is blocked before slot end",
            )
            time.sleep(11)
            no_show = rdv.MarkNoShow(
                rendezvous_pb2.MarkNoShowRequest(
                    appointment_id=short_appt.id,
                    reason="PXV3 slot ended",
                ),
                metadata=metadata,
                timeout=5,
            ).appointment
            assert no_show.status == rendezvous_pb2.APPOINTMENT_STATUS_NO_SHOW
            ok("NO_SHOW transition after slot end")

            # -----------------------------------------------------------------
            # PHARMACY CATALOG + PROCUREMENT WRITE PATHS ON ISOLATED FIXTURES
            # -----------------------------------------------------------------
            med = pharm.CreateMedicine(
                pharmacie_pb2.CreateMedicineRequest(
                    code=medicine_code,
                    name=f"PXV3 Medicine {suffix}",
                    form="TEST",
                    strength="1 unit",
                    unit="unit",
                    sale_price_minor=1,
                    currency="BIF",
                    reorder_level=0,
                    active=True,
                ),
                metadata=metadata,
                timeout=5,
            ).medicine
            medicine_created = True
            supplier = pharm.CreateSupplier(
                pharmacie_pb2.CreateSupplierRequest(
                    code=supplier_code,
                    name=f"PXV3 Supplier {suffix}",
                    phone="+25770000001",
                    email=f"supplier-{low}@projectx.test",
                ),
                metadata=metadata,
                timeout=5,
            ).supplier
            supplier_created = True
            updated_supplier = pharm.UpdateSupplier(
                pharmacie_pb2.UpdateSupplierRequest(
                    supplier_code=supplier_code,
                    name=f"PXV3 Supplier Updated {suffix}",
                    phone="+25770000002",
                    email=f"supplier-updated-{low}@projectx.test",
                    active=True,
                ),
                metadata=metadata,
                timeout=5,
            ).supplier
            assert "Updated" in updated_supplier.name
            ok("Pharmacy medicine + supplier create/update")

            po = pharm.CreatePurchaseOrder(
                pharmacie_pb2.CreatePurchaseOrderRequest(
                    supplier_code=supplier_code,
                    items=[pharmacie_pb2.PurchaseOrderItemInput(medicine_code=medicine_code, quantity=2)],
                    idempotency_key=f"pxv3-po-{low}",
                ),
                metadata=metadata,
                timeout=5,
            ).purchase_order
            expect(
                grpc.StatusCode.FAILED_PRECONDITION,
                lambda: pharm.ReceivePurchaseOrder(
                    pharmacie_pb2.ReceivePurchaseOrderRequest(
                        purchase_order_id=po.id,
                        items=[
                            pharmacie_pb2.PurchaseReceiptItem(
                                medicine_code=medicine_code,
                                batch_number=f"PXV3-{suffix[:4]}",
                                expiry_date=(today - timedelta(days=1)).isoformat(),
                                quantity=2,
                            )
                        ],
                        idempotency_key=f"pxv3-receive-expired-{low}",
                    ),
                    metadata=metadata,
                    timeout=5,
                ),
                "Expired purchase-order batch rejected",
            )
            received = pharm.ReceivePurchaseOrder(
                pharmacie_pb2.ReceivePurchaseOrderRequest(
                    purchase_order_id=po.id,
                    items=[
                        pharmacie_pb2.PurchaseReceiptItem(
                            medicine_code=medicine_code,
                            batch_number=f"PXV3-{suffix[:4]}",
                            expiry_date=(today + timedelta(days=365)).isoformat(),
                            quantity=2,
                        )
                    ],
                    idempotency_key=f"pxv3-receive-{low}",
                ),
                metadata=metadata,
                timeout=5,
            ).purchase_order
            assert received.status == pharmacie_pb2.PURCHASE_ORDER_STATUS_RECEIVED
            stock = pharm.GetStock(
                pharmacie_pb2.GetStockRequest(medicine_ref=medicine_code),
                metadata=metadata,
                timeout=5,
            ).stock
            assert stock.total_available == 2
            ok("Purchase order received into isolated PXV3 medicine stock")

            pharm.UpdateMedicine(
                pharmacie_pb2.UpdateMedicineRequest(
                    medicine_ref=medicine_code,
                    active=False,
                ),
                metadata=metadata,
                timeout=5,
            )
            medicine_created = False
            pharm.UpdateSupplier(
                pharmacie_pb2.UpdateSupplierRequest(
                    supplier_code=supplier_code,
                    active=False,
                ),
                metadata=metadata,
                timeout=5,
            )
            supplier_created = False
            ok("PXV3 pharmacy fixtures deactivated after terminal PO receipt")

            # -----------------------------------------------------------------
            # MATERNITY CASE: GUARD -> LABOR -> DELIVERY -> NEWBORN -> CLOSE
            # -----------------------------------------------------------------
            case = mat.CreateMaternityCase(
                maternite_pb2.CreateMaternityCaseRequest(
                    patient_id=p3.id,
                    gravida=1,
                    para=0,
                    lmp_date=(today - timedelta(days=270)).isoformat(),
                    edd=(today + timedelta(days=10)).isoformat(),
                    risk_level=maternite_pb2.RISK_LEVEL_LOW,
                    referral_reason="PXV3 write E2E",
                    idempotency_key=f"pxv3-mat-{low}",
                    correlation_id=f"pxv3-mat-corr-{low}",
                ),
                metadata=metadata,
                timeout=5,
            ).record
            preg_id = case.pregnancy.id
            expect(
                grpc.StatusCode.FAILED_PRECONDITION,
                lambda: mat.CloseMaternityCase(
                    maternite_pb2.CloseMaternityCaseRequest(
                        pregnancy_id=preg_id,
                        reason="too early",
                    ),
                    metadata=metadata,
                    timeout=5,
                ),
                "Maternity case cannot close before delivery",
            )
            mat.AdmitForLabor(
                maternite_pb2.AdmitForLaborRequest(
                    pregnancy_id=preg_id,
                    admitted_at=ts(datetime.now(timezone.utc)),
                    reason="PXV3 labor admission",
                    idempotency_key=f"pxv3-labor-{low}",
                ),
                metadata=metadata,
                timeout=5,
            )
            delivery = mat.RecordDelivery(
                maternite_pb2.RecordDeliveryRequest(
                    pregnancy_id=preg_id,
                    delivered_at=ts(datetime.now(timezone.utc)),
                    mode=maternite_pb2.DELIVERY_MODE_VAGINAL,
                    outcome=maternite_pb2.DELIVERY_OUTCOME_LIVE_BIRTH,
                    complications="None - PXV3 fixture",
                    idempotency_key=f"pxv3-delivery-{low}",
                ),
                metadata=metadata,
                timeout=8,
            ).delivery
            mat.RegisterNewborn(
                maternite_pb2.RegisterNewbornRequest(
                    delivery_id=delivery.id,
                    sex=maternite_pb2.NEWBORN_SEX_FEMALE,
                    weight_g=3200,
                    apgar_1=8,
                    apgar_5=9,
                    status=maternite_pb2.NEWBORN_STATUS_STABLE,
                    idempotency_key=f"pxv3-newborn-{low}",
                ),
                metadata=metadata,
                timeout=5,
            )
            closed = mat.CloseMaternityCase(
                maternite_pb2.CloseMaternityCaseRequest(
                    pregnancy_id=preg_id,
                    reason="PXV3 terminal close regression",
                ),
                metadata=metadata,
                timeout=5,
            ).record
            assert closed.pregnancy.status == maternite_pb2.PREGNANCY_STATUS_CLOSED
            ok("Maternity delivered case + newborn + close workflow")

            # Finalize test ward as inactive after all beds are released.
            inactive_ward = hosp.UpdateWard(
                hospitalisation_pb2.UpdateWardRequest(
                    ward_id=ward_id,
                    name=f"PXV3 Test Ward {suffix} (inactive)",
                    active=False,
                    daily_rate_minor=1,
                    currency="BIF",
                ),
                metadata=metadata,
                timeout=5,
            ).ward
            assert not inactive_ward.active
            ward_id = ""
            ok("PXV3 test ward disabled after discharge")

            # Finalize doctor identity as terminated, preserving HR/Audit history.
            hr.SetEmploymentStatus(
                hr_pb2.SetEmploymentStatusRequest(
                    employee_id=doctor_employee_id,
                    status=hr_pb2.EMPLOYMENT_STATUS_TERMINATED,
                    reason="PXV3 final write E2E completed",
                ),
                metadata=metadata,
                timeout=5,
            )
            doctor_employee_id = ""
            ok("PXV3 test doctor terminated after regression")

            print("\nPROJECTX BACKEND COMPLETION V3 FINAL WRITE/SECURITY E2E: PASS")

        finally:
            # Best-effort cleanup for test-only fixtures if a later assertion fails.
            # Never deletes clinical/audit history; it only tries to end active test state.
            for assignment_id in assignment_ids:
                try:
                    hosp.CompleteDoctorAssignment(
                        hospitalisation_pb2.CompleteDoctorAssignmentRequest(
                            assignment_id=assignment_id,
                            note="PXV3 best-effort cleanup",
                        ),
                        metadata=metadata,
                        timeout=3,
                    )
                except grpc.RpcError:
                    pass
            for idx, admission_id in enumerate(admission_ids, 1):
                try:
                    hosp.DischargePatient(
                        hospitalisation_pb2.DischargePatientRequest(
                            admission_id=admission_id,
                            discharge_summary="PXV3 best-effort cleanup",
                            idempotency_key=f"pxv3-clean-discharge-{low}-{idx}",
                        ),
                        metadata=metadata,
                        timeout=5,
                    )
                except grpc.RpcError:
                    pass
            if future_appointment_id:
                try:
                    rdv.CancelAppointment(
                        rendezvous_pb2.CancelAppointmentRequest(
                            appointment_id=future_appointment_id,
                            reason="PXV3 best-effort cleanup",
                            idempotency_key=f"pxv3-clean-appt-{low}",
                        ),
                        metadata=metadata,
                        timeout=3,
                    )
                except grpc.RpcError:
                    pass
            if future_slot_id:
                try:
                    rdv.BlockScheduleSlot(
                        rendezvous_pb2.BlockScheduleSlotRequest(
                            slot_id=future_slot_id,
                            reason="PXV3 best-effort cleanup",
                        ),
                        metadata=metadata,
                        timeout=3,
                    )
                except grpc.RpcError:
                    pass
            if medicine_created:
                try:
                    pharm.UpdateMedicine(
                        pharmacie_pb2.UpdateMedicineRequest(
                            medicine_ref=medicine_code,
                            active=False,
                        ),
                        metadata=metadata,
                        timeout=3,
                    )
                except grpc.RpcError:
                    pass
            if supplier_created:
                try:
                    pharm.UpdateSupplier(
                        pharmacie_pb2.UpdateSupplierRequest(
                            supplier_code=supplier_code,
                            active=False,
                        ),
                        metadata=metadata,
                        timeout=3,
                    )
                except grpc.RpcError:
                    pass
            if ward_id:
                try:
                    hosp.UpdateWard(
                        hospitalisation_pb2.UpdateWardRequest(
                            ward_id=ward_id,
                            name=f"PXV3 Test Ward {suffix} (cleanup)",
                            active=False,
                            daily_rate_minor=1,
                            currency="BIF",
                        ),
                        metadata=metadata,
                        timeout=3,
                    )
                except grpc.RpcError:
                    pass
            if doctor_employee_id:
                try:
                    hr.SetEmploymentStatus(
                        hr_pb2.SetEmploymentStatusRequest(
                            employee_id=doctor_employee_id,
                            status=hr_pb2.EMPLOYMENT_STATUS_TERMINATED,
                            reason="PXV3 best-effort cleanup after regression failure",
                        ),
                        metadata=metadata,
                        timeout=5,
                    )
                except grpc.RpcError:
                    pass


if __name__ == "__main__":
    try:
        main()
    except grpc.RpcError as exc:
        print("\nPROJECTX BACKEND COMPLETION V3 FINAL WRITE/SECURITY E2E: FAIL")
        print("STATUS:", exc.code().name)
        print("DETAIL:", exc.details())
        raise
