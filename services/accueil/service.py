from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from database.accueil_session import AccueilSessionLocal, engine
from services.accueil.config import SERVICE_VERSION
from services.accueil.models import Arrival, Patient
from services.accueil.repository import (
    find_obvious_duplicate,
    get_arrival_by_id,
    get_patient_by_id,
    get_patient_by_number,
    list_waiting_queue,
    search_patients,
)
from services.common.auth_guard import require_permission


logger = logging.getLogger("projectx.accueil.service")


SEX_PROTO_TO_DB = {
    accueil_pb2.SEX_MALE: "MALE",
    accueil_pb2.SEX_FEMALE: "FEMALE",
    accueil_pb2.SEX_OTHER: "OTHER",
}
SEX_DB_TO_PROTO = {
    "MALE": accueil_pb2.SEX_MALE,
    "FEMALE": accueil_pb2.SEX_FEMALE,
    "OTHER": accueil_pb2.SEX_OTHER,
}
PATIENT_STATUS_PROTO_TO_DB = {
    accueil_pb2.PATIENT_STATUS_ACTIVE: "ACTIVE",
    accueil_pb2.PATIENT_STATUS_INACTIVE: "INACTIVE",
    accueil_pb2.PATIENT_STATUS_DECEASED: "DECEASED",
}
PATIENT_STATUS_DB_TO_PROTO = {v: k for k, v in PATIENT_STATUS_PROTO_TO_DB.items()}
PRIORITY_PROTO_TO_DB = {
    accueil_pb2.ARRIVAL_PRIORITY_ROUTINE: "ROUTINE",
    accueil_pb2.ARRIVAL_PRIORITY_URGENT: "URGENT",
    accueil_pb2.ARRIVAL_PRIORITY_EMERGENCY: "EMERGENCY",
}
PRIORITY_DB_TO_PROTO = {v: k for k, v in PRIORITY_PROTO_TO_DB.items()}
ARRIVAL_STATUS_DB_TO_PROTO = {
    "WAITING": accueil_pb2.ARRIVAL_STATUS_WAITING,
    "ORIENTED": accueil_pb2.ARRIVAL_STATUS_ORIENTED,
    "CANCELLED": accueil_pb2.ARRIVAL_STATUS_CANCELLED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_birth_date(raw: str, context) -> date:
    try:
        value = date.fromisoformat(raw.strip())
    except (TypeError, ValueError):
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "birth_date must use YYYY-MM-DD.")
    if value > date.today():
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "birth_date cannot be in the future.")
    return value


def to_timestamp(value: datetime | None) -> Timestamp:
    result = Timestamp()
    if value is not None:
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        result.FromDatetime(aware)
    return result


def patient_to_proto(patient: Patient):
    return accueil_pb2.Patient(
        id=patient.id,
        patient_number=patient.patient_number,
        first_name=patient.first_name,
        last_name=patient.last_name,
        sex=SEX_DB_TO_PROTO.get(patient.sex, accueil_pb2.SEX_UNSPECIFIED),
        birth_date=patient.birth_date.isoformat(),
        phone=patient.phone or "",
        address=patient.address or "",
        status=PATIENT_STATUS_DB_TO_PROTO.get(patient.status, accueil_pb2.PATIENT_STATUS_UNSPECIFIED),
        created_at=to_timestamp(patient.created_at),
        updated_at=to_timestamp(patient.updated_at),
    )


def arrival_to_proto(arrival: Arrival):
    return accueil_pb2.Arrival(
        id=arrival.id,
        patient_id=arrival.patient_id,
        arrived_at=to_timestamp(arrival.arrived_at),
        reason=arrival.reason,
        target_service=arrival.target_service,
        priority=PRIORITY_DB_TO_PROTO.get(arrival.priority, accueil_pb2.ARRIVAL_PRIORITY_UNSPECIFIED),
        status=ARRIVAL_STATUS_DB_TO_PROTO.get(arrival.status, accueil_pb2.ARRIVAL_STATUS_UNSPECIFIED),
        orientation_note=arrival.orientation_note or "",
        oriented_at=to_timestamp(arrival.oriented_at),
        updated_at=to_timestamp(arrival.updated_at),
    )


def generate_patient_number() -> str:
    # Human-readable and collision-resistant without a race-prone global counter.
    return f"PAT-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _set_health_enum(response, desired: str) -> None:
    field = response.DESCRIPTOR.fields_by_name.get("status")
    if field is None or field.enum_type is None:
        return
    candidates = [desired, f"HEALTH_STATUS_{desired}", f"STATUS_{desired}"]
    for name in candidates:
        value = field.enum_type.values_by_name.get(name)
        if value is not None:
            response.status = value.number
            return


def build_health_response(desired: str, message: str):
    return build_health_response_compat("accueil", desired, message, SERVICE_VERSION)

def normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_phone(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def page_values(limit: int, offset: int, context) -> tuple[int, int]:
    if offset < 0:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "offset cannot be negative.")
    if limit <= 0:
        limit = 50
    if limit > 200:
        limit = 200
    return limit, offset


class AccueilService(accueil_pb2_grpc.AccueilServiceServicer):
    def CreatePatient(self, request, context):
        actor = require_permission(context, "accueil.patient.create")
        first_name = normalize_name(request.first_name)
        last_name = normalize_name(request.last_name)
        phone = normalize_phone(request.phone)

        if not first_name or not last_name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "first_name and last_name are required.")
        if request.sex not in SEX_PROTO_TO_DB:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "A valid sex value is required.")
        birth_date = parse_birth_date(request.birth_date, context)

        session = AccueilSessionLocal()
        try:
            duplicate = find_obvious_duplicate(
                session,
                first_name=first_name,
                last_name=last_name,
                birth_date=birth_date,
                phone=phone,
            )
            if duplicate is not None:
                context.abort(
                    grpc.StatusCode.ALREADY_EXISTS,
                    f"An obvious duplicate patient already exists: {duplicate.patient_number}",
                )

            patient = Patient(
                patient_number=generate_patient_number(),
                first_name=first_name,
                last_name=last_name,
                sex=SEX_PROTO_TO_DB[request.sex],
                birth_date=birth_date,
                phone=phone,
                address=request.address.strip() or None,
                status="ACTIVE",
                created_by=actor.id,
                updated_by=actor.id,
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)
            logger.info("rpc=CreatePatient peer=%s actor=%s patient=%s outcome=OK", context.peer(), actor.id, patient.id)
            return accueil_pb2.PatientResponse(patient=patient_to_proto(patient))
        except IntegrityError:
            session.rollback()
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Patient could not be created because of a duplicate value.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=CreatePatient peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Patient could not be created.")
        finally:
            session.close()

    def GetPatient(self, request, context):
        actor = require_permission(context, "accueil.patient.read")
        session = AccueilSessionLocal()
        try:
            patient = None
            if request.patient_id.strip():
                patient = get_patient_by_id(session, request.patient_id.strip())
            elif request.patient_number.strip():
                patient = get_patient_by_number(session, request.patient_number.strip())
            else:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id or patient_number is required.")
            if patient is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Patient not found.")
            logger.info("rpc=GetPatient peer=%s actor=%s patient=%s outcome=OK", context.peer(), actor.id, patient.id)
            return accueil_pb2.PatientResponse(patient=patient_to_proto(patient))
        finally:
            session.close()

    def SearchPatients(self, request, context):
        actor = require_permission(context, "accueil.patient.read")
        limit, offset = page_values(request.limit, request.offset, context)
        session = AccueilSessionLocal()
        try:
            patients, total = search_patients(
                session,
                query=request.query.strip(),
                limit=limit,
                offset=offset,
            )
            logger.info("rpc=SearchPatients peer=%s actor=%s count=%s outcome=OK", context.peer(), actor.id, len(patients))
            return accueil_pb2.SearchPatientsResponse(
                patients=[patient_to_proto(item) for item in patients],
                total=total,
            )
        finally:
            session.close()

    def UpdatePatient(self, request, context):
        actor = require_permission(context, "accueil.patient.update")
        if not request.patient_id.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id is required.")
        session = AccueilSessionLocal()
        try:
            patient = get_patient_by_id(session, request.patient_id.strip())
            if patient is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Patient not found.")

            if request.HasField("first_name"):
                value = normalize_name(request.first_name)
                if not value:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "first_name cannot be empty.")
                patient.first_name = value
            if request.HasField("last_name"):
                value = normalize_name(request.last_name)
                if not value:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "last_name cannot be empty.")
                patient.last_name = value
            if request.HasField("sex"):
                if request.sex not in SEX_PROTO_TO_DB:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid sex value.")
                patient.sex = SEX_PROTO_TO_DB[request.sex]
            if request.HasField("birth_date"):
                patient.birth_date = parse_birth_date(request.birth_date, context)
            if request.HasField("phone"):
                patient.phone = normalize_phone(request.phone)
            if request.HasField("address"):
                patient.address = request.address.strip() or None
            if request.HasField("status"):
                if request.status not in PATIENT_STATUS_PROTO_TO_DB:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid patient status.")
                patient.status = PATIENT_STATUS_PROTO_TO_DB[request.status]

            patient.updated_by = actor.id
            session.commit()
            session.refresh(patient)
            logger.info("rpc=UpdatePatient peer=%s actor=%s patient=%s outcome=OK", context.peer(), actor.id, patient.id)
            return accueil_pb2.PatientResponse(patient=patient_to_proto(patient))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=UpdatePatient peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Patient could not be updated.")
        finally:
            session.close()

    def RegisterArrival(self, request, context):
        actor = require_permission(context, "accueil.arrival.create")
        if not request.patient_id.strip() or not request.reason.strip() or not request.target_service.strip():
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "patient_id, reason and target_service are required.",
            )
        if request.priority not in PRIORITY_PROTO_TO_DB:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "A valid arrival priority is required.")

        session = AccueilSessionLocal()
        try:
            patient = get_patient_by_id(session, request.patient_id.strip())
            if patient is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Patient not found.")
            if patient.status != "ACTIVE":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only an ACTIVE patient can be checked in.")

            arrival = Arrival(
                patient_id=patient.id,
                reason=request.reason.strip(),
                target_service=request.target_service.strip().upper(),
                priority=PRIORITY_PROTO_TO_DB[request.priority],
                status="WAITING",
                created_by=actor.id,
            )
            session.add(arrival)
            session.commit()
            session.refresh(arrival)
            logger.info("rpc=RegisterArrival peer=%s actor=%s arrival=%s patient=%s outcome=OK", context.peer(), actor.id, arrival.id, patient.id)
            return accueil_pb2.ArrivalResponse(arrival=arrival_to_proto(arrival))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=RegisterArrival peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Arrival could not be registered.")
        finally:
            session.close()

    def OrientArrival(self, request, context):
        actor = require_permission(context, "accueil.arrival.create")
        if not request.arrival_id.strip() or not request.target_service.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "arrival_id and target_service are required.")

        session = AccueilSessionLocal()
        try:
            arrival = get_arrival_by_id(session, request.arrival_id.strip())
            if arrival is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Arrival not found.")
            if arrival.status != "WAITING":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only a WAITING arrival can be oriented.")

            arrival.target_service = request.target_service.strip().upper()
            arrival.orientation_note = request.orientation_note.strip() or None
            arrival.status = "ORIENTED"
            arrival.oriented_at = utc_now()
            session.commit()
            session.refresh(arrival)
            logger.info("rpc=OrientArrival peer=%s actor=%s arrival=%s outcome=OK", context.peer(), actor.id, arrival.id)
            return accueil_pb2.ArrivalResponse(arrival=arrival_to_proto(arrival))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=OrientArrival peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Arrival could not be oriented.")
        finally:
            session.close()

    def ListWaitingQueue(self, request, context):
        actor = require_permission(context, "accueil.queue.read")
        limit, offset = page_values(request.limit, request.offset, context)
        session = AccueilSessionLocal()
        try:
            arrivals, total = list_waiting_queue(
                session,
                target_service=request.target_service.strip().upper(),
                limit=limit,
                offset=offset,
            )
            entries = [
                accueil_pb2.QueueEntry(
                    arrival=arrival_to_proto(arrival),
                    patient=patient_to_proto(arrival.patient),
                )
                for arrival in arrivals
            ]
            logger.info("rpc=ListWaitingQueue peer=%s actor=%s count=%s outcome=OK", context.peer(), actor.id, len(entries))
            return accueil_pb2.ListWaitingQueueResponse(entries=entries, total=total)
        finally:
            session.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return build_health_response("ONLINE", "Accueil service and MySQL are available.")
        except Exception:
            logger.exception("rpc=HealthCheck peer=%s outcome=DEGRADED", context.peer())
            return build_health_response("DEGRADED", "Accueil service is running but MySQL is unavailable.")
