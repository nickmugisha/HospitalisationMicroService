"""create consultation schema

Revision ID: consultation_0001
Revises:
Create Date: 2026-08-13 09:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "consultation_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("consultation_number", sa.String(length=40), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("symptoms", sa.Text(), nullable=True),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("vitals_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consultations_consultation_number"), "consultations", ["consultation_number"], unique=True)
    op.create_index(op.f("ix_consultations_patient_id"), "consultations", ["patient_id"], unique=False)
    op.create_index(op.f("ix_consultations_doctor_id"), "consultations", ["doctor_id"], unique=False)
    op.create_index(op.f("ix_consultations_status"), "consultations", ["status"], unique=False)
    op.create_index(op.f("ix_consultations_created_at"), "consultations", ["created_at"], unique=False)
    op.create_index(op.f("ix_consultations_created_by"), "consultations", ["created_by"], unique=False)
    op.create_index(op.f("ix_consultations_updated_by"), "consultations", ["updated_by"], unique=False)

    op.create_table(
        "diagnoses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("consultation_id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diagnoses_consultation_id"), "diagnoses", ["consultation_id"], unique=False)
    op.create_index(op.f("ix_diagnoses_code"), "diagnoses", ["code"], unique=False)
    op.create_index(op.f("ix_diagnoses_created_by"), "diagnoses", ["created_by"], unique=False)

    op.create_table(
        "prescriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("prescription_number", sa.String(length=40), nullable=False),
        sa.Column("consultation_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prescriptions_prescription_number"), "prescriptions", ["prescription_number"], unique=True)
    op.create_index(op.f("ix_prescriptions_consultation_id"), "prescriptions", ["consultation_id"], unique=False)
    op.create_index(op.f("ix_prescriptions_patient_id"), "prescriptions", ["patient_id"], unique=False)
    op.create_index(op.f("ix_prescriptions_doctor_id"), "prescriptions", ["doctor_id"], unique=False)
    op.create_index(op.f("ix_prescriptions_status"), "prescriptions", ["status"], unique=False)
    op.create_index(op.f("ix_prescriptions_issued_at"), "prescriptions", ["issued_at"], unique=False)
    op.create_index(op.f("ix_prescriptions_created_by"), "prescriptions", ["created_by"], unique=False)

    op.create_table(
        "prescription_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("prescription_id", sa.String(length=36), nullable=False),
        sa.Column("medicine_ref", sa.String(length=120), nullable=False),
        sa.Column("dose", sa.String(length=120), nullable=False),
        sa.Column("frequency", sa.String(length=120), nullable=False),
        sa.Column("duration", sa.String(length=120), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["prescription_id"], ["prescriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prescription_items_prescription_id"), "prescription_items", ["prescription_id"], unique=False)
    op.create_index(op.f("ix_prescription_items_medicine_ref"), "prescription_items", ["medicine_ref"], unique=False)

    op.create_table(
        "outbound_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("consultation_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("request_type", sa.String(length=30), nullable=False),
        sa.Column("target_service", sa.String(length=40), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outbound_requests_correlation_id"), "outbound_requests", ["correlation_id"], unique=True)
    op.create_index(op.f("ix_outbound_requests_consultation_id"), "outbound_requests", ["consultation_id"], unique=False)
    op.create_index(op.f("ix_outbound_requests_patient_id"), "outbound_requests", ["patient_id"], unique=False)
    op.create_index(op.f("ix_outbound_requests_request_type"), "outbound_requests", ["request_type"], unique=False)
    op.create_index(op.f("ix_outbound_requests_target_service"), "outbound_requests", ["target_service"], unique=False)
    op.create_index(op.f("ix_outbound_requests_status"), "outbound_requests", ["status"], unique=False)
    op.create_index(op.f("ix_outbound_requests_created_at"), "outbound_requests", ["created_at"], unique=False)
    op.create_index(op.f("ix_outbound_requests_created_by"), "outbound_requests", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_table("outbound_requests")
    op.drop_table("prescription_items")
    op.drop_table("prescriptions")
    op.drop_table("diagnoses")
    op.drop_table("consultations")
