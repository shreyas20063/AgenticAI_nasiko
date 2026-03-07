"""
Tool Call Guardrails.
Validates all tool calls proposed by agents before execution.
Enforces allowlists, parameter validation, and persistent rate limits.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict
from security.rbac import is_tool_allowed, Permission, has_permission
from models.user import Role
import structlog
import json
import os
import threading

logger = structlog.get_logger()

# ============================================================
# Persistent Rate Limiting (file-backed, survives restarts)
# ============================================================

_RATE_LIMIT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".rate_limits.json")
_rate_limit_lock = threading.Lock()

RATE_LIMITS: dict[str, int] = {
    "send_email": 10,         # max 10 emails per hour
    "schedule_interview": 20,  # max 20 per hour
    "delete_data": 5,          # max 5 deletions per hour
    "export_data": 3,          # max 3 exports per hour
    "anonymize_data": 5,
}


def _load_rate_state() -> dict[str, list[float]]:
    """Load rate limit state from file."""
    try:
        if os.path.exists(_RATE_LIMIT_FILE):
            with open(_RATE_LIMIT_FILE, "r") as f:
                data = json.load(f)
                # Convert stored timestamps back
                return {k: [float(t) for t in v] for k, v in data.items()}
    except (json.JSONDecodeError, IOError, ValueError):
        pass
    return {}


def _save_rate_state(state: dict[str, list[float]]):
    """Persist rate limit state to file."""
    try:
        with open(_RATE_LIMIT_FILE, "w") as f:
            json.dump(state, f)
    except IOError:
        logger.warning("rate_limit_persist_failed")


def _check_rate_limit(tool_name: str, tenant_id: str = "", window_minutes: int = 60) -> bool:
    """Check if tool call is within rate limits. Persists across restarts. Thread-safe."""
    if tool_name not in RATE_LIMITS:
        return True

    with _rate_limit_lock:
        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - (window_minutes * 60)

        # Use tenant-scoped key for isolation
        key = f"{tenant_id}:{tool_name}" if tenant_id else tool_name

        state = _load_rate_state()
        entries = state.get(key, [])

        # Clean old entries
        entries = [t for t in entries if t > cutoff]

        if len(entries) >= RATE_LIMITS[tool_name]:
            return False

        entries.append(now)
        state[key] = entries
        _save_rate_state(state)
        return True


# ============================================================
# Parameter Validation Rules
# ============================================================

PARAMETER_VALIDATORS: dict[str, dict] = {
    "send_email": {
        "required": ["to", "subject", "body"],
        "max_recipients": 5,  # prevent mass emailing
        "blocked_domains": [],  # populate with known bad domains
    },
    "delete_data": {
        "required": ["resource_type", "resource_id"],
        "requires_confirmation": True,
    },
    "export_data": {
        "required": ["resource_type"],
        "requires_confirmation": True,
    },
    "update_candidate_status": {
        "required": ["candidate_id", "new_status"],
        "allowed_statuses": ["screened", "shortlisted", "interview", "offered", "rejected"],
    },
}


# ============================================================
# Tools requiring human approval before execution
# ============================================================

APPROVAL_REQUIRED_TOOLS = {
    "send_email",
    "delete_data",
    "export_data",
    "anonymize_data",
    "approve_hiring",
    "schedule_interview",  # bulk scheduling
}


class GuardrailResult:
    def __init__(self):
        self.allowed: bool = True
        self.requires_approval: bool = False
        self.denial_reason: Optional[str] = None
        self.warnings: list[str] = []

    def deny(self, reason: str):
        self.allowed = False
        self.denial_reason = reason

    def require_approval(self, reason: str):
        self.requires_approval = True
        self.warnings.append(reason)


def validate_tool_call(
    agent_name: str,
    tool_name: str,
    parameters: dict,
    user_role: Role,
    tenant_id: str,
) -> GuardrailResult:
    """
    Comprehensive validation of a proposed tool call.
    Checks: allowlist, rate limit, parameters, approval requirements.
    """
    result = GuardrailResult()

    # 1. Agent allowlist check
    if not is_tool_allowed(agent_name, tool_name):
        result.deny(
            f"Agent '{agent_name}' is not permitted to use tool '{tool_name}'"
        )
        return result

    # 2. Rate limit check (now persistent and tenant-scoped)
    if not _check_rate_limit(tool_name, tenant_id):
        result.deny(
            f"Rate limit exceeded for tool '{tool_name}'. "
            f"Max {RATE_LIMITS.get(tool_name, 'N/A')} calls per hour."
        )
        return result

    # 3. Parameter validation
    validator = PARAMETER_VALIDATORS.get(tool_name)
    if validator:
        # Check required params
        for req in validator.get("required", []):
            if req not in parameters or not parameters[req]:
                result.deny(f"Missing required parameter '{req}' for tool '{tool_name}'")
                return result

        # Check email recipient limits
        if tool_name == "send_email":
            recipients = parameters.get("to", [])
            if isinstance(recipients, list) and len(recipients) > validator["max_recipients"]:
                result.deny(
                    f"Too many email recipients ({len(recipients)}). "
                    f"Max allowed: {validator['max_recipients']}"
                )
                return result

        # Check status transitions
        if tool_name == "update_candidate_status":
            new_status = parameters.get("new_status")
            if new_status not in validator.get("allowed_statuses", []):
                result.deny(f"Invalid candidate status: '{new_status}'")
                return result

    # 4. Approval requirement check
    if tool_name in APPROVAL_REQUIRED_TOOLS:
        result.require_approval(
            f"Tool '{tool_name}' requires human approval before execution"
        )

    # 5. Tenant isolation check - ensure parameters reference correct tenant
    resource_id = parameters.get("resource_id") or parameters.get("candidate_id")
    if resource_id and "tenant_id" in parameters:
        if parameters["tenant_id"] != tenant_id:
            result.deny("Cross-tenant data access is not permitted")
            return result

    return result
