from alembic import op
import sqlalchemy as sa

revision = "hospitalisation_0002"
down_revision = "hospitalisation_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admissions", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("admissions", sa.Column("approved_by", sa.String(length=36), nullable=True))
    op.add_column("admissions", sa.Column("approval_reason", sa.Text(), nullable=True))
    op.create_index("ix_admissions_approved_at", "admissions", ["approved_at"], unique=False)
    op.create_index("ix_admissions_approved_by", "admissions", ["approved_by"], unique=False)

    op.create_table(
        "doctor_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("admission_id", sa.String(length=36), nullable=False),
        # Nullable unique key: while ACTIVE it equals admission_id. Clearing it on
        # completion lets history coexist while MySQL enforces one active doctor/admission.
        sa.Column("active_admission_key", sa.String(length=36), nullable=True),
        sa.Column("doctor_user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ACTIVE"),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("completion_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["admission_id"], ["admissions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_doctor_assignment_idempotency"),
        sa.UniqueConstraint("active_admission_key", name="uq_doctor_assignment_active_admission"),
    )
    op.create_index("ix_doctor_assignments_admission_id", "doctor_assignments", ["admission_id"], unique=False)
    op.create_index("ix_doctor_assignments_doctor_user_id", "doctor_assignments", ["doctor_user_id"], unique=False)
    op.create_index("ix_doctor_assignments_assigned_by", "doctor_assignments", ["assigned_by"], unique=False)
    op.create_index("ix_doctor_assignments_status", "doctor_assignments", ["status"], unique=False)
    op.create_index("ix_doctor_assignments_assigned_at", "doctor_assignments", ["assigned_at"], unique=False)
    op.create_index("ix_doctor_assignments_completed_at", "doctor_assignments", ["completed_at"], unique=False)


def downgrade():
    op.drop_table("doctor_assignments")
    op.drop_index("ix_admissions_approved_by", table_name="admissions")
    op.drop_index("ix_admissions_approved_at", table_name="admissions")
    op.drop_column("admissions", "approval_reason")
    op.drop_column("admissions", "approved_by")
    op.drop_column("admissions", "approved_at")
