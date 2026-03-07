"""Unit tests for the Tool Call Guardrails module."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security.tool_guardrails import (
    validate_tool_call,
    GuardrailResult,
    APPROVAL_REQUIRED_TOOLS,
    _tool_call_counts,
)
from models.user import Role


# ============================================================
# Helpers
# ============================================================


TENANT_ID = "tenant-abc-123"


def _clear_rate_limits():
    """Reset the in-memory rate limit counters between tests."""
    _tool_call_counts.clear()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Automatically clear rate limits before each test."""
    _clear_rate_limits()
    yield
    _clear_rate_limits()


# ============================================================
# Allowed tool calls pass
# ============================================================


class TestAllowedToolCalls:
    """Valid tool calls by authorized agents should pass."""

    def test_recruitment_agent_parse_resume(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="parse_resume",
            parameters={"resume_text": "Sample resume content"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True
        assert result.denial_reason is None

    def test_recruitment_agent_search_candidates(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="search_candidates",
            parameters={"query": "python developer"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True

    def test_helpdesk_agent_search_policies(self):
        result = validate_tool_call(
            agent_name="helpdesk_agent",
            tool_name="search_policies",
            parameters={"query": "remote work"},
            user_role=Role.EMPLOYEE,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True
        assert result.denial_reason is None

    def test_compliance_agent_get_audit_logs(self):
        result = validate_tool_call(
            agent_name="compliance_agent",
            tool_name="get_audit_logs",
            parameters={"date_range": "last_week"},
            user_role=Role.SECURITY_ADMIN,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True

    def test_onboarding_agent_get_onboarding_plan(self):
        result = validate_tool_call(
            agent_name="onboarding_agent",
            tool_name="get_onboarding_plan",
            parameters={"employee_id": "emp-001"},
            user_role=Role.HRBP,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True


# ============================================================
# Disallowed agent/tool combos are denied
# ============================================================


class TestDisallowedToolCalls:
    """Tool calls not in the agent's allowlist should be denied."""

    def test_recruitment_agent_cannot_get_audit_logs(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="get_audit_logs",
            parameters={},
            user_role=Role.HR_ADMIN,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "not permitted" in result.denial_reason

    def test_helpdesk_agent_cannot_send_email(self):
        result = validate_tool_call(
            agent_name="helpdesk_agent",
            tool_name="send_email",
            parameters={"to": ["a@b.com"], "subject": "Hi", "body": "Hello"},
            user_role=Role.EMPLOYEE,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "helpdesk_agent" in result.denial_reason

    def test_onboarding_agent_cannot_search_candidates(self):
        result = validate_tool_call(
            agent_name="onboarding_agent",
            tool_name="search_candidates",
            parameters={"query": "test"},
            user_role=Role.HRBP,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False

    def test_compliance_agent_cannot_parse_resume(self):
        result = validate_tool_call(
            agent_name="compliance_agent",
            tool_name="parse_resume",
            parameters={"resume_text": "content"},
            user_role=Role.SECURITY_ADMIN,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False

    def test_unknown_agent_denied(self):
        result = validate_tool_call(
            agent_name="unknown_agent",
            tool_name="send_email",
            parameters={"to": ["x@y.com"], "subject": "Hi", "body": "Hello"},
            user_role=Role.HR_ADMIN,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "not permitted" in result.denial_reason


# ============================================================
# Required parameters are enforced
# ============================================================


class TestRequiredParameters:
    """Tools with required parameters should fail when they are missing."""

    def test_send_email_missing_to(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={"subject": "Hi", "body": "Hello"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "to" in result.denial_reason

    def test_send_email_missing_subject(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={"to": ["a@b.com"], "body": "Hello"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "subject" in result.denial_reason

    def test_send_email_missing_body(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={"to": ["a@b.com"], "subject": "Hi"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "body" in result.denial_reason

    def test_send_email_empty_to(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={"to": "", "subject": "Hi", "body": "Hello"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "to" in result.denial_reason

    def test_update_candidate_status_missing_candidate_id(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="update_candidate_status",
            parameters={"new_status": "screened"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "candidate_id" in result.denial_reason

    def test_update_candidate_status_missing_new_status(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="update_candidate_status",
            parameters={"candidate_id": "c-001"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "new_status" in result.denial_reason

    def test_update_candidate_status_with_valid_params(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="update_candidate_status",
            parameters={"candidate_id": "c-001", "new_status": "screened"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True

    def test_update_candidate_status_invalid_status_value(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="update_candidate_status",
            parameters={"candidate_id": "c-001", "new_status": "invalid_status"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "invalid_status" in result.denial_reason.lower()


# ============================================================
# Email recipient limits
# ============================================================


class TestEmailRecipientLimits:
    """Send email should enforce the maximum number of recipients."""

    def test_within_recipient_limit(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={
                "to": ["a@b.com", "c@d.com", "e@f.com"],
                "subject": "Update",
                "body": "Details here",
            },
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True

    def test_at_exact_recipient_limit(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={
                "to": ["a@b.com", "c@d.com", "e@f.com", "g@h.com", "i@j.com"],
                "subject": "Update",
                "body": "Details here",
            },
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True

    def test_exceeds_recipient_limit(self):
        recipients = [f"user{i}@test.com" for i in range(10)]
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={
                "to": recipients,
                "subject": "Mass email",
                "body": "Hello all",
            },
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "Too many email recipients" in result.denial_reason
        assert "10" in result.denial_reason

    def test_six_recipients_exceeds_limit(self):
        recipients = [f"user{i}@test.com" for i in range(6)]
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={
                "to": recipients,
                "subject": "Update",
                "body": "Info",
            },
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False

    def test_string_recipient_not_checked_as_list(self):
        # When 'to' is a string (not a list), the list length check is skipped
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={
                "to": "single@test.com",
                "subject": "Update",
                "body": "Details",
            },
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True


# ============================================================
# Approval-required tools are flagged
# ============================================================


class TestApprovalRequiredTools:
    """Tools that need human approval should set requires_approval."""

    def test_send_email_requires_approval(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="send_email",
            parameters={"to": ["a@b.com"], "subject": "Hi", "body": "Hello"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True
        assert result.requires_approval is True
        assert any("approval" in w.lower() for w in result.warnings)

    def test_schedule_interview_requires_approval(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="schedule_interview",
            parameters={"candidate_id": "c-001", "time": "2025-01-01T10:00:00"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.requires_approval is True

    def test_export_data_requires_approval(self):
        result = validate_tool_call(
            agent_name="compliance_agent",
            tool_name="export_data",
            parameters={"resource_type": "audit_logs"},
            user_role=Role.SECURITY_ADMIN,
            tenant_id=TENANT_ID,
        )
        assert result.requires_approval is True

    def test_anonymize_data_requires_approval(self):
        result = validate_tool_call(
            agent_name="compliance_agent",
            tool_name="anonymize_data",
            parameters={"resource_id": "emp-999"},
            user_role=Role.SECURITY_ADMIN,
            tenant_id=TENANT_ID,
        )
        assert result.requires_approval is True

    def test_non_approval_tool_does_not_flag(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="parse_resume",
            parameters={"resume_text": "content"},
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.requires_approval is False
        assert len(result.warnings) == 0

    def test_search_policies_does_not_require_approval(self):
        result = validate_tool_call(
            agent_name="helpdesk_agent",
            tool_name="search_policies",
            parameters={"query": "leave policy"},
            user_role=Role.EMPLOYEE,
            tenant_id=TENANT_ID,
        )
        assert result.requires_approval is False


# ============================================================
# GuardrailResult class
# ============================================================


class TestGuardrailResult:
    """Tests for the GuardrailResult data class."""

    def test_default_state(self):
        result = GuardrailResult()
        assert result.allowed is True
        assert result.requires_approval is False
        assert result.denial_reason is None
        assert result.warnings == []

    def test_deny_sets_fields(self):
        result = GuardrailResult()
        result.deny("not allowed")
        assert result.allowed is False
        assert result.denial_reason == "not allowed"

    def test_require_approval_sets_fields(self):
        result = GuardrailResult()
        result.require_approval("needs human review")
        assert result.requires_approval is True
        assert "needs human review" in result.warnings

    def test_deny_does_not_change_approval(self):
        result = GuardrailResult()
        result.deny("blocked")
        assert result.requires_approval is False


# ============================================================
# Cross-tenant isolation
# ============================================================


class TestCrossTenantIsolation:
    """Ensure cross-tenant data access is denied."""

    def test_matching_tenant_allowed(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="update_candidate_status",
            parameters={
                "candidate_id": "c-001",
                "new_status": "screened",
                "tenant_id": TENANT_ID,
            },
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is True

    def test_mismatched_tenant_denied(self):
        result = validate_tool_call(
            agent_name="recruitment_agent",
            tool_name="update_candidate_status",
            parameters={
                "candidate_id": "c-001",
                "new_status": "screened",
                "tenant_id": "other-tenant-999",
            },
            user_role=Role.RECRUITER,
            tenant_id=TENANT_ID,
        )
        assert result.allowed is False
        assert "Cross-tenant" in result.denial_reason
