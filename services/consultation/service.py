from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from consultation.v1 import consultation_pb2, consultation_pb2_grpc
from laboratoire.v1 import laboratoire_pb2, laboratoire_pb2_grpc
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc
from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
from maternite.v1 import maternite_pb2, maternite_pb2_grpc
from database.consultation_session import ConsultationSessionLocal, engine
from services.common.auth_guard import require_permission
from services.consultation.config import ACCUEIL_GRPC_TARGET, LABORATOIRE_GRPC_TARGET, PHARMACIE_GRPC_TARGET, HOSPITALISATION_GRPC_TARGET, MATERNITE_GRPC_TARGET, SERVICE_VERSION
from services.consultation.models import Consultation, Diagnosis, OutboundRequest, Prescription, PrescriptionItem
from services.consultation.repository import get_consultation, list_patient_consultations


logger = logging.getLogger("projectx.consultation.service")


STATUS_DB_TO_PROTO = {
    "OPEN": consultation_pb2.CONSULTATION_STATUS_OPEN,
    "CLOSED": consultation_pb2.CONSULTATION_STATUS_CLOSED,
    "CANCELLED": consultation_pb2.CONSULTATION_STATUS_CANCELLED,
}
PRESCRIPTION_STATUS_DB_TO_PROTO = {
    "ISSUED": consultation_pb2.PRESCRIPTION_STATUS_ISSUED,
    "CANCELLED": consultation_pb2.PRESCRIPTION_STATUS_CANCELLED,
}
PRESCRIPTION_SOURCE_DB_TO_PROTO = {
    "HOSPITAL_CATALOG": consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_HOSPITAL_CATALOG,
    "EXTERNAL": consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_EXTERNAL,
}
EXTERNAL_TYPE_DB_TO_PROTO = {
    "LAB_TEST": consultation_pb2.EXTERNAL_REQUEST_TYPE_LAB_TEST,
    "HOSPITALIZATION": consultation_pb2.EXTERNAL_REQUEST_TYPE_HOSPITALIZATION,
    "MATERNITY": consultation_pb2.EXTERNAL_REQUEST_TYPE_MATERNITY,
}
EXTERNAL_STATUS_DB_TO_PROTO = {
    "PENDING_DELIVERY": consultation_pb2.EXTERNAL_REQUEST_STATUS_PENDING_DELIVERY,
    "DELIVERED": consultation_pb2.EXTERNAL_REQUEST_STATUS_DELIVERED,
    "FAILED": consultation_pb2.EXTERNAL_REQUEST_STATUS_FAILED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_timestamp(value: datetime | None) -> Timestamp:
    result = Timestamp()
    if value is not None:
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        result.FromDatetime(aware)
    return result


def generate_consultation_number() -> str:
    return f"CONS-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def generate_prescription_number() -> str:
    return f"RX-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _authorization_metadata(context):
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization" and item.value.strip():
            return (("authorization", item.value.strip()),)
    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing authorization metadata.")


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

    status_name = accueil_pb2.PatientStatus.Name(response.patient.status)
    if status_name != "PATIENT_STATUS_ACTIVE":
        context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Patient is not ACTIVE.")
    return response.patient


def _resolve_hospital_medicine(context, medicine_ref: str):
    """Resolve an exact active hospital medicine when Pharmacy is reachable.

    If Pharmacy is temporarily unavailable, prescription creation remains resilient and
    the provided reference/snapshot is persisted; Pharmacy will validate it on exposure/dispense.
    """
    try:
        with grpc.insecure_channel(PHARMACIE_GRPC_TARGET) as channel:
            stub = pharmacie_pb2_grpc.PharmacieServiceStub(channel)
            response = stub.SearchMedicines(
                pharmacie_pb2.SearchMedicinesRequest(query=medicine_ref, active_only=True, limit=50, offset=0),
                metadata=_authorization_metadata(context),
                timeout=3,
            )
    except grpc.RpcError as error:
        if error.code() in (grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED):
            context.abort(error.code(), error.details() or "Medicine catalogue access denied.")
        if error.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
            return None
        context.abort(grpc.StatusCode.UNAVAILABLE, f"Pharmacy catalogue unavailable: {error.code().name}")
    ref = medicine_ref.strip().upper()
    for medicine in response.medicines:
        if medicine.code.strip().upper() == ref or medicine.id.strip() == medicine_ref.strip():
            return medicine
    context.abort(grpc.StatusCode.NOT_FOUND, f"Active hospital medicine not found: {medicine_ref}")


def page_values(limit: int, offset: int, context) -> tuple[int, int]:
    if offset < 0:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "offset cannot be negative.")
    if limit <= 0:
        limit = 50
    if limit > 200:
        limit = 200
    return limit, offset


def vitals_to_dict(vitals) -> dict:
    result = {}
    scalar_fields = (
        "temperature_c",
        "systolic_bp",
        "diastolic_bp",
        "pulse_bpm",
        "respiratory_rate",
        "spo2_percent",
        "weight_kg",
        "height_cm",
    )
    for name in scalar_fields:
        try:
            present = vitals.HasField(name)
        except ValueError:
            present = False
        if present:
            result[name] = getattr(vitals, name)
    return result


def validate_vitals(values: dict, context) -> None:
    if "temperature_c" in values and not 25 <= values["temperature_c"] <= 45:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "temperature_c is outside the supported range.")
    for field in ("systolic_bp", "diastolic_bp", "pulse_bpm", "respiratory_rate"):
        if field in values and values[field] <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field} must be positive.")
    if "spo2_percent" in values and not 1 <= values["spo2_percent"] <= 100:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "spo2_percent must be between 1 and 100.")
    for field in ("weight_kg", "height_cm"):
        if field in values and values[field] <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"{field} must be positive.")


def vitals_to_proto(raw: str | None):
    result = consultation_pb2.Vitals()
    if not raw:
        return result
    try:
        values = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return result
    for name, value in values.items():
        if name in result.DESCRIPTOR.fields_by_name:
            setattr(result, name, value)
    return result


def diagnosis_to_proto(item: Diagnosis):
    return consultation_pb2.Diagnosis(
        id=item.id,
        text=item.text,
        code=item.code or "",
        is_primary=item.is_primary,
        created_at=to_timestamp(item.created_at),
    )


def prescription_item_to_proto(item: PrescriptionItem):
    return consultation_pb2.PrescriptionItem(
        id=item.id,
        medicine_ref=item.medicine_ref,
        dose=item.dose,
        frequency=item.frequency,
        duration=item.duration,
        instructions=item.instructions or "",
        medicine_source=PRESCRIPTION_SOURCE_DB_TO_PROTO.get(item.medicine_source, consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_UNSPECIFIED),
        medicine_name=item.medicine_name or item.medicine_ref,
        medicine_form=item.medicine_form or "",
        medicine_strength=item.medicine_strength or "",
        dispensable_by_hospital=(item.medicine_source != "EXTERNAL"),
    )


def prescription_to_proto(item: Prescription):
    return consultation_pb2.Prescription(
        id=item.id,
        prescription_number=item.prescription_number,
        consultation_id=item.consultation_id,
        patient_id=item.patient_id,
        doctor_id=item.doctor_id,
        status=PRESCRIPTION_STATUS_DB_TO_PROTO.get(item.status, consultation_pb2.PRESCRIPTION_STATUS_UNSPECIFIED),
        items=[prescription_item_to_proto(child) for child in item.items],
        issued_at=to_timestamp(item.issued_at),
    )


def consultation_to_proto(item: Consultation):
    return consultation_pb2.Consultation(
        id=item.id,
        consultation_number=item.consultation_number,
        patient_id=item.patient_id,
        doctor_id=item.doctor_id,
        reason=item.reason,
        symptoms=item.symptoms or "",
        observations=item.observations or "",
        notes=item.notes or "",
        vitals=vitals_to_proto(item.vitals_json),
        status=STATUS_DB_TO_PROTO.get(item.status, consultation_pb2.CONSULTATION_STATUS_UNSPECIFIED),
        diagnoses=[diagnosis_to_proto(child) for child in item.diagnoses],
        prescriptions=[prescription_to_proto(child) for child in item.prescriptions],
        created_at=to_timestamp(item.created_at),
        updated_at=to_timestamp(item.updated_at),
        closed_at=to_timestamp(item.closed_at),
    )


def outbound_to_proto(item: OutboundRequest):
    return consultation_pb2.ExternalRequest(
        id=item.id,
        correlation_id=item.correlation_id,
        consultation_id=item.consultation_id,
        patient_id=item.patient_id,
        request_type=EXTERNAL_TYPE_DB_TO_PROTO.get(item.request_type, consultation_pb2.EXTERNAL_REQUEST_TYPE_UNSPECIFIED),
        status=EXTERNAL_STATUS_DB_TO_PROTO.get(item.status, consultation_pb2.EXTERNAL_REQUEST_STATUS_UNSPECIFIED),
        target_service=item.target_service,
        summary=item.summary,
        created_at=to_timestamp(item.created_at),
    )


def require_open(item: Consultation, context) -> None:
    if item.status != "OPEN":
        context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Consultation must be OPEN for this operation.")


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
    return build_health_response_compat("consultation", desired, message, SERVICE_VERSION)

class ConsultationService(consultation_pb2_grpc.ConsultationServiceServicer):
    def CreateConsultation(self, request, context):
        actor = require_permission(context, "consultation.create")
        patient_id = request.patient_id.strip()
        reason = request.reason.strip()
        if not patient_id or not reason:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id and reason are required.")
        validate_patient_exists(context, patient_id)

        session = ConsultationSessionLocal()
        try:
            item = Consultation(
                consultation_number=generate_consultation_number(),
                patient_id=patient_id,
                doctor_id=actor.id,
                reason=reason,
                symptoms=request.symptoms.strip() or None,
                status="OPEN",
                created_by=actor.id,
                updated_by=actor.id,
            )
            session.add(item)
            session.commit()
            item = get_consultation(session, item.id)
            logger.info("rpc=CreateConsultation peer=%s actor=%s consultation=%s patient=%s outcome=OK", context.peer(), actor.id, item.id, patient_id)
            return consultation_pb2.ConsultationResponse(consultation=consultation_to_proto(item))
        except IntegrityError:
            session.rollback()
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Consultation could not be created because of a duplicate value.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=CreateConsultation peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Consultation could not be created.")
        finally:
            session.close()

    def GetConsultation(self, request, context):
        actor = require_permission(context, "consultation.read")
        consultation_id = request.consultation_id.strip()
        if not consultation_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "consultation_id is required.")
        session = ConsultationSessionLocal()
        try:
            item = get_consultation(session, consultation_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Consultation not found.")
            logger.info("rpc=GetConsultation peer=%s actor=%s consultation=%s outcome=OK", context.peer(), actor.id, item.id)
            return consultation_pb2.ConsultationResponse(consultation=consultation_to_proto(item))
        finally:
            session.close()

    def ListPatientConsultations(self, request, context):
        actor = require_permission(context, "consultation.read")
        patient_id = request.patient_id.strip()
        if not patient_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id is required.")
        limit, offset = page_values(request.limit, request.offset, context)
        session = ConsultationSessionLocal()
        try:
            items, total = list_patient_consultations(session, patient_id=patient_id, limit=limit, offset=offset)
            logger.info("rpc=ListPatientConsultations peer=%s actor=%s patient=%s count=%s outcome=OK", context.peer(), actor.id, patient_id, len(items))
            return consultation_pb2.ListPatientConsultationsResponse(
                consultations=[consultation_to_proto(item) for item in items],
                total=total,
            )
        finally:
            session.close()

    def UpdateClinicalNotes(self, request, context):
        actor = require_permission(context, "consultation.update")
        consultation_id = request.consultation_id.strip()
        if not consultation_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "consultation_id is required.")

        session = ConsultationSessionLocal()
        try:
            item = get_consultation(session, consultation_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Consultation not found.")
            require_open(item, context)

            if request.HasField("symptoms"):
                item.symptoms = request.symptoms.strip() or None
            if request.HasField("observations"):
                item.observations = request.observations.strip() or None
            if request.HasField("notes"):
                item.notes = request.notes.strip() or None

            vitals = vitals_to_dict(request.vitals)
            if vitals:
                validate_vitals(vitals, context)
                item.vitals_json = json.dumps(vitals, separators=(",", ":"), sort_keys=True)

            if request.replace_diagnoses:
                item.diagnoses.clear()
                session.flush()

            if request.diagnoses:
                if sum(1 for diagnosis in request.diagnoses if diagnosis.is_primary) > 1:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Only one diagnosis may be marked primary per update.")
                for diagnosis in request.diagnoses:
                    text_value = diagnosis.text.strip()
                    if not text_value:
                        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Diagnosis text is required.")
                    item.diagnoses.append(
                        Diagnosis(
                            text=text_value,
                            code=diagnosis.code.strip() or None,
                            is_primary=diagnosis.is_primary,
                            created_by=actor.id,
                        )
                    )

            item.updated_by = actor.id
            item.updated_at = utc_now()
            session.commit()
            item = get_consultation(session, item.id)
            logger.info("rpc=UpdateClinicalNotes peer=%s actor=%s consultation=%s outcome=OK", context.peer(), actor.id, item.id)
            return consultation_pb2.ConsultationResponse(consultation=consultation_to_proto(item))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=UpdateClinicalNotes peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Clinical notes could not be updated.")
        finally:
            session.close()

    def IssuePrescription(self, request, context):
        actor = require_permission(context, "consultation.prescription.issue")
        consultation_id = request.consultation_id.strip()
        if not consultation_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "consultation_id is required.")
        if not request.items:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "At least one prescription item is required.")

        session = ConsultationSessionLocal()
        try:
            consultation = get_consultation(session, consultation_id)
            if consultation is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Consultation not found.")
            require_open(consultation, context)

            prescription = Prescription(
                prescription_number=generate_prescription_number(),
                consultation_id=consultation.id,
                patient_id=consultation.patient_id,
                doctor_id=actor.id,
                status="ISSUED",
                created_by=actor.id,
            )
            for raw in request.items:
                medicine_ref = raw.medicine_ref.strip()
                medicine_name = raw.medicine_name.strip()
                medicine_form = raw.medicine_form.strip()
                medicine_strength = raw.medicine_strength.strip()
                dose = raw.dose.strip()
                frequency = raw.frequency.strip()
                duration = raw.duration.strip()
                if not dose or not frequency or not duration:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "dose, frequency and duration are required for every prescription item.")

                if raw.medicine_source == consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_EXTERNAL:
                    source = "EXTERNAL"
                elif raw.medicine_source in (
                    consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_UNSPECIFIED,
                    consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_HOSPITAL_CATALOG,
                ):
                    # Backward compatibility: legacy requests with medicine_ref remain hospital-catalog prescriptions.
                    source = "HOSPITAL_CATALOG" if medicine_ref else "EXTERNAL"
                else:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Unknown prescription medicine source.")

                if source == "HOSPITAL_CATALOG":
                    if not medicine_ref:
                        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "medicine_ref is required for a hospital catalogue medicine.")
                    catalog = _resolve_hospital_medicine(context, medicine_ref)
                    if catalog is not None:
                        medicine_ref = catalog.code
                        medicine_name = catalog.name
                        medicine_form = catalog.form
                        medicine_strength = catalog.strength
                    elif not medicine_name:
                        medicine_name = medicine_ref
                else:
                    if not medicine_name:
                        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "medicine_name is required for an external medicine.")
                    if not medicine_ref:
                        medicine_ref = f"EXT-{uuid.uuid4().hex[:12].upper()}"

                prescription.items.append(
                    PrescriptionItem(
                        medicine_ref=medicine_ref,
                        medicine_source=source,
                        medicine_name=medicine_name,
                        medicine_form=medicine_form or None,
                        medicine_strength=medicine_strength or None,
                        dose=dose,
                        frequency=frequency,
                        duration=duration,
                        instructions=raw.instructions.strip() or None,
                    )
                )
            session.add(prescription)
            session.commit()

            # LOT E integration: persist an outbox trace and expose the issued
            # prescription to Pharmacy when that service is online. The clinical
            # prescription stays valid even if Pharmacy is temporarily unavailable.
            pharmacy_outbox = OutboundRequest(
                correlation_id=str(uuid.uuid4()),
                consultation_id=consultation.id,
                patient_id=consultation.patient_id,
                request_type="PRESCRIPTION",
                target_service="PHARMACIE",
                payload_json=json.dumps({
                    "prescription_id": prescription.id,
                    "prescription_number": prescription.prescription_number,
                    "doctor_id": actor.id,
                    "items": [
                        {
                            "medicine_ref": line.medicine_ref,
                            "medicine_source": line.medicine_source,
                            "medicine_name": line.medicine_name,
                            "medicine_form": line.medicine_form or "",
                            "medicine_strength": line.medicine_strength or "",
                            "dose": line.dose,
                            "frequency": line.frequency,
                            "duration": line.duration,
                            "instructions": line.instructions or "",
                        }
                        for line in prescription.items
                    ],
                }, separators=(",", ":"), sort_keys=True),
                summary=f"Prescription: {prescription.prescription_number}",
                status="PENDING_DELIVERY",
                created_by=actor.id,
            )
            session.add(pharmacy_outbox)
            session.commit()
            session.refresh(pharmacy_outbox)

            try:
                with grpc.insecure_channel(PHARMACIE_GRPC_TARGET) as channel:
                    stub = pharmacie_pb2_grpc.PharmacieServiceStub(channel)
                    delivered = stub.ExposePrescription(
                        pharmacie_pb2.ExposePrescriptionRequest(
                            prescription_id=prescription.id,
                            prescription_number=prescription.prescription_number,
                            consultation_id=consultation.id,
                            patient_id=consultation.patient_id,
                            doctor_id=actor.id,
                            items=[
                                pharmacie_pb2.PrescriptionLine(
                                    medicine_ref=line.medicine_ref,
                                    dose=line.dose,
                                    frequency=line.frequency,
                                    duration=line.duration,
                                    instructions=line.instructions or "",
                                    medicine_source=(
                                        pharmacie_pb2.PRESCRIPTION_MEDICINE_SOURCE_EXTERNAL
                                        if line.medicine_source == "EXTERNAL"
                                        else pharmacie_pb2.PRESCRIPTION_MEDICINE_SOURCE_HOSPITAL_CATALOG
                                    ),
                                    medicine_name=line.medicine_name or line.medicine_ref,
                                    medicine_form=line.medicine_form or "",
                                    medicine_strength=line.medicine_strength or "",
                                    dispensable_by_hospital=(line.medicine_source != "EXTERNAL"),
                                )
                                for line in prescription.items
                            ],
                            correlation_id=pharmacy_outbox.correlation_id,
                        ),
                        metadata=_authorization_metadata(context),
                        timeout=5,
                    )
                pharmacy_outbox.status = "DELIVERED"
                pharmacy_outbox.summary = f"Prescription: {prescription.prescription_number} -> Pharmacy"
                session.commit()
                logger.info(
                    "rpc=IssuePrescription peer=%s actor=%s prescription=%s correlation_id=%s outcome=PHARMACY_DELIVERED",
                    context.peer(), actor.id, prescription.id, pharmacy_outbox.correlation_id,
                )
            except grpc.RpcError as error:
                if error.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    logger.warning(
                        "rpc=IssuePrescription peer=%s actor=%s prescription=%s correlation_id=%s outcome=PHARMACY_PENDING target_error=%s",
                        context.peer(), actor.id, prescription.id, pharmacy_outbox.correlation_id, error.code().name,
                    )
                else:
                    pharmacy_outbox.status = "FAILED"
                    pharmacy_outbox.summary = f"Prescription: {prescription.prescription_number} -> Pharmacy rejected"
                    session.commit()
                    logger.warning(
                        "rpc=IssuePrescription peer=%s actor=%s prescription=%s outcome=PHARMACY_REJECTED status=%s",
                        context.peer(), actor.id, prescription.id, error.code().name,
                    )

            # The prescription object already contains the committed database IDs
            # and its items in this session. Returning it directly avoids relying
            # on a previously-loaded Consultation.prescriptions collection, which
            # can remain stale when expire_on_commit=False.
            logger.info(
                "rpc=IssuePrescription peer=%s actor=%s consultation=%s prescription=%s outcome=OK",
                context.peer(),
                actor.id,
                consultation.id,
                prescription.id,
            )
            return consultation_pb2.PrescriptionResponse(
                prescription=prescription_to_proto(prescription)
            )
        except IntegrityError:
            session.rollback()
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Prescription could not be created because of a duplicate value.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=IssuePrescription peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Prescription could not be issued.")
        finally:
            session.close()


    def RequestLabTest(self, request, context):
        actor = require_permission(context, "consultation.lab.request")
        consultation_id = request.consultation_id.strip()
        test_code = request.test_code.strip().upper()
        test_name = request.test_name.strip()
        if not consultation_id or not test_name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "consultation_id and test_name are required.")

        session = ConsultationSessionLocal()
        try:
            consultation = get_consultation(session, consultation_id)
            if consultation is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Consultation not found.")
            require_open(consultation, context)

            payload = {
                "test_code": test_code,
                "test_name": test_name,
                "clinical_information": request.clinical_information.strip(),
                "doctor_id": actor.id,
            }
            item = OutboundRequest(
                correlation_id=str(uuid.uuid4()),
                consultation_id=consultation.id,
                patient_id=consultation.patient_id,
                request_type="LAB_TEST",
                target_service="LABORATOIRE",
                payload_json=json.dumps(payload, separators=(",", ":"), sort_keys=True),
                summary=f"Lab test: {test_name}",
                status="PENDING_DELIVERY",
                created_by=actor.id,
            )
            session.add(item)
            session.commit()
            session.refresh(item)

            # LOT D integration: deliver synchronously when Laboratoire is online.
            # The local outbox row remains the durable trace/fallback if the target is unavailable.
            if test_code:
                try:
                    with grpc.insecure_channel(LABORATOIRE_GRPC_TARGET) as channel:
                        stub = laboratoire_pb2_grpc.LaboratoireServiceStub(channel)
                        delivered = stub.CreateLabOrder(
                            laboratoire_pb2.CreateLabOrderRequest(
                                patient_id=consultation.patient_id,
                                consultation_id=consultation.id,
                                test_code=test_code,
                                priority=laboratoire_pb2.LAB_PRIORITY_ROUTINE,
                                clinical_question=request.clinical_information.strip(),
                                correlation_id=item.correlation_id,
                            ),
                            metadata=_authorization_metadata(context),
                            timeout=5,
                        )
                    item.status = "DELIVERED"
                    item.summary = f"Lab test: {test_name} -> {delivered.order.order_number}"
                    session.commit()
                    session.refresh(item)
                    logger.info(
                        "rpc=RequestLabTest peer=%s actor=%s consultation=%s correlation_id=%s lab_order=%s outcome=DELIVERED",
                        context.peer(), actor.id, consultation.id, item.correlation_id, delivered.order.id,
                    )
                except grpc.RpcError as error:
                    if error.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                        logger.warning(
                            "rpc=RequestLabTest peer=%s actor=%s consultation=%s correlation_id=%s outcome=PENDING target_error=%s",
                            context.peer(), actor.id, consultation.id, item.correlation_id, error.code().name,
                        )
                    else:
                        item.status = "FAILED"
                        session.commit()
                        context.abort(error.code(), error.details() or "Laboratory request rejected.")
            else:
                logger.warning(
                    "rpc=RequestLabTest peer=%s actor=%s consultation=%s correlation_id=%s outcome=PENDING reason=NO_TEST_CODE",
                    context.peer(), actor.id, consultation.id, item.correlation_id,
                )

            return consultation_pb2.ExternalRequestResponse(request=outbound_to_proto(item))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=RequestLabTest peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Laboratory request could not be queued.")
        finally:
            session.close()


    def RequestHospitalization(self, request, context):
        actor = require_permission(context, "hospitalisation.admit")
        consultation_id = request.consultation_id.strip()
        reason = request.reason.strip()
        if not consultation_id or not reason:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "consultation_id and reason are required.")
        if request.target not in (
            consultation_pb2.HOSPITALIZATION_TARGET_HOSPITALISATION,
            consultation_pb2.HOSPITALIZATION_TARGET_MATERNITE,
        ):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "A valid hospitalization target is required.")

        request_type = "MATERNITY" if request.target == consultation_pb2.HOSPITALIZATION_TARGET_MATERNITE else "HOSPITALIZATION"
        target_service = "MATERNITE" if request_type == "MATERNITY" else "HOSPITALISATION"
        session = ConsultationSessionLocal()
        try:
            consultation = get_consultation(session, consultation_id)
            if consultation is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Consultation not found.")
            require_open(consultation, context)
            payload = {"reason": reason, "preferred_ward": request.preferred_ward.strip(), "doctor_id": actor.id}
            item = OutboundRequest(
                correlation_id=str(uuid.uuid4()), consultation_id=consultation.id, patient_id=consultation.patient_id,
                request_type=request_type, target_service=target_service,
                payload_json=json.dumps(payload, separators=(",", ":"), sort_keys=True), summary=reason,
                status="PENDING_DELIVERY", created_by=actor.id,
            )
            session.add(item); session.commit(); session.refresh(item)

            # LOT I: real synchronous delivery for Hospitalisation and Maternite.
            if request_type == "HOSPITALIZATION":
                try:
                    with grpc.insecure_channel(HOSPITALISATION_GRPC_TARGET) as channel:
                        stub = hospitalisation_pb2_grpc.HospitalisationServiceStub(channel)
                        delivered = stub.CreateAdmission(
                            hospitalisation_pb2.CreateAdmissionRequest(
                                patient_id=consultation.patient_id,
                                consultation_id=consultation.id,
                                reason=reason,
                                preferred_ward=request.preferred_ward.strip(),
                                correlation_id=item.correlation_id,
                                idempotency_key=item.correlation_id,
                            ),
                            metadata=_authorization_metadata(context), timeout=5,
                        )
                    item.status = "DELIVERED"
                    item.summary = f"{reason} -> {delivered.admission.admission_number}"
                    session.commit(); session.refresh(item)
                    logger.info(
                        "rpc=RequestHospitalization peer=%s actor=%s consultation=%s correlation_id=%s admission=%s outcome=DELIVERED",
                        context.peer(), actor.id, consultation.id, item.correlation_id, delivered.admission.id,
                    )
                except grpc.RpcError as error:
                    if error.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                        logger.warning(
                            "rpc=RequestHospitalization peer=%s actor=%s consultation=%s correlation_id=%s outcome=PENDING target_error=%s",
                            context.peer(), actor.id, consultation.id, item.correlation_id, error.code().name,
                        )
                    else:
                        item.status = "FAILED"; session.commit()
                        context.abort(error.code(), error.details() or "Hospitalisation request rejected.")
            else:
                try:
                    with grpc.insecure_channel(MATERNITE_GRPC_TARGET) as channel:
                        stub = maternite_pb2_grpc.MaterniteServiceStub(channel)
                        delivered = stub.CreateMaternityCase(
                            maternite_pb2.CreateMaternityCaseRequest(
                                patient_id=consultation.patient_id,
                                consultation_id=consultation.id,
                                gravida=0,
                                para=0,
                                risk_level=maternite_pb2.RISK_LEVEL_LOW,
                                referral_reason=reason,
                                correlation_id=item.correlation_id,
                                idempotency_key=item.correlation_id,
                            ),
                            metadata=_authorization_metadata(context), timeout=5,
                        )
                    item.status = "DELIVERED"
                    item.summary = f"{reason} -> {delivered.record.pregnancy.pregnancy_number}"
                    session.commit(); session.refresh(item)
                    logger.info(
                        "rpc=RequestHospitalization peer=%s actor=%s consultation=%s correlation_id=%s pregnancy=%s target=MATERNITE outcome=DELIVERED",
                        context.peer(), actor.id, consultation.id, item.correlation_id, delivered.record.pregnancy.id,
                    )
                except grpc.RpcError as error:
                    if error.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                        logger.warning(
                            "rpc=RequestHospitalization peer=%s actor=%s consultation=%s correlation_id=%s target=MATERNITE outcome=PENDING target_error=%s",
                            context.peer(), actor.id, consultation.id, item.correlation_id, error.code().name,
                        )
                    else:
                        item.status = "FAILED"; session.commit()
                        context.abort(error.code(), error.details() or "Maternite request rejected.")
            return consultation_pb2.ExternalRequestResponse(request=outbound_to_proto(item))
        except SQLAlchemyError:
            session.rollback(); logger.exception("rpc=RequestHospitalization peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Hospitalization request could not be queued.")
        finally:
            session.close()

    def CloseConsultation(self, request, context):
        actor = require_permission(context, "consultation.close")
        consultation_id = request.consultation_id.strip()
        if not consultation_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "consultation_id is required.")
        session = ConsultationSessionLocal()
        try:
            item = get_consultation(session, consultation_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Consultation not found.")
            require_open(item, context)
            if request.closing_notes.strip():
                current = item.notes.strip() if item.notes else ""
                addition = request.closing_notes.strip()
                item.notes = f"{current}\n{addition}".strip()
            item.status = "CLOSED"
            item.closed_at = utc_now()
            item.updated_at = utc_now()
            item.updated_by = actor.id
            session.commit()
            item = get_consultation(session, item.id)
            logger.info("rpc=CloseConsultation peer=%s actor=%s consultation=%s outcome=OK", context.peer(), actor.id, item.id)
            return consultation_pb2.ConsultationResponse(consultation=consultation_to_proto(item))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=CloseConsultation peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Consultation could not be closed.")
        finally:
            session.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return build_health_response("ONLINE", "Consultation service and MySQL are available.")
        except SQLAlchemyError:
            logger.exception("rpc=HealthCheck peer=%s outcome=DEGRADED", context.peer())
            return build_health_response("DEGRADED", "Consultation service is running but MySQL is unavailable.")
