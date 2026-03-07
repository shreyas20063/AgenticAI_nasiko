"""Append-only audit log for compliance. Immutable by design."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Text
from database import Base


class AuditLog(Base):
    """
    Immutable audit trail. Every agent action, data access,
    and decision is logged here for compliance and investigation.

    Pattern: append-only. No UPDATE or DELETE operations should
    ever target this table in application code.
    """
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)

    # Who
    user_id = Column(String(36), nullable=True, index=True)
    user_role = Column(String(50), nullable=True)
    agent_name = Column(String(100), nullable=True)

    # What
    action = Column(String(100), nullable=False, index=True)  # e.g., "candidate.screen", "ticket.resolve"
    resource_type = Column(String(100), nullable=True)  # e.g., "candidate", "ticket", "policy"
    resource_id = Column(String(36), nullable=True, index=True)

    # Details
    input_summary = Column(Text, nullable=True)  # redacted summary of input
    output_summary = Column(Text, nullable=True)  # redacted summary of output/decision
    tools_used = Column(JSON, default=list)  # list of tools invoked
    metadata_ = Column("metadata", JSON, default=dict)  # extra context

    # Outcome
    status = Column(String(50), default="success")  # success, failure, denied, escalated
    risk_level = Column(String(20), nullable=True)  # low, medium, high

    # Timestamp (immutable)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
