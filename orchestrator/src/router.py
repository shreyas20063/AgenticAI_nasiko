"""Intent classification and routing for HR queries.

Routes user messages to the correct sub-agent based on role + intent.
Uses deterministic keyword rules (90%+ coverage) with employee_services fallback.
NO LLM is used for routing — this is pure Python logic.
"""

import logging
import re
from typing import Tuple

logger = logging.getLogger("orchestrator.router")

# ── Agent target constants ──────────────────────────────────────

RECRUITMENT = "recruitment"
EMPLOYEE_SERVICES = "employee_services"
ANALYTICS = "analytics"

# ── Role-based default routing ──────────────────────────────────
# These roles have unambiguous default agents.
# Keywords can still override (e.g., CEO asking about hiring).

ROLE_DEFAULTS = {
    "ceo": ANALYTICS,
    "applicant": RECRUITMENT,
}

# ── Keyword → agent mapping ────────────────────────────────────
# Checked in order: first match wins.
# Recruitment and Analytics checked before Employee Services (broadest).

KEYWORD_RULES = [
    # Recruitment keywords
    (
        [
            "resume", "candidate", "applicant", "hiring", "recruit",
            "interview", "offer letter", "rejection", "job opening",
            "vacancy", "screen", "shortlist", "application status",
            "application", "job position",
        ],
        RECRUITMENT,
    ),
    # Analytics keywords
    (
        [
            "headcount", "attrition", "turnover", "metrics", "analytics",
            "dashboard", "insights", "company health", "department stats",
            "workforce", "hiring pipeline", "kpi", "overview", "report",
            "company doing", "company overview",
        ],
        ANALYTICS,
    ),
    # Employee Services keywords (broadest — check last)
    (
        [
            "leave", "policy", "payslip", "salary slip", "ticket",
            "complaint", "harassment", "grievance", "remote work",
            "benefits", "insurance", "dress code", "pto", "sick",
            "vacation", "parental", "onboarding", "expense",
            "reimbursement", "approve", "reject", "pending",
        ],
        EMPLOYEE_SERVICES,
    ),
]

# ── Role extraction regex ───────────────────────────────────────
# Matches: "Role: EMPLOYEE (EMP-001). ..." or "Role: CEO. ..."
_ROLE_PATTERN = re.compile(
    r"^Role:\s*(\w+)(?:\s*\(([^)]+)\))?\s*\.?\s*(?:Request:\s*)?(.*)",
    re.IGNORECASE | re.DOTALL,
)


def extract_role_from_message(text: str) -> Tuple[str, str, str]:
    """Extract role, user ID, and clean message from prefixed text.

    Expected format: "Role: EMPLOYEE (EMP-001). What is the remote work policy?"
    Also handles: "Role: CEO. How is the company doing?"

    Returns:
        (role, user_id, clean_message)
        Defaults to ("employee", "unknown", original_text) if no prefix found.
    """
    match = _ROLE_PATTERN.match(text.strip())
    if match:
        role = match.group(1).strip()
        user_id = match.group(2).strip() if match.group(2) else "unknown"
        clean_message = match.group(3).strip()
        logger.info(f"[ROUTER] Extracted role={role}, user_id={user_id}")
        return role, user_id, clean_message

    logger.info("[ROUTER] No role prefix found, defaulting to EMPLOYEE")
    return "employee", "unknown", text.strip()


def classify_intent(user_message: str, role: str) -> Tuple[str, str]:
    """Classify which sub-agent should handle this request.

    Strategy:
    1. If role has an unambiguous default (CEO→analytics, applicant→recruitment),
       check keywords first for override, else use role default.
    2. For other roles, use keyword matching (first match wins).
    3. Fallback to employee_services (broadest coverage).

    Returns:
        (agent_key, reasoning) — e.g., ("analytics", "role_default:ceo")
    """
    msg_lower = user_message.lower()

    # Step 1: Role-based defaults with keyword override
    if role.lower() in ROLE_DEFAULTS:
        default = ROLE_DEFAULTS[role.lower()]
        # Still check keywords — CEO might ask about hiring specifically
        for keywords, agent in KEYWORD_RULES:
            matched = [kw for kw in keywords if kw in msg_lower]
            if matched:
                logger.info(
                    f"[ROUTER] Role={role} | Keyword override: "
                    f"'{matched[0]}' \u2192 {agent}"
                )
                return agent, f"keyword_match:{matched[0]}"
        logger.info(f"[ROUTER] Role={role} | Using role default \u2192 {default}")
        return default, f"role_default:{role.lower()}"

    # Step 2: Keyword matching for all other roles
    for keywords, agent in KEYWORD_RULES:
        matched = [kw for kw in keywords if kw in msg_lower]
        if matched:
            logger.info(
                f"[ROUTER] Role={role} | Keyword match: "
                f"'{matched[0]}' \u2192 {agent}"
            )
            return agent, f"keyword_match:{matched[0]}"

    # Step 3: Fallback — employee services has broadest coverage
    logger.info(
        f"[ROUTER] Role={role} | No keyword match, "
        f"falling back to {EMPLOYEE_SERVICES}"
    )
    return EMPLOYEE_SERVICES, "fallback:no_keyword_match"


def build_contextualized_message(
    original_message: str, role: str, user_id: str = "unknown"
) -> str:
    """Inject role context into the message before forwarding to sub-agent.

    The sub-agent sees WHO is asking and adjusts response by permission level.
    """
    return f"Role: {role.upper()} (ID: {user_id}). Request: {original_message}"
