"""create BI schema
Revision ID: bi_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision='bi_0001'; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('metric_snapshots',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('metric_code',sa.String(100),nullable=False),
        sa.Column('period_start',sa.String(10),nullable=True),
        sa.Column('period_end',sa.String(10),nullable=True),
        sa.Column('value',sa.BigInteger(),nullable=False),
        sa.Column('dimensions',sa.Text(),nullable=True),
        sa.Column('source_service',sa.String(80),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    for c in ['metric_code','period_start','period_end','source_service','created_at']: op.create_index(f'ix_metric_snapshots_{c}','metric_snapshots',[c])
    op.create_table('report_runs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('requested_by',sa.String(36),nullable=False),
        sa.Column('date_from',sa.String(10),nullable=True),
        sa.Column('date_to',sa.String(10),nullable=True),
        sa.Column('service_filter',sa.String(80),nullable=True),
        sa.Column('quality',sa.String(30),nullable=False),
        sa.Column('warnings',sa.Text(),nullable=True),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    for c in ['requested_by','quality','created_at']: op.create_index(f'ix_report_runs_{c}','report_runs',[c])
def downgrade():
    op.drop_table('report_runs'); op.drop_table('metric_snapshots')
