"""Job posting and requirement models."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, JSON, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    department = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    location = Column(String(255), nullable=True)
    employment_type = Column(String(50), default="full_time")  # full_time, part_time, contract
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    status = Column(String(50), default="open")  # draft, open, closed, on_hold

    # Structured requirements for screening
    required_skills = Column(JSON, default=list)  # [{"skill": "Python", "min_years": 2}]
    preferred_skills = Column(JSON, default=list)
    min_experience_years = Column(Float, nullable=True)
    education_requirement = Column(String(100), nullable=True)

    # Blind screening config
    blind_screening = Column(Boolean, default=False)

    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidates = relationship("Candidate", back_populates="job", lazy="selectin")
    requirements = relationship("JobRequirement", back_populates="job", lazy="selectin")


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False)  # skill, experience, education, certification
    requirement = Column(String(255), nullable=False)
    is_mandatory = Column(Boolean, default=True)
    weight = Column(Float, default=1.0)  # scoring weight

    job = relationship("Job", back_populates="requirements")
