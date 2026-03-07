"""
Admin API routes - tenant management, system health, user management.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models.user import User, Role
from models.tenant import Tenant, TenantConfig
from models.candidate import Candidate
from models.ticket import Ticket
from api.deps import require_roles
import uuid

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class CreateTenantRequest(BaseModel):
    """Request body for tenant creation - keeps passwords out of query params."""
    name: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=255)
    admin_email: str = Field(..., min_length=5)
    admin_password: str = Field(..., min_length=8)
    admin_name: str = Field(..., min_length=1)


@router.get("/health")
async def health_check():
    """System health check (no auth required)."""
    return {
        "status": "healthy",
        "service": "nasiko-hr-platform",
        "version": "1.0.0",
    }


@router.get("/dashboard")
async def admin_dashboard(
    user: User = Depends(require_roles(Role.HR_ADMIN, Role.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard with key metrics."""
    tenant_id = user.tenant_id

    # Gather metrics
    users_count = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant_id)
    )
    candidates_count = await db.execute(
        select(func.count(Candidate.id)).where(Candidate.tenant_id == tenant_id)
    )
    open_tickets = await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.tenant_id == tenant_id,
            Ticket.status.in_(["open", "in_progress"]),
        )
    )
    auto_resolved = await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.tenant_id == tenant_id,
            Ticket.is_auto_resolved == True,
        )
    )

    return {
        "tenant_id": tenant_id,
        "metrics": {
            "total_users": users_count.scalar() or 0,
            "total_candidates": candidates_count.scalar() or 0,
            "open_tickets": open_tickets.scalar() or 0,
            "auto_resolved_tickets": auto_resolved.scalar() or 0,
        },
    }


@router.post("/tenants", status_code=201)
async def create_tenant(
    request: CreateTenantRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    """
    Bootstrap a new tenant with an admin user.
    Restricted to SUPER_ADMIN role for security.
    """
    from api.deps import hash_password

    # Check domain uniqueness
    existing = await db.execute(select(Tenant).where(Tenant.domain == request.domain))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Domain already registered")

    # Create tenant
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=request.name,
        domain=request.domain,
    )
    db.add(tenant)

    # Create tenant config
    config = TenantConfig(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        allowed_tools=["send_email", "search_policies", "create_calendar_event"],
    )
    db.add(config)

    # Create admin user
    admin_user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email=request.admin_email,
        hashed_password=hash_password(request.admin_password),
        full_name=request.admin_name,
        role=Role.HR_ADMIN,
    )
    db.add(admin_user)
    await db.flush()

    return {
        "tenant_id": tenant.id,
        "domain": tenant.domain,
        "admin_user_id": admin_user.id,
        "message": "Tenant created successfully",
    }
