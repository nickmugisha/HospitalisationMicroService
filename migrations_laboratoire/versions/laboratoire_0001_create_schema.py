"""create laboratoire schema

Revision ID: laboratoire_0001
Revises:
Create Date: 2026-08-13 09:40:00
"""

from alembic import op
import sqlalchemy as sa

revision = "laboratoire_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_tests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("sample_type", sa.String(length=80), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lab_tests_code"), "lab_tests", ["code"], unique=True)
    op.create_index(op.f("ix_lab_tests_active"), "lab_tests", ["active"], unique=False)

    op.create_table(
        "lab_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("consultation_id", sa.String(length=36), nullable=False),
        sa.Column("lab_test_id", sa.String(length=36), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("clinical_question", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("ordered_by", sa.String(length=36), nullable=False),
        sa.Column("ordered_at", sa.DateTime(), nullable=False),
        sa.Column("billing_charge_status", sa.String(length=30), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["lab_test_id"], ["lab_tests.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, cols, unique in [
        ("ix_lab_orders_order_number", ["order_number"], True),
        ("ix_lab_orders_patient_id", ["patient_id"], False),
        ("ix_lab_orders_consultation_id", ["consultation_id"], False),
        ("ix_lab_orders_lab_test_id", ["lab_test_id"], False),
        ("ix_lab_orders_priority", ["priority"], False),
        ("ix_lab_orders_status", ["status"], False),
        ("ix_lab_orders_correlation_id", ["correlation_id"], True),
        ("ix_lab_orders_ordered_by", ["ordered_by"], False),
        ("ix_lab_orders_ordered_at", ["ordered_at"], False),
        ("ix_lab_orders_billing_charge_status", ["billing_charge_status"], False),
    ]:
        op.create_index(name, "lab_orders", cols, unique=unique)

    op.create_table(
        "samples",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("sample_code", sa.String(length=40), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("collected_by", sa.String(length=36), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["lab_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_samples_sample_code", "samples", ["sample_code"], unique=True)
    op.create_index("ix_samples_order_id", "samples", ["order_id"], unique=True)
    op.create_index("ix_samples_collected_by", "samples", ["collected_by"], unique=False)
    op.create_index("ix_samples_collected_at", "samples", ["collected_at"], unique=False)

    op.create_table(
        "results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("consultation_id", sa.String(length=36), nullable=False),
        sa.Column("values_json", sa.Text(), nullable=True),
        sa.Column("text_result", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("validated_by", sa.String(length=36), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["lab_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_results_order_id", "results", ["order_id"], unique=True)
    op.create_index("ix_results_patient_id", "results", ["patient_id"], unique=False)
    op.create_index("ix_results_consultation_id", "results", ["consultation_id"], unique=False)
    op.create_index("ix_results_recorded_by", "results", ["recorded_by"], unique=False)
    op.create_index("ix_results_recorded_at", "results", ["recorded_at"], unique=False)
    op.create_index("ix_results_validated_by", "results", ["validated_by"], unique=False)
    op.create_index("ix_results_validated_at", "results", ["validated_at"], unique=False)

    op.create_table(
        "result_corrections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("result_id", sa.String(length=36), nullable=False),
        sa.Column("previous_values_json", sa.Text(), nullable=True),
        sa.Column("previous_text_result", sa.Text(), nullable=True),
        sa.Column("previous_version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("corrected_by", sa.String(length=36), nullable=False),
        sa.Column("corrected_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["result_id"], ["results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_result_corrections_result_id", "result_corrections", ["result_id"], unique=False)
    op.create_index("ix_result_corrections_corrected_by", "result_corrections", ["corrected_by"], unique=False)
    op.create_index("ix_result_corrections_corrected_at", "result_corrections", ["corrected_at"], unique=False)

    op.create_table(
        "billing_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("source_ref", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billing_outbox_idempotency_key", "billing_outbox", ["idempotency_key"], unique=True)
    op.create_index("ix_billing_outbox_correlation_id", "billing_outbox", ["correlation_id"], unique=False)
    op.create_index("ix_billing_outbox_patient_id", "billing_outbox", ["patient_id"], unique=False)
    op.create_index("ix_billing_outbox_source_ref", "billing_outbox", ["source_ref"], unique=False)
    op.create_index("ix_billing_outbox_status", "billing_outbox", ["status"], unique=False)
    op.create_index("ix_billing_outbox_created_at", "billing_outbox", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("billing_outbox")
    op.drop_table("result_corrections")
    op.drop_table("results")
    op.drop_table("samples")
    op.drop_table("lab_orders")
    op.drop_table("lab_tests")
