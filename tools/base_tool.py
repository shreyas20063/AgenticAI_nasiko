"""
Base tool interface. All tools inherit from this.
Enforces structured input/output and audit trail.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None
    tool_name: str = ""


class BaseTool(ABC):
    """Base class for all tool connectors."""

    name: str = "base_tool"
    description: str = "Base tool"
    requires_approval: bool = False

    @abstractmethod
    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        """
        Execute the tool action.

        Args:
            parameters: Tool-specific parameters
            context: Request context (tenant_id, user_id, user_role)

        Returns:
            ToolResult with success/failure and data
        """
        pass

    def get_schema(self) -> dict:
        """Return JSON schema for tool parameters (for LLM function calling)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {},
        }

    async def _log_execution(self, parameters: dict, result: ToolResult, context: dict):
        logger.info(
            "tool_executed",
            tool=self.name,
            success=result.success,
            tenant_id=context.get("tenant_id"),
            user_id=context.get("user_id"),
        )
