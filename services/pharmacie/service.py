from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload

from billing.v1 import billing_pb2, billing_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from services.common.notifications import list_role_recipients, send_system_notification
from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc
from database.pharmacie_session import PharmacieSessionLocal, engine
from services.common.auth_guard import require_permission
from services.pharmacie.config import AUTH_GRPC_TARGET, BILLING_GRPC_TARGET, SERVICE_VERSION
from services.pharmacie.models import (
    Batch,
    BillingOutbox,
    Dispensation,
    DispensationAllocation,
    DispensationItem,
    Medicine,
    PrescriptionInbox,
    PrescriptionInboxItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    StockMovement,
    StockAlertDispatch,
    Supplier,
)
from services.pharmacie.repository import (
    get_dispensation,
    get_dispensation_by_key,
    get_medicine_by_ref,
    get_prescription,
    get_purchase_order,
    get_purchase_order_by_key,
    get_stock_batches,
    get_supplier_by_code,
    list_prescriptions,
    list_purchase_orders,
    list_suppliers,
    search_medicines,
)


logger = logging.getLogger("projectx.pharmacie.service")

PRESCRIPTION_STATUS_DB_TO_PROTO = {
    "ISSUED": pharmacie_pb2.PRESCRIPTION_INBOX_STATUS_ISSUED,
    "PARTIAL": pharmacie_pb2.PRESCRIPTION_INBOX_STATUS_PARTIAL,
    "COMPLETED": pharmacie_pb2.PRESCRIPTION_INBOX_STATUS_COMPLETED,
    "CANCELLED": pharmacie_pb2.PRESCRIPTION_INBOX_STATUS_CANCELLED,
}
DISP_STATUS_DB_TO_PROTO = {
    "PARTIAL": pharmacie_pb2.DISPENSATION_STATUS_PARTIAL,
    "COMPLETED": pharmacie_pb2.DISPENSATION_STATUS_COMPLETED,
}
BILLING_DB_TO_PROTO = {
    "NOT_CREATED": pharmacie_pb2.BILLING_CHARGE_STATUS_NOT_CREATED,
    "PENDING_DELIVERY": pharmacie_pb2.BILLING_CHARGE_STATUS_PENDING_DELIVERY,
    "DELIVERED": pharmacie_pb2.BILLING_CHARGE_STATUS_DELIVERED,
    "FAILED": pharmacie_pb2.BILLING_CHARGE_STATUS_FAILED,
}
PO_STATUS_PROTO_TO_DB = {
    pharmacie_pb2.PURCHASE_ORDER_STATUS_ORDERED: "ORDERED",
    pharmacie_pb2.PURCHASE_ORDER_STATUS_PARTIALLY_RECEIVED: "PARTIALLY_RECEIVED",
    pharmacie_pb2.PURCHASE_ORDER_STATUS_RECEIVED: "RECEIVED",
    pharmacie_pb2.PURCHASE_ORDER_STATUS_CANCELLED: "CANCELLED",
}

PO_STATUS_DB_TO_PROTO = {
    "ORDERED": pharmacie_pb2.PURCHASE_ORDER_STATUS_ORDERED,
    "PARTIALLY_RECEIVED": pharmacie_pb2.PURCHASE_ORDER_STATUS_PARTIALLY_RECEIVED,
    "RECEIVED": pharmacie_pb2.PURCHASE_ORDER_STATUS_RECEIVED,
    "CANCELLED": pharmacie_pb2.PURCHASE_ORDER_STATUS_CANCELLED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_timestamp(value: datetime | None) -> Timestamp:
    result = Timestamp()
    if value is not None:
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        result.FromDatetime(aware)
    return result


def parse_date(raw: str, context) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except (TypeError, ValueError):
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Date must use YYYY-MM-DD format.")


def generate_dispensation_number() -> str:
    return f"DSP-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def generate_po_number() -> str:
    return f"PO-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _authorization_metadata(context):
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization" and item.value.strip():
            return (("authorization", item.value.strip()),)
    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing authorization metadata.")


def _deliver_billing_charge(context, outbox: BillingOutbox, correlation_id: str) -> bool:
    try:
        with grpc.insecure_channel(BILLING_GRPC_TARGET) as channel:
            stub = billing_pb2_grpc.BillingServiceStub(channel)
            stub.CreateCharge(
                billing_pb2.CreateChargeRequest(
                    source_type="PHARMACIE",
                    source_id=outbox.dispensation_id,
                    patient_id=outbox.patient_id,
                    amount_minor=outbox.amount_minor,
                    currency_code=outbox.currency,
                    description=f"Pharmacie - dispensation {outbox.dispensation_id}",
                    idempotency_key=outbox.idempotency_key,
                    correlation_id=correlation_id,
                ),
                metadata=_authorization_metadata(context),
                timeout=5,
            )
        return True
    except grpc.RpcError as error:
        logger.warning(
            "billing delivery deferred source=PHARMACIE source_id=%s status=%s detail=%s",
            outbox.dispensation_id, error.code().name, error.details(),
        )
        return False


def page_values(limit: int, offset: int, context):
    if offset < 0:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "offset cannot be negative.")
    if limit <= 0:
        limit = 50
    return min(limit, 200), offset


def medicine_to_proto(item: Medicine):
    return pharmacie_pb2.Medicine(
        id=item.id,
        code=item.code,
        name=item.name,
        form=item.form,
        strength=item.strength,
        unit=item.unit,
        sale_price_minor=item.sale_price_minor,
        currency=item.currency,
        reorder_level=item.reorder_level,
        active=item.active,
    )


def supplier_to_proto(item: Supplier):
    return pharmacie_pb2.Supplier(
        id=item.id, code=item.code, name=item.name, phone=item.phone or "", email=item.email or "", active=item.active
    )


def batch_to_proto(item: Batch):
    return pharmacie_pb2.Batch(
        id=item.id,
        batch_number=item.batch_number,
        medicine_id=item.medicine_id,
        expiry_date=item.expiry_date.isoformat(),
        quantity_available=item.quantity_available,
    )


def stock_to_proto(medicine: Medicine, batches):
    today = date.today()
    total = sum(batch.quantity_available for batch in batches if batch.expiry_date > today and batch.quantity_available > 0)
    return pharmacie_pb2.StockSummary(
        medicine=medicine_to_proto(medicine),
        total_available=total,
        batches=[batch_to_proto(batch) for batch in batches],
    )


def prescription_to_proto(item: PrescriptionInbox):
    return pharmacie_pb2.PrescriptionInbox(
        prescription_id=item.id,
        prescription_number=item.prescription_number,
        consultation_id=item.consultation_id,
        patient_id=item.patient_id,
        doctor_id=item.doctor_id,
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
            for line in item.items
        ],
        status=PRESCRIPTION_STATUS_DB_TO_PROTO.get(item.status, pharmacie_pb2.PRESCRIPTION_INBOX_STATUS_UNSPECIFIED),
        correlation_id=item.correlation_id,
        exposed_at=to_timestamp(item.exposed_at),
    )


def dispensation_to_proto(item: Dispensation):
    result_items = []
    for line in item.items:
        allocations = []
        for allocation in line.allocations:
            allocations.append(
                pharmacie_pb2.BatchAllocation(
                    batch_id=allocation.batch.id,
                    batch_number=allocation.batch.batch_number,
                    quantity=allocation.quantity,
                    expiry_date=allocation.batch.expiry_date.isoformat(),
                )
            )
        result_items.append(
            pharmacie_pb2.DispensedItem(
                medicine_id=line.medicine_id,
                medicine_code=line.medicine.code,
                medicine_name=line.medicine.name,
                quantity=line.quantity,
                unit_price_minor=line.unit_price_minor,
                line_total_minor=line.line_total_minor,
                allocations=allocations,
            )
        )
    return pharmacie_pb2.Dispensation(
        id=item.id,
        dispensation_number=item.dispensation_number,
        prescription_id=item.prescription_id,
        patient_id=item.patient_id,
        status=DISP_STATUS_DB_TO_PROTO.get(item.status, pharmacie_pb2.DISPENSATION_STATUS_UNSPECIFIED),
        items=result_items,
        amount_minor=item.amount_minor,
        currency=item.currency,
        billing_charge_status=BILLING_DB_TO_PROTO.get(item.billing_charge_status, pharmacie_pb2.BILLING_CHARGE_STATUS_UNSPECIFIED),
        actor_id=item.actor_id,
        created_at=to_timestamp(item.created_at),
    )


def purchase_order_to_proto(item: PurchaseOrder):
    return pharmacie_pb2.PurchaseOrder(
        id=item.id,
        order_number=item.order_number,
        supplier_code=item.supplier.code,
        supplier_name=item.supplier.name,
        status=PO_STATUS_DB_TO_PROTO.get(item.status, pharmacie_pb2.PURCHASE_ORDER_STATUS_UNSPECIFIED),
        items=[
            pharmacie_pb2.PurchaseOrderItem(
                id=line.id,
                medicine=medicine_to_proto(line.medicine),
                quantity_ordered=line.quantity_ordered,
                quantity_received=line.quantity_received,
            )
            for line in item.items
        ],
        created_by=item.created_by,
        ordered_at=to_timestamp(item.ordered_at),
        received_at=to_timestamp(item.received_at),
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
    return build_health_response_compat("pharmacie", desired, message, SERVICE_VERSION)

def build_stock_alerts(session, days: int):
    days = min(max(int(days or 30), 1), 365)
    today = date.today(); limit_date = today + timedelta(days=days)
    medicines = session.scalars(select(Medicine).options(selectinload(Medicine.batches)).where(Medicine.active.is_(True))).all()
    alerts=[]
    for medicine in medicines:
        valid_total=sum(b.quantity_available for b in medicine.batches if b.expiry_date > today and b.quantity_available > 0)
        if valid_total == 0:
            alerts.append(pharmacie_pb2.StockAlert(type=pharmacie_pb2.STOCK_ALERT_TYPE_OUT_OF_STOCK,medicine_id=medicine.id,medicine_code=medicine.code,medicine_name=medicine.name,quantity=0,message="No usable stock available."))
        elif valid_total <= medicine.reorder_level:
            alerts.append(pharmacie_pb2.StockAlert(type=pharmacie_pb2.STOCK_ALERT_TYPE_LOW_STOCK,medicine_id=medicine.id,medicine_code=medicine.code,medicine_name=medicine.name,quantity=valid_total,message=f"Usable stock is at or below reorder level ({medicine.reorder_level})."))
        for batch in medicine.batches:
            if batch.quantity_available <= 0: continue
            if batch.expiry_date <= today:
                alert_type=pharmacie_pb2.STOCK_ALERT_TYPE_EXPIRED; message="Batch is expired and excluded from dispensing."
            elif batch.expiry_date <= limit_date:
                alert_type=pharmacie_pb2.STOCK_ALERT_TYPE_EXPIRING; message=f"Batch expires within {days} days."
            else: continue
            alerts.append(pharmacie_pb2.StockAlert(type=alert_type,medicine_id=medicine.id,medicine_code=medicine.code,medicine_name=medicine.name,batch_id=batch.id,batch_number=batch.batch_number,quantity=batch.quantity_available,expiry_date=batch.expiry_date.isoformat(),message=message))
    return alerts


def stock_alert_fingerprint(alert) -> str:
    # Use a fixed-size ASCII digest rather than indexing a 255-character
    # utf8mb4 string. This keeps the daily de-duplication key well below
    # MySQL/MariaDB index-size limits across supported storage-engine setups.
    raw = f"{int(alert.type)}:{alert.medicine_id}:{alert.batch_id or '-'}:{alert.message}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dispatch_stock_alert_notifications_once(days_to_expiry: int = 30) -> tuple[int,int,int]:
    session=PharmacieSessionLocal()
    try:
        alerts=build_stock_alerts(session,days_to_expiry)
        recipients=sorted(set(
            list_role_recipients(auth_target=AUTH_GRPC_TARGET,role_code="PHARMACIEN") +
            list_role_recipients(auth_target=AUTH_GRPC_TARGET,role_code="RESPONSABLE_LOGISTIQUE")
        ))
        sent=skipped=0; today=date.today()
        for alert in alerts:
            fp=stock_alert_fingerprint(alert)
            if session.scalar(select(StockAlertDispatch).where(StockAlertDispatch.fingerprint==fp,StockAlertDispatch.dispatched_on==today)) is not None:
                skipped+=1; continue
            delivered=0
            for recipient in recipients:
                if send_system_notification(auth_target=AUTH_GRPC_TARGET,recipient_id=recipient,notification_type="STOCK_ALERT",title="Alerte stock / Stock alert",body=f"{alert.medicine_name}: {alert.message}",source_service="pharmacie"):
                    delivered+=1; sent+=1
            if delivered:
                session.add(StockAlertDispatch(fingerprint=fp,alert_type=pharmacie_pb2.StockAlertType.Name(alert.type),medicine_id=alert.medicine_id,batch_id=alert.batch_id or None,dispatched_on=today,recipient_count=delivered))
        session.commit()
        return len(alerts),sent,skipped
    except IntegrityError:
        session.rollback()
        logger.info("stock alert dispatch race detected; another worker/request already recorded alerts")
        return 0,0,0
    except Exception:
        session.rollback(); logger.exception("automatic stock alert dispatch failed"); return 0,0,0
    finally: session.close()


class PharmacieService(pharmacie_pb2_grpc.PharmacieServiceServicer):
    def CreateMedicine(self, request, context):
        actor = require_permission(context, "pharmacy.catalog.manage")
        code=request.code.strip().upper(); name=request.name.strip(); form=request.form.strip(); strength=request.strength.strip(); unit=request.unit.strip()
        if not all([code,name,form,strength,unit]):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,"code, name, form, strength and unit are required.")
        if request.sale_price_minor < 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Price cannot be negative.")
        if request.reorder_level < 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Reorder level cannot be negative.")
        session=PharmacieSessionLocal()
        try:
            if get_medicine_by_ref(session,code) is not None:
                context.abort(grpc.StatusCode.ALREADY_EXISTS,"Medicine code already exists.")
            item=Medicine(code=code,name=name,form=form,strength=strength,unit=unit,sale_price_minor=request.sale_price_minor,
                          currency=request.currency.strip().upper() or "BIF",reorder_level=request.reorder_level,
                          active=(request.active if request.HasField("active") else True))
            session.add(item); session.commit(); session.refresh(item)
            logger.info("rpc=CreateMedicine peer=%s actor=%s medicine=%s outcome=OK",context.peer(),actor.id,item.code)
            return pharmacie_pb2.MedicineResponse(medicine=medicine_to_proto(item))
        except IntegrityError:
            session.rollback(); context.abort(grpc.StatusCode.ALREADY_EXISTS,"Medicine code already exists.")
        finally: session.close()

    def UpdateMedicine(self, request, context):
        actor=require_permission(context,"pharmacy.catalog.manage")
        ref=request.medicine_ref.strip()
        if not ref: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"medicine_ref is required.")
        if request.HasField("sale_price_minor") and request.sale_price_minor < 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Price cannot be negative.")
        if request.HasField("reorder_level") and request.reorder_level < 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,"Reorder level cannot be negative.")
        session=PharmacieSessionLocal()
        try:
            item=get_medicine_by_ref(session,ref)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Medicine not found.")
            if request.name.strip(): item.name=request.name.strip()
            if request.form.strip(): item.form=request.form.strip()
            if request.strength.strip(): item.strength=request.strength.strip()
            if request.unit.strip(): item.unit=request.unit.strip()
            if request.HasField("sale_price_minor"): item.sale_price_minor=request.sale_price_minor
            item.currency=request.currency.strip().upper() or item.currency
            if request.HasField("reorder_level"): item.reorder_level=request.reorder_level
            if request.HasField("active"): item.active=request.active
            session.commit(); session.refresh(item)
            logger.info("rpc=UpdateMedicine peer=%s actor=%s medicine=%s outcome=OK",context.peer(),actor.id,item.code)
            return pharmacie_pb2.MedicineResponse(medicine=medicine_to_proto(item))
        finally: session.close()

    def SearchMedicines(self, request, context):
        actor = require_permission(context, "pharmacy.catalog.read")
        limit, offset = page_values(request.limit, request.offset, context)
        session = PharmacieSessionLocal()
        try:
            rows, total = search_medicines(session, request.query.strip(), request.active_only, limit, offset)
            logger.info("rpc=SearchMedicines peer=%s actor=%s count=%s outcome=OK", context.peer(), actor.id, len(rows))
            return pharmacie_pb2.ListMedicinesResponse(medicines=[medicine_to_proto(x) for x in rows], total=total)
        finally:
            session.close()

    def GetStock(self, request, context):
        actor = require_permission(context, "pharmacy.stock.read")
        medicine_ref = request.medicine_ref.strip()
        if not medicine_ref:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "medicine_ref is required.")
        session = PharmacieSessionLocal()
        try:
            medicine = get_medicine_by_ref(session, medicine_ref)
            if medicine is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Medicine not found.")
            batches = get_stock_batches(session, medicine.id)
            logger.info("rpc=GetStock peer=%s actor=%s medicine=%s outcome=OK", context.peer(), actor.id, medicine.code)
            return pharmacie_pb2.StockResponse(stock=stock_to_proto(medicine, batches))
        finally:
            session.close()

    def RegisterStockEntry(self, request, context):
        actor = require_permission(context, "pharmacy.stock.manage")
        medicine_code = request.medicine_code.strip().upper()
        batch_number = request.batch_number.strip().upper()
        quantity = request.quantity
        reference = request.reference.strip() or "MANUAL_ENTRY"
        if not medicine_code or not batch_number or quantity <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "medicine_code, batch_number and positive quantity are required.")
        expiry = parse_date(request.expiry_date, context)
        if expiry <= date.today():
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Expired or same-day batch cannot be received into available stock.")

        session = PharmacieSessionLocal()
        try:
            medicine = get_medicine_by_ref(session, medicine_code)
            if medicine is None or not medicine.active:
                context.abort(grpc.StatusCode.NOT_FOUND, "Active medicine not found.")
            batch = session.scalar(
                select(Batch).where(Batch.medicine_id == medicine.id, Batch.batch_number == batch_number).with_for_update()
            )
            if batch is None:
                batch = Batch(medicine_id=medicine.id, batch_number=batch_number, expiry_date=expiry, quantity_available=0)
                session.add(batch)
                session.flush()
            elif batch.expiry_date != expiry:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Existing batch number has a different expiry date.")
            batch.quantity_available += quantity
            session.add(StockMovement(
                movement_type="ENTRY",
                medicine_id=medicine.id,
                batch_id=batch.id,
                quantity_delta=quantity,
                reference=reference,
                actor_id=actor.id,
            ))
            session.commit()
            batches = get_stock_batches(session, medicine.id)
            logger.info("rpc=RegisterStockEntry peer=%s actor=%s medicine=%s batch=%s qty=%s outcome=OK", context.peer(), actor.id, medicine.code, batch.batch_number, quantity)
            return pharmacie_pb2.StockResponse(stock=stock_to_proto(medicine, batches))
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=RegisterStockEntry peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Stock entry could not be saved.")
        finally:
            session.close()

    def ExposePrescription(self, request, context):
        actor = require_permission(context, "consultation.prescription.issue")
        prescription_id = request.prescription_id.strip()
        correlation_id = request.correlation_id.strip() or str(uuid.uuid4())
        if not prescription_id or not request.prescription_number.strip() or not request.patient_id.strip() or not request.items:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Prescription identity, patient and items are required.")
        session = PharmacieSessionLocal()
        try:
            existing = get_prescription(session, prescription_id)
            if existing is not None:
                return pharmacie_pb2.PrescriptionInboxResponse(prescription=prescription_to_proto(existing))
            item = PrescriptionInbox(
                id=prescription_id,
                prescription_number=request.prescription_number.strip(),
                consultation_id=request.consultation_id.strip(),
                patient_id=request.patient_id.strip(),
                doctor_id=request.doctor_id.strip() or actor.id,
                status="ISSUED",
                correlation_id=correlation_id,
            )
            hospital_line_count = 0
            for raw in request.items:
                medicine_ref = raw.medicine_ref.strip().upper()
                medicine_name = raw.medicine_name.strip()
                if not raw.dose.strip() or not raw.frequency.strip() or not raw.duration.strip():
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Every prescription line requires dose, frequency and duration.")
                source = (
                    "EXTERNAL"
                    if raw.medicine_source == pharmacie_pb2.PRESCRIPTION_MEDICINE_SOURCE_EXTERNAL
                    else "HOSPITAL_CATALOG"
                )
                if source == "HOSPITAL_CATALOG":
                    if not medicine_ref:
                        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Hospital prescription line requires medicine_ref.")
                    medicine = get_medicine_by_ref(session, medicine_ref)
                    if medicine is None or not medicine.active:
                        context.abort(grpc.StatusCode.NOT_FOUND, f"Active hospital medicine not found: {medicine_ref}")
                    medicine_ref = medicine.code
                    medicine_name = medicine.name
                    medicine_form = medicine.form
                    medicine_strength = medicine.strength
                    hospital_line_count += 1
                else:
                    if not medicine_ref:
                        medicine_ref = f"EXT-{uuid.uuid4().hex[:12].upper()}"
                    if not medicine_name:
                        context.abort(grpc.StatusCode.INVALID_ARGUMENT, "External prescription line requires medicine_name.")
                    medicine_form = raw.medicine_form.strip()
                    medicine_strength = raw.medicine_strength.strip()
                item.items.append(PrescriptionInboxItem(
                    medicine_ref=medicine_ref,
                    medicine_source=source,
                    medicine_name=medicine_name,
                    medicine_form=medicine_form or None,
                    medicine_strength=medicine_strength or None,
                    dose=raw.dose.strip(),
                    frequency=raw.frequency.strip(),
                    duration=raw.duration.strip(),
                    instructions=raw.instructions.strip() or None,
                ))
            # From the hospital Pharmacy viewpoint an external-only prescription has nothing to dispense.
            if hospital_line_count == 0:
                item.status = "COMPLETED"
            session.add(item)
            session.commit()
            item = get_prescription(session, prescription_id)
            logger.info("rpc=ExposePrescription peer=%s actor=%s prescription=%s patient=%s outcome=OK", context.peer(), actor.id, prescription_id, item.patient_id)
            return pharmacie_pb2.PrescriptionInboxResponse(prescription=prescription_to_proto(item))
        except IntegrityError:
            session.rollback()
            existing = get_prescription(session, prescription_id)
            if existing is not None:
                return pharmacie_pb2.PrescriptionInboxResponse(prescription=prescription_to_proto(existing))
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Prescription already exposed with conflicting data.")
        finally:
            session.close()

    def ListPrescriptionInbox(self, request, context):
        require_permission(context,"pharmacy.prescription.read")
        status=""
        if request.status != pharmacie_pb2.PRESCRIPTION_INBOX_STATUS_UNSPECIFIED:
            status=pharmacie_pb2.PrescriptionInboxStatus.Name(request.status).replace("PRESCRIPTION_INBOX_STATUS_","")
        limit,offset=page_values(request.limit,request.offset,context)
        session=PharmacieSessionLocal()
        try:
            items,total=list_prescriptions(session,patient_id=request.patient_id,status=status,limit=limit,offset=offset)
            return pharmacie_pb2.ListPrescriptionInboxResponse(prescriptions=[prescription_to_proto(x) for x in items],total=total)
        finally: session.close()

    def GetPrescriptionInbox(self, request, context):
        require_permission(context,"pharmacy.prescription.read")
        pid=request.prescription_id.strip()
        if not pid: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"prescription_id is required.")
        session=PharmacieSessionLocal()
        try:
            item=get_prescription(session,pid)
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Prescription not found in Pharmacy inbox.")
            return pharmacie_pb2.PrescriptionInboxResponse(prescription=prescription_to_proto(item))
        finally: session.close()

    def DispensePrescription(self, request, context):
        actor = require_permission(context, "pharmacy.dispense")
        prescription_id = request.prescription_id.strip()
        idem = request.idempotency_key.strip()
        if not prescription_id or not idem or not request.items:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "prescription_id, idempotency_key and items are required.")

        session = PharmacieSessionLocal()
        try:
            existing = get_dispensation_by_key(session, idem)
            if existing is not None:
                prescription = get_prescription(session, existing.prescription_id)
                return pharmacie_pb2.DispensationResponse(
                    dispensation=dispensation_to_proto(existing),
                    prescription=prescription_to_proto(prescription),
                )

            prescription = session.scalar(
                select(PrescriptionInbox)
                .options(selectinload(PrescriptionInbox.items))
                .where(PrescriptionInbox.id == prescription_id)
                .with_for_update()
            )
            if prescription is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Prescription was not exposed to Pharmacy.")
            if prescription.status in ("CANCELLED", "COMPLETED"):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Prescription status does not allow dispensing: {prescription.status}")

            line_by_ref = {line.medicine_ref.upper(): line for line in prescription.items}
            external_refs = {ref for ref, line in line_by_ref.items() if line.medicine_source == "EXTERNAL"}
            allowed_refs = {ref for ref, line in line_by_ref.items() if line.medicine_source != "EXTERNAL"}
            if not allowed_refs:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Prescription contains no medicine dispensable by the hospital pharmacy.")
            requested_refs = set()
            resolved = []
            for raw in request.items:
                ref = raw.medicine_ref.strip().upper()
                if not ref or raw.quantity <= 0:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Every dispense item needs medicine_ref and positive quantity.")
                if ref in requested_refs:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Duplicate medicine_ref in request: {ref}")
                requested_refs.add(ref)
                if ref in external_refs:
                    context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"External medicine is not supplied from hospital stock: {ref}")
                if ref not in allowed_refs:
                    context.abort(grpc.StatusCode.PERMISSION_DENIED, f"Medicine is not present in prescription: {ref}")
                medicine = get_medicine_by_ref(session, ref)
                if medicine is None or not medicine.active:
                    context.abort(grpc.StatusCode.NOT_FOUND, f"Active medicine not found: {ref}")
                batches = session.scalars(
                    select(Batch)
                    .where(
                        Batch.medicine_id == medicine.id,
                        Batch.expiry_date > date.today(),
                        Batch.quantity_available > 0,
                    )
                    .order_by(Batch.expiry_date, Batch.batch_number)
                    .with_for_update()
                ).all()
                available = sum(batch.quantity_available for batch in batches)
                if available < raw.quantity:
                    context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION,
                        f"Insufficient non-expired stock for {medicine.code}: requested={raw.quantity}, available={available}",
                    )
                resolved.append((raw, medicine, batches))

            status = "COMPLETED" if requested_refs == allowed_refs else "PARTIAL"
            disp = Dispensation(
                dispensation_number=generate_dispensation_number(),
                prescription_id=prescription.id,
                patient_id=prescription.patient_id,
                idempotency_key=idem,
                status=status,
                amount_minor=0,
                currency="BIF",
                billing_charge_status="PENDING_DELIVERY",
                actor_id=actor.id,
            )
            session.add(disp)
            session.flush()

            total_amount = 0
            for raw, medicine, batches in resolved:
                remaining = raw.quantity
                line_total = raw.quantity * medicine.sale_price_minor
                line = DispensationItem(
                    dispensation_id=disp.id,
                    medicine_id=medicine.id,
                    medicine_ref=raw.medicine_ref.strip().upper(),
                    quantity=raw.quantity,
                    unit_price_minor=medicine.sale_price_minor,
                    line_total_minor=line_total,
                )
                session.add(line)
                session.flush()
                for batch in batches:
                    if remaining <= 0:
                        break
                    take = min(remaining, batch.quantity_available)
                    if take <= 0:
                        continue
                    batch.quantity_available -= take
                    remaining -= take
                    session.add(DispensationAllocation(dispensation_item_id=line.id, batch_id=batch.id, quantity=take))
                    session.add(StockMovement(
                        movement_type="DISPENSE",
                        medicine_id=medicine.id,
                        batch_id=batch.id,
                        quantity_delta=-take,
                        reference=disp.dispensation_number,
                        actor_id=actor.id,
                    ))
                total_amount += line_total

            disp.amount_minor = total_amount
            prescription.status = status
            session.add(BillingOutbox(
                idempotency_key=f"pharmacy:{idem}",
                dispensation_id=disp.id,
                patient_id=prescription.patient_id,
                amount_minor=total_amount,
                currency="BIF",
                status="PENDING_DELIVERY",
            ))
            session.commit()

            outbox = session.scalar(
                select(BillingOutbox).where(BillingOutbox.dispensation_id == disp.id)
            )
            if outbox is not None and outbox.status == "PENDING_DELIVERY":
                if _deliver_billing_charge(context, outbox, prescription.correlation_id):
                    outbox.status = "DELIVERED"
                    disp.billing_charge_status = "DELIVERED"
                    session.commit()

            saved = get_dispensation(session, disp.id)
            prescription = get_prescription(session, prescription.id)
            logger.info("rpc=DispensePrescription peer=%s actor=%s prescription=%s dispensation=%s amount=%s outcome=OK", context.peer(), actor.id, prescription.id, saved.id, total_amount)
            return pharmacie_pb2.DispensationResponse(
                dispensation=dispensation_to_proto(saved),
                prescription=prescription_to_proto(prescription),
            )
        except IntegrityError:
            session.rollback()
            existing = get_dispensation_by_key(session, idem)
            if existing is not None:
                prescription = get_prescription(session, existing.prescription_id)
                return pharmacie_pb2.DispensationResponse(
                    dispensation=dispensation_to_proto(existing),
                    prescription=prescription_to_proto(prescription),
                )
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Dispensation idempotency conflict.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=DispensePrescription peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Dispensation could not be completed.")
        finally:
            session.close()

    def ListStockAlerts(self, request, context):
        actor=require_permission(context, "pharmacy.stock.read")
        session=PharmacieSessionLocal()
        try:
            alerts=build_stock_alerts(session, request.days_to_expiry or 30)
            logger.info("rpc=ListStockAlerts peer=%s actor=%s count=%s outcome=OK",context.peer(),actor.id,len(alerts))
            return pharmacie_pb2.ListStockAlertsResponse(alerts=alerts,total=len(alerts))
        finally: session.close()

    def DispatchStockAlertNotifications(self, request, context):
        actor=require_permission(context, "pharmacy.stock.manage")
        found,sent,skipped=dispatch_stock_alert_notifications_once(request.days_to_expiry or 30)
        logger.info("rpc=DispatchStockAlertNotifications peer=%s actor=%s alerts=%s sent=%s skipped=%s outcome=OK",context.peer(),actor.id,found,sent,skipped)
        return pharmacie_pb2.DispatchStockAlertNotificationsResponse(alerts_found=found,notifications_sent=sent,alerts_skipped_as_already_dispatched_today=skipped)

    def CreateSupplier(self, request, context):
        actor=require_permission(context,"pharmacy.procurement.manage")
        code=request.code.strip().upper(); name=request.name.strip()
        if not code or not name: context.abort(grpc.StatusCode.INVALID_ARGUMENT,"supplier code and name are required.")
        session=PharmacieSessionLocal()
        try:
            if get_supplier_by_code(session,code): context.abort(grpc.StatusCode.ALREADY_EXISTS,"Supplier code already exists.")
            item=Supplier(code=code,name=name,phone=request.phone.strip() or None,email=request.email.strip().lower() or None,active=True)
            session.add(item); session.commit(); session.refresh(item)
            logger.info("rpc=CreateSupplier peer=%s actor=%s supplier=%s outcome=OK",context.peer(),actor.id,item.code)
            return pharmacie_pb2.SupplierResponse(supplier=supplier_to_proto(item))
        finally: session.close()

    def UpdateSupplier(self, request, context):
        actor=require_permission(context,"pharmacy.procurement.manage")
        session=PharmacieSessionLocal()
        try:
            item=get_supplier_by_code(session,request.supplier_code.strip())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Supplier not found.")
            if request.name.strip(): item.name=request.name.strip()
            if request.phone.strip(): item.phone=request.phone.strip()
            if request.email.strip(): item.email=request.email.strip().lower()
            if request.HasField("active"):
                item.active=request.active
            session.commit(); session.refresh(item)
            logger.info("rpc=UpdateSupplier peer=%s actor=%s supplier=%s outcome=OK",context.peer(),actor.id,item.code)
            return pharmacie_pb2.SupplierResponse(supplier=supplier_to_proto(item))
        finally: session.close()

    def ListSuppliers(self, request, context):
        require_permission(context,"pharmacy.procurement.read")
        limit,offset=page_values(request.limit,request.offset,context)
        session=PharmacieSessionLocal()
        try:
            items,total=list_suppliers(session,query=request.query,active_only=request.active_only,limit=limit,offset=offset)
            return pharmacie_pb2.ListSuppliersResponse(suppliers=[supplier_to_proto(x) for x in items],total=total)
        finally: session.close()

    def CreatePurchaseOrder(self, request, context):
        actor = require_permission(context, "pharmacy.procurement.manage")
        supplier_code = request.supplier_code.strip().upper()
        idem = request.idempotency_key.strip()
        if not supplier_code or not idem or not request.items:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "supplier_code, idempotency_key and items are required.")
        session = PharmacieSessionLocal()
        try:
            existing = get_purchase_order_by_key(session, idem)
            if existing is not None:
                return pharmacie_pb2.PurchaseOrderResponse(purchase_order=purchase_order_to_proto(existing))
            supplier = get_supplier_by_code(session, supplier_code)
            if supplier is None or not supplier.active:
                context.abort(grpc.StatusCode.NOT_FOUND, "Active supplier not found.")
            po = PurchaseOrder(
                order_number=generate_po_number(),
                supplier_id=supplier.id,
                status="ORDERED",
                idempotency_key=idem,
                created_by=actor.id,
            )
            seen = set()
            for raw in request.items:
                code = raw.medicine_code.strip().upper()
                if not code or raw.quantity <= 0 or code in seen:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "PO items require unique medicine_code and positive quantity.")
                seen.add(code)
                medicine = get_medicine_by_ref(session, code)
                if medicine is None or not medicine.active:
                    context.abort(grpc.StatusCode.NOT_FOUND, f"Active medicine not found: {code}")
                po.items.append(PurchaseOrderItem(medicine_id=medicine.id, quantity_ordered=raw.quantity, quantity_received=0))
            session.add(po)
            session.commit()
            po = get_purchase_order(session, po.id)
            logger.info("rpc=CreatePurchaseOrder peer=%s actor=%s po=%s outcome=OK", context.peer(), actor.id, po.order_number)
            return pharmacie_pb2.PurchaseOrderResponse(purchase_order=purchase_order_to_proto(po))
        except IntegrityError:
            session.rollback()
            existing = get_purchase_order_by_key(session, idem)
            if existing is not None:
                return pharmacie_pb2.PurchaseOrderResponse(purchase_order=purchase_order_to_proto(existing))
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Purchase order idempotency conflict.")
        finally:
            session.close()

    def GetPurchaseOrder(self, request, context):
        require_permission(context,"pharmacy.procurement.read")
        session=PharmacieSessionLocal()
        try:
            item=get_purchase_order(session,request.purchase_order_id.strip())
            if item is None: context.abort(grpc.StatusCode.NOT_FOUND,"Purchase order not found.")
            return pharmacie_pb2.PurchaseOrderResponse(purchase_order=purchase_order_to_proto(item))
        finally: session.close()

    def ListPurchaseOrders(self, request, context):
        require_permission(context,"pharmacy.procurement.read")
        status=""
        if request.status != pharmacie_pb2.PURCHASE_ORDER_STATUS_UNSPECIFIED:
            status=PO_STATUS_PROTO_TO_DB.get(request.status,"")
        limit,offset=page_values(request.limit,request.offset,context)
        session=PharmacieSessionLocal()
        try:
            items,total=list_purchase_orders(session,supplier_code=request.supplier_code,status=status,limit=limit,offset=offset)
            return pharmacie_pb2.ListPurchaseOrdersResponse(purchase_orders=[purchase_order_to_proto(x) for x in items],total=total)
        finally: session.close()

    def ReceivePurchaseOrder(self, request, context):
        actor = require_permission(context, "pharmacy.procurement.manage")
        po_id = request.purchase_order_id.strip()
        idem = request.idempotency_key.strip()
        if not po_id or not idem or not request.items:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "purchase_order_id, idempotency_key and receipt items are required.")
        session = PharmacieSessionLocal()
        try:
            receipt = session.scalar(select(PurchaseReceipt).where(PurchaseReceipt.idempotency_key == idem))
            if receipt is not None:
                po = get_purchase_order(session, receipt.purchase_order_id)
                return pharmacie_pb2.PurchaseOrderResponse(purchase_order=purchase_order_to_proto(po))
            po = session.scalar(
                select(PurchaseOrder)
                .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.medicine))
                .where(PurchaseOrder.id == po_id)
                .with_for_update()
            )
            if po is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Purchase order not found.")
            if po.status in ("CANCELLED", "RECEIVED"):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Purchase order cannot receive stock in status {po.status}.")
            items_by_code = {line.medicine.code.upper(): line for line in po.items}
            seen = set()
            for raw in request.items:
                code = raw.medicine_code.strip().upper()
                batch_number = raw.batch_number.strip().upper()
                if not code or not batch_number or raw.quantity <= 0 or code in seen:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Receipt items require unique medicine_code, batch_number and positive quantity.")
                seen.add(code)
                expiry = parse_date(raw.expiry_date, context)
                if expiry <= date.today():
                    context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Cannot receive expired batch for {code}.")
                po_line = items_by_code.get(code)
                if po_line is None:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Medicine {code} is not on this purchase order.")
                remaining = po_line.quantity_ordered - po_line.quantity_received
                if raw.quantity > remaining:
                    context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Receipt exceeds remaining PO quantity for {code}: remaining={remaining}")
                batch = session.scalar(
                    select(Batch).where(Batch.medicine_id == po_line.medicine_id, Batch.batch_number == batch_number).with_for_update()
                )
                if batch is None:
                    batch = Batch(medicine_id=po_line.medicine_id, batch_number=batch_number, expiry_date=expiry, quantity_available=0)
                    session.add(batch)
                    session.flush()
                elif batch.expiry_date != expiry:
                    context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Existing batch {batch_number} has a different expiry date.")
                batch.quantity_available += raw.quantity
                po_line.quantity_received += raw.quantity
                session.add(StockMovement(
                    movement_type="PO_RECEIPT",
                    medicine_id=po_line.medicine_id,
                    batch_id=batch.id,
                    quantity_delta=raw.quantity,
                    reference=po.order_number,
                    actor_id=actor.id,
                ))
            all_received = all(line.quantity_received >= line.quantity_ordered for line in po.items)
            po.status = "RECEIVED" if all_received else "PARTIALLY_RECEIVED"
            if all_received:
                po.received_at = utc_now()
            session.add(PurchaseReceipt(purchase_order_id=po.id, idempotency_key=idem, actor_id=actor.id))
            session.commit()
            po = get_purchase_order(session, po.id)
            logger.info("rpc=ReceivePurchaseOrder peer=%s actor=%s po=%s status=%s outcome=OK", context.peer(), actor.id, po.order_number, po.status)
            return pharmacie_pb2.PurchaseOrderResponse(purchase_order=purchase_order_to_proto(po))
        except IntegrityError:
            session.rollback()
            receipt = session.scalar(select(PurchaseReceipt).where(PurchaseReceipt.idempotency_key == idem))
            if receipt is not None:
                po = get_purchase_order(session, receipt.purchase_order_id)
                return pharmacie_pb2.PurchaseOrderResponse(purchase_order=purchase_order_to_proto(po))
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Purchase receipt idempotency conflict.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=ReceivePurchaseOrder peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Purchase order receipt could not be completed.")
        finally:
            session.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return build_health_response("ONLINE", "Pharmacie service and MySQL are online.")
        except Exception:
            logger.exception("rpc=HealthCheck peer=%s outcome=DEGRADED", context.peer())
            return build_health_response("DEGRADED", "Pharmacie service is running but MySQL health check failed.")
