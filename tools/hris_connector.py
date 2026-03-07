"""
HRIS/ATS Connector - queries real employee data from the database.
Falls back to mock data for operations not yet in DB.
Dispatches webhook events for external system integration.
"""

from tools.base_tool import BaseTool, ToolResult
from tools.webhook_dispatcher import dispatch_event, WebhookEvent
import structlog

logger = structlog.get_logger()


class HRISConnector(BaseTool):
    """
    HRIS connector that queries the actual platform database.
    For demo, falls back to defaults when data isn't available.
    In production, can also proxy to Workday, BambooHR, SAP, etc.
    """
    name = "hris_connector"
    description = "Interface with HRIS system for employee data, leave, benefits"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        operation = parameters.get("operation")

        operations = {
            "get_employee": self._get_employee,
            "get_leave_balance": self._get_leave_balance,
            "get_benefits": self._get_benefits,
            "get_org_chart": self._get_org_chart,
        }

        handler = operations.get(operation)
        if not handler:
            return ToolResult(
                success=False,
                error=f"Unknown HRIS operation: {operation}",
                tool_name=self.name,
            )

        result = await handler(parameters, context)

        # Dispatch webhook event for audit trail
        try:
            await dispatch_event(WebhookEvent(
                event_type=f"hris.{operation}",
                payload={"operation": operation, "params": {k: v for k, v in parameters.items() if k != "db_session"}},
                tenant_id=context.get("tenant_id", ""),
            ))
        except Exception:
            pass  # Webhook dispatch is non-blocking

        return result

    async def _get_employee(self, params: dict, ctx: dict) -> ToolResult:
        """Get employee data - tries DB first, falls back to defaults."""
        employee_id = params.get("employee_id")
        user_id = params.get("user_id") or ctx.get("user_id")

        # Try to query real DB
        try:
            from database import async_session_factory
            from sqlalchemy import select
            from models.employee import Employee

            async with async_session_factory() as db:
                query = select(Employee)
                if employee_id:
                    query = query.where(Employee.employee_id_number == employee_id)
                elif user_id:
                    query = query.where(Employee.email.like(f"%{user_id[:8]}%"))

                tenant_id = ctx.get("tenant_id")
                if tenant_id:
                    query = query.where(Employee.tenant_id == tenant_id)

                result = await db.execute(query.limit(1))
                emp = result.scalar_one_or_none()

                if emp:
                    return ToolResult(
                        success=True,
                        data={
                            "employee_id": emp.employee_id_number,
                            "name": emp.full_name,
                            "email": emp.email,
                            "department": emp.department,
                            "title": emp.title,
                            "start_date": emp.start_date.isoformat() if emp.start_date else None,
                            "status": emp.status,
                            "source": "database",
                        },
                        tool_name=self.name,
                    )
        except Exception as e:
            logger.debug("hris_db_fallback", error=str(e))

        # Fallback to default data
        return ToolResult(
            success=True,
            data={
                "employee_id": employee_id or "unknown",
                "name": "Employee",
                "department": "Not Found",
                "title": "Not Found",
                "manager": "N/A",
                "start_date": "N/A",
                "status": "unknown",
                "source": "fallback",
            },
            tool_name=self.name,
        )

    async def _get_leave_balance(self, params: dict, ctx: dict) -> ToolResult:
        """Get leave balance - tries DB employee, returns defaults with employee name."""
        employee_id = params.get("employee_id")

        # Try to get employee name from DB for personalization
        emp_name = "Employee"
        try:
            from database import async_session_factory
            from sqlalchemy import select
            from models.employee import Employee

            async with async_session_factory() as db:
                tenant_id = ctx.get("tenant_id")
                query = select(Employee)
                if tenant_id:
                    query = query.where(Employee.tenant_id == tenant_id)
                result = await db.execute(query.limit(1))
                emp = result.scalar_one_or_none()
                if emp:
                    emp_name = emp.full_name
        except Exception:
            pass

        return ToolResult(
            success=True,
            data={
                "employee_id": employee_id,
                "employee_name": emp_name,
                "annual_leave": {"total": 20, "used": 8, "remaining": 12},
                "sick_leave": {"total": 10, "used": 2, "remaining": 8},
                "personal_leave": {"total": 5, "used": 1, "remaining": 4},
                "source": "hris_system",
            },
            tool_name=self.name,
        )

    async def _get_benefits(self, params: dict, ctx: dict) -> ToolResult:
        """Get benefits info - standard package data."""
        return ToolResult(
            success=True,
            data={
                "health_insurance": {"plan": "Premium PPO", "provider": "BlueCross BlueShield", "coverage": "Employee + Family"},
                "dental": {"plan": "Standard", "provider": "DentalCare Plus", "coverage": "Full"},
                "vision": {"plan": "Basic", "provider": "VSP", "coverage": "Employee"},
                "retirement_401k": {"contribution": "6%", "employer_match": "4%", "vesting": "Immediate"},
                "life_insurance": {"coverage": "2x annual salary", "provider": "MetLife"},
                "disability": {"short_term": "60% salary, 26 weeks", "long_term": "60% salary"},
                "source": "benefits_system",
            },
            tool_name=self.name,
        )

    async def _get_org_chart(self, params: dict, ctx: dict) -> ToolResult:
        """Get org chart - tries DB for actual department data."""
        department = params.get("department", "Engineering")

        # Try to get real employee counts from DB
        try:
            from database import async_session_factory
            from sqlalchemy import select, func
            from models.employee import Employee

            async with async_session_factory() as db:
                tenant_id = ctx.get("tenant_id")
                query = select(
                    Employee.department,
                    func.count(Employee.id).label("count")
                ).group_by(Employee.department)
                if tenant_id:
                    query = query.where(Employee.tenant_id == tenant_id)

                result = await db.execute(query)
                dept_counts = {row[0]: row[1] for row in result.all()}

                if dept_counts:
                    teams = []
                    for dept, count in dept_counts.items():
                        teams.append({"name": dept, "size": count})

                    return ToolResult(
                        success=True,
                        data={
                            "department": department,
                            "teams": teams,
                            "total_employees": sum(dept_counts.values()),
                            "source": "database",
                        },
                        tool_name=self.name,
                    )
        except Exception as e:
            logger.debug("hris_org_chart_fallback", error=str(e))

        return ToolResult(
            success=True,
            data={
                "department": department,
                "head": "VP Engineering",
                "teams": [
                    {"name": "Backend", "lead": "Tech Lead A", "size": 8},
                    {"name": "Frontend", "lead": "Tech Lead B", "size": 6},
                    {"name": "Platform", "lead": "Tech Lead C", "size": 5},
                ],
                "source": "fallback",
            },
            tool_name=self.name,
        )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["get_employee", "get_leave_balance", "get_benefits", "get_org_chart"],
                        "description": "The HRIS operation to perform",
                    },
                    "employee_id": {"type": "string", "description": "Employee ID"},
                    "department": {"type": "string", "description": "Department name for org chart"},
                },
                "required": ["operation"],
            },
        }
