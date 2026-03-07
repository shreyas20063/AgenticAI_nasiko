"""
Onboarding Agent - manages new hire onboarding workflows.
"""

from agents.base_agent import BaseAgent, AgentContext, AgentResponse
from agents.onboarding.prompts import ONBOARDING_SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE
from tools.onboarding_tools import CreateOnboardingPlanTool, UpdateTaskStatusTool, AssignTaskTool
from security.prompt_guard import validate_user_input
import json
import structlog

logger = structlog.get_logger()

# Standard onboarding task templates by department
ONBOARDING_TEMPLATES = {
    "engineering": [
        {"title": "Complete tax and banking forms", "category": "documentation", "due_day": -3, "order": 1},
        {"title": "Sign NDA and employment agreement", "category": "documentation", "due_day": -3, "order": 2},
        {"title": "Submit ID verification documents", "category": "documentation", "due_day": -1, "order": 3},
        {"title": "Set up laptop and dev environment", "category": "setup", "due_day": 1, "order": 4},
        {"title": "Attend orientation session", "category": "meeting", "due_day": 1, "order": 5},
        {"title": "Meet your team and manager", "category": "meeting", "due_day": 1, "order": 6},
        {"title": "Complete security training", "category": "training", "due_day": 3, "order": 7},
        {"title": "Set up code repository access", "category": "setup", "due_day": 3, "order": 8},
        {"title": "Complete HR policy review", "category": "training", "due_day": 5, "order": 9},
        {"title": "First 1:1 with manager", "category": "meeting", "due_day": 5, "order": 10},
        {"title": "30-day check-in survey", "category": "meeting", "due_day": 30, "order": 11},
    ],
    "default": [
        {"title": "Complete tax and banking forms", "category": "documentation", "due_day": -3, "order": 1},
        {"title": "Sign NDA and employment agreement", "category": "documentation", "due_day": -3, "order": 2},
        {"title": "Submit ID verification documents", "category": "documentation", "due_day": -1, "order": 3},
        {"title": "Attend orientation session", "category": "meeting", "due_day": 1, "order": 4},
        {"title": "Meet your team and manager", "category": "meeting", "due_day": 1, "order": 5},
        {"title": "Complete security training", "category": "training", "due_day": 3, "order": 6},
        {"title": "Complete HR policy review", "category": "training", "due_day": 5, "order": 7},
        {"title": "First 1:1 with manager", "category": "meeting", "due_day": 5, "order": 8},
        {"title": "30-day check-in survey", "category": "meeting", "due_day": 30, "order": 9},
    ],
}


class OnboardingAgent(BaseAgent):
    name = "onboarding_agent"
    description = "Manages new hire onboarding workflows and task tracking"
    system_prompt = ONBOARDING_SYSTEM_PROMPT

    def __init__(self):
        super().__init__()
        self.available_tools = {
            "create_onboarding_plan": CreateOnboardingPlanTool(),
            "update_task_status": UpdateTaskStatusTool(),
            "assign_task": AssignTaskTool(),
        }

    async def process(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Process onboarding-related requests using real tools."""
        # Build rich context for the LLM
        templates_info = json.dumps(
            {dept: [t["title"] for t in tasks] for dept, tasks in ONBOARDING_TEMPLATES.items()},
            indent=2,
        )

        plans_context = ""
        if context.db:
            try:
                from sqlalchemy import select
                from models.onboarding import OnboardingPlan, OnboardingTask
                from models.employee import Employee

                result = await context.db.execute(
                    select(Employee).where(Employee.tenant_id == context.tenant_id)
                )
                employees = result.scalars().all()

                result = await context.db.execute(
                    select(OnboardingPlan).where(OnboardingPlan.tenant_id == context.tenant_id)
                )
                plans = result.scalars().all()

                if employees:
                    plans_context += "\n**Current Employees (use their ID for tool calls):**\n"
                    for emp in employees:
                        plans_context += (
                            f"- ID: {emp.id} | {emp.full_name} | {emp.department} | {emp.title} | "
                            f"Started: {emp.start_date} | Onboarding: {'Complete' if emp.onboarding_complete else 'In Progress'}\n"
                        )

                if plans:
                    plans_context += "\n**Active Onboarding Plans:**\n"
                    for plan in plans:
                        plans_context += (
                            f"- Plan ID: {plan.id} | Employee: {plan.employee_id} | "
                            f"Progress: {plan.progress_pct}% | Status: {plan.status}\n"
                        )
                        for task in plan.tasks:
                            status_mark = "[x]" if task.is_completed else "[ ]"
                            plans_context += f"  {status_mark} Task ID: {task.id} | Day {task.due_day}: {task.title}\n"
            except Exception as e:
                logger.warning("onboarding_db_fetch_failed", error=str(e))

        extra_context = (
            f"AVAILABLE ONBOARDING TEMPLATES:\n{templates_info}\n\n"
            f"CURRENT DATA:\n{plans_context or 'No active onboarding plans yet.'}\n\n"
            f"You have tools to CREATE onboarding plans, UPDATE task status, and ASSIGN tasks. "
            f"Use the employee IDs and task IDs from the data above when calling tools. "
            f"If the user wants to create a plan, call create_onboarding_plan with the employee_id."
        )

        return await self._process_with_tools(user_input, context, extra_context=extra_context)

    def get_template(self, department: str) -> list[dict]:
        """Get onboarding task template for a department."""
        return ONBOARDING_TEMPLATES.get(
            department.lower(),
            ONBOARDING_TEMPLATES["default"]
        )
