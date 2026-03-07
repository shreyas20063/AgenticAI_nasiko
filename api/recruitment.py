"""
Recruitment API routes - job and candidate management, pipeline progression.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.user import User, Role
from models.job import Job
from models.candidate import Candidate, CandidateSkill
from models.interview import ScheduledInterview
from schemas.candidate import (
    CandidateCreate, CandidateResponse, CandidateBlindResponse,
    JobCreate, JobResponse
)
from api.deps import require_permission
from security.rbac import Permission
from security.tenant_isolation import TenantContext
from pydantic import BaseModel, Field
from typing import Optional
import uuid

router = APIRouter(prefix="/api/recruitment", tags=["Recruitment"])


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(
    request: JobCreate,
    user: User = Depends(require_permission(Permission.MANAGE_JOBS)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new job posting."""
    job = Job(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        title=request.title,
        department=request.department,
        description=request.description,
        location=request.location,
        employment_type=request.employment_type,
        salary_min=request.salary_min,
        salary_max=request.salary_max,
        required_skills=request.required_skills,
        preferred_skills=request.preferred_skills,
        min_experience_years=request.min_experience_years,
        education_requirement=request.education_requirement,
        blind_screening=request.blind_screening,
        created_by=user.id,
    )
    db.add(job)
    await db.flush()

    return JobResponse(
        id=job.id,
        title=job.title,
        department=job.department,
        description=job.description,
        location=job.location,
        status=job.status,
        created_at=job.created_at,
    )


@router.get("/jobs")
async def list_jobs(
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """List all job postings for the tenant."""
    result = await db.execute(
        select(Job).where(Job.tenant_id == user.tenant_id).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    return [
        JobResponse(
            id=j.id, title=j.title, department=j.department,
            description=j.description, location=j.location,
            status=j.status, candidate_count=len(j.candidates),
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.post("/candidates", status_code=201)
async def add_candidate(
    request: CandidateCreate,
    user: User = Depends(require_permission(Permission.MANAGE_JOBS)),
    db: AsyncSession = Depends(get_db),
):
    """Add a new candidate to the pipeline."""
    candidate = Candidate(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        job_id=request.job_id,
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
        resume_text=request.resume_text,
        location=request.location,
        expected_salary=request.expected_salary,
        consent_given=request.consent_given,
    )
    db.add(candidate)
    await db.flush()

    return {"id": candidate.id, "status": "created"}


@router.get("/candidates/{job_id}")
async def list_candidates(
    job_id: str,
    blind: bool = False,
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """List candidates for a job. Supports blind mode."""
    result = await db.execute(
        select(Candidate).where(
            Candidate.tenant_id == user.tenant_id,
            Candidate.job_id == job_id,
        ).order_by(Candidate.screening_score.desc())
    )
    candidates = result.scalars().all()

    if blind:
        return [
            CandidateBlindResponse(
                id=c.id,
                status=c.status,
                screening_score=c.screening_score,
                screening_explanation=c.screening_explanation,
                years_experience=c.years_experience,
                education_level=c.education_level,
                skills=[{"name": s.skill_name, "proficiency": s.proficiency} for s in c.skills],
            )
            for c in candidates
        ]

    return [
        CandidateResponse(
            id=c.id,
            full_name=c.full_name,
            email=c.email,
            status=c.status,
            screening_score=c.screening_score,
            screening_explanation=c.screening_explanation,
            years_experience=c.years_experience,
            current_title=c.current_title,
            current_company=c.current_company,
            education_level=c.education_level,
            location=c.location,
            skills=[{"name": s.skill_name, "proficiency": s.proficiency} for s in c.skills],
            created_at=c.created_at,
        )
        for c in candidates
    ]


class UpdateJobRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    status: Optional[str] = Field(default=None, pattern="^(open|closed|paused)$")


class UpdateStatusRequest(BaseModel):
    new_status: str = Field(..., pattern="^(screened|shortlisted|interview|offered|hired|rejected)$")
    reason: Optional[str] = None


VALID_TRANSITIONS = {
    "new": ["screened", "rejected"],
    "screened": ["shortlisted", "rejected"],
    "shortlisted": ["interview", "rejected"],
    "interview": ["offered", "rejected"],
    "offered": ["hired", "rejected"],
}


@router.get("/candidate/{candidate_id}")
async def get_candidate_detail(
    candidate_id: str,
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """Get full candidate detail including interviews and feedback."""
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.tenant_id == user.tenant_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Get interviews
    int_result = await db.execute(
        select(ScheduledInterview).where(
            ScheduledInterview.candidate_id == candidate_id,
        ).order_by(ScheduledInterview.scheduled_at.desc())
    )
    interviews = int_result.scalars().all()

    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "email": candidate.email,
        "phone": candidate.phone,
        "current_title": candidate.current_title,
        "current_company": candidate.current_company,
        "education_level": candidate.education_level,
        "location": candidate.location,
        "years_experience": candidate.years_experience,
        "expected_salary": candidate.expected_salary,
        "status": candidate.status,
        "screening_score": candidate.screening_score,
        "screening_explanation": candidate.screening_explanation,
        "resume_text": candidate.resume_text,
        "skills": [{"name": s.skill_name, "proficiency": s.proficiency, "years": s.years} for s in candidate.skills],
        "interviews": [
            {
                "id": i.id,
                "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
                "interview_type": i.interview_type,
                "status": i.status,
                "meeting_link": i.meeting_link,
                "interviewer_names": i.interviewer_names or [],
                "feedback": [
                    {
                        "interviewer_name": f.interviewer_name,
                        "overall_rating": f.overall_rating,
                        "recommendation": f.recommendation,
                        "strengths": f.strengths,
                        "weaknesses": f.weaknesses,
                    }
                    for f in (i.feedback or [])
                ],
            }
            for i in interviews
        ],
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }


@router.patch("/candidate/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: str,
    request: UpdateStatusRequest,
    user: User = Depends(require_permission(Permission.MANAGE_JOBS)),
    db: AsyncSession = Depends(get_db),
):
    """Advance a candidate through the pipeline."""
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.tenant_id == user.tenant_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    allowed = VALID_TRANSITIONS.get(candidate.status, [])
    if request.new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move from '{candidate.status}' to '{request.new_status}'. Allowed: {allowed}",
        )

    old_status = candidate.status
    candidate.status = request.new_status

    return {
        "id": candidate.id,
        "name": candidate.full_name,
        "old_status": old_status,
        "new_status": request.new_status,
        "message": f"{candidate.full_name} moved to '{request.new_status}'",
    }


@router.get("/pipeline/{job_id}")
async def get_pipeline(
    job_id: str,
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """Get candidates grouped by pipeline stage (for kanban board)."""
    result = await db.execute(
        select(Candidate).where(
            Candidate.tenant_id == user.tenant_id,
            Candidate.job_id == job_id,
        )
    )
    candidates = result.scalars().all()

    pipeline = {
        "new": [], "screened": [], "shortlisted": [],
        "interview": [], "offered": [], "hired": [], "rejected": [],
    }

    for c in candidates:
        stage = c.status if c.status in pipeline else "new"
        pipeline[stage].append({
            "id": c.id,
            "full_name": c.full_name,
            "current_title": c.current_title,
            "screening_score": c.screening_score,
            "years_experience": c.years_experience,
            "skills": [{"name": s.skill_name, "proficiency": s.proficiency} for s in (c.skills or [])[:3]],
        })

    return {
        "job_id": job_id,
        "pipeline": pipeline,
        "counts": {stage: len(candidates) for stage, candidates in pipeline.items()},
    }


@router.patch("/jobs/{job_id}")
async def update_job(
    job_id: str,
    request: UpdateJobRequest,
    user: User = Depends(require_permission(Permission.MANAGE_JOBS)),
    db: AsyncSession = Depends(get_db),
):
    """Update a job posting."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == user.tenant_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if request.title is not None:
        job.title = request.title
    if request.description is not None:
        job.description = request.description
    if request.location is not None:
        job.location = request.location
    if request.salary_min is not None:
        job.salary_min = request.salary_min
    if request.salary_max is not None:
        job.salary_max = request.salary_max
    if request.status is not None:
        job.status = request.status

    await db.flush()
    return {"id": job.id, "message": f"Job '{job.title}' updated successfully"}


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    user: User = Depends(require_permission(Permission.MANAGE_JOBS)),
    db: AsyncSession = Depends(get_db),
):
    """Archive/close a job posting."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == user.tenant_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "closed"
    await db.flush()
    return {"id": job.id, "message": f"Job '{job.title}' has been closed"}
