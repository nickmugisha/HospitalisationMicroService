"""create accueil schema

Revision ID: accueil_0001
Revises:
Create Date: 2026-08-13 08:32:00
"""

from alembic import op
import sqlalchemy as sa


revision = "accueil_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_number", sa.String(length=40), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("sex", sa.String(length=20), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patients_patient_number"), "patients", ["patient_number"], unique=True)
    op.create_index(op.f("ix_patients_first_name"), "patients", ["first_name"], unique=False)
    op.create_index(op.f("ix_patients_last_name"), "patients", ["last_name"], unique=False)
    op.create_index(op.f("ix_patients_phone"), "patients", ["phone"], unique=False)
    op.create_index(op.f("ix_patients_status"), "patients", ["status"], unique=False)
    op.create_index(op.f("ix_patients_created_by"), "patients", ["created_by"], unique=False)
    op.create_index(op.f("ix_patients_updated_by"), "patients", ["updated_by"], unique=False)

    op.create_table(
        "arrivals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("arrived_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("target_service", sa.String(length=80), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("orientation_note", sa.Text(), nullable=True),
        sa.Column("oriented_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_arrivals_patient_id"), "arrivals", ["patient_id"], unique=False)
    op.create_index(op.f("ix_arrivals_arrived_at"), "arrivals", ["arrived_at"], unique=False)
    op.create_index(op.f("ix_arrivals_target_service"), "arrivals", ["target_service"], unique=False)
    op.create_index(op.f("ix_arrivals_priority"), "arrivals", ["priority"], unique=False)
    op.create_index(op.f("ix_arrivals_status"), "arrivals", ["status"], unique=False)
    op.create_index(op.f("ix_arrivals_created_by"), "arrivals", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_arrivals_created_by"), table_name="arrivals")
    op.drop_index(op.f("ix_arrivals_status"), table_name="arrivals")
    op.drop_index(op.f("ix_arrivals_priority"), table_name="arrivals")
    op.drop_index(op.f("ix_arrivals_target_service"), table_name="arrivals")
    op.drop_index(op.f("ix_arrivals_arrived_at"), table_name="arrivals")
    op.drop_index(op.f("ix_arrivals_patient_id"), table_name="arrivals")
    op.drop_table("arrivals")

    op.drop_index(op.f("ix_patients_updated_by"), table_name="patients")
    op.drop_index(op.f("ix_patients_created_by"), table_name="patients")
    op.drop_index(op.f("ix_patients_status"), table_name="patients")
    op.drop_index(op.f("ix_patients_phone"), table_name="patients")
    op.drop_index(op.f("ix_patients_last_name"), table_name="patients")
    op.drop_index(op.f("ix_patients_first_name"), table_name="patients")
    op.drop_index(op.f("ix_patients_patient_number"), table_name="patients")
    op.drop_table("patients")
