"""
Plan Execution Engine.
Actually executes the multi-step plans created by the planner,
enforcing approval checkpoints and tracking step progress.
"""

from typing import Optional
from agents.base_agent import AgentContext, AgentResponse
from orchestrator.planner import ExecutionPlan, PlanStep
from security.audit import log_agent_action
import structlog

logger = structlog.get_logger()


class PlanExecutor:
    """
    Executes multi-step execution plans with:
    - Sequential step processing
    - Approval checkpoint enforcement
    - Step status tracking
    - Error handling with graceful degradation
    - Audit logging per step
    """

    def __init__(self, agents: dict):
        self._agents = agents

    async def execute(
        self,
        plan: ExecutionPlan,
        user_input: str,
        context: AgentContext,
    ) -> AgentResponse:
        """
        Execute a plan step by step.
        Returns combined response from all steps.
        Stops at approval checkpoints or errors.
        """
        combined_response = AgentResponse()
        step_results = []

        logger.info(
            "plan_execution_started",
            plan_name=plan.name,
            total_steps=len(plan.steps),
            risk_level=plan.risk_level,
            request_id=getattr(context, 'request_id', None),
        )

        for step in plan.steps:
            plan.current_step = step.step_number

            # Check if step requires approval
            if step.requires_approval:
                step.status = "awaiting_approval"
                combined_response.requires_approval = True
                combined_response.approval_action = {
                    "step": step.step_number,
                    "action": step.action,
                    "agent": step.agent,
                    "description": step.description,
                    "tools": step.tools,
                }
                logger.info(
                    "plan_step_needs_approval",
                    step=step.step_number,
                    action=step.action,
                )
                # Don't stop completely - execute up to this point, then pause
                break

            # Execute the step
            step.status = "executing"
            agent = self._agents.get(step.agent)

            if not agent:
                step.status = "failed"
                step.result = f"Agent '{step.agent}' not available"
                logger.warning("plan_step_agent_missing", agent=step.agent)
                continue

            try:
                step_response = await agent.process(user_input, context)
                step.status = "completed"
                step.result = step_response.message[:500]

                step_results.append({
                    "step": step.step_number,
                    "action": step.action,
                    "agent": step.agent,
                    "status": "completed",
                    "description": step.description,
                })

                # Merge actions taken
                combined_response.actions_taken.extend(step_response.actions_taken)

                # If any step requires approval, bubble it up
                if step_response.requires_approval:
                    combined_response.requires_approval = True
                    combined_response.approval_action = step_response.approval_action
                    break

                # If any step escalates, bubble it up
                if step_response.escalated:
                    combined_response.escalated = True
                    combined_response.escalation_reason = step_response.escalation_reason
                    combined_response.message = step_response.message
                    break

                # Use the last successful step's message as the final message
                combined_response.message = step_response.message

                # Audit log per step
                if context.db:
                    await log_agent_action(
                        context.db,
                        tenant_id=context.tenant_id,
                        user_id=context.user_id,
                        user_role=context.user_role.value,
                        agent_name=step.agent,
                        action=f"plan_step.{step.action}",
                        input_text=user_input[:200],
                        output_text=step_response.message[:200],
                        tools_used=[a["tool"] for a in step_response.actions_taken],
                        status="success",
                    )

            except Exception as e:
                step.status = "failed"
                step.result = str(e)
                logger.error(
                    "plan_step_failed",
                    step=step.step_number,
                    agent=step.agent,
                    error=str(e),
                )

                # For single-step plans, propagate the error
                if len(plan.steps) == 1:
                    raise

                # For multi-step, log and continue to next step
                step_results.append({
                    "step": step.step_number,
                    "action": step.action,
                    "agent": step.agent,
                    "status": "failed",
                    "error": str(e)[:200],
                })
                continue

        # Attach plan execution metadata to sources
        combined_response.sources.append({
            "plan_name": plan.name,
            "risk_level": plan.risk_level,
            "steps_total": len(plan.steps),
            "steps_completed": sum(1 for s in plan.steps if s.status == "completed"),
            "steps_detail": step_results,
        })

        logger.info(
            "plan_execution_finished",
            plan_name=plan.name,
            steps_completed=sum(1 for s in plan.steps if s.status == "completed"),
            steps_failed=sum(1 for s in plan.steps if s.status == "failed"),
        )

        return combined_response
