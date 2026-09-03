from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from services.laboratoire.models import LabOrder, LabTest, Result


def order_options():
    return (
        joinedload(LabOrder.test),
        joinedload(LabOrder.sample),
        joinedload(LabOrder.result),
    )


def get_test_by_code(session: Session, code: str) -> LabTest | None:
    return session.scalar(select(LabTest).where(LabTest.code == code))


def get_order(session: Session, order_id: str) -> LabOrder | None:
    return session.scalar(select(LabOrder).options(*order_options()).where(LabOrder.id == order_id))


def get_order_by_correlation(session: Session, correlation_id: str) -> LabOrder | None:
    return session.scalar(
        select(LabOrder).options(*order_options()).where(LabOrder.correlation_id == correlation_id)
    )


def list_pending_orders(session: Session, *, priority: str | None, limit: int, offset: int):
    filters = [LabOrder.status.notin_(["VALIDATED", "CANCELLED"])]
    if priority:
        filters.append(LabOrder.priority == priority)
    statement = (
        select(LabOrder)
        .options(*order_options())
        .where(*filters)
        .order_by(LabOrder.ordered_at.asc())
        .limit(limit)
        .offset(offset)
    )
    count_statement = select(func.count()).select_from(LabOrder).where(*filters)
    return list(session.scalars(statement).unique().all()), int(session.scalar(count_statement) or 0)


def list_patient_result_orders(session: Session, *, patient_id: str, limit: int, offset: int):
    filters = [LabOrder.patient_id == patient_id, LabOrder.status.in_(["RESULTED", "VALIDATED"])]
    statement = (
        select(LabOrder)
        .options(*order_options())
        .where(*filters)
        .order_by(LabOrder.ordered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_statement = select(func.count()).select_from(LabOrder).where(*filters)
    return list(session.scalars(statement).unique().all()), int(session.scalar(count_statement) or 0)


def get_test_by_ref(session: Session, ref: str) -> LabTest | None:
    value = ref.strip()
    if not value:
        return None
    return session.scalar(select(LabTest).where(or_(LabTest.id == value, func.upper(LabTest.code) == value.upper())))


def list_lab_tests(session: Session, *, query: str, active_only: bool, limit: int, offset: int):
    filters = []
    if query.strip():
        like = f"%{query.strip()}%"
        filters.append(or_(LabTest.code.like(like), LabTest.name.like(like), LabTest.sample_type.like(like)))
    if active_only:
        filters.append(LabTest.active.is_(True))
    total = int(session.scalar(select(func.count()).select_from(LabTest).where(*filters)) or 0)
    rows = list(session.scalars(select(LabTest).where(*filters).order_by(LabTest.name, LabTest.code).offset(offset).limit(limit)).all())
    return rows, total
