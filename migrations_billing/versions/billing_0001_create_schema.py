"""create billing schema

Revision ID: billing_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "billing_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("invoice_number", sa.String(length=60), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("paid_minor", sa.BigInteger(), nullable=False),
        sa.Column("balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
        sa.UniqueConstraint("patient_id"),
    )
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"], unique=True)
    op.create_index("ix_invoices_patient_id", "invoices", ["patient_id"], unique=True)
    op.create_index("ix_invoices_status", "invoices", ["status"], unique=False)

    op.create_table(
        "charges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("charge_number", sa.String(length=60), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("source_key", sa.String(length=180), nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=True),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("charge_number"),
        sa.UniqueConstraint("source_key"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_charge_source"),
    )
    for name, cols, unique in [
        ("ix_charges_charge_number", ["charge_number"], True),
        ("ix_charges_source_type", ["source_type"], False),
        ("ix_charges_source_id", ["source_id"], False),
        ("ix_charges_source_key", ["source_key"], True),
        ("ix_charges_idempotency_key", ["idempotency_key"], True),
        ("ix_charges_correlation_id", ["correlation_id"], False),
        ("ix_charges_patient_id", ["patient_id"], False),
        ("ix_charges_invoice_id", ["invoice_id"], False),
        ("ix_charges_status", ["status"], False),
    ]:
        op.create_index(name, "charges", cols, unique=unique)

    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payment_number", sa.String(length=60), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("cashier_id", sa.String(length=36), nullable=False),
        sa.Column("reference", sa.String(length=160), nullable=True),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_number"),
        sa.UniqueConstraint("idempotency_key"),
    )
    for name, cols, unique in [
        ("ix_payments_payment_number", ["payment_number"], True),
        ("ix_payments_invoice_id", ["invoice_id"], False),
        ("ix_payments_patient_id", ["patient_id"], False),
        ("ix_payments_cashier_id", ["cashier_id"], False),
        ("ix_payments_idempotency_key", ["idempotency_key"], True),
    ]:
        op.create_index(name, "payments", cols, unique=unique)

    op.create_table(
        "receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("receipt_number", sa.String(length=60), nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_number"),
        sa.UniqueConstraint("payment_id"),
    )
    op.create_index("ix_receipts_receipt_number", "receipts", ["receipt_number"], unique=True)
    op.create_index("ix_receipts_payment_id", "receipts", ["payment_id"], unique=True)
    op.create_index("ix_receipts_invoice_id", "receipts", ["invoice_id"], unique=False)

    op.create_table(
        "reversals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reversal_number", sa.String(length=60), nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reversal_number"),
        sa.UniqueConstraint("payment_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_reversals_reversal_number", "reversals", ["reversal_number"], unique=True)
    op.create_index("ix_reversals_payment_id", "reversals", ["payment_id"], unique=True)
    op.create_index("ix_reversals_invoice_id", "reversals", ["invoice_id"], unique=False)
    op.create_index("ix_reversals_actor_id", "reversals", ["actor_id"], unique=False)
    op.create_index("ix_reversals_idempotency_key", "reversals", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_table("reversals")
    op.drop_table("receipts")
    op.drop_table("payments")
    op.drop_table("charges")
    op.drop_table("invoices")
