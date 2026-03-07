"""Candidate and recruitment schemas."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class CandidateCreate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    job_id: Optional[str] = None
    resume_text: Optional[str] = None
    location: Optional[str] = None
    expected_salary: Optional[str] = None
    consent_given: bool = False


class CandidateResponse(BaseModel):
    id: str
    full_name: str
    email: str
    status: str
    screening_score: Optional[float]
    screening_explanation: Optional[str]
    years_experience: Optional[float]
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    education_level: Optional[str] = None
    location: Optional[str] = None
    skills: list[dict] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateBlindResponse(BaseModel):
    """Redacted view for blind screening - no PII."""
    id: str
    status: str
    screening_score: Optional[float]
    screening_explanation: Optional[str]
    years_experience: Optional[float]
    education_level: Optional[str]
    skills: list[dict] = []


class ScreeningResult(BaseModel):
    candidate_id: str
    score: float = Field(..., ge=0.0, le=100.0)
    explanation: str
    criteria_matches: list[dict] = []
    recommendation: str  # strong_yes, yes, maybe, no, strong_no


class JobCreate(BaseModel):
    title: str
    department: Optional[str] = None
    description: str
    location: Optional[str] = None
    employment_type: str = "full_time"
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    required_skills: list[dict] = []
    preferred_skills: list[dict] = []
    min_experience_years: Optional[float] = None
    education_requirement: Optional[str] = None
    blind_screening: bool = False


class JobResponse(BaseModel):
    id: str
    title: str
    department: Optional[str]
    description: str
    location: Optional[str]
    status: str
    candidate_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
