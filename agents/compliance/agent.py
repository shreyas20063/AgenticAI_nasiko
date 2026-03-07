"""
Compliance Agent - handles GDPR-like compliance, consent management,
audit reports, and bias monitoring.
"""

from agents.base_agent import BaseAgent, AgentContext, AgentResponse
from agents.compliance.prompts import COMPLIANCE_SYSTEM_PROMPT
from tools.compliance_tools import ExportEmployeeDataTool, AnonymizeDataTool, GetAuditLogsTool
from security.rbac import Permission, has_permission
import structlog
import json

logger = structlog.get_logger()


class ComplianceAgent(BaseAgent):
    name = "compliance_agent"
    description = "Compliance: consent, audit, data rights, bias monitoring"
    system_prompt = COMPLIANCE_SYSTEM_PROMPT

    def __init__(self):
        super().__init__()
        self.available_tools = {
            "export_data": ExportEmployeeDataTool(),
            "anonymize_data": AnonymizeDataTool(),
            "get_audit_logs": GetAuditLogsTool(),
        }

    async def process(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Route compliance requests."""
        text_lower = user_input.lower()

        if any(kw in text_lower for kw in ["consent", "withdraw", "opt out"]):
            return await self._handle_consent(user_input, context)
        elif any(kw in text_lower for kw in ["delete my data", "right to erasure", "forget me", "remove my data"]):
            return await self._handle_deletion_request(user_input, context)
        elif any(kw in text_lower for kw in ["access request", "my data", "export my data", "data portability"]):
            return await self._handle_access_request(user_input, context)
        elif any(kw in text_lower for kw in ["audit", "log", "trail", "who accessed"]):
            return await self._handle_audit_query(user_input, context)
        elif any(kw in text_lower for kw in ["bias", "fairness", "discrimination report"]):
            return await self._handle_bias_report(user_input, context)
        else:
            return await self._general_compliance(user_input, context)

    def _inject_history(self, messages: list, context: AgentContext):
        """Inject conversation history into messages for multi-turn awareness."""
        if hasattr(context, 'conversation_history') and context.conversation_history:
            for hist_msg in context.conversation_history[-6:]:
                role = hist_msg.get("role", "user")
                content = hist_msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:1000]})

    async def _handle_consent(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Manage consent records."""
        response = AgentResponse()

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": (
                "The user wants to manage consent. Help them understand:\n"
                "- What consent has been given and for what purposes\n"
                "- How to withdraw consent\n"
                "- What the implications of withdrawal are\n"
                "Process withdrawals if explicitly requested."
            )},
        ]
        self._inject_history(messages, context)
        messages.append({"role": "user", "content": user_input})

        llm_response = await self._call_llm(messages)
        response.message = llm_response.choices[0].message.content
        return response

    async def _handle_deletion_request(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Process data deletion / right to erasure requests using the anonymize_data tool."""
        extra_context = (
            "The user is requesting data deletion (right to erasure). "
            "This request requires approval before execution. "
            "Set requires_approval=True. Use the anonymize_data tool to process the request. "
            "Explain the right to erasure process and what data will be affected. "
            "Note: Some data may be retained if required by law."
        )
        response = await self._process_with_tools(user_input, context, extra_context=extra_context)
        response.requires_approval = True
        response.approval_action = {
            "type": "anonymize_data",
            "requester_id": context.user_id,
            "tenant_id": context.tenant_id,
            "requires_role": "hr_admin",
        }
        return response

    async def _handle_access_request(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Process Subject Access Requests (SAR) / data portability using the export_data tool."""
        extra_context = (
            "The user is making a Subject Access Request (data export). "
            "This request requires approval before execution. "
            "Set requires_approval=True. Use the export_data tool to compile the export. "
            "Explain what data will be included and the timeline."
        )
        response = await self._process_with_tools(user_input, context, extra_context=extra_context)
        response.requires_approval = True
        response.approval_action = {
            "type": "export_data",
            "requester_id": context.user_id,
            "tenant_id": context.tenant_id,
        }
        return response

    async def _handle_audit_query(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Query audit logs using the real get_audit_logs tool."""
        response = AgentResponse()

        if not has_permission(context.user_role, Permission.VIEW_AUDIT_LOGS):
            response.message = (
                "Access to audit logs requires HR Admin or Security Admin privileges. "
                "If you need audit information, please contact your system administrator."
            )
            return response

        extra_context = (
            "The user has admin access and is querying audit logs. "
            "Use the get_audit_logs tool to fetch real data. You can filter by action_filter if needed. "
            "Present the results in a clear, organized format."
        )
        return await self._process_with_tools(user_input, context, extra_context=extra_context)

    async def _handle_bias_report(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Generate or explain bias monitoring reports."""
        response = AgentResponse()

        if not has_permission(context.user_role, Permission.MANAGE_COMPLIANCE):
            response.message = (
                "Bias monitoring reports are available to HR Admin and Compliance roles. "
                "Please contact your compliance officer for this information."
            )
            return response

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": (
                "Generate a bias monitoring overview. Include:\n"
                "- Explanation of what metrics are tracked\n"
                "- Selection rate analysis framework (adverse impact ratio)\n"
                "- Blind vs non-blind screening comparison\n"
                "- Recommendations for improving fairness\n"
                "Note: Use placeholder data for the demo."
            )},
        ]
        self._inject_history(messages, context)
        messages.append({"role": "user", "content": user_input})

        llm_response = await self._call_llm(messages)
        response.message = llm_response.choices[0].message.content
        return response

    async def _general_compliance(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Handle general compliance queries."""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        self._inject_history(messages, context)
        messages.append({"role": "user", "content": user_input})

        llm_response = await self._call_llm(messages)
        response = AgentResponse()
        response.message = llm_response.choices[0].message.content
        return response
