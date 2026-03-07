"""
Compliance API routes - audit logs, consent management, data exports.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.user import User
from models.audit_log import AuditLog
from models.consent import ConsentRecord
from api.deps import require_permission
from security.rbac import Permission
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/compliance", tags=["Compliance"])


@router.get("/audit-logs")
async def get_audit_logs(
    action: str = Query(default=None, max_length=100),
    resource_type: str = Query(default=None, max_length=100),
    start_date: str = Query(default=None, max_length=30, description="ISO 8601 date string"),
    end_date: str = Query(default=None, max_length=30, description="ISO 8601 date string"),
    limit: int = Query(default=50, le=500),
    user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    db: AsyncSession = Depends(get_db),
):
    """Query audit logs with filters. Admin only."""
    query = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)

    if action:
        query = query.where(AuditLog.action.contains(action))
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if start_date:
        query = query.where(AuditLog.timestamp >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(AuditLog.timestamp <= datetime.fromisoformat(end_date))

    query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [{
        "id": log.id,
        "action": log.action,
        "agent": log.agent_name,
        "user_id": log.user_id,
        "user_role": log.user_role,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "status": log.status,
        "risk_level": log.risk_level,
        "timestamp": log.timestamp.isoformat(),
        "input_summary": log.input_summary,
        "output_summary": log.output_summary,
        "tools_used": log.tools_used,
    } for log in logs]


@router.get("/consent/{subject_id}")
async def get_consent_records(
    subject_id: str,
    user: User = Depends(require_permission(Permission.MANAGE_CONSENT)),
    db: AsyncSession = Depends(get_db),
):
    """Get consent records for a data subject."""
    result = await db.execute(
        select(ConsentRecord).where(
            ConsentRecord.tenant_id == user.tenant_id,
            ConsentRecord.subject_id == subject_id,
        )
    )
    records = result.scalars().all()

    return [{
        "id": r.id,
        "purpose": r.purpose,
        "lawful_basis": r.lawful_basis,
        "is_granted": r.is_granted,
        "granted_at": r.granted_at.isoformat() if r.granted_at else None,
        "withdrawn_at": r.withdrawn_at.isoformat() if r.withdrawn_at else None,
        "deletion_requested": r.deletion_requested,
    } for r in records]


@router.get("/metrics")
async def get_compliance_metrics(
    user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    db: AsyncSession = Depends(get_db),
):
    """Get compliance dashboard metrics."""
    now = datetime.now(timezone.utc)
    last_30_days = now - timedelta(days=30)

    # Use SQL aggregation instead of loading all records into memory
    base_where = [AuditLog.tenant_id == user.tenant_id, AuditLog.timestamp >= last_30_days]

    total_result = await db.execute(
        select(func.count(AuditLog.id)).where(*base_where)
    )
    total_actions = total_result.scalar() or 0

    denied_result = await db.execute(
        select(func.count(AuditLog.id)).where(*base_where, AuditLog.status == "denied")
    )
    denied_actions = denied_result.scalar() or 0

    escalated_result = await db.execute(
        select(func.count(AuditLog.id)).where(*base_where, AuditLog.status == "escalated")
    )
    escalated_actions = escalated_result.scalar() or 0

    high_risk_result = await db.execute(
        select(func.count(AuditLog.id)).where(*base_where, AuditLog.risk_level == "high")
    )
    high_risk = high_risk_result.scalar() or 0

    return {
        "period": "last_30_days",
        "total_actions": total_actions,
        "denied_actions": denied_actions,
        "escalated_actions": escalated_actions,
        "high_risk_actions": high_risk,
        "compliance_score": round((1 - (denied_actions + high_risk) / max(total_actions, 1)) * 100, 1),
    }
