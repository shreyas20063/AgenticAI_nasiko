"""Conversation memory for multi-turn chat support."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Index
from database import Base


class ConversationMessage(Base):
    """Stores individual messages in a conversation for context retrieval."""
    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    agent_used = Column(String(100), nullable=True)
    intent_detected = Column(String(50), nullable=True)
    turn_number = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_conv_tenant_convo", "tenant_id", "conversation_id"),
    )
