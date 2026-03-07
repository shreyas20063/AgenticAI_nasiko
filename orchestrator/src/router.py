"""Intent classification and routing for HR queries.

Routes user messages to the correct sub-agent based on role + intent.
Uses GPT-4o to classify intent — no brittle keyword lists.
"""

import logging
import os
import re
from typing import Tuple

from openai import AsyncOpenAI

logger = logging.getLogger("orchestrator.router")

RECRUITMENT = "recruitment"
EMPLOYEE_SERVICES = "employee_services"
ANALYTICS = "analytics"

# Hard role restrictions — LLM cannot override these
ROLE_RESTRICTIONS = {
    "employee": {EMPLOYEE_SERVICES},
    "applicant": {RECRUITMENT},
}

_ROLE_PATTERN = re.compile(
    r"^Role:\s*(\w+)(?:\s*\(([^)]+)\))?\s*\.?\s*(?:Request:\s*)?(.*)",
    re.IGNORECASE | re.DOTALL,
)

_client = None


def _get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        aipipe_token = os.getenv("AIPIPE_TOKEN")
        openai_key = os.getenv("OPENAI_API_KEY")
        if aipipe_token:
            _client = AsyncOpenAI(
                api_key=aipipe_token,
                base_url="https://aipipe.org/openai/v1",
            )
        else:
            _client = AsyncOpenAI(api_key=openai_key)
    return _client


def extract_role_from_message(text: str) -> Tuple[str, str, str]:
    """Extract role, user ID, and clean message from prefixed text."""
    match = _ROLE_PATTERN.match(text.strip())
    if match:
        role = match.group(1).strip()
        user_id = match.group(2).strip() if match.group(2) else "unknown"
        clean_message = match.group(3).strip()
        logger.info(f"[ROUTER] Extracted role={role}, user_id={user_id}")
        return role, user_id, clean_message
    logger.info("[ROUTER] No role prefix found, returning 'none'")
    return "none", "unknown", text.strip()


async def classify_intent(user_message: str, role: str) -> Tuple[str, str]:
    """Use GPT-4o to classify which sub-agent should handle this request."""
    role_lower = role.lower()

    # Hard restrictions — bypass LLM for single-agent roles
    allowed = ROLE_RESTRICTIONS.get(role_lower)
    if allowed and len(allowed) == 1:
        agent = next(iter(allowed))
        logger.info(f"[ROUTER] Role={role} restricted to {agent}, skipping LLM")
        return agent, f"role_restricted:{role_lower}"

    system_prompt = (
        "You are an HR request router. Classify the request into exactly one agent:\n\n"
        "- recruitment: hiring, job openings, resume screening, candidate status, "
        "interview scheduling, offer letters\n"
        "- employee_services: leave requests, payslips, policies, IT tickets, "
        "benefits, complaints, remote work, expenses\n"
        "- analytics: headcount, attrition, turnover, department stats, "
        "workforce metrics, company overview, KPIs\n\n"
        "Reply with ONLY the agent name: recruitment, employee_services, or analytics"
    )

    try:
        client = _get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Role: {role}\nRequest: {user_message}"},
            ],
            temperature=0,
            max_tokens=10,
        )
        result = response.choices[0].message.content.strip().lower()

        if result not in {RECRUITMENT, EMPLOYEE_SERVICES, ANALYTICS}:
            logger.warning(f"[ROUTER] LLM returned unexpected '{result}', defaulting to employee_services")
            return EMPLOYEE_SERVICES, "llm_invalid_fallback"

        logger.info(f"[ROUTER] LLM classified Role={role} -> {result}")
        return result, f"llm:{result}"

    except Exception as e:
        logger.error(f"[ROUTER] LLM failed: {e}, falling back to employee_services")
        return EMPLOYEE_SERVICES, "llm_error_fallback"


def build_contextualized_message(
    original_message: str, role: str, user_id: str = "unknown"
) -> str:
    """Inject role context into the message before forwarding to sub-agent."""
    return f"Role: {role.upper()} (ID: {user_id}). Request: {original_message}"
