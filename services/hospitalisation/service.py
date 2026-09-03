from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from auth.v1 import auth_pb2, auth_pb2_grpc
from billing.v1 import billing_pb2, billing_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from services.common.notifications import send_system_notification
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
from database.hospitalisation_session import HospitalisationSessionLocal, engine
from services.common.auth_guard import require_permission
from services.hospitalisation.config import ACCUEIL_GRPC_TARGET, AUTH_GRPC_TARGET, BILLING_GRPC_TARGET, SERVICE_VERSION
from services.hospitalisation.models import Admission, Bed, BillingOutbox, DoctorAssignment, Room, StayNote, Transfer, Ward
from services.hospitalisation.repository import (
    get_admission,
    get_admission_by_key,
    get_bed,
    get_current_admission,
    get_transfer_by_key,
    list_beds,
)

logger = logging.getLogger("projectx.hospitalisation.service")

BED_STATUS_DB_TO_PROTO = {
    "AVAILABLE": hospitalisation_pb2.BED_STATUS_AVAILABLE,
    "OCCUPIED": hospitalisation_pb2.BED_STATUS_OCCUPIED,
    "OUT_OF_SERVICE": hospitalisation_pb2.BED_STATUS_OUT_OF_SERVICE,
}
ADMISSION_STATUS_DB_TO_PROTO = {
    "PENDING": hospitalisation_pb2.ADMISSION_STATUS_PENDING,
    "ADMITTED": hospitalisation_pb2.ADMISSION_STATUS_ADMITTED,
    "DISCHARGED": hospitalisation_pb2.ADMISSION_STATUS_DISCHARGED,
    "CANCELLED": hospitalisation_pb2.ADMISSION_STATUS_CANCELLED,
}
DOCTOR_STATUS_DB_TO_PROTO = {
    "ACTIVE": hospitalisation_pb2.DOCTOR_ASSIGNMENT_STATUS_ACTIVE,
    "COMPLETED": hospitalisation_pb2.DOCTOR_ASSIGNMENT_STATUS_COMPLETED,
    "CANCELLED": hospitalisation_pb2.DOCTOR_ASSIGNMENT_STATUS_CANCELLED,
}
DOCTOR_STATUS_PROTO_TO_DB = {v:k for k,v in DOCTOR_STATUS_DB_TO_PROTO.items()}

BILLING_DB_TO_PROTO = {
    "NOT_CREATED": hospitalisation_pb2.BILLING_CHARGE_STATUS_NOT_CREATED,
    "PENDING_DELIVERY": hospitalisation_pb2.BILLING_CHARGE_STATUS_PENDING_DELIVERY,
    "DELIVERED": hospitalisation_pb2.BILLING_CHARGE_STATUS_DELIVERED,
    "FAILED": hospitalisation_pb2.BILLING_CHARGE_STATUS_FAILED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_timestamp(value: datetime | None) -> Timestamp:
    result = Timestamp()
    if value is not None:
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        result.FromDatetime(aware)
    return result


def generate_admission_number() -> str:
    return f"ADM-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _authorization_metadata(context):
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization" and item.value.strip():
            return (("authorization", item.value.strip()),)
    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing authorization metadata.")


def _deliver_billing_charge(context, outbox: BillingOutbox, correlation_id: str, admission_number: str) -> bool:
    try:
        with grpc.insecure_channel(BILLING_GRPC_TARGET) as channel:
            stub = billing_pb2_grpc.BillingServiceStub(channel)
            stub.CreateCharge(
                billing_pb2.CreateChargeRequest(
                    source_type="HOSPITALISATION",
                    source_id=outbox.admission_id,
                    patient_id=outbox.patient_id,
                    amount_minor=outbox.amount_minor,
                    currency_code=outbox.currency,
                    description=f"Hospitalisation - {admission_number}",
                    idempotency_key=outbox.idempotency_key,
                    correlation_id=correlation_id,
                ),
                metadata=_authorization_metadata(context),
                timeout=5,
            )
        return True
    except grpc.RpcError as error:
        logger.warning(
            "billing delivery deferred source=HOSPITALISATION source_id=%s status=%s detail=%s",
            outbox.admission_id, error.code().name, error.details(),
        )
        return False


def validate_patient_exists(context, patient_id: str):
    try:
        with grpc.insecure_channel(ACCUEIL_GRPC_TARGET) as channel:
            stub = accueil_pb2_grpc.AccueilServiceStub(channel)
            response = stub.GetPatient(
                accueil_pb2.GetPatientRequest(patient_id=patient_id),
                metadata=_authorization_metadata(context),
                timeout=3,
            )
    except grpc.RpcError as error:
        if error.code() == grpc.StatusCode.NOT_FOUND:
            context.abort(grpc.StatusCode.NOT_FOUND, "Patient not found in Accueil.")
        if error.code() in (grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED):
            context.abort(error.code(), error.details() or "Patient access denied.")
        context.abort(grpc.StatusCode.UNAVAILABLE, f"Accueil service unavailable: {error.code().name}")
    if accueil_pb2.PatientStatus.Name(response.patient.status) != "PATIENT_STATUS_ACTIVE":
        context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Patient is not ACTIVE.")
    return response.patient


def ward_to_proto(item):
    return hospitalisation_pb2.Ward(
        id=item.id, code=item.code, name=item.name, active=item.active,
        daily_rate_minor=item.daily_rate_minor, currency=item.currency,
    )


def room_to_proto(item):
    return hospitalisation_pb2.Room(id=item.id, code=item.code, name=item.name, ward=ward_to_proto(item.ward))


def bed_to_proto(item):
    return hospitalisation_pb2.Bed(
        id=item.id, code=item.code, room=room_to_proto(item.room),
        status=BED_STATUS_DB_TO_PROTO.get(item.status, hospitalisation_pb2.BED_STATUS_UNSPECIFIED),
    )


def admission_to_proto(item: Admission):
    result = hospitalisation_pb2.Admission(
        id=item.id,
        admission_number=item.admission_number,
        patient_id=item.patient_id,
        consultation_id=item.consultation_id or "",
        reason=item.reason,
        preferred_ward=item.preferred_ward or "",
        status=ADMISSION_STATUS_DB_TO_PROTO.get(item.status, hospitalisation_pb2.ADMISSION_STATUS_UNSPECIFIED),
        created_at=to_timestamp(item.created_at),
        admitted_at=to_timestamp(item.admitted_at),
        discharged_at=to_timestamp(item.discharged_at),
        discharge_summary=item.discharge_summary or "",
        created_by=item.created_by,
        billing_charge_status=BILLING_DB_TO_PROTO.get(item.billing_charge_status, hospitalisation_pb2.BILLING_CHARGE_STATUS_UNSPECIFIED),
        correlation_id=item.correlation_id,
        approved_at=to_timestamp(item.approved_at),
        approved_by=item.approved_by or "",
        approval_reason=item.approval_reason or "",
    )
    if item.current_bed is not None:
        result.current_bed.CopyFrom(bed_to_proto(item.current_bed))
    return result


def transfer_to_proto(item: Transfer):
    return hospitalisation_pb2.Transfer(
        id=item.id, admission_id=item.admission_id,
        from_bed_id=item.from_bed_id, to_bed_id=item.to_bed_id,
        requested_at=to_timestamp(item.requested_at), completed_at=to_timestamp(item.completed_at), actor_id=item.actor_id,
    )


def stay_note_to_proto(item: StayNote):
    return hospitalisation_pb2.StayNote(
        id=item.id, admission_id=item.admission_id, note=item.note,
        actor_id=item.actor_id, created_at=to_timestamp(item.created_at),
    )


def doctor_assignment_to_proto(item: DoctorAssignment):
    return hospitalisation_pb2.DoctorAssignment(
        id=item.id, admission_id=item.admission_id, doctor_user_id=item.doctor_user_id,
        assigned_by=item.assigned_by, status=DOCTOR_STATUS_DB_TO_PROTO.get(item.status, hospitalisation_pb2.DOCTOR_ASSIGNMENT_STATUS_UNSPECIFIED),
        assigned_at=to_timestamp(item.assigned_at), completed_at=to_timestamp(item.completed_at),
        completion_note=item.completion_note or "",
    )


def _directory_entry(context, user_id: str):
    try:
        with grpc.insecure_channel(AUTH_GRPC_TARGET) as channel:
            return auth_pb2_grpc.AuthServiceStub(channel).GetStaffDirectoryEntry(
                auth_pb2.GetStaffDirectoryEntryRequest(user_id=user_id), metadata=_authorization_metadata(context), timeout=3
            ).entry
    except grpc.RpcError as error:
        if error.code() in (grpc.StatusCode.NOT_FOUND, grpc.StatusCode.PERMISSION_DENIED, grpc.StatusCode.UNAUTHENTICATED):
            context.abort(error.code(), error.details() or "Doctor directory lookup denied.")
        context.abort(grpc.StatusCode.UNAVAILABLE, f"Auth staff directory unavailable: {error.code().name}")


def _doctor_summary_from_entry(session, entry):
    count = int(session.scalar(select(func.count()).select_from(DoctorAssignment).where(
        DoctorAssignment.doctor_user_id == entry.user_id, DoctorAssignment.status == "ACTIVE"
    )) or 0)
    return hospitalisation_pb2.DoctorSummary(
        user_id=entry.user_id, display_name=entry.display_name, employee_number=entry.employee_number,
        department=entry.department, job_title=entry.job_title, active_assignment_count=count, busy=count > 0,
    )


def _set_health_enum(response, desired: str) -> None:
    field = response.DESCRIPTOR.fields_by_name.get("status")
    if field is None or field.enum_type is None:
        return
    for name in (desired, f"HEALTH_STATUS_{desired}", f"STATUS_{desired}"):
        value = field.enum_type.values_by_name.get(name)
        if value is not None:
            response.status = value.number
            return


def build_health_response(desired: str, message: str):
    return build_health_response_compat("hospitalisation", desired, message, SERVICE_VERSION)

class HospitalisationService(hospitalisation_pb2_grpc.HospitalisationServiceServicer):
    def ListWards(self, request, context):
        require_permission(context,"hospitalisation.read")
        session=HospitalisationSessionLocal()
        try:
            stmt=select(Ward)
            if request.active_only: stmt=stmt.where(Ward.active.is_(True))
            items=list(session.scalars(stmt.order_by(Ward.code)).all())
            return hospitalisation_pb2.ListWardsResponse(wards=[ward_to_proto(x) for x in items],total=len(items))
        finally: session.close()

    def CreateWard(self, request, context):
        actor=require_permission(context,"hospitalisation.structure.manage")
        code=request.code.strip().upper(); name=request.name.strip()
        if not code or not name: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"ward code and name are required.")
        if request.daily_rate_minor < 0: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"daily_rate_minor cannot be negative.")
        session=HospitalisationSessionLocal()
        try:
            if session.scalar(select(Ward).where(Ward.code==code)):
                context.abort(grpc.StatusCode.ALREADY_EXISTS,"Ward code already exists.")
            item=Ward(code=code,name=name,active=True,daily_rate_minor=request.daily_rate_minor,currency=request.currency.strip().upper() or "BIF")
            session.add(item); session.commit(); session.refresh(item)
            logger.info("rpc=CreateWard peer=%s actor=%s ward=%s outcome=OK",context.peer(),actor.id,item.code)
            return hospitalisation_pb2.WardResponse(ward=ward_to_proto(item))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.ALREADY_EXISTS,"Ward code already exists.")
        finally: session.close()

    def UpdateWard(self, request, context):
        actor=require_permission(context,"hospitalisation.structure.manage")
        session=HospitalisationSessionLocal()
        try:
            item=session.get(Ward,request.ward_id.strip())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Ward not found.")
            if request.name.strip(): item.name=request.name.strip()
            if request.HasField("daily_rate_minor") and request.daily_rate_minor < 0: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"daily_rate_minor cannot be negative.")
            if request.HasField("daily_rate_minor"): item.daily_rate_minor=request.daily_rate_minor
            item.currency=request.currency.strip().upper() or item.currency
            if request.HasField("active"):
                if item.active and not request.active:
                    occupied = session.scalar(
                        select(Admission.id)
                        .join(Bed, Admission.current_bed_id == Bed.id)
                        .join(Room, Bed.room_id == Room.id)
                        .where(Room.ward_id == item.id, Admission.status == "ADMITTED")
                        .limit(1)
                    )
                    if occupied:
                        context.abort(grpc.StatusCode.FAILED_PRECONDITION, "A ward with an occupied bed cannot be disabled.")
                item.active=request.active
            session.commit(); session.refresh(item)
            logger.info("rpc=UpdateWard peer=%s actor=%s ward=%s outcome=OK",context.peer(),actor.id,item.code)
            return hospitalisation_pb2.WardResponse(ward=ward_to_proto(item))
        finally: session.close()

    def ListRooms(self, request, context):
        require_permission(context,"hospitalisation.read")
        session=HospitalisationSessionLocal()
        try:
            stmt=select(Room).options(joinedload(Room.ward)).join(Ward)
            if request.ward_id.strip(): stmt=stmt.where(Room.ward_id==request.ward_id.strip())
            if request.ward_code.strip(): stmt=stmt.where(Ward.code==request.ward_code.strip().upper())
            items=list(session.scalars(stmt.order_by(Ward.code,Room.code)).unique().all())
            return hospitalisation_pb2.ListRoomsResponse(rooms=[room_to_proto(x) for x in items],total=len(items))
        finally: session.close()

    def CreateRoom(self, request, context):
        actor=require_permission(context,"hospitalisation.structure.manage")
        code=request.code.strip().upper(); name=request.name.strip()
        if not request.ward_id.strip() or not code or not name: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"ward_id, code and name are required.")
        session=HospitalisationSessionLocal()
        try:
            ward=session.get(Ward,request.ward_id.strip())
            if ward is None: context.abort(grpc.StatusCode.NOT_FOUND,"Ward not found.")
            if not ward.active: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Cannot create a room in an inactive ward.")
            if session.scalar(select(Room).where(Room.ward_id==ward.id,Room.code==code)):
                context.abort(grpc.StatusCode.ALREADY_EXISTS,"Room code already exists in this ward.")
            item=Room(ward_id=ward.id,code=code,name=name); session.add(item); session.commit(); session.refresh(item); _=item.ward
            logger.info("rpc=CreateRoom peer=%s actor=%s room=%s outcome=OK",context.peer(),actor.id,item.id)
            return hospitalisation_pb2.RoomResponse(room=room_to_proto(item))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.ALREADY_EXISTS,"Room code already exists in this ward.")
        finally: session.close()

    def UpdateRoom(self, request, context):
        actor=require_permission(context,"hospitalisation.structure.manage")
        session=HospitalisationSessionLocal()
        try:
            item=session.scalar(select(Room).options(joinedload(Room.ward)).where(Room.id==request.room_id.strip()))
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Room not found.")
            if not request.name.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"name is required.")
            item.name=request.name.strip(); session.commit(); session.refresh(item); _=item.ward
            logger.info("rpc=UpdateRoom peer=%s actor=%s room=%s outcome=OK",context.peer(),actor.id,item.id)
            return hospitalisation_pb2.RoomResponse(room=room_to_proto(item))
        finally: session.close()

    def CreateBed(self, request, context):
        actor=require_permission(context,"hospitalisation.structure.manage")
        code=request.code.strip().upper()
        if not request.room_id.strip() or not code: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"room_id and code are required.")
        session=HospitalisationSessionLocal()
        try:
            room=session.scalar(select(Room).options(joinedload(Room.ward)).where(Room.id==request.room_id.strip()))
            if room is None: context.abort(grpc.StatusCode.NOT_FOUND,"Room not found.")
            if not room.ward.active: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Cannot create a bed in an inactive ward.")
            if session.scalar(select(Bed).where(Bed.room_id==room.id,Bed.code==code)):
                context.abort(grpc.StatusCode.ALREADY_EXISTS,"Bed code already exists in this room.")
            item=Bed(room_id=room.id,code=code,status="AVAILABLE"); session.add(item); session.commit(); session.refresh(item); _=item.room; _=item.room.ward
            logger.info("rpc=CreateBed peer=%s actor=%s bed=%s outcome=OK",context.peer(),actor.id,item.id)
            return hospitalisation_pb2.BedResponse(bed=bed_to_proto(item))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.ALREADY_EXISTS,"Bed code already exists in this room.")
        finally: session.close()

    def SetBedStatus(self, request, context):
        actor=require_permission(context,"hospitalisation.structure.manage")
        mapping={hospitalisation_pb2.BED_STATUS_AVAILABLE:"AVAILABLE",hospitalisation_pb2.BED_STATUS_OUT_OF_SERVICE:"OUT_OF_SERVICE"}
        desired=mapping.get(request.status)
        if desired is None: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Bed status may be set manually only to AVAILABLE or OUT_OF_SERVICE.")
        if not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"reason is required.")
        session=HospitalisationSessionLocal()
        try:
            item=session.scalar(select(Bed).options(joinedload(Bed.room).joinedload(Room.ward)).where(Bed.id==request.bed_id.strip()).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Bed not found.")
            occupied=session.scalar(select(Admission.id).where(Admission.current_bed_id==item.id,Admission.status=="ADMITTED").limit(1))
            if occupied: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Occupied bed status is controlled by the admission workflow.")
            if desired == "AVAILABLE" and not item.room.ward.active:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION,"A bed in an inactive ward cannot be made AVAILABLE.")
            item.status=desired; session.commit()
            logger.info("rpc=SetBedStatus peer=%s actor=%s bed=%s status=%s reason=%s outcome=OK",context.peer(),actor.id,item.id,desired,request.reason.strip())
            return hospitalisation_pb2.BedResponse(bed=bed_to_proto(item))
        finally: session.close()

    def GetBedAvailability(self, request, context):
        actor = require_permission(context, "hospitalisation.read")
        session = HospitalisationSessionLocal()
        try:
            beds = list_beds(session, request.ward_code.strip().upper(), request.available_only)
            all_for_counts = list_beds(session, request.ward_code.strip().upper(), False)
            response = hospitalisation_pb2.GetBedAvailabilityResponse(
                beds=[bed_to_proto(x) for x in beds], total=len(all_for_counts),
                available=sum(1 for x in all_for_counts if x.status == "AVAILABLE"),
                occupied=sum(1 for x in all_for_counts if x.status == "OCCUPIED"),
                out_of_service=sum(1 for x in all_for_counts if x.status == "OUT_OF_SERVICE"),
            )
            logger.info("rpc=GetBedAvailability peer=%s actor=%s count=%s outcome=OK", context.peer(), actor.id, len(beds))
            return response
        finally:
            session.close()

    def CreateAdmission(self, request, context):
        actor = require_permission(context, "hospitalisation.admit")
        patient_id = request.patient_id.strip()
        reason = request.reason.strip()
        if not patient_id or not reason:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id and reason are required.")
        key = request.idempotency_key.strip() or request.correlation_id.strip() or str(uuid.uuid4())
        correlation_id = request.correlation_id.strip() or str(uuid.uuid4())
        session = HospitalisationSessionLocal()
        try:
            existing = get_admission_by_key(session, key)
            if existing is not None:
                return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(existing))
            active = get_current_admission(session, patient_id)
            if active is not None:
                context.abort(grpc.StatusCode.ALREADY_EXISTS, "Patient already has an active admission.")
            validate_patient_exists(context, patient_id)
            item = Admission(
                admission_number=generate_admission_number(), patient_id=patient_id, active_patient_key=patient_id,
                consultation_id=request.consultation_id.strip() or None, reason=reason,
                preferred_ward=request.preferred_ward.strip().upper() or None, status="PENDING",
                idempotency_key=key, correlation_id=correlation_id, created_by=actor.id,
            )
            session.add(item)
            session.commit()
            item = get_admission(session, item.id)
            logger.info("rpc=CreateAdmission peer=%s actor=%s admission=%s patient=%s outcome=OK", context.peer(), actor.id, item.id, patient_id)
            return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(item))
        except IntegrityError:
            session.rollback()
            existing = get_admission_by_key(session, key)
            if existing is not None:
                return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(existing))
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Active or duplicate admission already exists.")
        except SQLAlchemyError:
            session.rollback(); logger.exception("rpc=CreateAdmission peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Admission could not be created.")
        finally:
            session.close()

    def ApproveAdmission(self, request, context):
        actor=require_permission(context,"hospitalisation.admission.approve")
        if not request.admission_id.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"admission_id is required.")
        if not request.reason.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"approval reason is required.")
        session=HospitalisationSessionLocal()
        try:
            item=session.scalar(select(Admission).where(Admission.id==request.admission_id.strip()).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Admission not found.")
            if item.status not in {"PENDING","ADMITTED"}: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only an active pending/admitted admission can be approved.")
            if item.approved_at is None:
                item.approved_at=utc_now(); item.approved_by=actor.id; item.approval_reason=request.reason.strip(); session.commit()
            item=get_admission(session,item.id)
            logger.info("rpc=ApproveAdmission peer=%s actor=%s admission=%s outcome=OK",context.peer(),actor.id,item.id)
            return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(item))
        finally: session.close()

    def ListAdmissions(self, request, context):
        require_permission(context,"hospitalisation.read")
        filters=[]
        if request.patient_id.strip(): filters.append(Admission.patient_id==request.patient_id.strip())
        if request.status != hospitalisation_pb2.ADMISSION_STATUS_UNSPECIFIED:
            name=hospitalisation_pb2.AdmissionStatus.Name(request.status).replace("ADMISSION_STATUS_","")
            filters.append(Admission.status==name)
        limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
        session=HospitalisationSessionLocal()
        try:
            total=int(session.scalar(select(func.count()).select_from(Admission).where(*filters)) or 0)
            items=list(session.scalars(select(Admission).options(joinedload(Admission.current_bed).joinedload(Bed.room).joinedload(Room.ward)).where(*filters).order_by(Admission.created_at.desc()).offset(offset).limit(limit)).unique().all())
            return hospitalisation_pb2.ListAdmissionsResponse(admissions=[admission_to_proto(x) for x in items],total=total)
        finally: session.close()

    def AssignBed(self, request, context):
        actor = require_permission(context, "hospitalisation.bed.assign")
        admission_id = request.admission_id.strip(); bed_id = request.bed_id.strip(); key = request.idempotency_key.strip()
        if not admission_id or not bed_id or not key:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "admission_id, bed_id and idempotency_key are required.")
        session = HospitalisationSessionLocal()
        try:
            admission = session.scalar(select(Admission).where(Admission.id == admission_id).with_for_update())
            if admission is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Admission not found.")
            if admission.bed_assignment_key == key:
                admission = get_admission(session, admission.id)
                return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(admission))
            if admission.status not in ("PENDING", "ADMITTED"):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Admission is not active.")
            if admission.approved_at is None:
                if "hospitalisation.admission.approve" not in set(actor.permissions):
                    context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Admission must be approved before a bed can be assigned.")
                admission.approved_at = utc_now(); admission.approved_by = actor.id
                admission.approval_reason = "Auto-approved by authorized bed assignment."
            if admission.current_bed_id:
                if admission.current_bed_id == bed_id:
                    admission.bed_assignment_key = key; session.commit(); admission = get_admission(session, admission.id)
                    return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(admission))
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Admission already has a bed. Use TransferBed.")
            bed = session.scalar(
                select(Bed).options(joinedload(Bed.room).joinedload(Room.ward)).where(Bed.id == bed_id).with_for_update()
            )
            if bed is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Bed not found.")
            if not bed.room.ward.active:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Bed belongs to an inactive ward.")
            if bed.status != "AVAILABLE":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Bed is not AVAILABLE.")
            bed.status = "OCCUPIED"
            admission.current_bed_id = bed.id; admission.status = "ADMITTED"; admission.admitted_at = admission.admitted_at or utc_now(); admission.bed_assignment_key = key
            session.commit(); admission = get_admission(session, admission.id)
            logger.info("rpc=AssignBed peer=%s actor=%s admission=%s bed=%s outcome=OK", context.peer(), actor.id, admission.id, bed.id)
            return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(admission))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Bed is already occupied or operation key was reused.")
        except SQLAlchemyError:
            session.rollback(); logger.exception("rpc=AssignBed peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Bed could not be assigned.")
        finally:
            session.close()

    def TransferBed(self, request, context):
        actor = require_permission(context, "hospitalisation.transfer")
        admission_id = request.admission_id.strip(); target_id = request.to_bed_id.strip(); key = request.idempotency_key.strip()
        if not admission_id or not target_id or not key:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "admission_id, to_bed_id and idempotency_key are required.")
        session = HospitalisationSessionLocal()
        try:
            existing = get_transfer_by_key(session, key)
            if existing is not None:
                admission = get_admission(session, existing.admission_id)
                return hospitalisation_pb2.TransferResponse(admission=admission_to_proto(admission), transfer=transfer_to_proto(existing))
            admission = session.scalar(select(Admission).where(Admission.id == admission_id).with_for_update())
            if admission is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Admission not found.")
            if admission.status != "ADMITTED" or not admission.current_bed_id:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Patient must be ADMITTED with a current bed.")
            if admission.current_bed_id == target_id:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Target bed must differ from current bed.")
            ids = sorted([admission.current_bed_id, target_id])
            locked = list(session.scalars(select(Bed).where(Bed.id.in_(ids)).order_by(Bed.id).with_for_update()).all())
            by_id = {x.id: x for x in locked}
            old_bed = by_id.get(admission.current_bed_id); new_bed = by_id.get(target_id)
            if old_bed is None or new_bed is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Current or target bed not found.")
            target_room = session.get(Room, new_bed.room_id)
            target_ward = session.get(Ward, target_room.ward_id) if target_room is not None else None
            if target_ward is None or not target_ward.active:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Target bed belongs to an inactive ward.")
            if new_bed.status != "AVAILABLE":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Target bed is not AVAILABLE.")
            now = utc_now(); old_bed.status = "AVAILABLE"; new_bed.status = "OCCUPIED"; admission.current_bed_id = new_bed.id
            transfer = Transfer(admission_id=admission.id, from_bed_id=old_bed.id, to_bed_id=new_bed.id, idempotency_key=key, requested_at=now, completed_at=now, actor_id=actor.id)
            session.add(transfer); session.commit(); admission = get_admission(session, admission.id); transfer = get_transfer_by_key(session, key)
            logger.info("rpc=TransferBed peer=%s actor=%s admission=%s from=%s to=%s outcome=OK", context.peer(), actor.id, admission.id, old_bed.id, new_bed.id)
            return hospitalisation_pb2.TransferResponse(admission=admission_to_proto(admission), transfer=transfer_to_proto(transfer))
        except IntegrityError:
            session.rollback(); existing = get_transfer_by_key(session, key)
            if existing is not None:
                admission = get_admission(session, existing.admission_id)
                return hospitalisation_pb2.TransferResponse(admission=admission_to_proto(admission), transfer=transfer_to_proto(existing))
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Transfer conflict.")
        except SQLAlchemyError:
            session.rollback(); logger.exception("rpc=TransferBed peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Bed transfer failed.")
        finally:
            session.close()

    def GetCurrentAdmission(self, request, context):
        actor = require_permission(context, "hospitalisation.read")
        patient_id = request.patient_id.strip()
        if not patient_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id is required.")
        session = HospitalisationSessionLocal()
        try:
            item = get_current_admission(session, patient_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "No active admission for patient.")
            logger.info("rpc=GetCurrentAdmission peer=%s actor=%s admission=%s outcome=OK", context.peer(), actor.id, item.id)
            return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(item))
        finally:
            session.close()

    def AddStayNote(self, request, context):
        actor = require_permission(context, "hospitalisation.read")
        admission_id = request.admission_id.strip(); note_text = request.note.strip()
        if not admission_id or not note_text:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "admission_id and note are required.")
        session = HospitalisationSessionLocal()
        try:
            admission = get_admission(session, admission_id)
            if admission is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Admission not found.")
            if admission.status != "ADMITTED":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Stay note requires an ADMITTED patient.")
            item = StayNote(admission_id=admission.id, note=note_text, actor_id=actor.id)
            session.add(item); session.commit(); session.refresh(item)
            logger.info("rpc=AddStayNote peer=%s actor=%s admission=%s note=%s outcome=OK", context.peer(), actor.id, admission.id, item.id)
            return hospitalisation_pb2.StayNoteResponse(note=stay_note_to_proto(item))
        except SQLAlchemyError:
            session.rollback(); logger.exception("rpc=AddStayNote peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Stay note could not be saved.")
        finally:
            session.close()

    def ListDoctors(self, request, context):
        require_permission(context,"hospitalisation.doctor.read")
        try:
            with grpc.insecure_channel(AUTH_GRPC_TARGET) as channel:
                response=auth_pb2_grpc.AuthServiceStub(channel).ListStaffDirectory(
                    auth_pb2.ListStaffDirectoryRequest(role_code="MEDECIN",search=request.search,active_only=request.active_only,page={"page":1,"page_size":100}),
                    metadata=_authorization_metadata(context),timeout=3)
        except grpc.RpcError as error:
            context.abort(error.code() if error.code() in (grpc.StatusCode.PERMISSION_DENIED,grpc.StatusCode.UNAUTHENTICATED) else grpc.StatusCode.UNAVAILABLE, error.details() or "Doctor directory unavailable.")
        session=HospitalisationSessionLocal()
        try:
            doctors=[_doctor_summary_from_entry(session,e) for e in response.entries]
            return hospitalisation_pb2.ListDoctorsResponse(doctors=doctors,total=len(doctors))
        finally: session.close()

    def AssignDoctor(self, request, context):
        actor=require_permission(context,"hospitalisation.doctor.assign")
        admission_id=request.admission_id.strip(); doctor_id=request.doctor_user_id.strip(); key=request.idempotency_key.strip()
        if not admission_id or not doctor_id or not key: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"admission_id, doctor_user_id and idempotency_key are required.")
        entry=_directory_entry(context,doctor_id)
        if not entry.active or "MEDECIN" not in set(entry.roles): context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Selected staff member is not an active doctor.")
        session=HospitalisationSessionLocal()
        try:
            existing=session.scalar(select(DoctorAssignment).where(DoctorAssignment.idempotency_key==key))
            if existing:
                summary=_doctor_summary_from_entry(session,entry)
                return hospitalisation_pb2.AssignDoctorResponse(assignment=doctor_assignment_to_proto(existing),doctor=summary,busy_warning=summary.active_assignment_count>1,warning_message="Doctor already has other active patients." if summary.active_assignment_count>1 else "")
            admission=session.scalar(select(Admission).where(Admission.id==admission_id).with_for_update())
            if admission is None: context.abort(grpc.StatusCode.NOT_FOUND,"Admission not found.")
            if admission.status not in {"PENDING","ADMITTED"}: context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Doctor can only be assigned to an active admission.")
            active_for_admission=session.scalar(select(DoctorAssignment).where(DoctorAssignment.admission_id==admission.id,DoctorAssignment.status=="ACTIVE").limit(1))
            if active_for_admission:
                if active_for_admission.doctor_user_id==doctor_id:
                    summary=_doctor_summary_from_entry(session,entry)
                    return hospitalisation_pb2.AssignDoctorResponse(assignment=doctor_assignment_to_proto(active_for_admission),doctor=summary,busy_warning=summary.active_assignment_count>1,warning_message="Doctor already has other active patients." if summary.active_assignment_count>1 else "")
                context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Admission already has an active doctor assignment. Complete it before assigning another doctor.")
            busy_before=int(session.scalar(select(func.count()).select_from(DoctorAssignment).where(DoctorAssignment.doctor_user_id==doctor_id,DoctorAssignment.status=="ACTIVE")) or 0)
            if admission.approved_at is None:
                if "hospitalisation.admission.approve" not in set(actor.permissions):
                    context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Admission must be approved before doctor assignment.")
                admission.approved_at=utc_now(); admission.approved_by=actor.id
                admission.approval_reason="Auto-approved by authorized doctor assignment."
            item=DoctorAssignment(admission_id=admission.id,active_admission_key=admission.id,doctor_user_id=doctor_id,assigned_by=actor.id,status="ACTIVE",idempotency_key=key)
            session.add(item); session.commit(); session.refresh(item)
            summary=_doctor_summary_from_entry(session,entry)
            send_system_notification(auth_target=AUTH_GRPC_TARGET,recipient_id=doctor_id,notification_type="HOSPITALISATION_ASSIGNMENT",
                title="Nouvelle hospitalisation assignée",body=f"Un patient hospitalisé vous a été assigné ({admission.admission_number}).",source_service="hospitalisation",correlation_id=admission.correlation_id)
            logger.info("rpc=AssignDoctor peer=%s actor=%s admission=%s doctor=%s busy_before=%s outcome=OK",context.peer(),actor.id,admission.id,doctor_id,busy_before)
            return hospitalisation_pb2.AssignDoctorResponse(assignment=doctor_assignment_to_proto(item),doctor=summary,busy_warning=busy_before>0,warning_message=(f"Doctor already had {busy_before} active patient assignment(s)." if busy_before>0 else ""))
        except IntegrityError:
            session.rollback()
            existing=session.scalar(select(DoctorAssignment).where(DoctorAssignment.idempotency_key==key))
            if existing:
                summary=_doctor_summary_from_entry(session,entry)
                return hospitalisation_pb2.AssignDoctorResponse(assignment=doctor_assignment_to_proto(existing),doctor=summary,busy_warning=summary.active_assignment_count>1,warning_message="Doctor already has other active patients." if summary.active_assignment_count>1 else "")
            context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Admission already has an active doctor assignment or the operation key conflicts.")
        finally: session.close()

    def ListDoctorAssignments(self, request, context):
        actor=require_permission(context,"hospitalisation.doctor.read")
        filters=[]
        if request.admission_id.strip(): filters.append(DoctorAssignment.admission_id==request.admission_id.strip())
        if request.doctor_user_id.strip(): filters.append(DoctorAssignment.doctor_user_id==request.doctor_user_id.strip())
        if request.status != hospitalisation_pb2.DOCTOR_ASSIGNMENT_STATUS_UNSPECIFIED:
            status=DOCTOR_STATUS_PROTO_TO_DB.get(request.status); filters.append(DoctorAssignment.status==status)
        limit=min(max(request.limit or 50,1),200); offset=max(request.offset,0)
        session=HospitalisationSessionLocal()
        try:
            total=int(session.scalar(select(func.count()).select_from(DoctorAssignment).where(*filters)) or 0)
            items=list(session.scalars(select(DoctorAssignment).where(*filters).order_by(DoctorAssignment.assigned_at.desc()).offset(offset).limit(limit)).all())
            return hospitalisation_pb2.ListDoctorAssignmentsResponse(assignments=[doctor_assignment_to_proto(x) for x in items],total=total)
        finally: session.close()

    def CompleteDoctorAssignment(self, request, context):
        actor=require_permission(context,"hospitalisation.doctor.complete")
        if not request.assignment_id.strip(): context.abort(grpc.StatusCode.INVALID_ARGUMENT,"assignment_id is required.")
        session=HospitalisationSessionLocal()
        try:
            item=session.scalar(select(DoctorAssignment).where(DoctorAssignment.id==request.assignment_id.strip()).with_for_update())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Doctor assignment not found.")
            if item.status=="COMPLETED": return hospitalisation_pb2.DoctorAssignmentResponse(assignment=doctor_assignment_to_proto(item))
            if item.status!="ACTIVE": context.abort(grpc.StatusCode.FAILED_PRECONDITION,"Only an ACTIVE doctor assignment can be completed.")
            if actor.id!=item.doctor_user_id and "hospitalisation.doctor.assign" not in set(actor.permissions):
                context.abort(grpc.StatusCode.PERMISSION_DENIED,"A doctor may complete only their own assignment.")
            item.status="COMPLETED"; item.active_admission_key=None; item.completed_at=utc_now(); item.completion_note=request.note.strip() or None
            session.commit(); session.refresh(item)
            logger.info("rpc=CompleteDoctorAssignment peer=%s actor=%s assignment=%s outcome=OK",context.peer(),actor.id,item.id)
            return hospitalisation_pb2.DoctorAssignmentResponse(assignment=doctor_assignment_to_proto(item))
        finally: session.close()

    def DischargePatient(self, request, context):
        actor = require_permission(context, "hospitalisation.discharge")
        admission_id = request.admission_id.strip(); summary = request.discharge_summary.strip(); key = request.idempotency_key.strip()
        if not admission_id or not summary or not key:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "admission_id, discharge_summary and idempotency_key are required.")
        session = HospitalisationSessionLocal()
        try:
            admission = session.scalar(select(Admission).where(Admission.id == admission_id).with_for_update())
            if admission is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Admission not found.")
            if admission.status == "DISCHARGED" and admission.discharge_idempotency_key == key:
                admission = get_admission(session, admission.id)
                return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(admission))
            if admission.status != "ADMITTED" or not admission.current_bed_id:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Patient must be ADMITTED before discharge.")
            bed = session.scalar(
                select(Bed).options(joinedload(Bed.room).joinedload(Room.ward)).where(Bed.id == admission.current_bed_id).with_for_update()
            )
            if bed is None:
                context.abort(grpc.StatusCode.INTERNAL, "Current bed could not be loaded.")
            now = utc_now(); start = admission.admitted_at or admission.created_at
            seconds = max(0, (now - start).total_seconds()); days = max(1, math.ceil(seconds / 86400))
            amount = days * bed.room.ward.daily_rate_minor
            currency = bed.room.ward.currency
            bed.status = "AVAILABLE"
            admission.status = "DISCHARGED"; admission.discharged_at = now; admission.discharge_summary = summary
            admission.current_bed_id = None; admission.active_patient_key = None; admission.discharge_idempotency_key = key
            admission.billing_charge_status = "PENDING_DELIVERY"
            active_assignments=list(session.scalars(select(DoctorAssignment).where(DoctorAssignment.admission_id==admission.id,DoctorAssignment.status=="ACTIVE")).all())
            for assignment in active_assignments:
                assignment.status="COMPLETED"; assignment.active_admission_key=None; assignment.completed_at=now
                assignment.completion_note=assignment.completion_note or "Auto-completed when patient was discharged."
            outbox_key = f"hospitalisation-discharge-{admission.id}"
            existing_outbox = session.scalar(select(BillingOutbox).where(BillingOutbox.idempotency_key == outbox_key))
            if existing_outbox is None:
                session.add(BillingOutbox(idempotency_key=outbox_key, admission_id=admission.id, patient_id=admission.patient_id, amount_minor=amount, currency=currency, status="PENDING_DELIVERY"))
            session.commit()

            outbox = session.scalar(
                select(BillingOutbox).where(BillingOutbox.admission_id == admission.id)
            )
            if outbox is not None and outbox.status == "PENDING_DELIVERY":
                if _deliver_billing_charge(context, outbox, admission.correlation_id, admission.admission_number):
                    outbox.status = "DELIVERED"
                    admission.billing_charge_status = "DELIVERED"
                    session.commit()

            admission = get_admission(session, admission.id)
            logger.info("rpc=DischargePatient peer=%s actor=%s admission=%s days=%s amount_minor=%s outcome=OK", context.peer(), actor.id, admission.id, days, amount)
            return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(admission))
        except IntegrityError:
            session.rollback(); admission = get_admission(session, admission_id)
            if admission and admission.status == "DISCHARGED" and admission.discharge_idempotency_key == key:
                return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(admission))
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Discharge operation conflict.")
        except SQLAlchemyError:
            session.rollback(); logger.exception("rpc=DischargePatient peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Patient could not be discharged.")
        finally:
            session.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return build_health_response("ONLINE", "Hospitalisation service and MySQL are available.")
        except SQLAlchemyError:
            logger.exception("rpc=HealthCheck peer=%s outcome=DEGRADED", context.peer())
            return build_health_response("DEGRADED", "Hospitalisation service is running but MySQL is unavailable.")
