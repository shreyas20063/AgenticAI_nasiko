"""
Intent Detection Module.
Classifies user input into HR workflow categories
to route to the appropriate specialized agent.
"""

from enum import Enum
from typing import Optional
from openai import AsyncOpenAI
from config import get_settings
import json
import structlog

logger = structlog.get_logger()
settings = get_settings()


class Intent(str, Enum):
    RECRUITMENT = "recruitment"
    ONBOARDING = "onboarding"
    HELPDESK = "helpdesk"
    COMPLIANCE = "compliance"
    GENERAL = "general"
    UNKNOWN = "unknown"


INTENT_DETECTION_PROMPT = """You are an HR intent classifier. Classify the user's message into exactly one category.

Categories:
- recruitment: Anything about hiring, candidates, resumes, job postings, screening, interviews, shortlisting, job descriptions
- onboarding: New hire setup, onboarding tasks, first day, orientation, document submission, training schedules
- helpdesk: Leave balance, benefits questions, policy queries, reimbursements, payroll, HR processes, complaints
- compliance: Data privacy, consent management, audit logs, GDPR requests, data deletion, bias reports, regulatory
- general: Greetings, general questions about the platform, help requests

IMPORTANT: If conversation history is provided, use it to understand context. Follow-up questions
(e.g. "what about the top 2?", "now schedule interviews", "what happens next?") should be classified
based on the TOPIC of the conversation, not just the words in the current message. A follow-up to a
recruitment discussion stays as "recruitment", even if the message alone sounds general.

CRITICAL RULE: If the conversation history shows a specific agent was handling the conversation
(indicated by [ACTIVE_AGENT: xxx]), the follow-up message ALMOST CERTAINLY belongs to the same
category. Only reclassify if the user EXPLICITLY changes topic (e.g., "let's talk about onboarding
instead"). Ambiguous follow-ups like "what happens next?", "tell me more", "what about the top 2?",
"what happens after approval?" MUST stay in the same category as the active agent.

Respond with ONLY a JSON object: {"intent": "<category>", "confidence": <0.0-1.0>, "summary": "<brief description>"}"""


async def detect_intent(
    user_input: str,
    conversation_history: list[dict] = None,
) -> tuple[Intent, float, str]:
    """
    Classify user input into an HR workflow intent.
    Uses conversation history for multi-turn context awareness.
    Returns (intent, confidence, summary).
    """
    client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    # Build messages with conversation context for multi-turn awareness
    messages = [{"role": "system", "content": INTENT_DETECTION_PROMPT}]

    # Include last few conversation messages so the LLM knows the topic
    if conversation_history:
        # Only include the last 4 messages to keep it concise
        recent = conversation_history[-4:]
        last_agent = None
        context_parts = []
        for m in recent:
            agent_tag = ""
            if m.get("agent_used"):
                last_agent = m["agent_used"]
                agent_tag = f" (via {m['agent_used']})"
            context_parts.append(f"[{m['role']}{agent_tag}]: {m['content'][:150]}")
        context_summary = "\n".join(context_parts)

        active_note = ""
        if last_agent:
            agent_category = last_agent.replace("_agent", "")
            active_note = (
                f"\n\n[ACTIVE_AGENT: {agent_category}] - The conversation is currently "
                f"in a {agent_category} context. Keep classifying as '{agent_category}' "
                f"unless the user EXPLICITLY changes topic."
            )

        messages.append({
            "role": "system",
            "content": f"RECENT CONVERSATION CONTEXT:\n{context_summary}{active_note}\n\nNow classify the LATEST user message below:",
        })

    messages.append({"role": "user", "content": user_input})

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.1,
            max_tokens=200,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        # Handle potential markdown wrapping
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        result = json.loads(content)
        intent = Intent(result.get("intent", "unknown"))
        confidence = float(result.get("confidence", 0.5))
        summary = result.get("summary", "")

        logger.info(
            "intent_detected",
            intent=intent.value,
            confidence=confidence,
            summary=summary,
        )

        return intent, confidence, summary

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("intent_detection_fallback", error=str(e))
        return _rule_based_fallback(user_input)


def _rule_based_fallback(user_input: str) -> tuple[Intent, float, str]:
    """Rule-based fallback when LLM intent detection fails."""
    text = user_input.lower()

    recruitment_keywords = [
        "resume", "candidate", "hire", "interview", "job", "screening",
        "shortlist", "recruit", "applicant", "jd", "job description",
        "rank candidates", "parse resume",
    ]
    onboarding_keywords = [
        "onboard", "new hire", "first day", "orientation", "checklist",
        "welcome", "new employee", "joining", "start date",
    ]
    helpdesk_keywords = [
        "leave", "balance", "benefit", "policy", "reimburse", "payroll",
        "vacation", "sick day", "pto", "insurance", "complaint",
        "harassment", "question about",
    ]
    compliance_keywords = [
        "gdpr", "consent", "audit", "data request", "delete my data",
        "privacy", "retention", "bias", "compliance", "subject access",
    ]

    scores = {
        Intent.RECRUITMENT: sum(1 for k in recruitment_keywords if k in text),
        Intent.ONBOARDING: sum(1 for k in onboarding_keywords if k in text),
        Intent.HELPDESK: sum(1 for k in helpdesk_keywords if k in text),
        Intent.COMPLIANCE: sum(1 for k in compliance_keywords if k in text),
    }

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    if best_score == 0:
        return Intent.GENERAL, 0.3, "No specific HR intent detected"

    confidence = min(0.9, 0.3 + (best_score * 0.15))
    return best_intent, confidence, f"Rule-based: matched {best_score} keywords"
