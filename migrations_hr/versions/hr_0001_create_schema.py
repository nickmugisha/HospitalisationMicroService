"""create HR schema

Revision ID: hr_0001
Revises:
Create Date: 2026-08-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "hr_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_number", sa.String(50), nullable=False),
        sa.Column("auth_user_id", sa.String(36), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(180), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("department", sa.String(120), nullable=False),
        sa.Column("job_title", sa.String(120), nullable=False),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("employment_type", sa.String(40), nullable=False),
        sa.Column("employment_status", sa.String(30), nullable=False),
        sa.Column("provisioning_status", sa.String(40), nullable=False),
        sa.Column("created_by_auth_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("employee_number", name="uq_hr_employee_number"),
        sa.UniqueConstraint("auth_user_id", name="uq_hr_auth_user_id"),
        sa.UniqueConstraint("email", name="uq_hr_employee_email"),
    )
    op.create_index("ix_hr_employees_department", "employees", ["department"])
    op.create_index("ix_hr_employees_status", "employees", ["employment_status"])

    op.create_table(
        "shifts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), nullable=False),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("location", sa.String(120), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("created_by_auth_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_hr_shift_idempotency"),
        sa.UniqueConstraint("employee_id", "shift_date", "start_time", name="uq_hr_employee_shift_start"),
    )
    op.create_index("ix_hr_shifts_date", "shifts", ["shift_date"])
    op.create_index("ix_hr_shifts_employee", "shifts", ["employee_id"])

    op.create_table(
        "attendance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("clock_in_at", sa.DateTime(), nullable=True),
        sa.Column("clock_out_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("corrected_by_auth_user_id", sa.String(36), nullable=True),
        sa.Column("corrected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("employee_id", "work_date", name="uq_hr_attendance_employee_day"),
    )
    op.create_index("ix_hr_attendance_date", "attendance", ["work_date"])
    op.create_index("ix_hr_attendance_status", "attendance", ["status"])

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), nullable=False),
        sa.Column("leave_type", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reviewed_by_auth_user_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hr_leave_employee", "leave_requests", ["employee_id"])
    op.create_index("ix_hr_leave_status", "leave_requests", ["status"])
    op.create_index("ix_hr_leave_dates", "leave_requests", ["start_date", "end_date"])

    op.create_table(
        "hr_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("actor_auth_user_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("peer", sa.String(255), nullable=True),
    )
    op.create_index("ix_hr_audit_timestamp", "hr_audit_logs", ["timestamp"])
    op.create_index("ix_hr_audit_actor", "hr_audit_logs", ["actor_auth_user_id"])

def downgrade() -> None:
    op.drop_table("hr_audit_logs")
    op.drop_table("leave_requests")
    op.drop_table("attendance")
    op.drop_table("shifts")
    op.drop_table("employees")
