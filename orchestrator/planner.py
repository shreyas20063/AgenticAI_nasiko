"""
Multi-Step Workflow Planner.
Decomposes complex HR requests into structured execution plans
with approval checkpoints and agent assignments.
"""

from typing import Optional
from openai import AsyncOpenAI
from config import get_settings
from orchestrator.intent_detector import Intent
import json
import structlog

logger = structlog.get_logger()
settings = get_settings()


PLANNER_PROMPT = """You are an HR workflow planner. Given a user request and its detected intent,
create a structured execution plan.

Each step must specify:
- step_number: sequential order
- action: what to do
- agent: which agent handles it (recruitment_agent, onboarding_agent, helpdesk_agent, compliance_agent)
- tools: list of tools needed
- requires_approval: boolean - true for actions affecting real people (sending emails, making decisions, scheduling)
- description: human-readable explanation

Rules:
- Always include a compliance check step for operations involving candidate/employee data
- Insert approval checkpoints before: hiring decisions, mass communications, data exports/deletions
- Keep plans concise (max 8 steps)
- Consider data minimization: only fetch what's needed

Respond with ONLY a JSON object:
{
  "plan_name": "<descriptive name>",
  "steps": [
    {
      "step_number": 1,
      "action": "<action_name>",
      "agent": "<agent_name>",
      "tools": ["tool1", "tool2"],
      "requires_approval": false,
      "description": "<what this step does>"
    }
  ],
  "estimated_steps": <number>,
  "risk_level": "low|medium|high"
}"""


class PlanStep:
    def __init__(self, step_number: int, action: str, agent: str,
                 tools: list[str], requires_approval: bool, description: str):
        self.step_number = step_number
        self.action = action
        self.agent = agent
        self.tools = tools
        self.requires_approval = requires_approval
        self.description = description
        self.status = "pending"  # pending, executing, completed, failed, awaiting_approval
        self.result = None

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "agent": self.agent,
            "tools": self.tools,
            "requires_approval": self.requires_approval,
            "description": self.description,
            "status": self.status,
            "result": self.result,
        }


class ExecutionPlan:
    def __init__(self, name: str, steps: list[PlanStep], risk_level: str = "low"):
        self.name = name
        self.steps = steps
        self.risk_level = risk_level
        self.current_step = 0

    def to_dict(self) -> dict:
        return {
            "plan_name": self.name,
            "risk_level": self.risk_level,
            "total_steps": len(self.steps),
            "current_step": self.current_step,
            "steps": [s.to_dict() for s in self.steps],
        }


async def create_plan(
    user_input: str,
    intent: Intent,
    context: dict = None,
) -> ExecutionPlan:
    """
    Generate a multi-step execution plan for a user request.
    Falls back to simple single-step plan if LLM planning fails.
    """
    client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": (
                    f"Intent: {intent.value}\n"
                    f"User request: {user_input}\n"
                    f"Context: {json.dumps(context or {})}"
                )},
            ],
            temperature=0.2,
            max_tokens=1000,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        plan_data = json.loads(content)

        steps = [
            PlanStep(
                step_number=s["step_number"],
                action=s["action"],
                agent=s["agent"],
                tools=s.get("tools", []),
                requires_approval=s.get("requires_approval", False),
                description=s["description"],
            )
            for s in plan_data.get("steps", [])
        ]

        plan = ExecutionPlan(
            name=plan_data.get("plan_name", "HR Workflow"),
            steps=steps,
            risk_level=plan_data.get("risk_level", "low"),
        )

        logger.info(
            "plan_created",
            name=plan.name,
            steps=len(steps),
            risk_level=plan.risk_level,
        )

        return plan

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("plan_creation_fallback", error=str(e))
        return _simple_plan(intent, user_input)


def _simple_plan(intent: Intent, user_input: str) -> ExecutionPlan:
    """Fallback: single-step plan routing to the appropriate agent."""
    agent_map = {
        Intent.RECRUITMENT: "recruitment_agent",
        Intent.ONBOARDING: "onboarding_agent",
        Intent.HELPDESK: "helpdesk_agent",
        Intent.COMPLIANCE: "compliance_agent",
        Intent.GENERAL: "helpdesk_agent",
    }

    agent = agent_map.get(intent, "helpdesk_agent")

    return ExecutionPlan(
        name=f"Simple {intent.value} request",
        steps=[
            PlanStep(
                step_number=1,
                action="process_request",
                agent=agent,
                tools=[],
                requires_approval=False,
                description=f"Process user request via {agent}",
            )
        ],
        risk_level="low",
    )
