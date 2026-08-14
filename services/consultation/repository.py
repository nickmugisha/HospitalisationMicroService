from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from services.consultation.models import Consultation, Prescription


def consultation_options():
    return (
        selectinload(Consultation.diagnoses),
        selectinload(Consultation.prescriptions).selectinload(Prescription.items),
    )


def get_consultation(session: Session, consultation_id: str) -> Consultation | None:
    return session.scalar(
        select(Consultation)
        .options(*consultation_options())
        .where(Consultation.id == consultation_id)
    )


def list_patient_consultations(
    session: Session,
    *,
    patient_id: str,
    limit: int,
    offset: int,
) -> tuple[list[Consultation], int]:
    statement = (
        select(Consultation)
        .options(*consultation_options())
        .where(Consultation.patient_id == patient_id)
        .order_by(Consultation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_statement = (
        select(func.count())
        .select_from(Consultation)
        .where(Consultation.patient_id == patient_id)
    )
    return list(session.scalars(statement).all()), int(session.scalar(count_statement) or 0)
