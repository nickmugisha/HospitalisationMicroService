from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from services.rendezvous.models import Appointment, ScheduleSlot


def get_slot(session: Session, slot_id: str, *, for_update: bool = False):
    stmt = select(ScheduleSlot).where(ScheduleSlot.id == slot_id)
    if for_update:
        stmt = stmt.with_for_update()
    return session.scalar(stmt)


def get_slot_by_idempotency(session: Session, key: str):
    return session.scalar(select(ScheduleSlot).where(ScheduleSlot.idempotency_key == key))


def get_appointment(session: Session, appointment_id: str):
    return session.scalar(
        select(Appointment)
        .options(selectinload(Appointment.slot))
        .where(Appointment.id == appointment_id)
    )


def get_appointment_by_number(session: Session, number: str):
    return session.scalar(
        select(Appointment)
        .options(selectinload(Appointment.slot))
        .where(Appointment.appointment_number == number)
    )


def get_appointment_by_idempotency(session: Session, key: str):
    return session.scalar(
        select(Appointment)
        .options(selectinload(Appointment.slot))
        .where(Appointment.idempotency_key == key)
    )
