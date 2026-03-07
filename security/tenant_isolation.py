"""
Tenant Isolation Middleware.
Ensures every database query is scoped to the current tenant.
Uses SQLAlchemy event hooks for AUTOMATIC tenant filtering on all SELECT queries.
"""

from contextvars import ContextVar
from typing import Optional
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
import structlog

logger = structlog.get_logger()

# Context variables for current request
_current_tenant: ContextVar[Optional[str]] = ContextVar('current_tenant', default=None)
_current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)
_current_user_role: ContextVar[Optional[str]] = ContextVar('current_user_role', default=None)
_current_request_id: ContextVar[Optional[str]] = ContextVar('current_request_id', default=None)

# Tables exempt from tenant filtering (global tables)
_TENANT_EXEMPT_TABLES = {"tenants", "tenant_configs"}


class TenantContext:
    """Manages tenant context for the current request."""

    @staticmethod
    def set(tenant_id: str, user_id: str = None, user_role: str = None, request_id: str = None):
        _current_tenant.set(tenant_id)
        if user_id:
            _current_user_id.set(user_id)
        if user_role:
            _current_user_role.set(user_role)
        if request_id:
            _current_request_id.set(request_id)

    @staticmethod
    def get_tenant_id() -> Optional[str]:
        return _current_tenant.get()

    @staticmethod
    def get_user_id() -> Optional[str]:
        return _current_user_id.get()

    @staticmethod
    def get_user_role() -> Optional[str]:
        return _current_user_role.get()

    @staticmethod
    def get_request_id() -> Optional[str]:
        return _current_request_id.get()

    @staticmethod
    def clear():
        _current_tenant.set(None)
        _current_user_id.set(None)
        _current_user_role.set(None)
        _current_request_id.set(None)

    @staticmethod
    def require_tenant() -> str:
        """Get tenant_id or raise if not set."""
        tid = _current_tenant.get()
        if not tid:
            raise RuntimeError("Tenant context not set. Cannot proceed without tenant isolation.")
        return tid


def tenant_filter(query, model_class):
    """
    Apply tenant_id filter to a query.
    STILL available for explicit use, but automatic filtering covers most cases.
    """
    tenant_id = TenantContext.get_tenant_id()
    if tenant_id and hasattr(model_class, 'tenant_id'):
        return query.filter(model_class.tenant_id == tenant_id)
    return query


def install_tenant_filter():
    """
    Install automatic tenant filtering on all SELECT queries.
    Call this once during app startup.

    Uses the do_orm_execute event on the Session class to automatically
    inject WHERE tenant_id = X on any query targeting a model with a tenant_id column.
    """
    @event.listens_for(Session, "do_orm_execute")
    def _apply_tenant_filter(orm_execute_state):
        # Only filter SELECT statements
        if not orm_execute_state.is_select:
            return

        tenant_id = _current_tenant.get()
        if not tenant_id:
            return  # No tenant context = no filtering (e.g., during seed)

        # Check if any of the query's entities have a tenant_id column
        if not hasattr(orm_execute_state, 'statement'):
            return

        stmt = orm_execute_state.statement

        # Extract table references from the statement
        # Try 'froms' first (standard in SQLAlchemy 1.4+/2.x), then fallback
        froms = getattr(stmt, 'froms', None)
        if not froms:
            froms = getattr(stmt, 'columns_clause_froms', None)

        if froms:
            for from_clause in froms:
                table_name = getattr(from_clause, 'name', None)
                if table_name and table_name in _TENANT_EXEMPT_TABLES:
                    continue
                if hasattr(from_clause, 'c') and hasattr(from_clause.c, 'tenant_id'):
                    stmt = stmt.where(from_clause.c.tenant_id == tenant_id)
                    orm_execute_state.statement = stmt
                    return

    logger.info("automatic_tenant_filtering_installed")
