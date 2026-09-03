from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.hospitalisation_base import HospitalisationBase


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Ward(HospitalisationBase):
    __tablename__ = "wards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    daily_rate_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    rooms: Mapped[list["Room"]] = relationship(back_populates="ward", cascade="all, delete-orphan")


class Room(HospitalisationBase):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("ward_id", "code", name="uq_room_ward_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    ward_id: Mapped[str] = mapped_column(String(36), ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    ward: Mapped[Ward] = relationship(back_populates="rooms")
    beds: Mapped[list["Bed"]] = relationship(back_populates="room", cascade="all, delete-orphan")


class Bed(HospitalisationBase):
    __tablename__ = "beds"
    __table_args__ = (UniqueConstraint("room_id", "code", name="uq_bed_room_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="AVAILABLE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    room: Mapped[Room] = relationship(back_populates="beds")


class Admission(HospitalisationBase):
    __tablename__ = "admissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    admission_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    active_patient_key: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True, index=True)
    consultation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_ward: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    current_bed_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("beds.id", ondelete="RESTRICT"), nullable=True, unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    bed_assignment_key: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True, index=True)
    discharge_idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    discharge_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_charge_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_CREATED", index=True)
    current_bed: Mapped[Bed | None] = relationship(foreign_keys=[current_bed_id])
    transfers: Mapped[list["Transfer"]] = relationship(back_populates="admission", cascade="all, delete-orphan", foreign_keys="Transfer.admission_id")
    stay_notes: Mapped[list["StayNote"]] = relationship(back_populates="admission", cascade="all, delete-orphan")


class Transfer(HospitalisationBase):
    __tablename__ = "transfers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    admission_id: Mapped[str] = mapped_column(String(36), ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    from_bed_id: Mapped[str] = mapped_column(String(36), ForeignKey("beds.id", ondelete="RESTRICT"), nullable=False, index=True)
    to_bed_id: Mapped[str] = mapped_column(String(36), ForeignKey("beds.id", ondelete="RESTRICT"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    admission: Mapped[Admission] = relationship(back_populates="transfers", foreign_keys=[admission_id])
    from_bed: Mapped[Bed] = relationship(foreign_keys=[from_bed_id])
    to_bed: Mapped[Bed] = relationship(foreign_keys=[to_bed_id])


class StayNote(HospitalisationBase):
    __tablename__ = "stay_notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    admission_id: Mapped[str] = mapped_column(String(36), ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    admission: Mapped[Admission] = relationship(back_populates="stay_notes")


class BillingOutbox(HospitalisationBase):
    __tablename__ = "billing_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    admission_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_DELIVERY", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)


class DoctorAssignment(HospitalisationBase):
    __tablename__ = "doctor_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    admission_id: Mapped[str] = mapped_column(String(36), ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    active_admission_key: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True, index=True)
    doctor_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assigned_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
