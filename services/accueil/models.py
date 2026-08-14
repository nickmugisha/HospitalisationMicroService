from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.accueil_base import AccueilBase


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Patient(AccueilBase):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    patient_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)

    arrivals: Mapped[list["Arrival"]] = relationship(back_populates="patient")


class Arrival(AccueilBase):
    __tablename__ = "arrivals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    arrived_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    target_service: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="ROUTINE", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="WAITING", index=True)
    orientation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    oriented_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)

    patient: Mapped[Patient] = relationship(back_populates="arrivals")
