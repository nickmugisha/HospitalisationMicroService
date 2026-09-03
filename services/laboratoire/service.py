from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from accueil.v1 import accueil_pb2, accueil_pb2_grpc
from billing.v1 import billing_pb2, billing_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from services.common.notifications import send_system_notification
from laboratoire.v1 import laboratoire_pb2, laboratoire_pb2_grpc
from database.laboratoire_session import LaboratoireSessionLocal, engine
from services.common.auth_guard import require_permission
from services.laboratoire.config import ACCUEIL_GRPC_TARGET, AUTH_GRPC_TARGET, BILLING_GRPC_TARGET, SERVICE_VERSION
from services.laboratoire.models import BillingOutbox, LabOrder, Result, ResultCorrection, Sample
from services.laboratoire.repository import (
    get_order,
    get_test_by_ref,
    list_lab_tests,
    get_order_by_correlation,
    get_test_by_code,
    list_patient_result_orders,
    list_pending_orders,
)


logger = logging.getLogger("projectx.laboratoire.service")

STATUS_DB_TO_PROTO = {
    "ORDERED": laboratoire_pb2.LAB_ORDER_STATUS_ORDERED,
    "SAMPLE_COLLECTED": laboratoire_pb2.LAB_ORDER_STATUS_SAMPLE_COLLECTED,
    "IN_PROGRESS": laboratoire_pb2.LAB_ORDER_STATUS_IN_PROGRESS,
    "RESULTED": laboratoire_pb2.LAB_ORDER_STATUS_RESULTED,
    "VALIDATED": laboratoire_pb2.LAB_ORDER_STATUS_VALIDATED,
    "CANCELLED": laboratoire_pb2.LAB_ORDER_STATUS_CANCELLED,
}
PRIORITY_PROTO_TO_DB = {
    laboratoire_pb2.LAB_PRIORITY_ROUTINE: "ROUTINE",
    laboratoire_pb2.LAB_PRIORITY_URGENT: "URGENT",
    laboratoire_pb2.LAB_PRIORITY_STAT: "STAT",
}
PRIORITY_DB_TO_PROTO = {value: key for key, value in PRIORITY_PROTO_TO_DB.items()}
BILLING_DB_TO_PROTO = {
    "NOT_CREATED": laboratoire_pb2.BILLING_CHARGE_STATUS_NOT_CREATED,
    "PENDING_DELIVERY": laboratoire_pb2.BILLING_CHARGE_STATUS_PENDING_DELIVERY,
    "DELIVERED": laboratoire_pb2.BILLING_CHARGE_STATUS_DELIVERED,
    "FAILED": laboratoire_pb2.BILLING_CHARGE_STATUS_FAILED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_timestamp(value: datetime | None) -> Timestamp:
    result = Timestamp()
    if value is not None:
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        result.FromDatetime(aware)
    return result


def generate_order_number() -> str:
    return f"LAB-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def generate_sample_code() -> str:
    return f"SMP-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _authorization_metadata(context):
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization" and item.value.strip():
            return (("authorization", item.value.strip()),)
    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing authorization metadata.")


def _deliver_billing_charge(context, outbox: BillingOutbox) -> bool:
    try:
        with grpc.insecure_channel(BILLING_GRPC_TARGET) as channel:
            stub = billing_pb2_grpc.BillingServiceStub(channel)
            stub.CreateCharge(
                billing_pb2.CreateChargeRequest(
                    source_type="LABORATOIRE",
                    source_id=outbox.source_ref,
                    patient_id=outbox.patient_id,
                    amount_minor=outbox.amount_minor,
                    currency_code=outbox.currency,
                    description=outbox.description,
                    idempotency_key=outbox.idempotency_key,
                    correlation_id=outbox.correlation_id,
                ),
                metadata=_authorization_metadata(context),
                timeout=5,
            )
        return True
    except grpc.RpcError as error:
        logger.warning(
            "billing delivery deferred source=LABORATOIRE source_id=%s status=%s detail=%s",
            outbox.source_ref, error.code().name, error.details(),
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


def page_values(limit: int, offset: int, context):
    if offset < 0:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "offset cannot be negative.")
    if limit <= 0:
        limit = 50
    return min(limit, 200), offset


def test_to_proto(item):
    return laboratoire_pb2.LabTest(
        id=item.id,
        code=item.code,
        name=item.name,
        sample_type=item.sample_type,
        price_minor=item.price_minor,
        currency=item.currency,
        active=item.active,
    )


def sample_to_proto(item):
    if item is None:
        return laboratoire_pb2.Sample()
    return laboratoire_pb2.Sample(
        id=item.id,
        sample_code=item.sample_code,
        order_id=item.order_id,
        collected_by=item.collected_by,
        collected_at=to_timestamp(item.collected_at),
        notes=item.notes or "",
    )


def result_values_to_proto(raw: str | None):
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return [laboratoire_pb2.ResultValue(**item) for item in values]


def result_to_proto(item: Result | None):
    if item is None:
        return laboratoire_pb2.LabResult()
    return laboratoire_pb2.LabResult(
        id=item.id,
        order_id=item.order_id,
        patient_id=item.patient_id,
        consultation_id=item.consultation_id,
        values=result_values_to_proto(item.values_json),
        text_result=item.text_result or "",
        recorded_by=item.recorded_by,
        recorded_at=to_timestamp(item.recorded_at),
        validated_by=item.validated_by or "",
        validated_at=to_timestamp(item.validated_at),
        version=item.version,
    )


def order_to_proto(item: LabOrder):
    return laboratoire_pb2.LabOrder(
        id=item.id,
        order_number=item.order_number,
        patient_id=item.patient_id,
        consultation_id=item.consultation_id,
        test=test_to_proto(item.test),
        priority=PRIORITY_DB_TO_PROTO.get(item.priority, laboratoire_pb2.LAB_PRIORITY_UNSPECIFIED),
        clinical_question=item.clinical_question or "",
        status=STATUS_DB_TO_PROTO.get(item.status, laboratoire_pb2.LAB_ORDER_STATUS_UNSPECIFIED),
        correlation_id=item.correlation_id,
        ordered_by=item.ordered_by,
        ordered_at=to_timestamp(item.ordered_at),
        sample=sample_to_proto(item.sample),
        result=result_to_proto(item.result),
        billing_charge_status=BILLING_DB_TO_PROTO.get(
            item.billing_charge_status,
            laboratoire_pb2.BILLING_CHARGE_STATUS_UNSPECIFIED,
        ),
    )


def serialize_result_values(values, context):
    serialized = []
    for value in values:
        name = value.name.strip()
        raw_value = value.value.strip()
        if not name or not raw_value:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Each structured result needs name and value.")
        serialized.append({
            "name": name,
            "value": raw_value,
            "unit": value.unit.strip(),
            "reference_range": value.reference_range.strip(),
            "flag": value.flag.strip(),
        })
    return json.dumps(serialized, ensure_ascii=False, separators=(",", ":"), sort_keys=True) if serialized else None


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
    return build_health_response_compat("laboratoire", desired, message, SERVICE_VERSION)

class LaboratoireService(laboratoire_pb2_grpc.LaboratoireServiceServicer):
    def ListLabTests(self, request, context):
        require_permission(context, "lab.catalog.read")
        limit, offset = page_values(request.limit, request.offset, context)
        session = LaboratoireSessionLocal()
        try:
            items, total = list_lab_tests(session, query=request.query, active_only=request.active_only, limit=limit, offset=offset)
            return laboratoire_pb2.ListLabTestsResponse(tests=[test_to_proto(item) for item in items], total=total)
        finally:
            session.close()

    def GetLabTest(self, request, context):
        require_permission(context, "lab.catalog.read")
        ref = request.test_ref.strip()
        if not ref:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "test_ref is required.")
        session = LaboratoireSessionLocal()
        try:
            item = get_test_by_ref(session, ref)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Laboratory test not found.")
            return laboratoire_pb2.LabTestResponse(test=test_to_proto(item))
        finally:
            session.close()

    def CreateLabOrder(self, request, context):
        actor = require_permission(context, "consultation.lab.request")
        patient_id = request.patient_id.strip()
        consultation_id = request.consultation_id.strip()
        test_code = request.test_code.strip().upper()
        correlation_id = request.correlation_id.strip() or str(uuid.uuid4())
        if not patient_id or not consultation_id or not test_code:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id, consultation_id and test_code are required.")
        priority = PRIORITY_PROTO_TO_DB.get(request.priority, "ROUTINE")
        validate_patient_exists(context, patient_id)

        session = LaboratoireSessionLocal()
        try:
            existing = get_order_by_correlation(session, correlation_id)
            if existing is not None:
                return laboratoire_pb2.LabOrderResponse(order=order_to_proto(existing))
            lab_test = get_test_by_code(session, test_code)
            if lab_test is None or not lab_test.active:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Active laboratory test not found: {test_code}")
            item = LabOrder(
                order_number=generate_order_number(),
                patient_id=patient_id,
                consultation_id=consultation_id,
                lab_test_id=lab_test.id,
                priority=priority,
                clinical_question=request.clinical_question.strip() or None,
                status="ORDERED",
                correlation_id=correlation_id,
                ordered_by=actor.id,
                billing_charge_status="NOT_CREATED",
            )
            session.add(item)
            session.commit()
            item = get_order(session, item.id)
            logger.info(
                "rpc=CreateLabOrder peer=%s actor=%s order=%s patient=%s correlation_id=%s outcome=OK",
                context.peer(), actor.id, item.id, patient_id, correlation_id,
            )
            return laboratoire_pb2.LabOrderResponse(order=order_to_proto(item))
        except IntegrityError:
            session.rollback()
            existing = get_order_by_correlation(session, correlation_id)
            if existing is not None:
                return laboratoire_pb2.LabOrderResponse(order=order_to_proto(existing))
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Laboratory order could not be created because of a duplicate value.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=CreateLabOrder peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Laboratory order could not be created.")
        finally:
            session.close()

    def ListPendingOrders(self, request, context):
        actor = require_permission(context, "lab.orders.read")
        limit, offset = page_values(request.limit, request.offset, context)
        priority = PRIORITY_PROTO_TO_DB.get(request.priority) if request.priority else None
        session = LaboratoireSessionLocal()
        try:
            items, total = list_pending_orders(session, priority=priority, limit=limit, offset=offset)
            logger.info("rpc=ListPendingOrders peer=%s actor=%s count=%s outcome=OK", context.peer(), actor.id, len(items))
            return laboratoire_pb2.ListLabOrdersResponse(
                orders=[order_to_proto(item) for item in items],
                total=total,
            )
        finally:
            session.close()

    def CollectSample(self, request, context):
        actor = require_permission(context, "lab.sample.collect")
        order_id = request.order_id.strip()
        if not order_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "order_id is required.")
        session = LaboratoireSessionLocal()
        try:
            item = get_order(session, order_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Laboratory order not found.")
            if item.status != "ORDERED":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Sample can only be collected for an ORDERED lab order.")
            item.sample = Sample(
                sample_code=generate_sample_code(),
                collected_by=actor.id,
                notes=request.notes.strip() or None,
            )
            item.status = "SAMPLE_COLLECTED"
            item.updated_at = utc_now()
            session.commit()
            item = get_order(session, item.id)
            logger.info("rpc=CollectSample peer=%s actor=%s order=%s sample=%s outcome=OK", context.peer(), actor.id, item.id, item.sample.id)
            return laboratoire_pb2.LabOrderResponse(order=order_to_proto(item))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=CollectSample peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Sample could not be recorded.")
        finally:
            session.close()

    def RecordResult(self, request, context):
        actor = require_permission(context, "lab.result.record")
        order_id = request.order_id.strip()
        if not order_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "order_id is required.")
        if not request.values and not request.text_result.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Structured values or text_result is required.")
        values_json = serialize_result_values(request.values, context)
        text_result = request.text_result.strip() or None
        correction_reason = request.correction_reason.strip()

        session = LaboratoireSessionLocal()
        try:
            item = get_order(session, order_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Laboratory order not found.")
            if item.status in ("ORDERED", "CANCELLED"):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "A sample must be collected before recording results.")

            if item.status == "VALIDATED":
                if not correction_reason:
                    context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION,
                        "Validated result is final. A traced correction requires correction_reason.",
                    )
                if item.result is None:
                    context.abort(grpc.StatusCode.INTERNAL, "Validated order has no result record.")
                session.add(ResultCorrection(
                    result_id=item.result.id,
                    previous_values_json=item.result.values_json,
                    previous_text_result=item.result.text_result,
                    previous_version=item.result.version,
                    reason=correction_reason,
                    corrected_by=actor.id,
                ))
                item.result.values_json = values_json
                item.result.text_result = text_result
                item.result.recorded_by = actor.id
                item.result.recorded_at = utc_now()
                item.result.validated_by = None
                item.result.validated_at = None
                item.result.version += 1
                item.status = "RESULTED"
                item.billing_charge_status = "NOT_CREATED"
            elif item.status in ("SAMPLE_COLLECTED", "IN_PROGRESS", "RESULTED"):
                if item.result is None:
                    item.result = Result(
                        patient_id=item.patient_id,
                        consultation_id=item.consultation_id,
                        values_json=values_json,
                        text_result=text_result,
                        recorded_by=actor.id,
                        version=1,
                    )
                else:
                    item.result.values_json = values_json
                    item.result.text_result = text_result
                    item.result.recorded_by = actor.id
                    item.result.recorded_at = utc_now()
                item.status = "RESULTED"
            else:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Cannot record result while order is {item.status}.")

            item.updated_at = utc_now()
            session.commit()
            item = get_order(session, item.id)
            logger.info("rpc=RecordResult peer=%s actor=%s order=%s version=%s outcome=OK", context.peer(), actor.id, item.id, item.result.version)
            return laboratoire_pb2.LabResultResponse(result=result_to_proto(item.result), order=order_to_proto(item))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=RecordResult peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Laboratory result could not be recorded.")
        finally:
            session.close()

    def ValidateResult(self, request, context):
        actor = require_permission(context, "lab.result.validate")
        order_id = request.order_id.strip()
        if not order_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "order_id is required.")
        session = LaboratoireSessionLocal()
        try:
            item = get_order(session, order_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Laboratory order not found.")
            if item.status == "VALIDATED":
                return laboratoire_pb2.LabResultResponse(result=result_to_proto(item.result), order=order_to_proto(item))
            if item.status != "RESULTED" or item.result is None:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only a RESULTED laboratory order can be validated.")

            item.result.validated_by = actor.id
            item.result.validated_at = utc_now()
            item.status = "VALIDATED"
            item.updated_at = utc_now()

            if item.test.price_minor > 0:
                key = f"LAB:{item.id}"
                existing_charge = session.scalar(select(BillingOutbox).where(BillingOutbox.idempotency_key == key))
                if existing_charge is None:
                    session.add(BillingOutbox(
                        idempotency_key=key,
                        correlation_id=item.correlation_id,
                        patient_id=item.patient_id,
                        source_ref=item.id,
                        amount_minor=item.test.price_minor,
                        currency=item.test.currency,
                        description=f"Laboratoire - {item.test.name}",
                        status="PENDING_DELIVERY",
                    ))
                item.billing_charge_status = "PENDING_DELIVERY"

            session.commit()

            if item.billing_charge_status == "PENDING_DELIVERY":
                outbox = session.scalar(
                    select(BillingOutbox).where(BillingOutbox.source_ref == item.id)
                )
                if outbox is not None and _deliver_billing_charge(context, outbox):
                    outbox.status = "DELIVERED"
                    outbox.delivered_at = utc_now()
                    item.billing_charge_status = "DELIVERED"
                    session.commit()

            item = get_order(session, item.id)
            send_system_notification(
                auth_target=AUTH_GRPC_TARGET, recipient_id=item.ordered_by,
                notification_type="LAB_RESULT_VALIDATED",
                title="Résultat laboratoire validé / Lab result validated",
                body=f"Le résultat / result {item.order_number} ({item.test.name}) est validé et disponible.",
                source_service="laboratoire", correlation_id=item.correlation_id,
            )
            logger.info("rpc=ValidateResult peer=%s actor=%s order=%s billing=%s outcome=OK", context.peer(), actor.id, item.id, item.billing_charge_status)
            return laboratoire_pb2.LabResultResponse(result=result_to_proto(item.result), order=order_to_proto(item))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=ValidateResult peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Laboratory result could not be validated.")
        finally:
            session.close()

    def GetLabResult(self, request, context):
        actor = require_permission(context, "lab.orders.read")
        order_id = request.order_id.strip()
        if not order_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "order_id is required.")
        session = LaboratoireSessionLocal()
        try:
            item = get_order(session, order_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Laboratory order not found.")
            if item.result is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Laboratory result is not available yet.")
            logger.info("rpc=GetLabResult peer=%s actor=%s order=%s outcome=OK", context.peer(), actor.id, item.id)
            return laboratoire_pb2.LabResultResponse(result=result_to_proto(item.result), order=order_to_proto(item))
        finally:
            session.close()

    def ListPatientLabResults(self, request, context):
        actor = require_permission(context, "lab.orders.read")
        patient_id = request.patient_id.strip()
        if not patient_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id is required.")
        limit, offset = page_values(request.limit, request.offset, context)
        session = LaboratoireSessionLocal()
        try:
            items, total = list_patient_result_orders(session, patient_id=patient_id, limit=limit, offset=offset)
            results = [result_to_proto(item.result) for item in items if item.result is not None]
            logger.info("rpc=ListPatientLabResults peer=%s actor=%s patient=%s count=%s outcome=OK", context.peer(), actor.id, patient_id, len(results))
            return laboratoire_pb2.ListLabResultsResponse(results=results, total=total)
        finally:
            session.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return build_health_response("ONLINE", "Laboratoire service and MySQL are available.")
        except SQLAlchemyError:
            logger.exception("rpc=HealthCheck peer=%s outcome=DEGRADED", context.peer())
            return build_health_response("DEGRADED", "Laboratoire service is running but MySQL is unavailable.")
