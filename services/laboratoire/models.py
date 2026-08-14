from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.laboratoire_base import LaboratoireBase


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LabTest(LaboratoireBase):
    __tablename__ = "lab_tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    sample_type: Mapped[str] = mapped_column(String(80), nullable=False)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BIF")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)

    orders: Mapped[list["LabOrder"]] = relationship(back_populates="test")


class LabOrder(LaboratoireBase):
    __tablename__ = "lab_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    order_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    consultation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lab_test_id: Mapped[str] = mapped_column(String(36), ForeignKey("lab_tests.id", ondelete="RESTRICT"), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="ROUTINE", index=True)
    clinical_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ORDERED", index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    ordered_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    billing_charge_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_CREATED", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)

    test: Mapped[LabTest] = relationship(back_populates="orders")
    sample: Mapped["Sample | None"] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")
    result: Mapped["Result | None"] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")


class Sample(LaboratoireBase):
    __tablename__ = "samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sample_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("lab_orders.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    collected_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[LabOrder] = relationship(back_populates="sample")


class Result(LaboratoireBase):
    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("lab_orders.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    consultation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    values_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    validated_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    order: Mapped[LabOrder] = relationship(back_populates="result")
    corrections: Mapped[list["ResultCorrection"]] = relationship(back_populates="result", cascade="all, delete-orphan")


class ResultCorrection(LaboratoireBase):
    __tablename__ = "result_corrections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    result_id: Mapped[str] = mapped_column(String(36), ForeignKey("results.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_values_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_text_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    corrected_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)

    result: Mapped[Result] = relationship(back_populates="corrections")


class BillingOutbox(LaboratoireBase):
    __tablename__ = "billing_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BIF")
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_DELIVERY", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
