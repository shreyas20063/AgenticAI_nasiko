"""
Authentication API routes.
Login, token generation, user creation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.user import User, Role
from models.tenant import Tenant
from schemas.auth import LoginRequest, TokenResponse, RefreshRequest, UserCreate, UserResponse
from config import get_settings

settings = get_settings()
from api.deps import hash_password, verify_password, create_access_token, create_refresh_token, verify_refresh_token, get_current_user
import uuid

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token_data = {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "role": user.role.value,
        "email": user.email,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        role=user.role.value,
        tenant_id=user.tenant_id,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Get a new access token using a refresh token."""
    try:
        payload = verify_refresh_token(request.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    token_data = {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "role": user.role.value,
        "email": user.email,
    }

    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user_id=user.id,
        role=user.role.value,
        tenant_id=user.tenant_id,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    request: UserCreate,
    tenant_domain: str,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user under an existing tenant."""
    # Find tenant
    result = await db.execute(select(Tenant).where(Tenant.domain == tenant_domain))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Check duplicate email
    existing = await db.execute(
        select(User).where(User.email == request.email, User.tenant_id == tenant.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role=request.role,
        department=request.department,
    )

    db.add(user)
    await db.flush()

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        department=user.department,
        tenant_id=user.tenant_id,
        is_active=True,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        department=user.department,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
    )
