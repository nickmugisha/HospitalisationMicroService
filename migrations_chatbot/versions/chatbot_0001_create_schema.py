"""create chatbot schema
Revision ID: chatbot_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision='chatbot_0001'; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('chat_sessions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),nullable=False),
        sa.Column('client_request_id',sa.String(100),nullable=True),
        sa.Column('started_at',sa.DateTime(),nullable=False),
        sa.Column('updated_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('client_request_id',name='uq_chat_sessions_client_request_id'))
    op.create_index('ix_chat_sessions_user_id','chat_sessions',['user_id'])
    op.create_table('chat_messages',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('session_id',sa.String(36),sa.ForeignKey('chat_sessions.id',ondelete='CASCADE'),nullable=False),
        sa.Column('role',sa.String(20),nullable=False),
        sa.Column('content',sa.Text(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_chat_messages_session_id','chat_messages',['session_id'])
    op.create_table('tool_calls',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('session_id',sa.String(36),sa.ForeignKey('chat_sessions.id',ondelete='CASCADE'),nullable=False),
        sa.Column('message_id',sa.String(36),sa.ForeignKey('chat_messages.id',ondelete='SET NULL'),nullable=True),
        sa.Column('service',sa.String(80),nullable=False),
        sa.Column('rpc',sa.String(120),nullable=False),
        sa.Column('correlation_id',sa.String(80),nullable=False),
        sa.Column('outcome',sa.String(40),nullable=False),
        sa.Column('detail',sa.Text(),nullable=True),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_tool_calls_session_id','tool_calls',['session_id'])
    op.create_index('ix_tool_calls_correlation_id','tool_calls',['correlation_id'])

def downgrade():
    op.drop_table('tool_calls'); op.drop_table('chat_messages'); op.drop_table('chat_sessions')
