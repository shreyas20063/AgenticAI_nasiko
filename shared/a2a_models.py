"""A2A JSON-RPC 2.0 Protocol Models for HRFlow AI.

Pydantic v2 models matching Google A2A protocol spec.
All JSON field names use camelCase per A2A requirement.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────


class MessagePart(BaseModel):
    kind: str = "text"
    text: Optional[str] = None


class Message(BaseModel):
    role: str
    parts: List[MessagePart]
    messageId: Optional[str] = Field(default_factory=lambda: str(uuid4()))


class JsonRpcParams(BaseModel):
    message: Message
    session_id: Optional[str] = None


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    method: str = "message/send"
    params: JsonRpcParams


# ── Response Models ─────────────────────────────────────────────


class TaskStatus(BaseModel):
    state: str  # "completed" | "working" | "failed"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ArtifactPart(BaseModel):
    kind: str = "text"
    text: str


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: str = "text"
    parts: List[ArtifactPart]


class Task(BaseModel):
    id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:8]}")
    kind: str = "task"
    status: TaskStatus
    artifacts: List[Artifact] = []
    contextId: Optional[str] = None


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    result: Task


class JsonRpcError(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    error: dict  # {"code": int, "message": str}


# ── Helpers ─────────────────────────────────────────────────────


def create_completed_task(response_text: str, request_id: str) -> JsonRpcResponse:
    """Build a complete JsonRpcResponse from just the agent's text output."""
    return JsonRpcResponse(
        id=request_id,
        result=Task(
            status=TaskStatus(state="completed"),
            artifacts=[
                Artifact(parts=[ArtifactPart(text=response_text)])
            ],
        ),
    )


def create_failed_task(error_text: str, request_id: str) -> JsonRpcResponse:
    """Build a failed JsonRpcResponse for error cases."""
    return JsonRpcResponse(
        id=request_id,
        result=Task(
            status=TaskStatus(state="failed"),
            artifacts=[
                Artifact(parts=[ArtifactPart(text=error_text)])
            ],
        ),
    )
