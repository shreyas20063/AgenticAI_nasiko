"""Onboarding API routes - plan listing, task CRUD, and statistics."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.user import User
from models.onboarding import OnboardingPlan, OnboardingTask
from models.employee import Employee
from api.deps import require_permission, get_current_user
from security.rbac import Permission
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.get("/plans")
async def list_plans(
    status: str = Query(default=None, max_length=50),
    limit: int = Query(default=50, le=200),
    user: User = Depends(require_permission(Permission.VIEW_ONBOARDING)),
    db: AsyncSession = Depends(get_db),
):
    """List onboarding plans with tasks for the tenant."""
    query = select(OnboardingPlan).where(OnboardingPlan.tenant_id == user.tenant_id)

    if status:
        query = query.where(OnboardingPlan.status == status)

    query = query.order_by(OnboardingPlan.started_at.desc()).limit(limit)
    result = await db.execute(query)
    plans = result.scalars().all()

    # Get employee details
    emp_ids = [p.employee_id for p in plans]
    emp_result = await db.execute(select(Employee).where(Employee.id.in_(emp_ids)))
    emp_map = {e.id: e for e in emp_result.scalars().all()}

    output = []
    for p in plans:
        emp = emp_map.get(p.employee_id)
        sorted_tasks = sorted(p.tasks, key=lambda t: t.order)
        output.append({
            "id": p.id,
            "employee_name": emp.full_name if emp else "Unknown",
            "employee_email": emp.email if emp else "",
            "department": emp.department if emp else "",
            "template_name": p.template_name,
            "status": p.status,
            "progress_pct": p.progress_pct,
            "started_at": p.started_at.isoformat() if p.started_at else None,
            "target_completion": p.target_completion.isoformat() if p.target_completion else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            "tasks": [{
                "id": t.id,
                "title": t.title,
                "category": t.category,
                "due_day": t.due_day,
                "is_completed": t.is_completed,
                "order": t.order,
            } for t in sorted_tasks],
        })

    return output


@router.get("/stats")
async def onboarding_stats(
    user: User = Depends(require_permission(Permission.VIEW_ONBOARDING)),
    db: AsyncSession = Depends(get_db),
):
    """Get onboarding statistics for the tenant using efficient SQL aggregation."""
    tenant_where = OnboardingPlan.tenant_id == user.tenant_id

    total_r = await db.execute(select(func.count(OnboardingPlan.id)).where(tenant_where))
    active_r = await db.execute(select(func.count(OnboardingPlan.id)).where(tenant_where, OnboardingPlan.status == "active"))
    completed_r = await db.execute(select(func.count(OnboardingPlan.id)).where(tenant_where, OnboardingPlan.status == "completed"))
    paused_r = await db.execute(select(func.count(OnboardingPlan.id)).where(tenant_where, OnboardingPlan.status == "paused"))

    # Average progress of active plans (use SQL AVG for efficiency)
    avg_r = await db.execute(
        select(func.avg(OnboardingPlan.progress_pct)).where(tenant_where, OnboardingPlan.status == "active")
    )

    return {
        "total_plans": total_r.scalar() or 0,
        "active": active_r.scalar() or 0,
        "completed": completed_r.scalar() or 0,
        "paused": paused_r.scalar() or 0,
        "avg_progress": round(avg_r.scalar() or 0),
    }


# ============================================================
# Task Management Endpoints
# ============================================================

class TaskStatusUpdate(BaseModel):
    is_completed: bool


class TaskAssignUpdate(BaseModel):
    assigned_to: str


@router.get("/plans/{plan_id}")
async def get_plan_detail(
    plan_id: str,
    user: User = Depends(require_permission(Permission.VIEW_ONBOARDING)),
    db: AsyncSession = Depends(get_db),
):
    """Get full onboarding plan detail with all tasks."""
    result = await db.execute(
        select(OnboardingPlan).where(
            OnboardingPlan.id == plan_id,
            OnboardingPlan.tenant_id == user.tenant_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    emp_result = await db.execute(select(Employee).where(Employee.id == plan.employee_id))
    emp = emp_result.scalar_one_or_none()

    sorted_tasks = sorted(plan.tasks, key=lambda t: t.order)
    return {
        "id": plan.id,
        "employee_name": emp.full_name if emp else "Unknown",
        "employee_email": emp.email if emp else "",
        "department": emp.department if emp else "",
        "template_name": plan.template_name,
        "status": plan.status,
        "progress_pct": plan.progress_pct,
        "started_at": plan.started_at.isoformat() if plan.started_at else None,
        "target_completion": plan.target_completion.isoformat() if plan.target_completion else None,
        "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
        "tasks": [{
            "id": t.id,
            "title": t.title,
            "category": t.category,
            "due_day": t.due_day,
            "is_completed": t.is_completed,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "assigned_to": t.assigned_to,
            "notes": t.notes,
            "order": t.order,
        } for t in sorted_tasks],
    }


@router.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    request: TaskStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an onboarding task as complete or incomplete."""
    result = await db.execute(select(OnboardingTask).where(OnboardingTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify tenant access
    plan_result = await db.execute(
        select(OnboardingPlan).where(
            OnboardingPlan.id == task.plan_id,
            OnboardingPlan.tenant_id == user.tenant_id,
        )
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    task.is_completed = request.is_completed
    task.completed_at = datetime.utcnow() if request.is_completed else None

    # Recalculate plan progress
    all_tasks_result = await db.execute(
        select(OnboardingTask).where(OnboardingTask.plan_id == plan.id)
    )
    all_tasks = all_tasks_result.scalars().all()
    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.is_completed or (t.id == task_id and request.is_completed))
    if not request.is_completed:
        completed = sum(1 for t in all_tasks if t.is_completed and t.id != task_id)

    plan.progress_pct = int((completed / total) * 100) if total > 0 else 0
    if plan.progress_pct >= 100:
        plan.status = "completed"
        plan.completed_at = datetime.utcnow()

    await db.flush()
    return {
        "task_id": task_id,
        "is_completed": request.is_completed,
        "plan_progress": plan.progress_pct,
        "plan_status": plan.status,
        "message": f"Task {'completed' if request.is_completed else 'reopened'} successfully",
    }


@router.patch("/tasks/{task_id}/assign")
async def assign_task(
    task_id: str,
    request: TaskAssignUpdate,
    user: User = Depends(require_permission(Permission.MANAGE_ONBOARDING)),
    db: AsyncSession = Depends(get_db),
):
    """Assign or reassign an onboarding task."""
    result = await db.execute(select(OnboardingTask).where(OnboardingTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.assigned_to = request.assigned_to
    await db.flush()
    return {"task_id": task_id, "assigned_to": request.assigned_to, "message": "Task assigned successfully"}
