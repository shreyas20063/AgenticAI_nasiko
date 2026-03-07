"""
Interview API routes - scheduling, calendar view, feedback management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.user import User
from models.interview import ScheduledInterview, InterviewFeedback
from models.candidate import Candidate
from models.job import Job
from api.deps import require_permission
from security.rbac import Permission
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field
from typing import Optional
import uuid

router = APIRouter(prefix="/api/interviews", tags=["Interviews"])


class ScheduleInterviewRequest(BaseModel):
    candidate_id: str
    job_id: str
    scheduled_at: str = Field(..., description="ISO 8601 datetime")
    duration_minutes: int = 60
    interview_type: str = "video"
    interviewer_ids: list[str] = []
    interviewer_names: list[str] = []
    location: Optional[str] = None
    notes: Optional[str] = None


class SubmitFeedbackRequest(BaseModel):
    overall_rating: float = Field(..., ge=1, le=5)
    technical_score: Optional[float] = Field(None, ge=1, le=5)
    communication_score: Optional[float] = Field(None, ge=1, le=5)
    culture_fit_score: Optional[float] = Field(None, ge=1, le=5)
    problem_solving_score: Optional[float] = Field(None, ge=1, le=5)
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    notes: Optional[str] = None
    recommendation: str = Field(..., pattern="^(strong_hire|hire|no_hire|strong_no_hire)$")


@router.get("/")
async def list_interviews(
    status: str = Query(default=None, max_length=50),
    days_ahead: int = Query(default=30, le=365),
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """List upcoming interviews for the tenant."""
    query = select(ScheduledInterview).where(
        ScheduledInterview.tenant_id == user.tenant_id,
    )

    if status:
        query = query.where(ScheduledInterview.status == status)
    else:
        # Default: show future scheduled interviews
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        query = query.where(
            ScheduledInterview.scheduled_at >= now - timedelta(days=1),
            ScheduledInterview.scheduled_at <= cutoff,
        )

    query = query.order_by(ScheduledInterview.scheduled_at.asc())
    result = await db.execute(query)
    interviews = result.scalars().all()

    # Fetch candidate names
    cand_ids = list({i.candidate_id for i in interviews})
    cand_result = await db.execute(select(Candidate).where(Candidate.id.in_(cand_ids))) if cand_ids else None
    cand_map = {c.id: c for c in (cand_result.scalars().all() if cand_result else [])}

    # Fetch job titles
    job_ids = list({i.job_id for i in interviews if i.job_id})
    job_result = await db.execute(select(Job).where(Job.id.in_(job_ids))) if job_ids else None
    job_map = {j.id: j for j in (job_result.scalars().all() if job_result else [])}

    return [
        {
            "id": i.id,
            "candidate_id": i.candidate_id,
            "candidate_name": cand_map.get(i.candidate_id, Candidate(full_name="Unknown")).full_name,
            "job_id": i.job_id,
            "job_title": job_map.get(i.job_id, Job(title="Unknown")).title if i.job_id else None,
            "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
            "duration_minutes": i.duration_minutes,
            "interview_type": i.interview_type,
            "meeting_link": i.meeting_link,
            "location": i.location,
            "interviewer_names": i.interviewer_names or [],
            "status": i.status,
            "feedback_count": len(i.feedback) if i.feedback else 0,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in interviews
    ]


@router.get("/calendar")
async def get_interview_calendar(
    start_date: str = Query(default=None, description="ISO date (YYYY-MM-DD)"),
    end_date: str = Query(default=None, description="ISO date (YYYY-MM-DD)"),
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """Get interviews grouped by date for calendar view."""
    now = datetime.now(timezone.utc)

    if start_date:
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    else:
        start = now - timedelta(days=1)

    if end_date:
        end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
    else:
        end = now + timedelta(days=30)

    result = await db.execute(
        select(ScheduledInterview).where(
            ScheduledInterview.tenant_id == user.tenant_id,
            ScheduledInterview.scheduled_at >= start,
            ScheduledInterview.scheduled_at <= end,
        ).order_by(ScheduledInterview.scheduled_at.asc())
    )
    interviews = result.scalars().all()

    # Fetch candidate names
    cand_ids = list({i.candidate_id for i in interviews})
    cand_result = await db.execute(select(Candidate).where(Candidate.id.in_(cand_ids))) if cand_ids else None
    cand_map = {c.id: c for c in (cand_result.scalars().all() if cand_result else [])}

    # Group by date
    calendar = {}
    for i in interviews:
        date_key = i.scheduled_at.strftime("%Y-%m-%d") if i.scheduled_at else "unknown"
        if date_key not in calendar:
            calendar[date_key] = []
        cand = cand_map.get(i.candidate_id)
        calendar[date_key].append({
            "id": i.id,
            "candidate_name": cand.full_name if cand else "Unknown",
            "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
            "time": i.scheduled_at.strftime("%I:%M %p") if i.scheduled_at else None,
            "duration_minutes": i.duration_minutes,
            "interview_type": i.interview_type,
            "meeting_link": i.meeting_link,
            "status": i.status,
            "interviewer_names": i.interviewer_names or [],
        })

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_interviews": len(interviews),
        "calendar": calendar,
    }


@router.get("/upcoming")
async def get_upcoming_interviews(
    days: int = Query(default=7, le=90),
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """Get interview stats for the upcoming N days (for dashboard widget)."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)

    result = await db.execute(
        select(ScheduledInterview).where(
            ScheduledInterview.tenant_id == user.tenant_id,
            ScheduledInterview.status == "scheduled",
            ScheduledInterview.scheduled_at >= now,
            ScheduledInterview.scheduled_at <= cutoff,
        ).order_by(ScheduledInterview.scheduled_at.asc())
    )
    interviews = result.scalars().all()

    # Count by date
    today_count = sum(1 for i in interviews if i.scheduled_at and i.scheduled_at.date() == now.date())
    this_week = sum(1 for i in interviews if i.scheduled_at and i.scheduled_at <= now + timedelta(days=7))

    # Fetch candidate names for upcoming list
    cand_ids = list({i.candidate_id for i in interviews[:10]})
    cand_result = await db.execute(select(Candidate).where(Candidate.id.in_(cand_ids))) if cand_ids else None
    cand_map = {c.id: c for c in (cand_result.scalars().all() if cand_result else [])}

    return {
        "total_upcoming": len(interviews),
        "today": today_count,
        "this_week": this_week,
        "next_interviews": [
            {
                "id": i.id,
                "candidate_name": cand_map.get(i.candidate_id, Candidate(full_name="Unknown")).full_name,
                "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
                "interview_type": i.interview_type,
                "status": i.status,
            }
            for i in interviews[:5]
        ],
    }


@router.post("/", status_code=201)
async def schedule_interview(
    request: ScheduleInterviewRequest,
    user: User = Depends(require_permission(Permission.MANAGE_JOBS)),
    db: AsyncSession = Depends(get_db),
):
    """Schedule a new interview."""
    # Verify candidate exists
    cand_result = await db.execute(select(Candidate).where(
        Candidate.id == request.candidate_id,
        Candidate.tenant_id == user.tenant_id,
    ))
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    scheduled_time = datetime.fromisoformat(request.scheduled_at.replace("Z", "+00:00"))

    # Check for conflicts
    end_time = scheduled_time + timedelta(minutes=request.duration_minutes)
    conflict = await db.execute(
        select(ScheduledInterview).where(
            ScheduledInterview.tenant_id == user.tenant_id,
            ScheduledInterview.candidate_id == request.candidate_id,
            ScheduledInterview.status == "scheduled",
            ScheduledInterview.scheduled_at < end_time,
            ScheduledInterview.scheduled_at >= scheduled_time - timedelta(minutes=request.duration_minutes),
        )
    )
    if conflict.scalars().first():
        raise HTTPException(status_code=409, detail="Scheduling conflict for this candidate")

    meeting_link = f"https://meet.nasiko.ai/{uuid.uuid4().hex[:8]}"

    interview = ScheduledInterview(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        candidate_id=request.candidate_id,
        job_id=request.job_id,
        scheduled_at=scheduled_time,
        duration_minutes=request.duration_minutes,
        interview_type=request.interview_type,
        meeting_link=meeting_link,
        location=request.location,
        interviewer_ids=request.interviewer_ids,
        interviewer_names=request.interviewer_names,
        created_by=user.id,
        notes=request.notes,
    )
    db.add(interview)

    # Update candidate status if appropriate
    if candidate.status in ("new", "screened", "shortlisted"):
        candidate.status = "interview"

    await db.flush()

    return {
        "id": interview.id,
        "candidate_name": candidate.full_name,
        "scheduled_at": scheduled_time.isoformat(),
        "meeting_link": meeting_link,
        "status": "scheduled",
        "message": f"Interview scheduled for {candidate.full_name}",
    }


@router.patch("/{interview_id}")
async def update_interview(
    interview_id: str,
    status: str = Query(default=None, max_length=50),
    scheduled_at: str = Query(default=None),
    user: User = Depends(require_permission(Permission.MANAGE_JOBS)),
    db: AsyncSession = Depends(get_db),
):
    """Update an interview (reschedule, cancel, mark completed)."""
    result = await db.execute(select(ScheduledInterview).where(
        ScheduledInterview.id == interview_id,
        ScheduledInterview.tenant_id == user.tenant_id,
    ))
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if status:
        interview.status = status
    if scheduled_at:
        interview.scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        interview.status = "rescheduled"

    return {"id": interview.id, "status": interview.status, "message": "Interview updated"}


@router.delete("/{interview_id}")
async def cancel_interview(
    interview_id: str,
    reason: str = Query(default="", max_length=500),
    user: User = Depends(require_permission(Permission.MANAGE_JOBS)),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an interview."""
    result = await db.execute(select(ScheduledInterview).where(
        ScheduledInterview.id == interview_id,
        ScheduledInterview.tenant_id == user.tenant_id,
    ))
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    interview.status = "cancelled"
    interview.cancellation_reason = reason
    return {"id": interview.id, "status": "cancelled", "message": "Interview cancelled"}


@router.post("/{interview_id}/feedback", status_code=201)
async def submit_feedback(
    interview_id: str,
    request: SubmitFeedbackRequest,
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """Submit interview feedback."""
    # Verify interview exists
    int_result = await db.execute(select(ScheduledInterview).where(
        ScheduledInterview.id == interview_id,
        ScheduledInterview.tenant_id == user.tenant_id,
    ))
    interview = int_result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    feedback = InterviewFeedback(
        id=str(uuid.uuid4()),
        interview_id=interview_id,
        interviewer_id=user.id,
        interviewer_name=user.full_name,
        overall_rating=request.overall_rating,
        technical_score=request.technical_score,
        communication_score=request.communication_score,
        culture_fit_score=request.culture_fit_score,
        problem_solving_score=request.problem_solving_score,
        strengths=request.strengths,
        weaknesses=request.weaknesses,
        notes=request.notes,
        recommendation=request.recommendation,
    )
    db.add(feedback)

    # Mark interview as completed
    interview.status = "completed"

    await db.flush()
    return {
        "id": feedback.id,
        "interview_id": interview_id,
        "recommendation": request.recommendation,
        "message": "Feedback submitted successfully",
    }


@router.get("/{interview_id}/feedback")
async def get_feedback(
    interview_id: str,
    user: User = Depends(require_permission(Permission.VIEW_CANDIDATES)),
    db: AsyncSession = Depends(get_db),
):
    """Get all feedback for an interview."""
    result = await db.execute(
        select(InterviewFeedback).where(InterviewFeedback.interview_id == interview_id)
    )
    feedback_list = result.scalars().all()

    return [
        {
            "id": f.id,
            "interviewer_name": f.interviewer_name,
            "overall_rating": f.overall_rating,
            "technical_score": f.technical_score,
            "communication_score": f.communication_score,
            "culture_fit_score": f.culture_fit_score,
            "problem_solving_score": f.problem_solving_score,
            "strengths": f.strengths,
            "weaknesses": f.weaknesses,
            "recommendation": f.recommendation,
            "notes": f.notes,
            "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
        }
        for f in feedback_list
    ]
