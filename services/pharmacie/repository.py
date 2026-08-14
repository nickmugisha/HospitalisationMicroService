from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from services.pharmacie.models import (
    Batch,
    DispensationAllocation,
    Dispensation,
    DispensationItem,
    Medicine,
    PrescriptionInbox,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)


def get_medicine_by_ref(session: Session, medicine_ref: str) -> Medicine | None:
    ref = medicine_ref.strip()
    return session.scalar(
        select(Medicine).where(
            or_(Medicine.id == ref, func.upper(Medicine.code) == ref.upper())
        )
    )


def search_medicines(session: Session, query: str, active_only: bool, limit: int, offset: int):
    statement = select(Medicine)
    count_statement = select(func.count()).select_from(Medicine)
    filters = []
    if query:
        like = f"%{query}%"
        filters.append(or_(Medicine.code.like(like), Medicine.name.like(like)))
    if active_only:
        filters.append(Medicine.active.is_(True))
    if filters:
        statement = statement.where(*filters)
        count_statement = count_statement.where(*filters)
    total = session.scalar(count_statement) or 0
    rows = session.scalars(statement.order_by(Medicine.name, Medicine.code).offset(offset).limit(limit)).all()
    return rows, total


def get_stock_batches(session: Session, medicine_id: str):
    return session.scalars(
        select(Batch).where(Batch.medicine_id == medicine_id).order_by(Batch.expiry_date, Batch.batch_number)
    ).all()


def get_prescription(session: Session, prescription_id: str) -> PrescriptionInbox | None:
    return session.scalar(
        select(PrescriptionInbox)
        .options(selectinload(PrescriptionInbox.items))
        .where(PrescriptionInbox.id == prescription_id)
    )


def get_dispensation_by_key(session: Session, key: str) -> Dispensation | None:
    return session.scalar(
        select(Dispensation)
        .options(
            selectinload(Dispensation.items).selectinload(DispensationItem.medicine),
            selectinload(Dispensation.items).selectinload(DispensationItem.allocations).selectinload(DispensationAllocation.batch),
        )
        .where(Dispensation.idempotency_key == key)
    )


def get_dispensation(session: Session, dispensation_id: str) -> Dispensation | None:
    return session.scalar(
        select(Dispensation)
        .options(
            selectinload(Dispensation.items).selectinload(DispensationItem.medicine),
            selectinload(Dispensation.items).selectinload(DispensationItem.allocations).selectinload(DispensationAllocation.batch),
        )
        .where(Dispensation.id == dispensation_id)
    )


def get_supplier_by_code(session: Session, code: str) -> Supplier | None:
    return session.scalar(select(Supplier).where(func.upper(Supplier.code) == code.upper()))


def get_purchase_order_by_key(session: Session, key: str) -> PurchaseOrder | None:
    return session.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.medicine))
        .where(PurchaseOrder.idempotency_key == key)
    )


def get_purchase_order(session: Session, po_id: str) -> PurchaseOrder | None:
    return session.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.medicine))
        .where(PurchaseOrder.id == po_id)
    )
