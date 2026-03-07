"""
API Dependencies - authentication, authorization, tenant context injection.
Used as FastAPI dependency injection across all routes.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.user import User, Role
from security.tenant_isolation import TenantContext
from security.rbac import Permission, has_permission
from config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    """Create a longer-lived refresh token (7 days)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_refresh_token(token: str) -> dict:
    """Verify a refresh token and return its payload."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        return payload
    except JWTError:
        raise ValueError("Invalid or expired refresh token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate current user from JWT token."""
    token = credentials.credentials

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        # Reject refresh tokens used as access tokens
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type: expected access token")

        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        if user_id is None or tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Set tenant context for this request with unique correlation ID
    import uuid as _uuid
    TenantContext.set(
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role.value,
        request_id=str(_uuid.uuid4()),
    )

    return user


def require_permission(permission: Permission):
    """Dependency factory that checks for a specific permission."""
    async def _check(user: User = Depends(get_current_user)):
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires '{permission.value}'"
            )
        return user
    return _check


def require_roles(*roles: Role):
    """Dependency factory that restricts to specific roles."""
    async def _check(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access restricted to roles: {[r.value for r in roles]}"
            )
        return user
    return _check
