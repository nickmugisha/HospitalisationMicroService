"""add staff HR workflow and QR expiration

Revision ID: a14b2026hr01
Revises: 8f6a91c2d4e1
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a14b2026hr01"
down_revision: Union[str, Sequence[str], None] = "8f6a91c2d4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize the old public-registration wording to the HR workflow wording.
    op.execute(
        "UPDATE users SET approval_status = 'PENDING_APPROVAL' "
        "WHERE approval_status = 'PENDING'"
    )

    op.create_table(
        "staff_profiles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("employee_number", sa.String(length=50), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=False),
        sa.Column("registered_by_id", sa.String(length=36), nullable=True),
        sa.Column("registered_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("employee_number", name="uq_staff_profiles_employee_number"),
        sa.UniqueConstraint("email", name="uq_staff_profiles_email"),
    )
    op.create_index("ix_staff_profiles_registered_by_id", "staff_profiles", ["registered_by_id"], unique=False)

    op.add_column("qr_credentials", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.create_index("ix_qr_credentials_expires_at", "qr_credentials", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_qr_credentials_expires_at", table_name="qr_credentials")
    op.drop_column("qr_credentials", "expires_at")

    op.drop_index("ix_staff_profiles_registered_by_id", table_name="staff_profiles")
    op.drop_table("staff_profiles")

    op.execute(
        "UPDATE users SET approval_status = 'PENDING' "
        "WHERE approval_status = 'PENDING_APPROVAL'"
    )
