"""track stock alert notification dispatches

Revision ID: pharmacie_0002
Revises: pharmacie_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "pharmacie_0002"
down_revision = "pharmacie_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_alert_dispatches",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("alert_type", sa.String(40), nullable=False),
        sa.Column("medicine_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=True),
        sa.Column("dispatched_on", sa.Date(), nullable=False),
        sa.Column("recipient_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", "dispatched_on", name="uq_stock_alert_dispatch_day"),
    )
    for col in ("fingerprint", "alert_type", "medicine_id", "batch_id", "dispatched_on"):
        op.create_index(f"ix_stock_alert_dispatches_{col}", "stock_alert_dispatches", [col], unique=False)


def downgrade() -> None:
    op.drop_table("stock_alert_dispatches")
