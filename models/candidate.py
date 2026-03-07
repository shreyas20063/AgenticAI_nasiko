"""Candidate models for recruitment pipeline."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, JSON, Text, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship
from database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True, index=True)

    # PII fields - subject to redaction in blind mode
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)

    # Structured resume data
    resume_text = Column(Text, nullable=True)
    parsed_resume = Column(JSON, nullable=True)  # structured extraction
    years_experience = Column(Float, nullable=True)
    education_level = Column(String(100), nullable=True)
    current_company = Column(String(255), nullable=True)
    current_title = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    expected_salary = Column(String(100), nullable=True)

    # Screening results
    screening_score = Column(Float, nullable=True)
    screening_explanation = Column(Text, nullable=True)
    status = Column(String(50), default="new")  # new, screened, shortlisted, interview, offered, rejected, hired
    is_blind_screened = Column(Boolean, default=False)

    # Consent
    consent_given = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    skills = relationship("CandidateSkill", back_populates="candidate", lazy="selectin")
    job = relationship("Job", back_populates="candidates")


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    skill_name = Column(String(100), nullable=False)
    proficiency = Column(String(50), nullable=True)  # beginner, intermediate, advanced, expert
    years = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="skills")
