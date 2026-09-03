"""timed reminders and schedule administration

Revision ID: rendezvous_0002
Revises: rendezvous_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "rendezvous_0002"
down_revision = "rendezvous_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("reminder_due_at", sa.DateTime(), nullable=True))
    op.add_column("appointments", sa.Column("reminder_sent_at", sa.DateTime(), nullable=True))
    op.create_index("ix_appointments_reminder_due_at", "appointments", ["reminder_due_at"], unique=False)
    op.create_index("ix_appointments_reminder_sent_at", "appointments", ["reminder_sent_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_appointments_reminder_sent_at", table_name="appointments")
    op.drop_index("ix_appointments_reminder_due_at", table_name="appointments")
    op.drop_column("appointments", "reminder_sent_at")
    op.drop_column("appointments", "reminder_due_at")
