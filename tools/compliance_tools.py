"""
Compliance tools - data export, data deletion/anonymization, audit log queries.
These are REAL tools that persist to the database.
"""

from tools.base_tool import BaseTool, ToolResult
from datetime import datetime
import uuid
import json
import structlog

logger = structlog.get_logger()


class ExportEmployeeDataTool(BaseTool):
    name = "export_data"
    description = "Export all personal data for an employee (Subject Access Request / data portability)"
    requires_approval = True

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        employee_id = parameters.get("employee_id")
        resource_type = parameters.get("resource_type", "employee")

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
            from models.ticket import Ticket
            from models.onboarding import OnboardingPlan, OnboardingTask

            async with async_session_factory() as db:
                tenant_id = context.get("tenant_id")

                # Fetch employee
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

                export_data = {
                    "export_metadata": {
                        "generated_at": datetime.utcnow().isoformat(),
                        "requested_by": context.get("user_id"),
                        "format": "JSON",
                        "type": "subject_access_request",
                    },
                    "personal_data": {
                        "full_name": employee.full_name,
                        "email": employee.email,
                        "employee_id": employee.employee_id_number,
                        "department": employee.department,
                        "title": employee.title,
                        "location": employee.location,
                        "start_date": employee.start_date.isoformat() if employee.start_date else None,
                        "status": employee.status,
                    },
                    "leave_balance": employee.leave_balance,
                    "benefits_enrolled": employee.benefits_enrolled,
                }

                # Fetch tickets
                ticket_result = await db.execute(
                    select(Ticket).where(Ticket.tenant_id == tenant_id)
                )
                tickets = ticket_result.scalars().all()
                export_data["helpdesk_tickets"] = [
                    {
                        "subject": t.subject,
                        "category": t.category,
                        "status": t.status,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                    }
                    for t in tickets
                    if t.requester_id == context.get("user_id")
                ]

                # Fetch onboarding plans
                plan_result = await db.execute(
                    select(OnboardingPlan).where(
                        OnboardingPlan.employee_id == employee_id,
                    )
                )
                plans = plan_result.scalars().all()
                export_data["onboarding_plans"] = [
                    {
                        "template": p.template_name,
                        "status": p.status,
                        "progress": p.progress_pct,
                        "started_at": p.started_at.isoformat() if p.started_at else None,
                        "tasks": [
                            {"title": t.title, "completed": t.is_completed, "due_day": t.due_day}
                            for t in p.tasks
                        ],
                    }
                    for p in plans
                ]

                logger.info(
                    "data_exported",
                    employee_id=employee_id,
                    sections=list(export_data.keys()),
                    tenant_id=tenant_id,
                )

                return ToolResult(
                    success=True,
                    data={
                        "employee_name": employee.full_name,
                        "export_sections": list(export_data.keys()),
                        "record_count": sum(
                            len(v) if isinstance(v, list) else 1
                            for v in export_data.values()
                        ),
                        "export_preview": json.dumps(export_data, indent=2, default=str)[:2000],
                        "message": (
                            f"Data export completed for {employee.full_name}. "
                            f"Includes: personal data, leave balance, benefits, "
                            f"{len(export_data['helpdesk_tickets'])} ticket(s), "
                            f"{len(export_data['onboarding_plans'])} onboarding plan(s)."
                        ),
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("export_data_failed", error=str(e), employee_id=employee_id)
            return ToolResult(
                success=False,
                error=f"Failed to export data: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string", "description": "Employee ID to export data for"},
                    "resource_type": {"type": "string", "description": "Resource type (default: employee)"},
                },
                "required": ["employee_id", "resource_type"],
            },
        }


class AnonymizeDataTool(BaseTool):
    name = "anonymize_data"
    description = "Anonymize an employee's personal data (right to erasure / GDPR deletion)"
    requires_approval = True

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        employee_id = parameters.get("employee_id")
        reason = parameters.get("reason", "GDPR right to erasure request")

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

            async with async_session_factory() as db:
                tenant_id = context.get("tenant_id")

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

                original_name = employee.full_name
                anon_id = str(uuid.uuid4())[:8]

                # Anonymize PII fields
                employee.full_name = f"Anonymized Employee #{anon_id}"
                employee.email = f"anonymized-{anon_id}@redacted.local"
                employee.employee_id_number = f"ANON-{anon_id}"
                employee.location = "Redacted"
                employee.leave_balance = {}
                employee.benefits_enrolled = []
                employee.status = "anonymized"

                await db.commit()

                logger.info(
                    "employee_data_anonymized",
                    employee_id=employee_id,
                    reason=reason,
                    tenant_id=tenant_id,
                    anonymized_by=context.get("user_id"),
                )

                return ToolResult(
                    success=True,
                    data={
                        "employee_id": employee_id,
                        "original_name": original_name,
                        "anonymized_as": f"Anonymized Employee #{anon_id}",
                        "fields_anonymized": [
                            "full_name", "email", "employee_id_number",
                            "location", "leave_balance", "benefits_enrolled",
                        ],
                        "reason": reason,
                        "message": (
                            f"Employee data has been anonymized. "
                            f"Original name: {original_name} → Anonymized Employee #{anon_id}. "
                            f"6 PII fields redacted. Department and title retained for statistical purposes."
                        ),
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("anonymize_data_failed", error=str(e), employee_id=employee_id)
            return ToolResult(
                success=False,
                error=f"Failed to anonymize data: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string", "description": "Employee ID to anonymize"},
                    "reason": {"type": "string", "description": "Reason for anonymization (e.g., GDPR request)"},
                },
                "required": ["employee_id"],
            },
        }


class GetAuditLogsTool(BaseTool):
    name = "get_audit_logs"
    description = "Query audit logs for compliance reporting and investigation"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        action_filter = parameters.get("action_filter")
        limit = parameters.get("limit", 50)

        try:
            from database import async_session_factory
            from sqlalchemy import select
            from models.audit import AuditLog

            async with async_session_factory() as db:
                tenant_id = context.get("tenant_id")

                query = select(AuditLog).where(
                    AuditLog.tenant_id == tenant_id
                ).order_by(AuditLog.timestamp.desc()).limit(limit)

                if action_filter:
                    query = query.where(AuditLog.action.contains(action_filter))

                result = await db.execute(query)
                logs = result.scalars().all()

                log_entries = []
                for log in logs:
                    log_entries.append({
                        "id": log.id[:8] + "...",
                        "action": log.action,
                        "actor_id": log.actor_id[:8] + "..." if log.actor_id else "system",
                        "resource_type": log.resource_type,
                        "resource_id": log.resource_id[:8] + "..." if log.resource_id else None,
                        "outcome": log.outcome,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                        "risk_level": log.risk_level,
                    })

                return ToolResult(
                    success=True,
                    data={
                        "total_entries": len(log_entries),
                        "filter": action_filter or "all",
                        "entries": log_entries,
                        "message": f"Found {len(log_entries)} audit log entries" + (
                            f" matching '{action_filter}'" if action_filter else ""
                        ),
                    },
                    tool_name=self.name,
                )

        except Exception as e:
            logger.error("audit_log_query_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to query audit logs: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action_filter": {"type": "string", "description": "Filter by action type (e.g., 'login', 'data_export')"},
                    "limit": {"type": "integer", "description": "Max number of entries to return (default: 50)"},
                },
            },
        }
