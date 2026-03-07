"""SQLAlchemy ORM models for the HR Automation Platform."""

from models.tenant import Tenant, TenantConfig
from models.user import User, Role
from models.candidate import Candidate, CandidateSkill
from models.job import Job, JobRequirement
from models.employee import Employee
from models.onboarding import OnboardingPlan, OnboardingTask
from models.ticket import Ticket, TicketMessage
from models.audit_log import AuditLog
from models.consent import ConsentRecord
from models.policy_document import PolicyDocument
from models.conversation import ConversationMessage
from models.interview import ScheduledInterview, InterviewFeedback

__all__ = [
    "Tenant", "TenantConfig",
    "User", "Role",
    "Candidate", "CandidateSkill",
    "Job", "JobRequirement",
    "Employee",
    "OnboardingPlan", "OnboardingTask",
    "Ticket", "TicketMessage",
    "AuditLog",
    "ConsentRecord",
    "PolicyDocument",
    "ConversationMessage",
    "ScheduledInterview", "InterviewFeedback",
]
