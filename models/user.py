"""User and role models with RBAC support."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Role(str, PyEnum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    RECRUITER = "recruiter"
    HRBP = "hrbp"
    HR_ADMIN = "hr_admin"
    SECURITY_ADMIN = "security_admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(Role), nullable=False, default=Role.EMPLOYEE)
    department = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="users")
