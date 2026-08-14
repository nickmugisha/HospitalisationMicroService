from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from billing.v1 import billing_pb2, billing_pb2_grpc
from common.v1 import common_pb2
from services.common.health_compat import build_health_response_compat
from database.billing_session import BillingSessionLocal, engine
from services.billing.config import SERVICE_VERSION
from services.billing.models import Charge, Invoice, Payment, Receipt, Reversal
from services.billing.repository import (
    get_charge_by_idempotency,
    get_charge_by_source_key,
    get_invoice,
    get_invoice_by_number,
    get_invoice_for_patient,
    get_payment,
    get_payment_by_key,
    get_receipt,
    get_reversal_by_key,
    get_reversal_for_payment,
    recompute_invoice,
)
from services.common.auth_guard import require_permission


logger = logging.getLogger("projectx.billing.service")

INVOICE_STATUS_DB_TO_PROTO = {
    "OPEN": billing_pb2.INVOICE_STATUS_OPEN,
    "PARTIALLY_PAID": billing_pb2.INVOICE_STATUS_PARTIALLY_PAID,
    "PAID": billing_pb2.INVOICE_STATUS_PAID,
}
PAYMENT_METHOD_PROTO_TO_DB = {
    billing_pb2.PAYMENT_METHOD_CASH: "CASH",
    billing_pb2.PAYMENT_METHOD_CARD: "CARD",
    billing_pb2.PAYMENT_METHOD_MOBILE_MONEY: "MOBILE_MONEY",
    billing_pb2.PAYMENT_METHOD_BANK_TRANSFER: "BANK_TRANSFER",
    billing_pb2.PAYMENT_METHOD_OTHER: "OTHER",
}
PAYMENT_METHOD_DB_TO_PROTO = {value: key for key, value in PAYMENT_METHOD_PROTO_TO_DB.items()}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_timestamp(value: datetime | None) -> Timestamp:
    result = Timestamp()
    if value is not None:
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        result.FromDatetime(aware)
    return result


def money(amount_minor: int, currency_code: str):
    """Build Money against the shared proto without assuming the currency field name."""
    fields = common_pb2.Money.DESCRIPTOR.fields_by_name
    payload = {"amount_minor": int(amount_minor)}

    if "currency_code" in fields:
        payload["currency_code"] = currency_code
    elif "currency" in fields:
        payload["currency"] = currency_code
    else:
        raise RuntimeError(
            "hospital.common.v1.Money must expose currency_code or currency"
        )

    return common_pb2.Money(**payload)


def generate_number(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def charge_to_proto(item: Charge):
    return billing_pb2.Charge(
        id=item.id,
        charge_number=item.charge_number,
        source_type=item.source_type,
        source_id=item.source_id,
        patient_id=item.patient_id,
        invoice_id=item.invoice_id,
        amount=money(item.amount_minor, item.currency_code),
        description=item.description,
        status=billing_pb2.CHARGE_STATUS_ACTIVE,
        correlation_id=item.correlation_id or "",
        created_at=to_timestamp(item.created_at),
    )


def invoice_to_proto(item: Invoice):
    return billing_pb2.Invoice(
        id=item.id,
        invoice_number=item.invoice_number,
        patient_id=item.patient_id,
        total=money(item.total_minor, item.currency_code),
        paid=money(item.paid_minor, item.currency_code),
        balance=money(item.balance_minor, item.currency_code),
        status=INVOICE_STATUS_DB_TO_PROTO.get(item.status, billing_pb2.INVOICE_STATUS_UNSPECIFIED),
        created_at=to_timestamp(item.created_at),
        updated_at=to_timestamp(item.updated_at),
    )


def payment_to_proto(item: Payment, reversal: Reversal | None = None):
    status = billing_pb2.PAYMENT_STATUS_REVERSED if reversal is not None else billing_pb2.PAYMENT_STATUS_VALIDATED
    return billing_pb2.Payment(
        id=item.id,
        payment_number=item.payment_number,
        invoice_id=item.invoice_id,
        patient_id=item.patient_id,
        amount=money(item.amount_minor, item.currency_code),
        method=PAYMENT_METHOD_DB_TO_PROTO.get(item.method, billing_pb2.PAYMENT_METHOD_OTHER),
        cashier_id=item.cashier_id,
        reference=item.reference or "",
        status=status,
        created_at=to_timestamp(item.created_at),
    )


def receipt_to_proto(item: Receipt):
    return billing_pb2.Receipt(
        id=item.id,
        receipt_number=item.receipt_number,
        payment_id=item.payment_id,
        invoice_id=item.invoice_id,
        amount=money(item.amount_minor, item.currency_code),
        issued_at=to_timestamp(item.issued_at),
    )


def reversal_to_proto(item: Reversal):
    return billing_pb2.Reversal(
        id=item.id,
        reversal_number=item.reversal_number,
        payment_id=item.payment_id,
        invoice_id=item.invoice_id,
        amount=money(item.amount_minor, item.currency_code),
        reason=item.reason,
        actor_id=item.actor_id,
        created_at=to_timestamp(item.created_at),
    )


def build_health_response(status_name: str, message: str):
    return build_health_response_compat("billing", status_name, message, SERVICE_VERSION)

def _same_charge(item: Charge, *, source_type: str, source_id: str, patient_id: str, amount_minor: int, currency_code: str) -> bool:
    return (
        item.source_type == source_type
        and item.source_id == source_id
        and item.patient_id == patient_id
        and item.amount_minor == amount_minor
        and item.currency_code == currency_code
    )


class BillingService(billing_pb2_grpc.BillingServiceServicer):
    def CreateCharge(self, request, context):
        actor = require_permission(context, "billing.charge.create")
        source_type = request.source_type.strip().upper()
        source_id = request.source_id.strip()
        patient_id = request.patient_id.strip()
        description = request.description.strip()
        idem = request.idempotency_key.strip()
        correlation_id = request.correlation_id.strip()
        currency = (request.currency_code.strip() or "BIF").upper()
        amount = int(request.amount_minor)

        if not source_type or not source_id or not patient_id or not idem:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "source_type, source_id, patient_id and idempotency_key are required.")
        if amount <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "amount_minor must be greater than zero.")
        if currency != "BIF":
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "ProjectX Billing MVP accepts BIF only.")
        if not description:
            description = f"{source_type} charge"

        source_key = f"{source_type}:{source_id}"
        session = BillingSessionLocal()
        try:
            existing = get_charge_by_idempotency(session, idem) or get_charge_by_source_key(session, source_key)
            if existing is not None:
                if not _same_charge(
                    existing,
                    source_type=source_type,
                    source_id=source_id,
                    patient_id=patient_id,
                    amount_minor=amount,
                    currency_code=currency,
                ):
                    context.abort(grpc.StatusCode.ALREADY_EXISTS, "Charge idempotency/source key already exists with different data.")
                invoice = get_invoice(session, existing.invoice_id)
                logger.info("rpc=CreateCharge peer=%s actor=%s charge=%s replayed=true outcome=OK", context.peer(), actor.id, existing.id)
                return billing_pb2.CreateChargeResponse(
                    charge=charge_to_proto(existing),
                    invoice=invoice_to_proto(invoice),
                    replayed=True,
                )

            invoice = session.scalar(select(Invoice).where(Invoice.patient_id == patient_id).with_for_update())
            if invoice is None:
                invoice = Invoice(
                    invoice_number=generate_number("INV"),
                    patient_id=patient_id,
                    total_minor=0,
                    paid_minor=0,
                    balance_minor=0,
                    currency_code=currency,
                    status="OPEN",
                )
                session.add(invoice)
                session.flush()
            elif invoice.currency_code != currency:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Patient invoice currency does not match the charge currency.")

            item = Charge(
                charge_number=generate_number("CHG"),
                source_type=source_type,
                source_id=source_id,
                source_key=source_key,
                idempotency_key=idem,
                correlation_id=correlation_id or None,
                patient_id=patient_id,
                invoice_id=invoice.id,
                amount_minor=amount,
                currency_code=currency,
                description=description,
                status="ACTIVE",
            )
            session.add(item)
            session.flush()
            recompute_invoice(session, invoice)
            session.commit()
            saved = get_charge_by_idempotency(session, idem)
            invoice = get_invoice(session, invoice.id)
            logger.info("rpc=CreateCharge peer=%s actor=%s charge=%s patient=%s amount_minor=%s outcome=OK", context.peer(), actor.id, saved.id, patient_id, amount)
            return billing_pb2.CreateChargeResponse(
                charge=charge_to_proto(saved),
                invoice=invoice_to_proto(invoice),
                replayed=False,
            )
        except IntegrityError:
            session.rollback()
            existing = get_charge_by_idempotency(session, idem) or get_charge_by_source_key(session, source_key)
            if existing is not None and _same_charge(
                existing,
                source_type=source_type,
                source_id=source_id,
                patient_id=patient_id,
                amount_minor=amount,
                currency_code=currency,
            ):
                invoice = get_invoice(session, existing.invoice_id)
                return billing_pb2.CreateChargeResponse(charge=charge_to_proto(existing), invoice=invoice_to_proto(invoice), replayed=True)
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Charge conflict.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=CreateCharge peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Charge could not be created.")
        finally:
            session.close()

    def GetPatientBalance(self, request, context):
        actor = require_permission(context, "billing.read")
        patient_id = request.patient_id.strip()
        if not patient_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "patient_id is required.")
        session = BillingSessionLocal()
        try:
            invoice = get_invoice_for_patient(session, patient_id)
            if invoice is None:
                return billing_pb2.GetPatientBalanceResponse(
                    patient_id=patient_id,
                    total_charges=money(0, "BIF"),
                    total_paid=money(0, "BIF"),
                    balance=money(0, "BIF"),
                )
            recompute_invoice(session, invoice)
            session.commit()
            invoice = get_invoice(session, invoice.id)
            logger.info("rpc=GetPatientBalance peer=%s actor=%s patient=%s balance_minor=%s outcome=OK", context.peer(), actor.id, patient_id, invoice.balance_minor)
            return billing_pb2.GetPatientBalanceResponse(
                patient_id=patient_id,
                total_charges=money(invoice.total_minor, invoice.currency_code),
                total_paid=money(invoice.paid_minor, invoice.currency_code),
                balance=money(invoice.balance_minor, invoice.currency_code),
                invoice=invoice_to_proto(invoice),
            )
        finally:
            session.close()

    def GetInvoice(self, request, context):
        actor = require_permission(context, "billing.read")
        session = BillingSessionLocal()
        try:
            if request.invoice_id.strip():
                invoice = get_invoice(session, request.invoice_id.strip())
            elif request.invoice_number.strip():
                invoice = get_invoice_by_number(session, request.invoice_number.strip())
            elif request.patient_id.strip():
                invoice = get_invoice_for_patient(session, request.patient_id.strip())
            else:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invoice_id, invoice_number or patient_id is required.")
            if invoice is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Invoice not found.")
            recompute_invoice(session, invoice)
            session.commit()
            invoice = get_invoice(session, invoice.id)
            payments = [payment_to_proto(p, p.reversal) for p in invoice.payments]
            logger.info("rpc=GetInvoice peer=%s actor=%s invoice=%s outcome=OK", context.peer(), actor.id, invoice.id)
            return billing_pb2.InvoiceResponse(
                invoice=invoice_to_proto(invoice),
                charges=[charge_to_proto(x) for x in invoice.charges],
                payments=payments,
            )
        finally:
            session.close()

    def RecordPayment(self, request, context):
        actor = require_permission(context, "billing.payment.record")
        invoice_id = request.invoice_id.strip()
        idem = request.idempotency_key.strip()
        reference = request.reference.strip()
        currency = (request.currency_code.strip() or "BIF").upper()
        amount = int(request.amount_minor)
        method = PAYMENT_METHOD_PROTO_TO_DB.get(request.method)

        if not invoice_id or not idem:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invoice_id and idempotency_key are required.")
        if amount <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "amount_minor must be greater than zero.")
        if currency != "BIF":
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "ProjectX Billing MVP accepts BIF only.")
        if method is None:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "A valid payment method is required.")

        session = BillingSessionLocal()
        try:
            existing = get_payment_by_key(session, idem)
            if existing is not None:
                invoice = get_invoice(session, existing.invoice_id)
                return billing_pb2.PaymentResponse(
                    payment=payment_to_proto(existing, existing.reversal),
                    receipt=receipt_to_proto(existing.receipt),
                    invoice=invoice_to_proto(invoice),
                    replayed=True,
                )

            invoice = session.scalar(select(Invoice).where(Invoice.id == invoice_id).with_for_update())
            if invoice is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Invoice not found.")
            recompute_invoice(session, invoice)
            if invoice.currency_code != currency:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Payment currency must match invoice currency.")
            if invoice.balance_minor <= 0:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Invoice has no outstanding balance.")
            if amount > invoice.balance_minor:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Payment exceeds outstanding invoice balance.")

            payment = Payment(
                payment_number=generate_number("PAY"),
                invoice_id=invoice.id,
                patient_id=invoice.patient_id,
                amount_minor=amount,
                currency_code=currency,
                method=method,
                cashier_id=actor.id,
                reference=reference or None,
                idempotency_key=idem,
                status="VALIDATED",
            )
            session.add(payment)
            session.flush()
            receipt = Receipt(
                receipt_number=generate_number("RCT"),
                payment_id=payment.id,
                invoice_id=invoice.id,
                amount_minor=amount,
                currency_code=currency,
            )
            session.add(receipt)
            session.flush()
            recompute_invoice(session, invoice)
            session.commit()
            saved = get_payment(session, payment.id)
            invoice = get_invoice(session, invoice.id)
            logger.info("rpc=RecordPayment peer=%s actor=%s payment=%s invoice=%s amount_minor=%s outcome=OK", context.peer(), actor.id, saved.id, invoice.id, amount)
            return billing_pb2.PaymentResponse(
                payment=payment_to_proto(saved, saved.reversal),
                receipt=receipt_to_proto(saved.receipt),
                invoice=invoice_to_proto(invoice),
                replayed=False,
            )
        except IntegrityError:
            session.rollback()
            existing = get_payment_by_key(session, idem)
            if existing is not None:
                invoice = get_invoice(session, existing.invoice_id)
                return billing_pb2.PaymentResponse(payment=payment_to_proto(existing, existing.reversal), receipt=receipt_to_proto(existing.receipt), invoice=invoice_to_proto(invoice), replayed=True)
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Payment idempotency conflict.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=RecordPayment peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Payment could not be recorded.")
        finally:
            session.close()

    def ReversePayment(self, request, context):
        actor = require_permission(context, "billing.payment.reverse")
        payment_id = request.payment_id.strip()
        reason = request.reason.strip()
        idem = request.idempotency_key.strip()
        if not payment_id or not reason or not idem:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "payment_id, reason and idempotency_key are required.")

        session = BillingSessionLocal()
        try:
            existing_by_key = get_reversal_by_key(session, idem)
            if existing_by_key is not None:
                payment = get_payment(session, existing_by_key.payment_id)
                invoice = get_invoice(session, existing_by_key.invoice_id)
                return billing_pb2.ReversePaymentResponse(
                    reversal=reversal_to_proto(existing_by_key),
                    payment=payment_to_proto(payment, existing_by_key),
                    invoice=invoice_to_proto(invoice),
                    replayed=True,
                )

            payment = session.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
            if payment is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Payment not found.")
            existing_for_payment = get_reversal_for_payment(session, payment.id)
            if existing_for_payment is not None:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Payment already has a reversal.")
            if payment.status != "VALIDATED":
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Only a validated payment can be reversed.")

            invoice = session.scalar(select(Invoice).where(Invoice.id == payment.invoice_id).with_for_update())
            reversal = Reversal(
                reversal_number=generate_number("REV"),
                payment_id=payment.id,
                invoice_id=payment.invoice_id,
                amount_minor=payment.amount_minor,
                currency_code=payment.currency_code,
                reason=reason,
                actor_id=actor.id,
                idempotency_key=idem,
            )
            session.add(reversal)
            session.flush()
            recompute_invoice(session, invoice)
            session.commit()
            saved = get_reversal_by_key(session, idem)
            payment = get_payment(session, payment.id)
            invoice = get_invoice(session, invoice.id)
            logger.info("rpc=ReversePayment peer=%s actor=%s payment=%s reversal=%s outcome=OK", context.peer(), actor.id, payment.id, saved.id)
            return billing_pb2.ReversePaymentResponse(
                reversal=reversal_to_proto(saved),
                payment=payment_to_proto(payment, saved),
                invoice=invoice_to_proto(invoice),
                replayed=False,
            )
        except IntegrityError:
            session.rollback()
            existing = get_reversal_by_key(session, idem)
            if existing is not None:
                payment = get_payment(session, existing.payment_id)
                invoice = get_invoice(session, existing.invoice_id)
                return billing_pb2.ReversePaymentResponse(reversal=reversal_to_proto(existing), payment=payment_to_proto(payment, existing), invoice=invoice_to_proto(invoice), replayed=True)
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Payment reversal conflict.")
        except SQLAlchemyError:
            session.rollback()
            logger.exception("rpc=ReversePayment peer=%s actor=%s outcome=DB_ERROR", context.peer(), actor.id)
            context.abort(grpc.StatusCode.INTERNAL, "Payment could not be reversed.")
        finally:
            session.close()

    def GetPaymentStatus(self, request, context):
        actor = require_permission(context, "billing.read")
        payment_id = request.payment_id.strip()
        if not payment_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "payment_id is required.")
        session = BillingSessionLocal()
        try:
            payment = get_payment(session, payment_id)
            if payment is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Payment not found.")
            reversal = payment.reversal
            logger.info("rpc=GetPaymentStatus peer=%s actor=%s payment=%s reversed=%s outcome=OK", context.peer(), actor.id, payment.id, bool(reversal))
            response = billing_pb2.PaymentStatusResponse(
                payment=payment_to_proto(payment, reversal),
                reversed=bool(reversal),
            )
            if reversal is not None:
                response.reversal.CopyFrom(reversal_to_proto(reversal))
            return response
        finally:
            session.close()

    def GetReceipt(self, request, context):
        actor = require_permission(context, "billing.read")
        receipt_id = request.receipt_id.strip()
        receipt_number = request.receipt_number.strip()
        payment_id = request.payment_id.strip()
        if not receipt_id and not receipt_number and not payment_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "receipt_id, receipt_number or payment_id is required.")
        session = BillingSessionLocal()
        try:
            item = get_receipt(session, receipt_id=receipt_id, receipt_number=receipt_number, payment_id=payment_id)
            if item is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Receipt not found.")
            logger.info("rpc=GetReceipt peer=%s actor=%s receipt=%s outcome=OK", context.peer(), actor.id, item.id)
            return billing_pb2.ReceiptResponse(receipt=receipt_to_proto(item))
        finally:
            session.close()

    def HealthCheck(self, request, context):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return build_health_response("ONLINE", "Billing service and MySQL are available.")
        except SQLAlchemyError:
            logger.exception("rpc=HealthCheck peer=%s outcome=DEGRADED", context.peer())
            return build_health_response("DEGRADED", "Billing service is running but MySQL is unavailable.")
