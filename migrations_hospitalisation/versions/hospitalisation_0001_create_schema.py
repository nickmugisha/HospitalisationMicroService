"""create hospitalisation schema

Revision ID: hospitalisation_0001
Revises:
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
revision = "hospitalisation_0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "wards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("daily_rate_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="BIF"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code", name="uq_wards_code"),
    )
    op.create_index("ix_wards_code", "wards", ["code"]); op.create_index("ix_wards_active", "wards", ["active"])

    op.create_table(
        "rooms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ward_id", sa.String(36), sa.ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("ward_id", "code", name="uq_room_ward_code"),
    )
    op.create_index("ix_rooms_ward_id", "rooms", ["ward_id"]); op.create_index("ix_rooms_code", "rooms", ["code"])

    op.create_table(
        "beds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="AVAILABLE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("room_id", "code", name="uq_bed_room_code"),
    )
    op.create_index("ix_beds_room_id", "beds", ["room_id"]); op.create_index("ix_beds_code", "beds", ["code"]); op.create_index("ix_beds_status", "beds", ["status"])

    op.create_table(
        "admissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admission_number", sa.String(60), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("active_patient_key", sa.String(36), nullable=True),
        sa.Column("consultation_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("preferred_ward", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("current_bed_id", sa.String(36), sa.ForeignKey("beds.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("bed_assignment_key", sa.String(160), nullable=True),
        sa.Column("discharge_idempotency_key", sa.String(160), nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("admitted_at", sa.DateTime(), nullable=True),
        sa.Column("discharged_at", sa.DateTime(), nullable=True),
        sa.Column("discharge_summary", sa.Text(), nullable=True),
        sa.Column("billing_charge_status", sa.String(30), nullable=False, server_default="NOT_CREATED"),
        sa.UniqueConstraint("admission_number", name="uq_admissions_number"),
        sa.UniqueConstraint("active_patient_key", name="uq_admissions_active_patient"),
        sa.UniqueConstraint("current_bed_id", name="uq_admissions_current_bed"),
        sa.UniqueConstraint("idempotency_key", name="uq_admissions_idempotency"),
        sa.UniqueConstraint("bed_assignment_key", name="uq_admissions_bed_assignment_key"),
        sa.UniqueConstraint("discharge_idempotency_key", name="uq_admissions_discharge_key"),
        sa.UniqueConstraint("correlation_id", name="uq_admissions_correlation"),
    )
    for col in ("admission_number","patient_id","active_patient_key","consultation_id","preferred_ward","status","current_bed_id","idempotency_key","bed_assignment_key","discharge_idempotency_key","correlation_id","created_by","billing_charge_status"):
        op.create_index(f"ix_admissions_{col}", "admissions", [col])

    op.create_table(
        "transfers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admission_id", sa.String(36), sa.ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_bed_id", sa.String(36), sa.ForeignKey("beds.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("to_bed_id", sa.String(36), sa.ForeignKey("beds.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_transfers_idempotency"),
    )
    for col in ("admission_id","from_bed_id","to_bed_id","idempotency_key","actor_id"):
        op.create_index(f"ix_transfers_{col}", "transfers", [col])

    op.create_table(
        "stay_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admission_id", sa.String(36), sa.ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stay_notes_admission_id", "stay_notes", ["admission_id"]); op.create_index("ix_stay_notes_actor_id", "stay_notes", ["actor_id"]); op.create_index("ix_stay_notes_created_at", "stay_notes", ["created_at"])

    op.create_table(
        "billing_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("admission_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="BIF"),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_DELIVERY"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_hosp_billing_outbox_idempotency"),
    )
    for col in ("idempotency_key","admission_id","patient_id","status"):
        op.create_index(f"ix_hosp_billing_outbox_{col}", "billing_outbox", [col])

def downgrade() -> None:
    for table in ("billing_outbox", "stay_notes", "transfers", "admissions", "beds", "rooms", "wards"):
        op.drop_table(table)
