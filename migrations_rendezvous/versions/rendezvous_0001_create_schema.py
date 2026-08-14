"""create rendezvous schema
Revision ID: rendezvous_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision="rendezvous_0001"; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("schedule_slots",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("provider_id",sa.String(80),nullable=False),
        sa.Column("service",sa.String(100),nullable=False),
        sa.Column("start_at",sa.DateTime(),nullable=False),
        sa.Column("end_at",sa.DateTime(),nullable=False),
        sa.Column("status",sa.String(30),nullable=False),
        sa.Column("idempotency_key",sa.String(160),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.UniqueConstraint("provider_id","start_at","end_at",name="uq_slot_provider_window"),
        sa.UniqueConstraint("idempotency_key",name="uq_schedule_slots_idempotency_key"),
    )
    for c in ["provider_id","service","start_at","end_at","status","idempotency_key"]: op.create_index(f"ix_schedule_slots_{c}","schedule_slots",[c])
    op.create_table("appointments",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("appointment_number",sa.String(60),nullable=False),
        sa.Column("patient_id",sa.String(36),nullable=False),
        sa.Column("provider_id",sa.String(80),nullable=False),
        sa.Column("service",sa.String(100),nullable=False),
        sa.Column("reason",sa.Text(),nullable=False),
        sa.Column("status",sa.String(30),nullable=False),
        sa.Column("slot_id",sa.String(36),sa.ForeignKey("schedule_slots.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("active_slot_key",sa.String(36),nullable=True),
        sa.Column("idempotency_key",sa.String(160),nullable=False),
        sa.Column("correlation_id",sa.String(36),nullable=False),
        sa.Column("cancellation_reason",sa.Text(),nullable=True),
        sa.Column("arrival_id",sa.String(36),nullable=True),
        sa.Column("checkin_idempotency_key",sa.String(160),nullable=True),
        sa.Column("last_reschedule_key",sa.String(160),nullable=True),
        sa.Column("cancel_idempotency_key",sa.String(160),nullable=True),
        sa.Column("reminder_requested",sa.Boolean(),nullable=False),
        sa.Column("reminder_recipient_user_id",sa.String(36),nullable=True),
        sa.Column("reminder_status",sa.String(30),nullable=False),
        sa.Column("reminder_error",sa.Text(),nullable=True),
        sa.Column("created_by",sa.String(36),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.Column("checked_in_at",sa.DateTime(),nullable=True),
        sa.Column("completed_at",sa.DateTime(),nullable=True),
        sa.UniqueConstraint("appointment_number",name="uq_appointments_appointment_number"),
        sa.UniqueConstraint("active_slot_key",name="uq_appointments_active_slot_key"),
        sa.UniqueConstraint("idempotency_key",name="uq_appointments_idempotency_key"),
        sa.UniqueConstraint("checkin_idempotency_key",name="uq_appointments_checkin_key"),
        sa.UniqueConstraint("last_reschedule_key",name="uq_appointments_reschedule_key"),
        sa.UniqueConstraint("cancel_idempotency_key",name="uq_appointments_cancel_key"),
    )
    for c in ["appointment_number","patient_id","provider_id","service","status","slot_id","active_slot_key","idempotency_key","correlation_id","arrival_id","reminder_recipient_user_id","reminder_status","created_by"]: op.create_index(f"ix_appointments_{c}","appointments",[c])
    op.create_table("appointment_events",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("appointment_id",sa.String(36),sa.ForeignKey("appointments.id",ondelete="CASCADE"),nullable=False),
        sa.Column("event_type",sa.String(50),nullable=False),
        sa.Column("from_status",sa.String(30),nullable=True),
        sa.Column("to_status",sa.String(30),nullable=True),
        sa.Column("old_slot_id",sa.String(36),nullable=True),
        sa.Column("new_slot_id",sa.String(36),nullable=True),
        sa.Column("reason",sa.Text(),nullable=True),
        sa.Column("actor_id",sa.String(36),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
    )
    for c in ["appointment_id","event_type","actor_id"]: op.create_index(f"ix_appointment_events_{c}","appointment_events",[c])

def downgrade():
    op.drop_table("appointment_events"); op.drop_table("appointments"); op.drop_table("schedule_slots")
