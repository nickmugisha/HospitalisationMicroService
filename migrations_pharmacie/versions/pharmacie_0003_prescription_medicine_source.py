"""formalize hospital-catalog versus external prescription medicines in pharmacy inbox

Revision ID: pharmacie_0003
Revises: pharmacie_0002
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "pharmacie_0003"
down_revision = "pharmacie_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prescription_inbox_items", sa.Column("medicine_source", sa.String(length=24), nullable=False, server_default="HOSPITAL_CATALOG"))
    op.add_column("prescription_inbox_items", sa.Column("medicine_name", sa.String(length=200), nullable=False, server_default=""))
    op.add_column("prescription_inbox_items", sa.Column("medicine_form", sa.String(length=120), nullable=True))
    op.add_column("prescription_inbox_items", sa.Column("medicine_strength", sa.String(length=120), nullable=True))
    op.create_index("ix_prescription_inbox_items_medicine_source", "prescription_inbox_items", ["medicine_source"], unique=False)
    op.execute("UPDATE prescription_inbox_items SET medicine_source='HOSPITAL_CATALOG', medicine_name=medicine_ref WHERE medicine_name='' OR medicine_name IS NULL")


def downgrade() -> None:
    op.drop_index("ix_prescription_inbox_items_medicine_source", table_name="prescription_inbox_items")
    op.drop_column("prescription_inbox_items", "medicine_strength")
    op.drop_column("prescription_inbox_items", "medicine_form")
    op.drop_column("prescription_inbox_items", "medicine_name")
    op.drop_column("prescription_inbox_items", "medicine_source")
