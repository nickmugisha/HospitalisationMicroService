from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.chatbot_base import ChatbotBase

def uid(): return str(uuid.uuid4())
def utc_now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class ChatSession(ChatbotBase):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    client_request_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now, onupdate=utc_now)
    messages: Mapped[list['ChatMessage']] = relationship(back_populates='session', cascade='all, delete-orphan')
    tool_calls: Mapped[list['ToolCall']] = relationship(back_populates='session', cascade='all, delete-orphan')

class ChatMessage(ChatbotBase):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    session: Mapped[ChatSession] = relationship(back_populates='messages')

class ToolCall(ChatbotBase):
    __tablename__ = "tool_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('chat_messages.id', ondelete='SET NULL'), nullable=True)
    service: Mapped[str] = mapped_column(String(80), nullable=False)
    rpc: Mapped[str] = mapped_column(String(120), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now)
    session: Mapped[ChatSession] = relationship(back_populates='tool_calls')
