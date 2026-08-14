from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from services.accueil.models import Arrival, Patient


def get_patient_by_id(session: Session, patient_id: str) -> Patient | None:
    return session.scalar(select(Patient).where(Patient.id == patient_id))


def get_patient_by_number(session: Session, patient_number: str) -> Patient | None:
    return session.scalar(select(Patient).where(Patient.patient_number == patient_number))


def find_obvious_duplicate(
    session: Session,
    *,
    first_name: str,
    last_name: str,
    birth_date: date,
    phone: str | None,
) -> Patient | None:
    # Without a phone number, same name + birth date is not strong enough
    # evidence to reject a real hospital patient as a duplicate.
    if not phone:
        return None
    conditions = [
        func.lower(Patient.first_name) == first_name.lower(),
        func.lower(Patient.last_name) == last_name.lower(),
        Patient.birth_date == birth_date,
        Patient.phone == phone,
    ]
    return session.scalar(select(Patient).where(*conditions))


def search_patients(
    session: Session,
    *,
    query: str,
    limit: int,
    offset: int,
) -> tuple[list[Patient], int]:
    statement = select(Patient)
    count_statement = select(func.count()).select_from(Patient)

    if query:
        like = f"%{query}%"
        predicate = or_(
            Patient.id == query,
            Patient.patient_number == query,
            Patient.first_name.ilike(like),
            Patient.last_name.ilike(like),
            Patient.phone.ilike(like),
        )
        statement = statement.where(predicate)
        count_statement = count_statement.where(predicate)

    statement = statement.order_by(Patient.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(statement).all()), int(session.scalar(count_statement) or 0)


def get_arrival_by_id(session: Session, arrival_id: str) -> Arrival | None:
    return session.scalar(
        select(Arrival)
        .options(joinedload(Arrival.patient))
        .where(Arrival.id == arrival_id)
    )


def list_waiting_queue(
    session: Session,
    *,
    target_service: str,
    limit: int,
    offset: int,
) -> tuple[list[Arrival], int]:
    statement = (
        select(Arrival)
        .options(joinedload(Arrival.patient))
        .where(Arrival.status == "WAITING")
    )
    count_statement = (
        select(func.count())
        .select_from(Arrival)
        .where(Arrival.status == "WAITING")
    )

    if target_service:
        statement = statement.where(Arrival.target_service == target_service)
        count_statement = count_statement.where(Arrival.target_service == target_service)

    # Emergency first, then urgent, then routine; oldest first inside a priority.
    priority_order = func.field(Arrival.priority, "EMERGENCY", "URGENT", "ROUTINE")
    statement = statement.order_by(priority_order.asc(), Arrival.arrived_at.asc()).limit(limit).offset(offset)

    return list(session.scalars(statement).unique().all()), int(session.scalar(count_statement) or 0)
