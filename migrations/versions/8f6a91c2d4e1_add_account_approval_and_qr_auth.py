"""add account approval and qr auth

Revision ID: 8f6a91c2d4e1
Revises: 27cfa472222c
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8f6a91c2d4e1"
down_revision: Union[str, Sequence[str], None] = "27cfa472222c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.add_column("users", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("approved_by_id", sa.String(length=36), nullable=True))
    op.create_index("ix_users_approval_status", "users", ["approval_status"], unique=False)

    # Preserve the behavior of all users created before this feature.
    op.execute(
        "UPDATE users SET approval_status = CASE WHEN active = 1 THEN 'ACTIVE' ELSE 'DISABLED' END"
    )

    op.create_table(
        "qr_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("issued_by_id", sa.String(length=36), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qr_credentials_user_id", "qr_credentials", ["user_id"], unique=False)
    op.create_index("ix_qr_credentials_token_hash", "qr_credentials", ["token_hash"], unique=True)
    op.create_index("ix_qr_credentials_active", "qr_credentials", ["active"], unique=False)

    op.alter_column("users", "approval_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_qr_credentials_active", table_name="qr_credentials")
    op.drop_index("ix_qr_credentials_token_hash", table_name="qr_credentials")
    op.drop_index("ix_qr_credentials_user_id", table_name="qr_credentials")
    op.drop_table("qr_credentials")

    op.drop_index("ix_users_approval_status", table_name="users")
    op.drop_column("users", "approved_by_id")
    op.drop_column("users", "approved_at")
    op.drop_column("users", "approval_status")
