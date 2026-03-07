"""
Role-Based Access Control (RBAC) enforcement.
Defines permissions per role and provides decorators/checks for API and agent actions.
"""

from enum import Enum
from typing import Optional
from models.user import Role

# ============================================================
# Permission Definitions
# ============================================================

class Permission(str, Enum):
    # Recruitment
    VIEW_CANDIDATES = "view_candidates"
    SCREEN_CANDIDATES = "screen_candidates"
    MANAGE_JOBS = "manage_jobs"
    APPROVE_HIRING = "approve_hiring"

    # Onboarding
    VIEW_ONBOARDING = "view_onboarding"
    MANAGE_ONBOARDING = "manage_onboarding"

    # Helpdesk
    CREATE_TICKET = "create_ticket"
    VIEW_OWN_TICKETS = "view_own_tickets"
    VIEW_ALL_TICKETS = "view_all_tickets"
    RESOLVE_TICKETS = "resolve_tickets"

    # Employee Data
    VIEW_OWN_PROFILE = "view_own_profile"
    VIEW_TEAM_PROFILES = "view_team_profiles"
    VIEW_ALL_EMPLOYEES = "view_all_employees"
    MANAGE_EMPLOYEES = "manage_employees"

    # Compliance & Admin
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_COMPLIANCE = "manage_compliance"
    MANAGE_CONSENT = "manage_consent"
    EXPORT_DATA = "export_data"
    DELETE_DATA = "delete_data"
    MANAGE_TENANTS = "manage_tenants"

    # Agent interactions
    USE_CHAT = "use_chat"
    APPROVE_AGENT_ACTIONS = "approve_agent_actions"


# ============================================================
# Role -> Permission Mapping
# ============================================================

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.EMPLOYEE: {
        Permission.USE_CHAT,
        Permission.VIEW_OWN_PROFILE,
        Permission.CREATE_TICKET,
        Permission.VIEW_OWN_TICKETS,
        Permission.VIEW_ONBOARDING,
    },
    Role.MANAGER: {
        Permission.USE_CHAT,
        Permission.VIEW_OWN_PROFILE,
        Permission.VIEW_TEAM_PROFILES,
        Permission.CREATE_TICKET,
        Permission.VIEW_OWN_TICKETS,
        Permission.VIEW_ONBOARDING,
        Permission.APPROVE_AGENT_ACTIONS,
    },
    Role.RECRUITER: {
        Permission.USE_CHAT,
        Permission.VIEW_OWN_PROFILE,
        Permission.VIEW_CANDIDATES,
        Permission.SCREEN_CANDIDATES,
        Permission.MANAGE_JOBS,
        Permission.CREATE_TICKET,
        Permission.VIEW_OWN_TICKETS,
    },
    Role.HRBP: {
        Permission.USE_CHAT,
        Permission.VIEW_OWN_PROFILE,
        Permission.VIEW_ALL_EMPLOYEES,
        Permission.VIEW_CANDIDATES,
        Permission.SCREEN_CANDIDATES,
        Permission.MANAGE_JOBS,
        Permission.VIEW_ONBOARDING,
        Permission.MANAGE_ONBOARDING,
        Permission.VIEW_ALL_TICKETS,
        Permission.RESOLVE_TICKETS,
        Permission.CREATE_TICKET,
        Permission.VIEW_OWN_TICKETS,
        Permission.APPROVE_AGENT_ACTIONS,
        Permission.APPROVE_HIRING,
    },
    Role.HR_ADMIN: {
        Permission.USE_CHAT,
        Permission.VIEW_OWN_PROFILE,
        Permission.VIEW_ALL_EMPLOYEES,
        Permission.MANAGE_EMPLOYEES,
        Permission.VIEW_CANDIDATES,
        Permission.SCREEN_CANDIDATES,
        Permission.MANAGE_JOBS,
        Permission.VIEW_ONBOARDING,
        Permission.MANAGE_ONBOARDING,
        Permission.VIEW_ALL_TICKETS,
        Permission.RESOLVE_TICKETS,
        Permission.CREATE_TICKET,
        Permission.VIEW_OWN_TICKETS,
        Permission.VIEW_AUDIT_LOGS,
        Permission.MANAGE_COMPLIANCE,
        Permission.MANAGE_CONSENT,
        Permission.EXPORT_DATA,
        Permission.APPROVE_AGENT_ACTIONS,
        Permission.APPROVE_HIRING,
    },
    Role.SECURITY_ADMIN: {
        Permission.USE_CHAT,
        Permission.VIEW_OWN_PROFILE,
        Permission.VIEW_AUDIT_LOGS,
        Permission.MANAGE_COMPLIANCE,
        Permission.MANAGE_CONSENT,
        Permission.EXPORT_DATA,
        Permission.DELETE_DATA,
        Permission.MANAGE_TENANTS,
    },
    Role.SUPER_ADMIN: {p for p in Permission},  # all permissions
}


def has_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def check_permission(role: Role, permission: Permission) -> None:
    """Raise if the role lacks the required permission."""
    if not has_permission(role, permission):
        raise PermissionError(
            f"Role '{role.value}' does not have permission '{permission.value}'"
        )


def get_permissions(role: Role) -> set[Permission]:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, set())


# ============================================================
# Tool Allowlists Per Agent
# ============================================================

AGENT_TOOL_ALLOWLIST: dict[str, set[str]] = {
    "recruitment_agent": {
        "parse_resume", "search_candidates", "rank_candidates",
        "send_email", "schedule_interview", "create_calendar_event",
        "get_job_details", "update_candidate_status",
    },
    "onboarding_agent": {
        "get_onboarding_plan", "create_onboarding_plan",
        "update_task_status", "assign_task",
        "send_email", "create_calendar_event", "get_employee_details",
        "send_notification",
    },
    "helpdesk_agent": {
        "search_policies", "get_employee_details", "create_ticket",
        "update_ticket", "update_ticket_status", "escalate_ticket",
        "get_leave_balance", "submit_leave_request",
        "hris_connector",
    },
    "compliance_agent": {
        "get_audit_logs", "get_consent_records", "update_consent",
        "generate_report", "anonymize_data", "export_data",
    },
}


def is_tool_allowed(agent_name: str, tool_name: str) -> bool:
    """Check if an agent is permitted to use a specific tool."""
    allowed = AGENT_TOOL_ALLOWLIST.get(agent_name, set())
    return tool_name in allowed
