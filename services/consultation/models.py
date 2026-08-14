from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.consultation_base import ConsultationBase


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Consultation(ConsultationBase):
    __tablename__ = "consultations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    consultation_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    vitals_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    diagnoses: Mapped[list["Diagnosis"]] = relationship(
        back_populates="consultation",
        cascade="all, delete-orphan",
        order_by="Diagnosis.created_at",
    )
    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="consultation",
        cascade="all, delete-orphan",
        order_by="Prescription.issued_at",
    )
    outbound_requests: Mapped[list["OutboundRequest"]] = relationship(
        back_populates="consultation",
        cascade="all, delete-orphan",
    )


class Diagnosis(ConsultationBase):
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    consultation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    consultation: Mapped[Consultation] = relationship(back_populates="diagnoses")


class Prescription(ConsultationBase):
    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    prescription_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    consultation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ISSUED", index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    consultation: Mapped[Consultation] = relationship(back_populates="prescriptions")
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PrescriptionItem.id",
    )


class PrescriptionItem(ConsultationBase):
    __tablename__ = "prescription_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    prescription_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medicine_ref: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dose: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(120), nullable=False)
    duration: Mapped[str] = mapped_column(String(120), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    prescription: Mapped[Prescription] = relationship(back_populates="items")


class OutboundRequest(ConsultationBase):
    __tablename__ = "outbound_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    consultation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    target_service: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_DELIVERY", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    consultation: Mapped[Consultation] = relationship(back_populates="outbound_requests")
