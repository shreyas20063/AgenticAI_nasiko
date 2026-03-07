"""Interview and feedback models for recruitment pipeline."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, Integer, JSON, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base


class ScheduledInterview(Base):
    __tablename__ = "scheduled_interviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)

    # Scheduling details
    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)
    interview_type = Column(String(50), default="video")  # phone, video, onsite
    meeting_link = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)

    # Participants
    interviewer_ids = Column(JSON, default=list)  # list of user IDs
    interviewer_names = Column(JSON, default=list)  # display names for convenience
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Status tracking
    status = Column(String(50), default="scheduled")  # scheduled, completed, cancelled, no_show, rescheduled
    cancellation_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    candidate = relationship("Candidate", backref="interviews")
    job = relationship("Job", backref="interviews")
    feedback = relationship("InterviewFeedback", back_populates="interview", lazy="selectin")


class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String(36), ForeignKey("scheduled_interviews.id"), nullable=False, index=True)
    interviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    interviewer_name = Column(String(255), nullable=True)

    # Scoring (1-5 scale)
    overall_rating = Column(Float, nullable=True)
    technical_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    culture_fit_score = Column(Float, nullable=True)
    problem_solving_score = Column(Float, nullable=True)

    # Qualitative feedback
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Decision
    recommendation = Column(String(50), nullable=True)  # strong_hire, hire, no_hire, strong_no_hire

    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    interview = relationship("ScheduledInterview", back_populates="feedback")
