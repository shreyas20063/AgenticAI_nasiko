"""Helpdesk ticket schemas."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class TicketCreate(BaseModel):
    subject: str
    category: Optional[str] = None
    message: str = Field(..., min_length=1)


class TicketResponse(BaseModel):
    id: str
    subject: str
    category: Optional[str]
    status: str
    priority: str
    is_sensitive: bool
    is_auto_resolved: bool
    messages: list[dict] = []
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class TicketMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
