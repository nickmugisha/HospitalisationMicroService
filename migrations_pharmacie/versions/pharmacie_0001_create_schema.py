"""create pharmacie schema

Revision ID: pharmacie_0001
Revises:
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "pharmacie_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medicines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("form", sa.String(80), nullable=False),
        sa.Column("strength", sa.String(80), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("sale_price_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="BIF"),
        sa.Column("reorder_level", sa.BigInteger(), nullable=False, server_default="10"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code", name="uq_medicines_code"),
    )
    op.create_index("ix_medicines_code", "medicines", ["code"])
    op.create_index("ix_medicines_name", "medicines", ["name"])
    op.create_index("ix_medicines_active", "medicines", ["active"])

    op.create_table(
        "batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_number", sa.String(120), nullable=False),
        sa.Column("medicine_id", sa.String(36), sa.ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("quantity_available", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("medicine_id", "batch_number", name="uq_batch_medicine_number"),
    )
    op.create_index("ix_batches_batch_number", "batches", ["batch_number"])
    op.create_index("ix_batches_medicine_id", "batches", ["medicine_id"])
    op.create_index("ix_batches_expiry_date", "batches", ["expiry_date"])

    op.create_table(
        "movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("medicine_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("quantity_delta", sa.BigInteger(), nullable=False),
        sa.Column("reference", sa.String(160), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ("movement_type", "medicine_id", "batch_id", "reference", "actor_id", "created_at"):
        op.create_index(f"ix_movements_{col}", "movements", [col])

    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(180), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code", name="uq_suppliers_code"),
    )
    op.create_index("ix_suppliers_code", "suppliers", ["code"])
    op.create_index("ix_suppliers_active", "suppliers", ["active"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("ordered_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("order_number", name="uq_purchase_orders_order_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_purchase_orders_idempotency"),
    )
    for col in ("order_number", "supplier_id", "status", "idempotency_key", "created_by"):
        op.create_index(f"ix_purchase_orders_{col}", "purchase_orders", [col])

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medicine_id", sa.String(36), sa.ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity_ordered", sa.BigInteger(), nullable=False),
        sa.Column("quantity_received", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint("purchase_order_id", "medicine_id", name="uq_po_medicine"),
    )
    op.create_index("ix_purchase_order_items_purchase_order_id", "purchase_order_items", ["purchase_order_id"])
    op.create_index("ix_purchase_order_items_medicine_id", "purchase_order_items", ["medicine_id"])

    op.create_table(
        "purchase_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_purchase_receipts_idempotency"),
    )
    op.create_index("ix_purchase_receipts_purchase_order_id", "purchase_receipts", ["purchase_order_id"])
    op.create_index("ix_purchase_receipts_idempotency_key", "purchase_receipts", ["idempotency_key"])
    op.create_index("ix_purchase_receipts_actor_id", "purchase_receipts", ["actor_id"])

    op.create_table(
        "prescription_inbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prescription_number", sa.String(50), nullable=False),
        sa.Column("consultation_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("doctor_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("exposed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("prescription_number", name="uq_prescription_inbox_number"),
        sa.UniqueConstraint("correlation_id", name="uq_prescription_inbox_correlation"),
    )
    for col in ("prescription_number", "consultation_id", "patient_id", "doctor_id", "status", "correlation_id"):
        op.create_index(f"ix_prescription_inbox_{col}", "prescription_inbox", [col])

    op.create_table(
        "prescription_inbox_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prescription_id", sa.String(36), sa.ForeignKey("prescription_inbox.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medicine_ref", sa.String(120), nullable=False),
        sa.Column("dose", sa.String(120), nullable=False),
        sa.Column("frequency", sa.String(120), nullable=False),
        sa.Column("duration", sa.String(120), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
    )
    op.create_index("ix_prescription_inbox_items_prescription_id", "prescription_inbox_items", ["prescription_id"])
    op.create_index("ix_prescription_inbox_items_medicine_ref", "prescription_inbox_items", ["medicine_ref"])

    op.create_table(
        "dispensations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dispensation_number", sa.String(50), nullable=False),
        sa.Column("prescription_id", sa.String(36), sa.ForeignKey("prescription_inbox.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="BIF"),
        sa.Column("billing_charge_status", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("dispensation_number", name="uq_dispensations_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_dispensations_idempotency"),
    )
    for col in ("dispensation_number", "prescription_id", "patient_id", "idempotency_key", "status", "billing_charge_status", "actor_id", "created_at"):
        op.create_index(f"ix_dispensations_{col}", "dispensations", [col])

    op.create_table(
        "dispensation_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dispensation_id", sa.String(36), sa.ForeignKey("dispensations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medicine_id", sa.String(36), sa.ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("medicine_ref", sa.String(120), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_dispensation_items_dispensation_id", "dispensation_items", ["dispensation_id"])
    op.create_index("ix_dispensation_items_medicine_id", "dispensation_items", ["medicine_id"])

    op.create_table(
        "dispensation_allocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dispensation_item_id", sa.String(36), sa.ForeignKey("dispensation_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_dispensation_allocations_dispensation_item_id", "dispensation_allocations", ["dispensation_item_id"])
    op.create_index("ix_dispensation_allocations_batch_id", "dispensation_allocations", ["batch_id"])

    op.create_table(
        "billing_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("dispensation_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="BIF"),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_billing_outbox_idempotency"),
    )
    for col in ("idempotency_key", "dispensation_id", "patient_id", "status"):
        op.create_index(f"ix_billing_outbox_{col}", "billing_outbox", [col])


def downgrade() -> None:
    for table in (
        "billing_outbox",
        "dispensation_allocations",
        "dispensation_items",
        "dispensations",
        "prescription_inbox_items",
        "prescription_inbox",
        "purchase_receipts",
        "purchase_order_items",
        "purchase_orders",
        "suppliers",
        "movements",
        "batches",
        "medicines",
    ):
        op.drop_table(table)
