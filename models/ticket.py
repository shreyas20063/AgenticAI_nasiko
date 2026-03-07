"""HR helpdesk ticket and message models."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship
from database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    requester_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assigned_to = Column(String(36), nullable=True)  # human HR agent if escalated
    category = Column(String(100), nullable=True)  # leave, benefits, payroll, policy, complaint, other
    subject = Column(String(255), nullable=False)
    status = Column(String(50), default="open")  # open, in_progress, waiting, escalated, resolved, closed
    priority = Column(String(20), default="medium")  # low, medium, high, urgent
    is_sensitive = Column(Boolean, default=False)  # flagged for human-only handling
    is_auto_resolved = Column(Boolean, default=False)

    # Resolution metadata
    resolution_summary = Column(Text, nullable=True)
    satisfaction_rating = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    messages = relationship("TicketMessage", back_populates="ticket", lazy="selectin",
                            order_by="TicketMessage.created_at")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=False, index=True)

    sender_type = Column(String(20), nullable=False)  # user, agent, system
    sender_id = Column(String(36), nullable=True)
    content = Column(Text, nullable=False)
    content_redacted = Column(Text, nullable=True)  # PII-redacted version for logs
    metadata_ = Column("metadata", JSON, default=dict)  # tool calls, sources, etc.

    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="messages")
