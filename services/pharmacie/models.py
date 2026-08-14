from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.pharmacie_base import PharmacieBase


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Medicine(PharmacieBase):
    __tablename__ = "medicines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    form: Mapped[str] = mapped_column(String(80), nullable=False)
    strength: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    sale_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    reorder_level: Mapped[int] = mapped_column(BigInteger, nullable=False, default=10)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)

    batches: Mapped[list["Batch"]] = relationship(back_populates="medicine", cascade="all, delete-orphan")


class Batch(PharmacieBase):
    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("medicine_id", "batch_number", name="uq_batch_medicine_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    batch_number: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    medicine_id: Mapped[str] = mapped_column(String(36), ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False, index=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity_available: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)

    medicine: Mapped[Medicine] = relationship(back_populates="batches")


class StockMovement(PharmacieBase):
    __tablename__ = "movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    medicine_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    quantity_delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)


class Supplier(PharmacieBase):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")


class PurchaseOrder(PharmacieBase):
    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    order_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ORDERED", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(PharmacieBase):
    __tablename__ = "purchase_order_items"
    __table_args__ = (UniqueConstraint("purchase_order_id", "medicine_id", name="uq_po_medicine"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    medicine_id: Mapped[str] = mapped_column(String(36), ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_ordered: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity_received: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    medicine: Mapped[Medicine] = relationship()


class PurchaseReceipt(PharmacieBase):
    __tablename__ = "purchase_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)


class PrescriptionInbox(PharmacieBase):
    __tablename__ = "prescription_inbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prescription_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    consultation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ISSUED", index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    exposed_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)

    items: Mapped[list["PrescriptionInboxItem"]] = relationship(back_populates="prescription", cascade="all, delete-orphan")
    dispensations: Mapped[list["Dispensation"]] = relationship(back_populates="prescription")


class PrescriptionInboxItem(PharmacieBase):
    __tablename__ = "prescription_inbox_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    prescription_id: Mapped[str] = mapped_column(String(36), ForeignKey("prescription_inbox.id", ondelete="CASCADE"), nullable=False, index=True)
    medicine_ref: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dose: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(120), nullable=False)
    duration: Mapped[str] = mapped_column(String(120), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    prescription: Mapped[PrescriptionInbox] = relationship(back_populates="items")


class Dispensation(PharmacieBase):
    __tablename__ = "dispensations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    dispensation_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    prescription_id: Mapped[str] = mapped_column(String(36), ForeignKey("prescription_inbox.id", ondelete="RESTRICT"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    billing_charge_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_DELIVERY", index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, index=True)

    prescription: Mapped[PrescriptionInbox] = relationship(back_populates="dispensations")
    items: Mapped[list["DispensationItem"]] = relationship(back_populates="dispensation", cascade="all, delete-orphan")


class DispensationItem(PharmacieBase):
    __tablename__ = "dispensation_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    dispensation_id: Mapped[str] = mapped_column(String(36), ForeignKey("dispensations.id", ondelete="CASCADE"), nullable=False, index=True)
    medicine_id: Mapped[str] = mapped_column(String(36), ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False, index=True)
    medicine_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    dispensation: Mapped[Dispensation] = relationship(back_populates="items")
    medicine: Mapped[Medicine] = relationship()
    allocations: Mapped[list["DispensationAllocation"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class DispensationAllocation(PharmacieBase):
    __tablename__ = "dispensation_allocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    dispensation_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("dispensation_items.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)

    item: Mapped[DispensationItem] = relationship(back_populates="allocations")
    batch: Mapped[Batch] = relationship()


class BillingOutbox(PharmacieBase):
    __tablename__ = "billing_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    dispensation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="BIF")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_DELIVERY", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
