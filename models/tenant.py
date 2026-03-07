"""Multi-tenant models. Every entity references tenant_id for isolation."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="tenant", lazy="selectin")
    config = relationship("TenantConfig", back_populates="tenant", uselist=False, lazy="selectin")


class TenantConfig(Base):
    """Per-tenant configuration for workflows, retention, compliance."""
    __tablename__ = "tenant_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, unique=True)

    # Feature toggles
    recruitment_enabled = Column(Boolean, default=True)
    onboarding_enabled = Column(Boolean, default=True)
    helpdesk_enabled = Column(Boolean, default=True)
    compliance_enabled = Column(Boolean, default=True)

    # Compliance settings
    # NOTE: Stored as String for backward compatibility; use retention_days property for int access
    data_retention_days = Column(String(10), default="365")
    gdpr_strict_mode = Column(Boolean, default=False)
    blind_screening_enabled = Column(Boolean, default=True)
    bias_monitoring_enabled = Column(Boolean, default=True)

    # Allowed tools per tenant (JSON list of tool names)
    allowed_tools = Column(JSON, default=list)

    # Custom policies or overrides
    custom_config = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="config",
                          foreign_keys=[tenant_id],
                          primaryjoin="TenantConfig.tenant_id == Tenant.id")

    @property
    def retention_days(self) -> int:
        """Get data_retention_days as integer."""
        try:
            return int(self.data_retention_days)
        except (ValueError, TypeError):
            return 365
