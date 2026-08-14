from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from billing.v1 import billing_pb2, billing_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
from database.hospitalisation_session import HospitalisationSessionLocal, engine
from services.common.auth_guard import require_permission
from services.hospitalisation.config import ACCUEIL_GRPC_TARGET, BILLING_GRPC_TARGET, SERVICE_VERSION
from services.hospitalisation.models import Admission, Bed, BillingOutbox, Room, StayNote, Transfer
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
            if admission.current_bed_id:
                if admission.current_bed_id == bed_id:
                    admission.bed_assignment_key = key; session.commit(); admission = get_admission(session, admission.id)
                    return hospitalisation_pb2.AdmissionResponse(admission=admission_to_proto(admission))
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Admission already has a bed. Use TransferBed.")
            bed = session.scalar(select(Bed).where(Bed.id == bed_id).with_for_update())
            if bed is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Bed not found.")
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
