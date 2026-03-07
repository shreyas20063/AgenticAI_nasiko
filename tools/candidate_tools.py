"""
Candidate pipeline tools - status updates, notes, and pipeline management.
"""

from tools.base_tool import BaseTool, ToolResult
import structlog

logger = structlog.get_logger()

# Valid status transitions for candidate pipeline
VALID_TRANSITIONS = {
    "new": ["screened", "rejected"],
    "screened": ["shortlisted", "rejected"],
    "shortlisted": ["interview", "rejected"],
    "interview": ["offered", "rejected"],
    "offered": ["hired", "rejected"],
    "rejected": [],  # terminal state
    "hired": [],      # terminal state
}

# Statuses that require approval before transition
APPROVAL_REQUIRED_STATUSES = {"offered", "hired", "rejected"}


class UpdateCandidateStatusTool(BaseTool):
    name = "update_candidate_status"
    description = "Advance a candidate through the recruitment pipeline (e.g., new → screened → shortlisted → interview → offered → hired)"
    requires_approval = False  # dynamically set based on target status

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        candidate_id = parameters.get("candidate_id")
        new_status = parameters.get("new_status")
        reason = parameters.get("reason", "")

        if not candidate_id or not new_status:
            return ToolResult(
                success=False,
                error="candidate_id and new_status are required",
                tool_name=self.name,
            )

        if new_status not in VALID_TRANSITIONS and new_status not in [
            s for transitions in VALID_TRANSITIONS.values() for s in transitions
        ]:
            return ToolResult(
                success=False,
                error=f"Invalid status: {new_status}. Valid statuses: {list(VALID_TRANSITIONS.keys())}",
                tool_name=self.name,
            )

        # Get DB session from context, fallback to factory
        db = context.get("db")
        db_owned = False
        if not db:
            try:
                from database import async_session_factory
                db = async_session_factory()
                db_owned = True
                await db.__aenter__()
            except Exception:
                return ToolResult(
                    success=False,
                    error="Database session not available",
                    tool_name=self.name,
                )

        try:
            from sqlalchemy import select
            from models.candidate import Candidate

            result = await db.execute(
                select(Candidate).where(Candidate.id == candidate_id)
            )
            candidate = result.scalar_one_or_none()

            if not candidate:
                return ToolResult(
                    success=False,
                    error=f"Candidate {candidate_id} not found",
                    tool_name=self.name,
                )

            current_status = candidate.status
            allowed = VALID_TRANSITIONS.get(current_status, [])
            if new_status not in allowed:
                return ToolResult(
                    success=False,
                    error=f"Cannot transition from '{current_status}' to '{new_status}'. Allowed: {allowed}",
                    tool_name=self.name,
                )

            # Update status
            candidate.status = new_status
            await db.commit()

            logger.info(
                "candidate_status_updated",
                candidate_id=candidate_id,
                old_status=current_status,
                new_status=new_status,
                reason=reason,
                tenant_id=context.get("tenant_id"),
            )

            if db_owned:
                await db.__aexit__(None, None, None)

            return ToolResult(
                success=True,
                data={
                    "candidate_id": candidate_id,
                    "candidate_name": candidate.full_name,
                    "old_status": current_status,
                    "new_status": new_status,
                    "reason": reason,
                    "message": f"Candidate {candidate.full_name} moved from '{current_status}' to '{new_status}'",
                },
                tool_name=self.name,
            )

        except Exception as e:
            if db_owned:
                try:
                    await db.__aexit__(None, None, None)
                except Exception:
                    pass
            logger.error("candidate_status_update_failed", error=str(e), candidate_id=candidate_id)
            return ToolResult(
                success=False,
                error=f"Failed to update candidate status: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "description": "The candidate ID to update"},
                    "new_status": {
                        "type": "string",
                        "enum": ["screened", "shortlisted", "interview", "offered", "hired", "rejected"],
                        "description": "The new pipeline status",
                    },
                    "reason": {"type": "string", "description": "Reason for the status change"},
                },
                "required": ["candidate_id", "new_status"],
            },
        }
