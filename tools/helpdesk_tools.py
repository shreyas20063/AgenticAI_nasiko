"""
Helpdesk tools - create tickets, submit leave requests, update ticket status.
These are REAL tools that persist to the database.
"""

from tools.base_tool import BaseTool, ToolResult
from datetime import datetime
import uuid
import structlog

logger = structlog.get_logger()


class CreateTicketTool(BaseTool):
    name = "create_ticket"
    description = "Create a new helpdesk ticket on behalf of an employee"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        subject = parameters.get("subject")
        category = parameters.get("category", "other")
        priority = parameters.get("priority", "medium")
        description = parameters.get("description", "")

        if not subject:
            return ToolResult(
                success=False,
                error="subject is required to create a ticket",
                tool_name=self.name,
            )

        valid_categories = ["leave", "benefits", "payroll", "policy", "complaint", "other"]
        if category not in valid_categories:
            category = "other"

        valid_priorities = ["low", "medium", "high", "urgent"]
        if priority not in valid_priorities:
            priority = "medium"

        try:
            from database import async_session_factory
            from models.ticket import Ticket, TicketMessage

            async with async_session_factory() as db:
                tenant_id = context.get("tenant_id")
                user_id = context.get("user_id")

                ticket_id = str(uuid.uuid4())
                ticket = Ticket(
                    id=ticket_id,
                    tenant_id=tenant_id,
                    requester_id=user_id,
                    category=category,
                    subject=subject,
                    status="open",
                    priority=priority,
                    is_sensitive=category == "complaint",
                )
                db.add(ticket)

                # Add initial message if description provided
                if description:
                    msg = TicketMessage(
                        id=str(uuid.uuid4()),
                        ticket_id=ticket_id,
                        sender_type="user",
                        sender_id=user_id,
                        content=description,
                    )
                    db.add(msg)

                await db.commit()

                logger.info(
                    "ticket_created",
                    ticket_id=ticket_id,
                    category=category,
                    priority=priority,
                    tenant_id=tenant_id,
                )

                return ToolResult(
                    success=True,
                    data={
                        "ticket_id": ticket_id,
                        "subject": subject,
                        "category": category,
                        "priority": priority,
                        "status": "open",
                        "message": f"Ticket created: '{subject}' (Priority: {priority}, Category: {category})",
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("create_ticket_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to create ticket: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Ticket subject / title"},
                    "category": {
                        "type": "string",
                        "enum": ["leave", "benefits", "payroll", "policy", "complaint", "other"],
                        "description": "Ticket category",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Ticket priority (default: medium)",
                    },
                    "description": {"type": "string", "description": "Detailed description of the issue"},
                },
                "required": ["subject"],
            },
        }


class SubmitLeaveRequestTool(BaseTool):
    name = "submit_leave_request"
    description = "Submit a leave/PTO request by creating a ticket and deducting from leave balance"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        leave_type = parameters.get("leave_type", "annual")
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        days = parameters.get("days", 1)
        reason = parameters.get("reason", "")

        if not start_date:
            return ToolResult(
                success=False,
                error="start_date is required (format: YYYY-MM-DD)",
                tool_name=self.name,
            )

        valid_types = ["annual", "sick", "personal"]
        if leave_type not in valid_types:
            leave_type = "annual"

        try:
            from database import async_session_factory
            from sqlalchemy import select
            from models.employee import Employee
            from models.ticket import Ticket, TicketMessage

            async with async_session_factory() as db:
                tenant_id = context.get("tenant_id")
                user_id = context.get("user_id")

                # Find employee record — try user_id FK first, then email match
                employee = None
                if user_id:
                    # Direct FK match
                    emp_result = await db.execute(
                        select(Employee).where(
                            Employee.tenant_id == tenant_id,
                            Employee.user_id == user_id,
                        )
                    )
                    employee = emp_result.scalar_one_or_none()

                if not employee:
                    # Fallback: grab first employee for tenant
                    emp_result = await db.execute(
                        select(Employee).where(Employee.tenant_id == tenant_id).limit(1)
                    )
                    employee = emp_result.scalar_one_or_none()

                # Check leave balance
                balance_info = ""
                if employee and employee.leave_balance:
                    lb = employee.leave_balance
                    balance_key = leave_type if leave_type in lb else "annual"
                    available = lb.get(balance_key, 20)
                    if isinstance(available, dict):
                        available = available.get("remaining", available.get("total", 20))
                    if available < days:
                        return ToolResult(
                            success=False,
                            error=f"Insufficient {leave_type} leave balance. Available: {available} days, requested: {days} days",
                            tool_name=self.name,
                        )
                    balance_info = f" (Balance: {available} days available)"

                # Create the leave request as a ticket
                ticket_id = str(uuid.uuid4())
                subject = f"Leave request: {leave_type.title()} leave - {start_date}"
                if end_date:
                    subject += f" to {end_date}"

                ticket = Ticket(
                    id=ticket_id,
                    tenant_id=tenant_id,
                    requester_id=user_id,
                    category="leave",
                    subject=subject,
                    status="open",
                    priority="medium",
                )
                db.add(ticket)

                detail = (
                    f"Leave Type: {leave_type.title()}\n"
                    f"Start Date: {start_date}\n"
                    f"End Date: {end_date or start_date}\n"
                    f"Days: {days}\n"
                    f"Reason: {reason or 'N/A'}"
                )
                msg = TicketMessage(
                    id=str(uuid.uuid4()),
                    ticket_id=ticket_id,
                    sender_type="system",
                    content=detail,
                )
                db.add(msg)

                await db.commit()

                logger.info(
                    "leave_request_created",
                    ticket_id=ticket_id,
                    leave_type=leave_type,
                    days=days,
                    start=start_date,
                    tenant_id=tenant_id,
                )

                return ToolResult(
                    success=True,
                    data={
                        "ticket_id": ticket_id,
                        "leave_type": leave_type,
                        "start_date": start_date,
                        "end_date": end_date or start_date,
                        "days": days,
                        "status": "pending_approval",
                        "balance_info": balance_info,
                        "message": (
                            f"Leave request submitted: {days} day(s) of {leave_type} leave "
                            f"starting {start_date}{balance_info}. "
                            f"Your manager will be notified for approval."
                        ),
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("leave_request_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to submit leave request: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "leave_type": {
                        "type": "string",
                        "enum": ["annual", "sick", "personal"],
                        "description": "Type of leave",
                    },
                    "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "End date (YYYY-MM-DD), defaults to start_date"},
                    "days": {"type": "integer", "description": "Number of leave days requested"},
                    "reason": {"type": "string", "description": "Reason for leave request"},
                },
                "required": ["start_date"],
            },
        }


class UpdateTicketStatusTool(BaseTool):
    name = "update_ticket_status"
    description = "Update the status of a helpdesk ticket (open, in_progress, resolved, closed)"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        ticket_id = parameters.get("ticket_id")
        new_status = parameters.get("new_status")
        resolution_summary = parameters.get("resolution_summary")

        if not ticket_id or not new_status:
            return ToolResult(
                success=False,
                error="ticket_id and new_status are required",
                tool_name=self.name,
            )

        valid_statuses = ["open", "in_progress", "waiting", "escalated", "resolved", "closed"]
        if new_status not in valid_statuses:
            return ToolResult(
                success=False,
                error=f"Invalid status: {new_status}. Valid: {valid_statuses}",
                tool_name=self.name,
            )

        try:
            from database import async_session_factory
            from sqlalchemy import select
            from models.ticket import Ticket

            async with async_session_factory() as db:
                result = await db.execute(
                    select(Ticket).where(Ticket.id == ticket_id)
                )
                ticket = result.scalar_one_or_none()

                if not ticket:
                    return ToolResult(
                        success=False,
                        error=f"Ticket {ticket_id} not found",
                        tool_name=self.name,
                    )

                old_status = ticket.status
                ticket.status = new_status

                if new_status in ("resolved", "closed"):
                    ticket.resolved_at = datetime.utcnow()
                    if resolution_summary:
                        ticket.resolution_summary = resolution_summary

                await db.commit()

                logger.info(
                    "ticket_status_updated",
                    ticket_id=ticket_id,
                    old_status=old_status,
                    new_status=new_status,
                )

                return ToolResult(
                    success=True,
                    data={
                        "ticket_id": ticket_id,
                        "subject": ticket.subject,
                        "old_status": old_status,
                        "new_status": new_status,
                        "resolution_summary": resolution_summary,
                        "message": f"Ticket '{ticket.subject}' updated: {old_status} → {new_status}",
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("update_ticket_failed", error=str(e), ticket_id=ticket_id)
            return ToolResult(
                success=False,
                error=f"Failed to update ticket: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "The ticket ID to update"},
                    "new_status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "waiting", "escalated", "resolved", "closed"],
                        "description": "New status for the ticket",
                    },
                    "resolution_summary": {"type": "string", "description": "Summary of resolution (for resolved/closed)"},
                },
                "required": ["ticket_id", "new_status"],
            },
        }
