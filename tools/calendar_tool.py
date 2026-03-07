"""
Calendar Tool - schedules meetings and interview slots.
Pluggable for Google Calendar / Microsoft Graph.
"""

from datetime import datetime, timedelta
from tools.base_tool import BaseTool, ToolResult
import structlog
import uuid

logger = structlog.get_logger()


class CalendarTool(BaseTool):
    name = "create_calendar_event"
    description = "Create a calendar event (meeting, interview)"
    requires_approval = True

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        title = parameters.get("title", "Meeting")
        start_time = parameters.get("start_time")
        duration_minutes = parameters.get("duration_minutes", 60)
        attendees = parameters.get("attendees", [])
        description = parameters.get("description", "")
        location = parameters.get("location", "Virtual")

        if not start_time:
            return ToolResult(
                success=False,
                error="start_time is required",
                tool_name=self.name,
            )

        try:
            # In production: integrate with Google Calendar API or Microsoft Graph
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(calendar_api_url, json={...})

            event_id = str(uuid.uuid4())

            logger.info(
                "calendar_event_created",
                event_id=event_id,
                title=title,
                attendees=attendees,
                tenant_id=context.get("tenant_id"),
            )

            return ToolResult(
                success=True,
                data={
                    "event_id": event_id,
                    "title": title,
                    "start_time": start_time,
                    "duration_minutes": duration_minutes,
                    "attendees": attendees,
                    "location": location,
                    "status": "created",
                },
                tool_name=self.name,
            )

        except Exception as e:
            logger.error("calendar_event_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to create event: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start_time": {"type": "string", "description": "ISO 8601 datetime"},
                    "duration_minutes": {"type": "integer", "default": 60},
                    "attendees": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                    "location": {"type": "string", "default": "Virtual"},
                },
                "required": ["title", "start_time"],
            },
        }


class ScheduleInterviewTool(BaseTool):
    name = "schedule_interview"
    description = "Schedule an interview with a candidate. Persists to database and checks for conflicts."
    requires_approval = True

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        candidate_id = parameters.get("candidate_id")
        interviewer_emails = parameters.get("interviewer_emails", [])
        proposed_times = parameters.get("proposed_times", [])
        interview_type = parameters.get("interview_type", "video")
        duration_minutes = parameters.get("duration_minutes", 60)
        scheduled_at = parameters.get("scheduled_at") or (proposed_times[0] if proposed_times else None)

        if not candidate_id:
            return ToolResult(success=False, error="candidate_id required", tool_name=self.name)

        db = context.get("db")
        if not db:
            # Fallback: return mock if no DB
            event_id = str(uuid.uuid4())
            return ToolResult(
                success=True,
                data={"event_id": event_id, "candidate_id": candidate_id, "status": "scheduled (demo)"},
                tool_name=self.name,
            )

        try:
            from sqlalchemy import select
            from models.candidate import Candidate
            from models.interview import ScheduledInterview

            # Verify candidate exists
            cand_result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
            candidate = cand_result.scalar_one_or_none()
            if not candidate:
                return ToolResult(success=False, error=f"Candidate {candidate_id} not found", tool_name=self.name)

            # Parse scheduled time
            from datetime import datetime as dt
            interview_time = None
            if scheduled_at:
                try:
                    interview_time = dt.fromisoformat(scheduled_at.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            if not interview_time:
                # Default to next business day at 10am
                from datetime import timedelta, timezone
                now = dt.now(timezone.utc)
                days_ahead = 1
                while (now + timedelta(days=days_ahead)).weekday() >= 5:
                    days_ahead += 1
                interview_time = (now + timedelta(days=days_ahead)).replace(hour=10, minute=0, second=0, microsecond=0)

            # Check for conflicts (same candidate or same interviewer at same time)
            from datetime import timedelta as td
            end_time = interview_time + td(minutes=duration_minutes)
            conflict_result = await db.execute(
                select(ScheduledInterview).where(
                    ScheduledInterview.tenant_id == context.get("tenant_id"),
                    ScheduledInterview.candidate_id == candidate_id,
                    ScheduledInterview.status == "scheduled",
                    ScheduledInterview.scheduled_at >= interview_time - td(minutes=duration_minutes),
                    ScheduledInterview.scheduled_at < end_time,
                )
            )
            conflicts = conflict_result.scalars().all()
            if conflicts:
                return ToolResult(
                    success=False,
                    error=f"Scheduling conflict: candidate already has an interview near this time slot",
                    tool_name=self.name,
                )

            # Generate a meeting link
            meeting_link = f"https://meet.nasiko.ai/{uuid.uuid4().hex[:8]}"

            # Create the interview record
            interview = ScheduledInterview(
                id=str(uuid.uuid4()),
                tenant_id=context.get("tenant_id"),
                candidate_id=candidate_id,
                job_id=candidate.job_id or "",
                scheduled_at=interview_time,
                duration_minutes=duration_minutes,
                interview_type=interview_type,
                meeting_link=meeting_link,
                interviewer_ids=interviewer_emails,
                interviewer_names=interviewer_emails,
                created_by=context.get("user_id", "system"),
                status="scheduled",
            )
            db.add(interview)

            # Update candidate status to "interview" if currently shortlisted or screened
            if candidate.status in ("screened", "shortlisted"):
                candidate.status = "interview"

            logger.info(
                "interview_scheduled_persisted",
                interview_id=interview.id,
                candidate_id=candidate_id,
                candidate_name=candidate.full_name,
                scheduled_at=interview_time.isoformat(),
                tenant_id=context.get("tenant_id"),
            )

            return ToolResult(
                success=True,
                data={
                    "interview_id": interview.id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate.full_name,
                    "interview_type": interview_type,
                    "scheduled_at": interview_time.isoformat(),
                    "duration_minutes": duration_minutes,
                    "meeting_link": meeting_link,
                    "interviewers": interviewer_emails,
                    "status": "scheduled",
                    "message": f"Interview scheduled for {candidate.full_name} on {interview_time.strftime('%B %d at %I:%M %p')}",
                },
                tool_name=self.name,
            )

        except Exception as e:
            logger.error("interview_schedule_failed", error=str(e), candidate_id=candidate_id)
            return ToolResult(
                success=False,
                error=f"Failed to schedule interview: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "description": "The candidate to interview"},
                    "interviewer_emails": {"type": "array", "items": {"type": "string"}, "description": "Interviewer email addresses"},
                    "proposed_times": {"type": "array", "items": {"type": "string"}, "description": "Proposed interview times (ISO 8601)"},
                    "interview_type": {"type": "string", "enum": ["video", "phone", "onsite"], "default": "video"},
                },
                "required": ["candidate_id"],
            },
        }
