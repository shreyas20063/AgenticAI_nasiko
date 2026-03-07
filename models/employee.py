"""Employee model for onboarding and helpdesk."""

import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, JSON, ForeignKey, Boolean
from database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    employee_id_number = Column(String(50), nullable=True)  # internal HR ID
    department = Column(String(100), nullable=True)
    title = Column(String(255), nullable=True)
    manager_id = Column(String(36), nullable=True)
    location = Column(String(255), nullable=True)
    start_date = Column(Date, nullable=True)

    # Leave and benefits (simplified)
    leave_balance = Column(JSON, default=lambda: {"annual": 20, "sick": 10, "personal": 5})
    benefits_enrolled = Column(JSON, default=list)

    status = Column(String(50), default="active")  # active, onboarding, offboarding, terminated
    onboarding_complete = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
