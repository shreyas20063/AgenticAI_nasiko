"""Policy documents for RAG-based helpdesk answers."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from database import Base


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)  # leave, benefits, conduct, compliance, general
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

    # Metadata for vector store indexing
    chunk_count = Column(Integer, default=0)
    last_indexed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
