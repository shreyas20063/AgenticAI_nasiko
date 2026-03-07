"""
HR Helpdesk Agent - answers policy questions using RAG,
handles leave/benefits queries, and escalates sensitive topics.
"""

from agents.base_agent import BaseAgent, AgentContext, AgentResponse
from agents.helpdesk.prompts import HELPDESK_SYSTEM_PROMPT, SENSITIVE_KEYWORDS
from tools.vector_store import VectorStoreTool
from tools.hris_connector import HRISConnector
from tools.helpdesk_tools import CreateTicketTool, SubmitLeaveRequestTool, UpdateTicketStatusTool
from security.prompt_guard import validate_user_input
import structlog

logger = structlog.get_logger()


class HelpdeskAgent(BaseAgent):
    name = "helpdesk_agent"
    description = "HR helpdesk: policy Q&A, leave/benefits, ticket management"
    system_prompt = HELPDESK_SYSTEM_PROMPT

    def __init__(self):
        super().__init__()
        self.vector_search = VectorStoreTool()
        self.available_tools = {
            "search_policies": self.vector_search,
            "hris_connector": HRISConnector(),
            "create_ticket": CreateTicketTool(),
            "submit_leave_request": SubmitLeaveRequestTool(),
            "update_ticket_status": UpdateTicketStatusTool(),
        }

    async def process(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Process helpdesk requests with sensitivity detection."""
        response = AgentResponse()

        # Step 1: Check for sensitive topics FIRST
        if self._is_sensitive(user_input):
            return await self._handle_sensitive(user_input, context)

        text_lower = user_input.lower()

        # Step 2: Specific ACTION keywords first (before generic "ticket"/"status")
        # Ticket actions: update, resolve, close, assign, reopen
        if any(kw in text_lower for kw in [
            "update ticket", "resolve ticket", "close ticket", "reopen ticket",
            "mark as resolved", "mark resolved", "mark as closed", "mark closed",
            "i have resolved", "i have approved", "change status", "change priority",
            "assign ticket", "escalate ticket",
        ]):
            return await self._handle_ticket_action(user_input, context)

        # Leave requests (specific action)
        if any(kw in text_lower for kw in [
            "request leave", "apply for leave", "take leave", "book leave",
            "submit leave", "request time off", "request pto",
        ]):
            return await self._handle_leave_request(user_input, context)

        # Ticket creation (specific action)
        if any(kw in text_lower for kw in [
            "create ticket", "create a ticket", "raise ticket", "raise a ticket",
            "new ticket", "file a ticket",
        ]):
            return await self._handle_create_ticket(user_input, context)

        # Step 3: Read-only queries
        if any(kw in text_lower for kw in ["leave balance", "leave remaining", "pto", "vacation days"]):
            return await self._handle_leave_query(user_input, context)
        if any(kw in text_lower for kw in ["benefit", "insurance", "401k", "dental", "health plan"]):
            return await self._handle_benefits_query(user_input, context)

        # Ticket queries (generic read — AFTER specific actions)
        if any(kw in text_lower for kw in [
            "ticket", "tickets", "open ticket", "helpdesk ticket",
            "open issues", "my issues",
        ]):
            return await self._handle_ticket_query(user_input, context)

        # Step 4: RAG-powered policy Q&A
        return await self._handle_policy_query(user_input, context)

    def _is_sensitive(self, text: str) -> bool:
        """Detect sensitive topics requiring human escalation."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in SENSITIVE_KEYWORDS)

    async def _handle_sensitive(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Escalate sensitive topics to human HR with empathy. Creates a real ticket."""
        response = AgentResponse()
        response.escalated = True
        response.escalation_reason = "Sensitive topic detected - requires human HR review"

        # Actually create a confidential ticket in the DB
        ticket_tool = self.available_tools.get("create_ticket")
        ticket_result = None
        if ticket_tool:
            ticket_result = await ticket_tool.execute(
                {
                    "subject": "Confidential: Sensitive HR matter (auto-escalated)",
                    "category": "complaint",
                    "priority": "urgent",
                    "description": "[Content redacted for confidentiality. Requires human HR review.]",
                },
                {"tenant_id": context.tenant_id, "user_id": context.user_id},
            )

        ticket_ref = ""
        if ticket_result and ticket_result.success:
            ticket_id = ticket_result.data.get("ticket_id", "")[:8]
            ticket_ref = f"\n**Your Ticket Reference:** #{ticket_id}...\n"

        response.message = (
            "I understand this is an important and sensitive matter. Thank you for bringing it to our attention.\n\n"
            "This type of concern needs to be handled by a human HR representative who can provide "
            "the proper support and follow the appropriate procedures.\n\n"
            "**What happens next:**\n"
            "- I've created a confidential ticket for our HR team\n"
            "- A human HR representative will reach out to you within 24 hours\n"
            "- All communications will be kept strictly confidential\n"
            f"{ticket_ref}\n"
            "**Immediate Resources:**\n"
            "- **Employee Assistance Program (EAP):** 1-800-EAP-HELP (24/7 confidential support)\n"
            "- **HR Direct Line:** hr-confidential@company.com\n"
            "- **Emergency:** If you feel unsafe, please contact security or call 911\n\n"
            "Your wellbeing matters to us. You're not alone in this."
        )

        response.actions_taken.append({
            "tool": "create_ticket",
            "success": ticket_result.success if ticket_result else False,
            "result": ticket_result.data if ticket_result and ticket_result.success else {
                "ticket_type": "sensitive_escalation",
                "priority": "urgent",
                "assigned_to": "hr_team",
            },
        })

        return response

    async def _build_tickets_context(self, context: AgentContext) -> str:
        """Fetch current tickets from DB and build a context string for the LLM."""
        if not context.db:
            return "No ticket data available."
        try:
            from sqlalchemy import select
            from models.ticket import Ticket
            from models.user import User

            result = await context.db.execute(
                select(Ticket).where(Ticket.tenant_id == context.tenant_id)
            )
            tickets = result.scalars().all()

            user_result = await context.db.execute(
                select(User).where(User.tenant_id == context.tenant_id)
            )
            users = {u.id: u.full_name for u in user_result.scalars().all()}

            if not tickets:
                return "No tickets found."

            lines = []
            for t in tickets:
                requester = users.get(t.requester_id, "Unknown")
                assigned = users.get(t.assigned_to, "Unassigned") if t.assigned_to else "Unassigned"
                lines.append(
                    f"- ID: {t.id} | Subject: {t.subject} | Status: {t.status} | "
                    f"Priority: {t.priority} | Category: {t.category} | "
                    f"Requester: {requester} | Assigned: {assigned} | Created: {t.created_at}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.warning("helpdesk_ticket_fetch_failed", error=str(e))
            return "Error loading tickets."

    async def _handle_ticket_query(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Fetch and summarize helpdesk tickets — uses tools so LLM can also update if needed."""
        tickets_context = await self._build_tickets_context(context)
        extra_context = (
            f"CURRENT HELPDESK TICKETS:\n{tickets_context}\n\n"
            "Answer the user's question about these tickets. "
            "If the user wants to update a ticket status, use the update_ticket_status tool. "
            "If the user wants to create a ticket, use the create_ticket tool."
        )
        return await self._process_with_tools(user_input, context, extra_context=extra_context)

    async def _handle_ticket_action(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Handle ticket modifications: update status, resolve, close, assign, escalate."""
        tickets_context = await self._build_tickets_context(context)
        extra_context = (
            f"CURRENT HELPDESK TICKETS:\n{tickets_context}\n\n"
            "The user wants to perform an action on one or more tickets. "
            "Use the update_ticket_status tool to change ticket status. "
            "Valid statuses are: open, in_progress, resolved, closed. "
            "Extract the ticket ID(s) and desired status from the user's message. "
            "If the user says 'resolve' or 'resolved', set status to 'resolved'. "
            "If the user references tickets by number (e.g., '2nd and 3rd'), match them to the ticket list above."
        )
        return await self._process_with_tools(user_input, context, extra_context=extra_context)

    async def _handle_leave_query(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Look up employee leave balance."""
        response = AgentResponse()

        # Fetch leave balance from HRIS
        hris = HRISConnector()
        result = await hris.execute(
            {"operation": "get_leave_balance", "employee_id": context.user_id},
            {"tenant_id": context.tenant_id, "user_id": context.user_id},
        )

        if result.success:
            balances = result.data
            response.message = (
                "Here's your current leave balance:\n\n"
                f"**Annual Leave:** {balances['annual_leave']['remaining']} days remaining "
                f"(used {balances['annual_leave']['used']} of {balances['annual_leave']['total']})\n"
                f"**Sick Leave:** {balances['sick_leave']['remaining']} days remaining "
                f"(used {balances['sick_leave']['used']} of {balances['sick_leave']['total']})\n"
                f"**Personal Leave:** {balances['personal_leave']['remaining']} days remaining "
                f"(used {balances['personal_leave']['used']} of {balances['personal_leave']['total']})\n\n"
                "Would you like to request time off or learn more about our leave policies?"
            )
            response.actions_taken.append({
                "tool": "get_leave_balance",
                "success": True,
                "result": balances,
            })
        else:
            response.message = "I wasn't able to retrieve your leave balance. Let me create a ticket for our HR team to help you."

        return response

    async def _handle_benefits_query(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Look up employee benefits info."""
        response = AgentResponse()

        hris = HRISConnector()
        result = await hris.execute(
            {"operation": "get_benefits"},
            {"tenant_id": context.tenant_id, "user_id": context.user_id},
        )

        if result.success:
            benefits = result.data

            # Also search policies for additional context
            policy_result = await self.vector_search.execute(
                {"query": user_input, "n_results": 3, "category": "benefits"},
                {"tenant_id": context.tenant_id},
            )

            response.message = (
                "Here's a summary of your benefits:\n\n"
                f"**Health Insurance:** {benefits['health_insurance']['plan']} plan ({benefits['health_insurance']['provider']})\n"
                f"**Dental:** {benefits['dental']['plan']} plan ({benefits['dental']['provider']})\n"
                f"**401(k):** {benefits['retirement_401k']['contribution']} contribution, "
                f"{benefits['retirement_401k']['employer_match']} company match\n"
                f"**Life Insurance:** {benefits['life_insurance']['coverage']}\n"
            )

            if policy_result.success and policy_result.data.get("results"):
                response.message += "\n**Relevant Policy Information:**\n"
                for doc in policy_result.data["results"][:2]:
                    response.message += f"- {doc['content'][:200]}...\n"
                    response.sources.append(doc.get("metadata", {}))

        else:
            response.message = "I wasn't able to retrieve your benefits information. Let me connect you with HR."

        return response

    async def _handle_leave_request(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Process leave requests using the SubmitLeaveRequestTool via LLM tool calling."""
        extra_context = (
            "The user wants to submit a leave request. Use the submit_leave_request tool. "
            "Extract the leave type (annual/sick/personal), start_date (YYYY-MM-DD), "
            "end_date, number of days, and reason from the user's message. "
            "If date details are missing, ask the user to provide them."
        )
        return await self._process_with_tools(user_input, context, extra_context=extra_context)

    async def _handle_create_ticket(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Create a helpdesk ticket using the CreateTicketTool via LLM tool calling."""
        extra_context = (
            "The user wants to create a helpdesk ticket. Use the create_ticket tool. "
            "Extract the subject, category (leave/benefits/payroll/policy/complaint/other), "
            "priority (low/medium/high/urgent), and description from the user's message."
        )
        return await self._process_with_tools(user_input, context, extra_context=extra_context)

    async def _handle_policy_query(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Answer policy questions using RAG over policy documents."""
        response = AgentResponse()

        # Search policy knowledge base
        search_result = await self.vector_search.execute(
            {"query": user_input, "n_results": 5},
            {"tenant_id": context.tenant_id},
        )

        if search_result.success and search_result.data.get("results"):
            # Build context from retrieved documents
            policy_context = "\n\n".join([
                f"[Source: {doc.get('metadata', {}).get('title', 'HR Policy')}]\n{doc['content']}"
                for doc in search_result.data["results"]
            ])

            extra_context = (
                f"Use the following HR policy documents to answer the employee's question.\n"
                f"Only cite information from these documents. If the answer isn't in the documents, say so.\n\n"
                f"RETRIEVED POLICIES:\n{policy_context}"
            )

            # Use LLM to synthesize answer
            messages = [
                {"role": "system", "content": self.system_prompt + "\n\n" + extra_context},
            ]

            # Inject conversation history for multi-turn awareness
            if hasattr(context, 'conversation_history') and context.conversation_history:
                for hist_msg in context.conversation_history[-6:]:
                    role = hist_msg.get("role", "user")
                    content = hist_msg.get("content", "")
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": content[:1000]})

            messages.append({"role": "user", "content": user_input})

            llm_response = await self._call_llm(messages)
            response.message = llm_response.choices[0].message.content

            for doc in search_result.data["results"]:
                response.sources.append({
                    "type": "policy_document",
                    "metadata": doc.get("metadata", {}),
                    "relevance": doc.get("relevance_score", 0),
                })

        else:
            # No relevant policies found - provide general help
            messages = [
                {"role": "system", "content": self.system_prompt},
            ]

            # Inject conversation history for multi-turn awareness
            if hasattr(context, 'conversation_history') and context.conversation_history:
                for hist_msg in context.conversation_history[-6:]:
                    role = hist_msg.get("role", "user")
                    content = hist_msg.get("content", "")
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": content[:1000]})

            messages.append({"role": "user", "content": user_input})
            llm_response = await self._call_llm(messages)
            response.message = (
                llm_response.choices[0].message.content +
                "\n\n*Note: I couldn't find a specific policy document for this question. "
                "Please verify with your HR team for the most accurate information.*"
            )

        return response
