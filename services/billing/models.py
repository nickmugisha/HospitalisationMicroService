from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.billing_base import BillingBase


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Invoice(BillingBase):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    invoice_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    paid_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    balance_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)

    charges: Mapped[list["Charge"]] = relationship(back_populates="invoice")
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")


class Charge(BillingBase):
    __tablename__ = "charges"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_charge_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    charge_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)

    invoice: Mapped[Invoice] = relationship(back_populates="charges")


class Payment(BillingBase):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    payment_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    cashier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="VALIDATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)

    invoice: Mapped[Invoice] = relationship(back_populates="payments")
    receipt: Mapped["Receipt | None"] = relationship(back_populates="payment", uselist=False)
    reversal: Mapped["Reversal | None"] = relationship(back_populates="payment", uselist=False)


class Receipt(BillingBase):
    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    receipt_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    payment_id: Mapped[str] = mapped_column(String(36), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    issued_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="receipt")


class Reversal(BillingBase):
    __tablename__ = "reversals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    reversal_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    payment_id: Mapped[str] = mapped_column(String(36), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)

    payment: Mapped[Payment] = relationship(back_populates="reversal")
