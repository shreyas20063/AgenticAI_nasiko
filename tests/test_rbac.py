"""Unit tests for the RBAC (Role-Based Access Control) module."""

import sys
import os
import pytest

# Add project root to path so imports resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security.rbac import (
    has_permission,
    check_permission,
    get_permissions,
    is_tool_allowed,
    Permission,
    ROLE_PERMISSIONS,
)
from models.user import Role


# ============================================================
# has_permission
# ============================================================


class TestHasPermission:
    """Tests for the has_permission function."""

    # -- Employee role --

    def test_employee_can_use_chat(self):
        assert has_permission(Role.EMPLOYEE, Permission.USE_CHAT) is True

    def test_employee_can_view_own_profile(self):
        assert has_permission(Role.EMPLOYEE, Permission.VIEW_OWN_PROFILE) is True

    def test_employee_can_create_ticket(self):
        assert has_permission(Role.EMPLOYEE, Permission.CREATE_TICKET) is True

    def test_employee_can_view_own_tickets(self):
        assert has_permission(Role.EMPLOYEE, Permission.VIEW_OWN_TICKETS) is True

    def test_employee_can_view_onboarding(self):
        assert has_permission(Role.EMPLOYEE, Permission.VIEW_ONBOARDING) is True

    def test_employee_cannot_view_audit_logs(self):
        assert has_permission(Role.EMPLOYEE, Permission.VIEW_AUDIT_LOGS) is False

    def test_employee_cannot_manage_employees(self):
        assert has_permission(Role.EMPLOYEE, Permission.MANAGE_EMPLOYEES) is False

    def test_employee_cannot_view_all_tickets(self):
        assert has_permission(Role.EMPLOYEE, Permission.VIEW_ALL_TICKETS) is False

    def test_employee_cannot_export_data(self):
        assert has_permission(Role.EMPLOYEE, Permission.EXPORT_DATA) is False

    def test_employee_cannot_approve_agent_actions(self):
        assert has_permission(Role.EMPLOYEE, Permission.APPROVE_AGENT_ACTIONS) is False

    # -- Manager role --

    def test_manager_can_view_team_profiles(self):
        assert has_permission(Role.MANAGER, Permission.VIEW_TEAM_PROFILES) is True

    def test_manager_can_approve_agent_actions(self):
        assert has_permission(Role.MANAGER, Permission.APPROVE_AGENT_ACTIONS) is True

    def test_manager_cannot_view_all_employees(self):
        assert has_permission(Role.MANAGER, Permission.VIEW_ALL_EMPLOYEES) is False

    def test_manager_cannot_manage_compliance(self):
        assert has_permission(Role.MANAGER, Permission.MANAGE_COMPLIANCE) is False

    # -- Recruiter role --

    def test_recruiter_can_view_candidates(self):
        assert has_permission(Role.RECRUITER, Permission.VIEW_CANDIDATES) is True

    def test_recruiter_can_screen_candidates(self):
        assert has_permission(Role.RECRUITER, Permission.SCREEN_CANDIDATES) is True

    def test_recruiter_can_manage_jobs(self):
        assert has_permission(Role.RECRUITER, Permission.MANAGE_JOBS) is True

    def test_recruiter_cannot_approve_hiring(self):
        assert has_permission(Role.RECRUITER, Permission.APPROVE_HIRING) is False

    def test_recruiter_cannot_manage_onboarding(self):
        assert has_permission(Role.RECRUITER, Permission.MANAGE_ONBOARDING) is False

    # -- HRBP role --

    def test_hrbp_can_approve_hiring(self):
        assert has_permission(Role.HRBP, Permission.APPROVE_HIRING) is True

    def test_hrbp_can_manage_onboarding(self):
        assert has_permission(Role.HRBP, Permission.MANAGE_ONBOARDING) is True

    def test_hrbp_can_resolve_tickets(self):
        assert has_permission(Role.HRBP, Permission.RESOLVE_TICKETS) is True

    def test_hrbp_cannot_manage_employees(self):
        assert has_permission(Role.HRBP, Permission.MANAGE_EMPLOYEES) is False

    def test_hrbp_cannot_view_audit_logs(self):
        assert has_permission(Role.HRBP, Permission.VIEW_AUDIT_LOGS) is False

    # -- HR Admin role --

    def test_hr_admin_can_view_audit_logs(self):
        assert has_permission(Role.HR_ADMIN, Permission.VIEW_AUDIT_LOGS) is True

    def test_hr_admin_can_manage_employees(self):
        assert has_permission(Role.HR_ADMIN, Permission.MANAGE_EMPLOYEES) is True

    def test_hr_admin_can_manage_compliance(self):
        assert has_permission(Role.HR_ADMIN, Permission.MANAGE_COMPLIANCE) is True

    def test_hr_admin_can_export_data(self):
        assert has_permission(Role.HR_ADMIN, Permission.EXPORT_DATA) is True

    def test_hr_admin_cannot_delete_data(self):
        assert has_permission(Role.HR_ADMIN, Permission.DELETE_DATA) is False

    def test_hr_admin_cannot_manage_tenants(self):
        assert has_permission(Role.HR_ADMIN, Permission.MANAGE_TENANTS) is False

    # -- Security Admin role --

    def test_security_admin_can_view_audit_logs(self):
        assert has_permission(Role.SECURITY_ADMIN, Permission.VIEW_AUDIT_LOGS) is True

    def test_security_admin_can_delete_data(self):
        assert has_permission(Role.SECURITY_ADMIN, Permission.DELETE_DATA) is True

    def test_security_admin_can_manage_tenants(self):
        assert has_permission(Role.SECURITY_ADMIN, Permission.MANAGE_TENANTS) is True

    def test_security_admin_cannot_screen_candidates(self):
        assert has_permission(Role.SECURITY_ADMIN, Permission.SCREEN_CANDIDATES) is False

    def test_security_admin_cannot_manage_employees(self):
        assert has_permission(Role.SECURITY_ADMIN, Permission.MANAGE_EMPLOYEES) is False

    # -- Super Admin role --

    def test_super_admin_has_all_permissions(self):
        for perm in Permission:
            assert has_permission(Role.SUPER_ADMIN, perm) is True, (
                f"SUPER_ADMIN should have permission {perm.value}"
            )


# ============================================================
# check_permission
# ============================================================


class TestCheckPermission:
    """Tests for the check_permission function."""

    def test_check_permission_passes_when_allowed(self):
        # Should not raise
        check_permission(Role.HR_ADMIN, Permission.VIEW_AUDIT_LOGS)

    def test_check_permission_raises_when_denied(self):
        with pytest.raises(PermissionError) as exc_info:
            check_permission(Role.EMPLOYEE, Permission.VIEW_AUDIT_LOGS)
        assert "employee" in str(exc_info.value)
        assert "view_audit_logs" in str(exc_info.value)

    def test_check_permission_raises_for_employee_manage_employees(self):
        with pytest.raises(PermissionError):
            check_permission(Role.EMPLOYEE, Permission.MANAGE_EMPLOYEES)

    def test_check_permission_raises_for_recruiter_delete_data(self):
        with pytest.raises(PermissionError):
            check_permission(Role.RECRUITER, Permission.DELETE_DATA)

    def test_check_permission_passes_for_super_admin_any(self):
        # Super admin should never raise
        for perm in Permission:
            check_permission(Role.SUPER_ADMIN, perm)


# ============================================================
# get_permissions
# ============================================================


class TestGetPermissions:
    """Tests for the get_permissions function."""

    def test_employee_permissions_count(self):
        perms = get_permissions(Role.EMPLOYEE)
        assert len(perms) == 5

    def test_employee_permissions_contents(self):
        perms = get_permissions(Role.EMPLOYEE)
        expected = {
            Permission.USE_CHAT,
            Permission.VIEW_OWN_PROFILE,
            Permission.CREATE_TICKET,
            Permission.VIEW_OWN_TICKETS,
            Permission.VIEW_ONBOARDING,
        }
        assert perms == expected

    def test_super_admin_has_every_permission(self):
        perms = get_permissions(Role.SUPER_ADMIN)
        assert perms == {p for p in Permission}

    def test_recruiter_permissions_include_manage_jobs(self):
        perms = get_permissions(Role.RECRUITER)
        assert Permission.MANAGE_JOBS in perms

    def test_get_permissions_returns_set(self):
        perms = get_permissions(Role.MANAGER)
        assert isinstance(perms, set)

    def test_all_roles_in_role_permissions_mapping(self):
        for role in Role:
            assert role in ROLE_PERMISSIONS, (
                f"Role {role.value} missing from ROLE_PERMISSIONS"
            )


# ============================================================
# is_tool_allowed
# ============================================================


class TestIsToolAllowed:
    """Tests for the is_tool_allowed function."""

    # Recruitment agent
    def test_recruitment_agent_can_parse_resume(self):
        assert is_tool_allowed("recruitment_agent", "parse_resume") is True

    def test_recruitment_agent_can_send_email(self):
        assert is_tool_allowed("recruitment_agent", "send_email") is True

    def test_recruitment_agent_cannot_get_audit_logs(self):
        assert is_tool_allowed("recruitment_agent", "get_audit_logs") is False

    def test_recruitment_agent_cannot_anonymize_data(self):
        assert is_tool_allowed("recruitment_agent", "anonymize_data") is False

    # Onboarding agent
    def test_onboarding_agent_can_get_onboarding_plan(self):
        assert is_tool_allowed("onboarding_agent", "get_onboarding_plan") is True

    def test_onboarding_agent_can_send_notification(self):
        assert is_tool_allowed("onboarding_agent", "send_notification") is True

    def test_onboarding_agent_cannot_search_candidates(self):
        assert is_tool_allowed("onboarding_agent", "search_candidates") is False

    # Helpdesk agent
    def test_helpdesk_agent_can_search_policies(self):
        assert is_tool_allowed("helpdesk_agent", "search_policies") is True

    def test_helpdesk_agent_can_escalate_ticket(self):
        assert is_tool_allowed("helpdesk_agent", "escalate_ticket") is True

    def test_helpdesk_agent_cannot_send_email(self):
        assert is_tool_allowed("helpdesk_agent", "send_email") is False

    # Compliance agent
    def test_compliance_agent_can_get_audit_logs(self):
        assert is_tool_allowed("compliance_agent", "get_audit_logs") is True

    def test_compliance_agent_can_export_data(self):
        assert is_tool_allowed("compliance_agent", "export_data") is True

    def test_compliance_agent_cannot_parse_resume(self):
        assert is_tool_allowed("compliance_agent", "parse_resume") is False

    # Unknown agent
    def test_unknown_agent_has_no_tools(self):
        assert is_tool_allowed("unknown_agent", "send_email") is False

    def test_unknown_agent_any_tool_denied(self):
        assert is_tool_allowed("nonexistent", "parse_resume") is False
