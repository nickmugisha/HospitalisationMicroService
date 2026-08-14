from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from services.billing.models import Charge, Invoice, Payment, Receipt, Reversal


def get_invoice(session: Session, invoice_id: str) -> Invoice | None:
    return session.scalar(
        select(Invoice)
        .options(
            selectinload(Invoice.charges),
            selectinload(Invoice.payments).selectinload(Payment.receipt),
            selectinload(Invoice.payments).selectinload(Payment.reversal),
        )
        .where(Invoice.id == invoice_id)
    )


def get_invoice_by_number(session: Session, invoice_number: str) -> Invoice | None:
    return session.scalar(
        select(Invoice)
        .options(
            selectinload(Invoice.charges),
            selectinload(Invoice.payments).selectinload(Payment.receipt),
            selectinload(Invoice.payments).selectinload(Payment.reversal),
        )
        .where(Invoice.invoice_number == invoice_number)
    )


def get_invoice_for_patient(session: Session, patient_id: str) -> Invoice | None:
    return session.scalar(
        select(Invoice)
        .options(
            selectinload(Invoice.charges),
            selectinload(Invoice.payments).selectinload(Payment.receipt),
            selectinload(Invoice.payments).selectinload(Payment.reversal),
        )
        .where(Invoice.patient_id == patient_id)
    )


def get_charge_by_idempotency(session: Session, key: str) -> Charge | None:
    return session.scalar(select(Charge).where(Charge.idempotency_key == key))


def get_charge_by_source_key(session: Session, source_key: str) -> Charge | None:
    return session.scalar(select(Charge).where(Charge.source_key == source_key))


def get_payment(session: Session, payment_id: str) -> Payment | None:
    return session.scalar(
        select(Payment)
        .options(selectinload(Payment.receipt), selectinload(Payment.reversal))
        .where(Payment.id == payment_id)
    )


def get_payment_by_key(session: Session, key: str) -> Payment | None:
    return session.scalar(
        select(Payment)
        .options(selectinload(Payment.receipt), selectinload(Payment.reversal))
        .where(Payment.idempotency_key == key)
    )


def get_reversal_by_key(session: Session, key: str) -> Reversal | None:
    return session.scalar(select(Reversal).where(Reversal.idempotency_key == key))


def get_reversal_for_payment(session: Session, payment_id: str) -> Reversal | None:
    return session.scalar(select(Reversal).where(Reversal.payment_id == payment_id))


def get_receipt(session: Session, *, receipt_id: str = "", receipt_number: str = "", payment_id: str = "") -> Receipt | None:
    stmt = select(Receipt)
    if receipt_id:
        stmt = stmt.where(Receipt.id == receipt_id)
    elif receipt_number:
        stmt = stmt.where(Receipt.receipt_number == receipt_number)
    elif payment_id:
        stmt = stmt.where(Receipt.payment_id == payment_id)
    else:
        return None
    return session.scalar(stmt)


def recompute_invoice(session: Session, invoice: Invoice) -> Invoice:
    total = session.scalar(
        select(func.coalesce(func.sum(Charge.amount_minor), 0)).where(
            Charge.invoice_id == invoice.id,
            Charge.status == "ACTIVE",
        )
    ) or 0

    paid = session.scalar(
        select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
            Payment.invoice_id == invoice.id,
            Payment.status == "VALIDATED",
        )
    ) or 0

    reversed_amount = session.scalar(
        select(func.coalesce(func.sum(Reversal.amount_minor), 0)).where(
            Reversal.invoice_id == invoice.id,
        )
    ) or 0

    net_paid = max(0, int(paid) - int(reversed_amount))
    total = int(total)
    balance = max(0, total - net_paid)

    invoice.total_minor = total
    invoice.paid_minor = net_paid
    invoice.balance_minor = balance

    if total > 0 and balance == 0:
        invoice.status = "PAID"
    elif net_paid > 0:
        invoice.status = "PARTIALLY_PAID"
    else:
        invoice.status = "OPEN"

    return invoice
