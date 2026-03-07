"""Onboarding schemas."""

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class OnboardingPlanResponse(BaseModel):
    id: str
    employee_id: str
    template_name: Optional[str]
    status: str
    progress_pct: int
    tasks: list[dict] = []
    started_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OnboardingTaskUpdate(BaseModel):
    is_completed: Optional[bool] = None
    notes: Optional[str] = None
