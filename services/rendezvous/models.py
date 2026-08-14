from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.rendezvous_base import RendezvousBase


def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class ScheduleSlot(RendezvousBase):
    __tablename__ = "schedule_slots"
    __table_args__ = (
        UniqueConstraint("provider_id", "start_at", "end_at", name="uq_slot_provider_window"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    provider_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="AVAILABLE", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="slot")

class Appointment(RendezvousBase):
    __tablename__ = "appointments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    appointment_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="BOOKED", index=True)
    slot_id: Mapped[str] = mapped_column(String(36), ForeignKey("schedule_slots.id", ondelete="RESTRICT"), nullable=False, index=True)
    active_slot_key: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    arrival_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    checkin_idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True, index=True)
    last_reschedule_key: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True, index=True)
    cancel_idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True, index=True)
    reminder_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reminder_recipient_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    reminder_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_REQUESTED", index=True)
    reminder_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    slot: Mapped[ScheduleSlot] = relationship(back_populates="appointments")
    events: Mapped[list["AppointmentEvent"]] = relationship(back_populates="appointment", cascade="all, delete-orphan")

class AppointmentEvent(RendezvousBase):
    __tablename__ = "appointment_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    appointment_id: Mapped[str] = mapped_column(String(36), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    old_slot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    new_slot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    appointment: Mapped[Appointment] = relationship(back_populates="events")
