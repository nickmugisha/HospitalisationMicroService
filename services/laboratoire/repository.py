from __future__ import annotations

from sqlalchemy import func, select
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
