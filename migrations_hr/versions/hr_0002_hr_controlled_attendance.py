"""HR-controlled attendance enhancements

Revision ID: hr_0002
Revises: hr_0001
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = "hr_0002"
down_revision = "hr_0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("attendance", sa.Column("source", sa.String(30), nullable=False, server_default="EMPLOYEE_CLOCK"))
    op.add_column("attendance", sa.Column("late_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("attendance", sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("attendance", sa.Column("validated_by_auth_user_id", sa.String(36), nullable=True))
    op.add_column("attendance", sa.Column("validated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_hr_attendance_source", "attendance", ["source"])

def downgrade() -> None:
    op.drop_index("ix_hr_attendance_source", table_name="attendance")
    op.drop_column("attendance", "validated_at")
    op.drop_column("attendance", "validated_by_auth_user_id")
    op.drop_column("attendance", "worked_minutes")
    op.drop_column("attendance", "late_minutes")
    op.drop_column("attendance", "source")
