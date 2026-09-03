"""ProjectX v3.1 self-service security token version

Revision ID: b16aug2026auth01
Revises: a14b2026hr01
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "b16aug2026auth01"
down_revision = "a14b2026hr01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute("UPDATE users SET auth_version = 1 WHERE auth_version IS NULL OR auth_version < 1")
    # Leaving the server default in place is intentional: every future account starts at version 1.


def downgrade() -> None:
    op.drop_column("users", "auth_version")
