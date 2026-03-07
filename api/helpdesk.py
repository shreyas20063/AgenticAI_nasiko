"""Helpdesk API routes - ticket CRUD, detail, responses, and statistics."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.user import User
from models.ticket import Ticket, TicketMessage
from api.deps import require_permission, get_current_user
from security.rbac import Permission
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/helpdesk", tags=["Helpdesk"])


@router.get("/tickets")
async def list_tickets(
    status: str = Query(default=None, max_length=50),
    priority: str = Query(default=None, max_length=50),
    category: str = Query(default=None, max_length=100),
    limit: int = Query(default=50, le=200),
    user: User = Depends(require_permission(Permission.VIEW_ALL_TICKETS)),
    db: AsyncSession = Depends(get_db),
):
    """List helpdesk tickets for the tenant."""
    query = select(Ticket).where(Ticket.tenant_id == user.tenant_id)

    if status:
        query = query.where(Ticket.status == status)
    if priority:
        query = query.where(Ticket.priority == priority)
    if category:
        query = query.where(Ticket.category == category)

    query = query.order_by(Ticket.created_at.desc()).limit(limit)
    result = await db.execute(query)
    tickets = result.scalars().all()

    # Build user name lookup
    user_ids = set()
    for t in tickets:
        user_ids.add(t.requester_id)
        if t.assigned_to:
            user_ids.add(t.assigned_to)

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    user_map = {u.id: u.full_name for u in user_result.scalars().all()}

    return [{
        "id": t.id,
        "subject": t.subject,
        "category": t.category,
        "status": t.status,
        "priority": t.priority,
        "requester_name": user_map.get(t.requester_id, "Unknown"),
        "assigned_to_name": user_map.get(t.assigned_to, "Unassigned") if t.assigned_to else "Unassigned",
        "is_auto_resolved": t.is_auto_resolved,
        "resolution_summary": t.resolution_summary,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
    } for t in tickets]


@router.get("/stats")
async def ticket_stats(
    user: User = Depends(require_permission(Permission.VIEW_ALL_TICKETS)),
    db: AsyncSession = Depends(get_db),
):
    """Get ticket statistics for the tenant using efficient SQL aggregation."""
    tenant_where = Ticket.tenant_id == user.tenant_id

    total_r = await db.execute(select(func.count(Ticket.id)).where(tenant_where))
    open_r = await db.execute(select(func.count(Ticket.id)).where(tenant_where, Ticket.status == "open"))
    in_progress_r = await db.execute(select(func.count(Ticket.id)).where(tenant_where, Ticket.status == "in_progress"))
    resolved_r = await db.execute(select(func.count(Ticket.id)).where(tenant_where, Ticket.status == "resolved"))
    closed_r = await db.execute(select(func.count(Ticket.id)).where(tenant_where, Ticket.status == "closed"))
    escalated_r = await db.execute(select(func.count(Ticket.id)).where(tenant_where, Ticket.status == "escalated"))
    auto_resolved_r = await db.execute(select(func.count(Ticket.id)).where(tenant_where, Ticket.is_auto_resolved == True))

    return {
        "total": total_r.scalar() or 0,
        "open": open_r.scalar() or 0,
        "in_progress": in_progress_r.scalar() or 0,
        "resolved": resolved_r.scalar() or 0,
        "closed": closed_r.scalar() or 0,
        "escalated": escalated_r.scalar() or 0,
        "auto_resolved": auto_resolved_r.scalar() or 0,
    }


# ============================================================
# Ticket Detail, Create, Update, Respond, Assign
# ============================================================

class CreateTicketRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=200)
    category: str = Field(default="other")
    priority: str = Field(default="medium")
    description: str = Field(default="")


class TicketStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|in_progress|resolved|closed)$")
    resolution_summary: Optional[str] = None


class TicketRespondRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)


class TicketAssignRequest(BaseModel):
    assigned_to: str = Field(..., description="User ID to assign to")


@router.get("/tickets/{ticket_id}")
async def get_ticket_detail(
    ticket_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full ticket detail with message thread."""
    result = await db.execute(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.tenant_id == user.tenant_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Get messages
    msg_result = await db.execute(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()

    # Get user names for display
    user_ids = {ticket.requester_id}
    if ticket.assigned_to:
        user_ids.add(ticket.assigned_to)
    for m in messages:
        if m.sender_id:
            user_ids.add(m.sender_id)

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    user_map = {u.id: u.full_name for u in user_result.scalars().all()}

    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "category": ticket.category,
        "status": ticket.status,
        "priority": ticket.priority,
        "requester_id": ticket.requester_id,
        "requester_name": user_map.get(ticket.requester_id, "Unknown"),
        "assigned_to": ticket.assigned_to,
        "assigned_to_name": user_map.get(ticket.assigned_to, "Unassigned") if ticket.assigned_to else "Unassigned",
        "is_auto_resolved": ticket.is_auto_resolved,
        "resolution_summary": ticket.resolution_summary,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_name": user_map.get(m.sender_id, "System"),
                "content": m.content,
                "is_internal": m.is_internal,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post("/tickets", status_code=201)
async def create_ticket(
    request: CreateTicketRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new helpdesk ticket."""
    ticket = Ticket(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        requester_id=user.id,
        subject=request.subject,
        category=request.category,
        priority=request.priority,
        status="open",
    )
    db.add(ticket)

    if request.description:
        msg = TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            sender_id=user.id,
            content=request.description,
            is_internal=False,
        )
        db.add(msg)

    await db.flush()
    return {"id": ticket.id, "subject": ticket.subject, "status": "open", "message": "Ticket created successfully"}


@router.patch("/tickets/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: str,
    request: TicketStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update ticket status."""
    result = await db.execute(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.tenant_id == user.tenant_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_status = ticket.status
    ticket.status = request.status

    if request.status in ("resolved", "closed"):
        ticket.resolved_at = datetime.utcnow()
        if request.resolution_summary:
            ticket.resolution_summary = request.resolution_summary

    await db.flush()
    return {
        "id": ticket.id,
        "old_status": old_status,
        "new_status": request.status,
        "message": f"Ticket status updated from '{old_status}' to '{request.status}'",
    }


@router.post("/tickets/{ticket_id}/respond")
async def respond_to_ticket(
    ticket_id: str,
    request: TicketRespondRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a response message to a ticket thread."""
    result = await db.execute(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.tenant_id == user.tenant_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = TicketMessage(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        sender_id=user.id,
        content=request.message,
        is_internal=False,
    )
    db.add(msg)
    await db.flush()

    return {"id": msg.id, "ticket_id": ticket_id, "message": "Response added successfully"}


@router.patch("/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    request: TicketAssignRequest,
    user: User = Depends(require_permission(Permission.RESOLVE_TICKETS)),
    db: AsyncSession = Depends(get_db),
):
    """Assign or reassign a ticket to a team member."""
    result = await db.execute(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.tenant_id == user.tenant_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.assigned_to = request.assigned_to
    await db.flush()

    return {"id": ticket.id, "assigned_to": request.assigned_to, "message": "Ticket assigned successfully"}
