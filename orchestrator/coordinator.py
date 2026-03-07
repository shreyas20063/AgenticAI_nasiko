"""
Coordinator Agent - the central brain of the HR platform.
Routes requests to specialized agents, manages multi-step workflows,
enforces guardrails, and handles human-in-the-loop approvals.
"""

from typing import Optional
from agents.base_agent import AgentContext, AgentResponse
from orchestrator.intent_detector import detect_intent, Intent
from orchestrator.planner import create_plan, ExecutionPlan
from orchestrator.plan_executor import PlanExecutor
from security.audit import log_agent_action
from security.prompt_guard import validate_user_input
import structlog

logger = structlog.get_logger()

# Lazy imports to avoid circular dependencies
_agents = {}
_executor = None


def _get_agents():
    """Lazy-load specialized agents."""
    global _agents
    if not _agents:
        from agents.recruitment.agent import RecruitmentAgent
        from agents.onboarding.agent import OnboardingAgent
        from agents.helpdesk.agent import HelpdeskAgent
        from agents.compliance.agent import ComplianceAgent

        _agents = {
            "recruitment_agent": RecruitmentAgent(),
            "onboarding_agent": OnboardingAgent(),
            "helpdesk_agent": HelpdeskAgent(),
            "compliance_agent": ComplianceAgent(),
        }
    return _agents


def _get_executor():
    """Lazy-load plan executor."""
    global _executor
    if not _executor:
        _executor = PlanExecutor(_get_agents())
    return _executor


GENERAL_RESPONSE = """I'm the Nasiko HR Platform assistant. I can help you with:

**Recruitment** - Screen resumes, rank candidates, schedule interviews
**Onboarding** - Track new hire tasks, send welcome materials, manage checklists
**HR Helpdesk** - Answer policy questions, check leave balances, handle requests
**Compliance** - Manage consent, data access requests, audit logs, bias monitoring

How can I help you today?"""


async def process_message(
    user_input: str,
    context: AgentContext,
    conversation_history: list[dict] = None,
) -> AgentResponse:
    """
    Main entry point for processing user messages.

    Flow:
    1. Validate input (prompt injection check)
    2. Detect intent
    3. Create execution plan
    4. Execute plan (routes to specialized agents with step tracking)
    5. Log and return response
    """
    response = AgentResponse()

    # Step 1: Input validation
    is_safe, sanitized, warning = validate_user_input(user_input)
    if not is_safe:
        response.message = (
            "I'm unable to process that request due to a security concern. "
            "Please rephrase your question."
        )
        if context.db:
            await log_agent_action(
                context.db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                user_role=context.user_role.value,
                agent_name="coordinator",
                action="input_blocked",
                input_text=sanitized[:200],
                output_text=warning or "Blocked",
                status="denied",
            )
        return response

    # Step 2: Detect intent (with conversation history for multi-turn awareness)
    intent, confidence, summary = await detect_intent(sanitized, conversation_history)
    logger.info(
        "request_routed",
        intent=intent.value,
        confidence=confidence,
        user_id=context.user_id,
        request_id=context.request_id,
    )

    # Step 3a: Conversation continuity bias — if the LLM classified to a DIFFERENT
    # agent than what's currently active, and confidence isn't very high, trust the
    # conversation context over the classification. This prevents follow-up questions
    # like "what happens after approval?" from being misrouted to helpdesk when the
    # user was in a recruitment conversation.
    if conversation_history and intent not in (Intent.GENERAL, Intent.UNKNOWN):
        last_agent = _get_last_agent_from_history(conversation_history)
        if last_agent:
            expected_intent = _agent_to_intent(last_agent)
            if intent != expected_intent and confidence < 0.85:
                logger.info(
                    "continuity_bias_override",
                    original_intent=intent.value,
                    original_confidence=confidence,
                    overridden_to=expected_intent.value,
                    last_agent=last_agent,
                )
                intent = expected_intent
                confidence = 0.6  # moderate confidence for context-inferred intent

    # Step 3b: Handle general/unknown intents
    if intent in (Intent.GENERAL, Intent.UNKNOWN) or confidence < 0.3:
        # If there's an active conversation, route to the last agent instead of
        # returning the generic help menu. This keeps follow-up questions like
        # "do you hallucinate?" or "explain that" in the right context.
        last_agent = _get_last_agent_from_history(conversation_history)
        if last_agent:
            intent = _agent_to_intent(last_agent)
            confidence = 0.5  # moderate confidence for context-inferred intent
            logger.info(
                "general_intent_rerouted_to_last_agent",
                last_agent=last_agent,
                inferred_intent=intent.value,
            )
        else:
            response.message = GENERAL_RESPONSE
            return response

    # Step 4: Create execution plan
    plan = await create_plan(sanitized, intent)

    # Attach conversation history to context for multi-turn support
    context.conversation_history = conversation_history or []

    # Step 5: Execute plan via PlanExecutor
    executor = _get_executor()
    try:
        response = await executor.execute(plan, sanitized, context)

        # Add routing metadata to sources
        response.sources.append({
            "agent": _intent_to_agent(intent),
            "intent": intent.value,
            "confidence": confidence,
            "plan": plan.to_dict(),
        })
    except Exception as e:
        logger.error("plan_execution_failed", error=str(e), request_id=context.request_id)
        response.message = (
            "I encountered an error processing your request. "
            "I've escalated this to our HR team for review."
        )
        response.escalated = True
        response.escalation_reason = str(e)

    # Step 6: Audit log
    if context.db:
        await log_agent_action(
            context.db,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            user_role=context.user_role.value,
            agent_name=_intent_to_agent(intent),
            action=f"{intent.value}.process",
            input_text=sanitized[:200],
            output_text=response.message[:200],
            tools_used=[a["tool"] for a in response.actions_taken],
            status="escalated" if response.escalated else "success",
        )

    return response


def _intent_to_agent(intent: Intent) -> str:
    """Map intent to agent name."""
    mapping = {
        Intent.RECRUITMENT: "recruitment_agent",
        Intent.ONBOARDING: "onboarding_agent",
        Intent.HELPDESK: "helpdesk_agent",
        Intent.COMPLIANCE: "compliance_agent",
    }
    return mapping.get(intent, "helpdesk_agent")


def _agent_to_intent(agent_name: str) -> Intent:
    """Reverse map: agent name back to intent."""
    mapping = {
        "recruitment_agent": Intent.RECRUITMENT,
        "onboarding_agent": Intent.ONBOARDING,
        "helpdesk_agent": Intent.HELPDESK,
        "compliance_agent": Intent.COMPLIANCE,
    }
    return mapping.get(agent_name, Intent.HELPDESK)


def _get_last_agent_from_history(conversation_history: list[dict] = None) -> Optional[str]:
    """
    Find the last agent used in conversation history.
    Returns None if no history or no agent found (i.e., brand new conversation).
    """
    if not conversation_history:
        return None

    # Walk backwards through history to find the most recent assistant message with an agent
    for msg in reversed(conversation_history):
        agent = msg.get("agent_used")
        if agent and msg.get("role") == "assistant":
            return agent

    return None
