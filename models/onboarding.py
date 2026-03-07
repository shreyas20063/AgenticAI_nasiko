"""Onboarding plan and task tracking models."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship
from database import Base


class OnboardingPlan(Base):
    __tablename__ = "onboarding_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)

    template_name = Column(String(100), nullable=True)  # e.g., "engineering_onboarding"
    status = Column(String(50), default="active")  # active, completed, paused
    progress_pct = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    target_completion = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    tasks = relationship("OnboardingTask", back_populates="plan", lazy="selectin")


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String(36), ForeignKey("onboarding_plans.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # documentation, training, setup, meeting
    assigned_to = Column(String(36), nullable=True)  # user_id of who must complete it
    due_day = Column(Integer, nullable=True)  # day N of onboarding (e.g., day 1, day 3)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(String(36), nullable=True)
    notes = Column(Text, nullable=True)
    order = Column(Integer, default=0)

    plan = relationship("OnboardingPlan", back_populates="tasks")
