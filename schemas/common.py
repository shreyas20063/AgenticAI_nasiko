"""Shared schemas used across modules."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class ChatRequest(BaseModel):
    """Main chat interaction endpoint schema."""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[str] = None
    context: Optional[dict] = None  # extra context (e.g., current page, selected job)


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    agent_used: Optional[str] = None
    actions_taken: list[dict] = []
    requires_approval: bool = False
    approval_action: Optional[dict] = None
    sources: list[dict] = []


class AgentAction(BaseModel):
    """Represents a planned or executed agent action."""
    action_type: str  # tool_call, decision, escalation, notification
    tool_name: Optional[str] = None
    parameters: dict = {}
    result: Optional[Any] = None
    status: str = "pending"  # pending, approved, executed, denied, failed
    requires_approval: bool = False
    explanation: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_more: bool
