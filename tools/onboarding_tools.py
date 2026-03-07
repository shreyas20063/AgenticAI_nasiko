"""
Onboarding tools - create plans, manage tasks, track progress.
These are REAL tools that persist to the database.
"""

from tools.base_tool import BaseTool, ToolResult
from datetime import datetime, timedelta
import uuid
import structlog

logger = structlog.get_logger()


class CreateOnboardingPlanTool(BaseTool):
    name = "create_onboarding_plan"
    description = "Create a new onboarding plan for an employee from a department template"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        employee_id = parameters.get("employee_id")
        template_name = parameters.get("template_name", "default")
        target_days = parameters.get("target_days", 30)

        if not employee_id:
            return ToolResult(
                success=False,
                error="employee_id is required",
                tool_name=self.name,
            )

        try:
            from database import async_session_factory
            from sqlalchemy import select
            from models.employee import Employee
            from models.onboarding import OnboardingPlan, OnboardingTask

            # Import templates from the agent
            from agents.onboarding.agent import ONBOARDING_TEMPLATES

            async with async_session_factory() as db:
                tenant_id = context.get("tenant_id")

                # Verify employee exists
                result = await db.execute(
                    select(Employee).where(
                        Employee.id == employee_id,
                        Employee.tenant_id == tenant_id,
                    )
                )
                employee = result.scalar_one_or_none()
                if not employee:
                    return ToolResult(
                        success=False,
                        error=f"Employee {employee_id} not found",
                        tool_name=self.name,
                    )

                # Check for existing active plan
                existing = await db.execute(
                    select(OnboardingPlan).where(
                        OnboardingPlan.employee_id == employee_id,
                        OnboardingPlan.status == "active",
                    )
                )
                if existing.scalar_one_or_none():
                    return ToolResult(
                        success=False,
                        error=f"Employee {employee.full_name} already has an active onboarding plan",
                        tool_name=self.name,
                    )

                # Get template tasks
                dept_key = employee.department.lower() if employee.department else "default"
                template_tasks = ONBOARDING_TEMPLATES.get(dept_key, ONBOARDING_TEMPLATES["default"])

                now = datetime.utcnow()
                plan_id = str(uuid.uuid4())
                plan = OnboardingPlan(
                    id=plan_id,
                    tenant_id=tenant_id,
                    employee_id=employee_id,
                    template_name=template_name or f"{dept_key}_onboarding",
                    status="active",
                    progress_pct=0,
                    started_at=now,
                    target_completion=now + timedelta(days=target_days),
                )
                db.add(plan)

                created_tasks = []
                for task_def in template_tasks:
                    task = OnboardingTask(
                        id=str(uuid.uuid4()),
                        plan_id=plan_id,
                        title=task_def["title"],
                        category=task_def.get("category", "general"),
                        due_day=task_def.get("due_day", 1),
                        order=task_def.get("order", 0),
                        is_completed=False,
                    )
                    db.add(task)
                    created_tasks.append(task_def["title"])

                # Update employee status
                employee.onboarding_complete = False

                await db.commit()

                logger.info(
                    "onboarding_plan_created",
                    plan_id=plan_id,
                    employee=employee.full_name,
                    tasks=len(created_tasks),
                    tenant_id=tenant_id,
                )

                return ToolResult(
                    success=True,
                    data={
                        "plan_id": plan_id,
                        "employee_name": employee.full_name,
                        "department": employee.department,
                        "template": template_name or f"{dept_key}_onboarding",
                        "tasks_created": len(created_tasks),
                        "task_titles": created_tasks,
                        "target_completion": (now + timedelta(days=target_days)).isoformat(),
                        "message": f"Onboarding plan created for {employee.full_name} with {len(created_tasks)} tasks",
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("create_onboarding_plan_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to create onboarding plan: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string", "description": "The employee ID to create an onboarding plan for"},
                    "template_name": {"type": "string", "description": "Template name (e.g., 'engineering', 'default')"},
                    "target_days": {"type": "integer", "description": "Target number of days to complete onboarding (default: 30)"},
                },
                "required": ["employee_id"],
            },
        }


class UpdateTaskStatusTool(BaseTool):
    name = "update_task_status"
    description = "Mark an onboarding task as complete or incomplete, and update plan progress"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        task_id = parameters.get("task_id")
        is_completed = parameters.get("is_completed", True)
        notes = parameters.get("notes")

        if not task_id:
            return ToolResult(
                success=False,
                error="task_id is required",
                tool_name=self.name,
            )

        try:
            from database import async_session_factory
            from sqlalchemy import select
            from models.onboarding import OnboardingPlan, OnboardingTask

            async with async_session_factory() as db:
                result = await db.execute(
                    select(OnboardingTask).where(OnboardingTask.id == task_id)
                )
                task = result.scalar_one_or_none()

                if not task:
                    return ToolResult(
                        success=False,
                        error=f"Task {task_id} not found",
                        tool_name=self.name,
                    )

                old_status = task.is_completed
                task.is_completed = is_completed
                task.completed_at = datetime.utcnow() if is_completed else None
                task.completed_by = context.get("user_id")
                if notes:
                    task.notes = notes

                # Update plan progress
                plan_result = await db.execute(
                    select(OnboardingTask).where(OnboardingTask.plan_id == task.plan_id)
                )
                all_tasks = plan_result.scalars().all()
                total = len(all_tasks)
                completed = sum(1 for t in all_tasks if t.is_completed)
                progress = int((completed / total) * 100) if total > 0 else 0

                plan_result2 = await db.execute(
                    select(OnboardingPlan).where(OnboardingPlan.id == task.plan_id)
                )
                plan = plan_result2.scalar_one_or_none()
                if plan:
                    plan.progress_pct = progress
                    if progress == 100:
                        plan.status = "completed"
                        plan.completed_at = datetime.utcnow()

                await db.commit()

                logger.info(
                    "onboarding_task_updated",
                    task_id=task_id,
                    task_title=task.title,
                    completed=is_completed,
                    plan_progress=progress,
                )

                return ToolResult(
                    success=True,
                    data={
                        "task_id": task_id,
                        "task_title": task.title,
                        "is_completed": is_completed,
                        "plan_progress": progress,
                        "total_tasks": total,
                        "completed_tasks": completed,
                        "plan_status": plan.status if plan else "unknown",
                        "message": f"Task '{task.title}' marked as {'complete' if is_completed else 'incomplete'}. Plan progress: {progress}%",
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("update_task_status_failed", error=str(e), task_id=task_id)
            return ToolResult(
                success=False,
                error=f"Failed to update task: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The onboarding task ID to update"},
                    "is_completed": {"type": "boolean", "description": "Whether the task is complete (default: true)"},
                    "notes": {"type": "string", "description": "Optional notes about the task completion"},
                },
                "required": ["task_id"],
            },
        }


class AssignTaskTool(BaseTool):
    name = "assign_task"
    description = "Assign an onboarding task to a specific user (e.g., buddy, manager, IT)"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        task_id = parameters.get("task_id")
        assignee_id = parameters.get("assignee_id")

        if not task_id or not assignee_id:
            return ToolResult(
                success=False,
                error="task_id and assignee_id are required",
                tool_name=self.name,
            )

        try:
            from database import async_session_factory
            from sqlalchemy import select
            from models.onboarding import OnboardingTask
            from models.user import User

            async with async_session_factory() as db:
                # Verify task
                result = await db.execute(
                    select(OnboardingTask).where(OnboardingTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if not task:
                    return ToolResult(
                        success=False,
                        error=f"Task {task_id} not found",
                        tool_name=self.name,
                    )

                # Verify assignee
                user_result = await db.execute(
                    select(User).where(User.id == assignee_id)
                )
                assignee = user_result.scalar_one_or_none()
                assignee_name = assignee.full_name if assignee else "Unknown User"

                task.assigned_to = assignee_id
                await db.commit()

                logger.info(
                    "onboarding_task_assigned",
                    task_id=task_id,
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                )

                return ToolResult(
                    success=True,
                    data={
                        "task_id": task_id,
                        "task_title": task.title,
                        "assignee_id": assignee_id,
                        "assignee_name": assignee_name,
                        "message": f"Task '{task.title}' assigned to {assignee_name}",
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("assign_task_failed", error=str(e), task_id=task_id)
            return ToolResult(
                success=False,
                error=f"Failed to assign task: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The onboarding task ID to assign"},
                    "assignee_id": {"type": "string", "description": "User ID of the person to assign the task to"},
                },
                "required": ["task_id", "assignee_id"],
            },
        }
