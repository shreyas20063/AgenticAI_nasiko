"""GDPR-style consent and data subject rights tracking."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text
from database import Base


class ConsentRecord(Base):
    """Tracks consent status for candidates and employees (GDPR Art. 6/7)."""
    __tablename__ = "consent_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)

    # Subject
    subject_type = Column(String(50), nullable=False)  # candidate, employee
    subject_id = Column(String(36), nullable=False, index=True)
    subject_email = Column(String(255), nullable=True)

    # Consent details
    purpose = Column(String(100), nullable=False)  # recruitment_processing, data_retention, marketing
    lawful_basis = Column(String(100), nullable=True)  # consent, legitimate_interest, contract
    is_granted = Column(Boolean, default=False)
    granted_at = Column(DateTime, nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)

    # Data subject requests
    access_requested = Column(Boolean, default=False)
    access_request_date = Column(DateTime, nullable=True)
    access_fulfilled_date = Column(DateTime, nullable=True)

    deletion_requested = Column(Boolean, default=False)
    deletion_request_date = Column(DateTime, nullable=True)
    deletion_fulfilled_date = Column(DateTime, nullable=True)

    # Retention
    retention_until = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
