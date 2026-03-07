"""
Audit Logging Service.
Creates immutable audit records for every significant action.
Integrates with PII redaction to ensure logs are safe.
All entries include a correlation request_id for end-to-end tracing.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from models.audit_log import AuditLog
from security.pii_detector import redact_for_logging
from security.tenant_isolation import TenantContext
import structlog

logger = structlog.get_logger()


def _get_request_id() -> Optional[str]:
    """Get the current request's correlation ID from TenantContext."""
    return TenantContext.get_request_id()


async def log_action(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    agent_name: Optional[str] = None,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    input_summary: Optional[str] = None,
    output_summary: Optional[str] = None,
    tools_used: list[str] = None,
    metadata: dict = None,
    status: str = "success",
    risk_level: Optional[str] = None,
    request_id: Optional[str] = None,
) -> AuditLog:
    """
    Create an immutable audit log entry.
    All text fields are PII-redacted before storage.
    Includes correlation request_id for end-to-end tracing.
    """
    # Use provided request_id or get from context
    corr_id = request_id or _get_request_id()

    # Merge request_id into metadata
    meta = metadata or {}
    if corr_id:
        meta["request_id"] = corr_id

    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        agent_name=agent_name,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        input_summary=redact_for_logging(input_summary) if input_summary else None,
        output_summary=redact_for_logging(output_summary) if output_summary else None,
        tools_used=tools_used or [],
        metadata_=meta,
        status=status,
        risk_level=risk_level,
        timestamp=datetime.now(timezone.utc),
    )

    db.add(entry)
    await db.flush()

    logger.info(
        "audit_log_created",
        action=action,
        tenant_id=tenant_id,
        user_id=user_id,
        agent=agent_name,
        resource=f"{resource_type}:{resource_id}",
        status=status,
        request_id=corr_id,
    )

    return entry


async def log_agent_action(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    user_role: str,
    agent_name: str,
    action: str,
    input_text: str,
    output_text: str,
    tools_used: list[str] = None,
    status: str = "success",
    request_id: Optional[str] = None,
):
    """Convenience wrapper for logging agent interactions."""
    return await log_action(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        agent_name=agent_name,
        action=action,
        input_summary=input_text[:500],  # truncate for storage
        output_summary=output_text[:500],
        tools_used=tools_used,
        status=status,
        request_id=request_id or _get_request_id(),
    )
