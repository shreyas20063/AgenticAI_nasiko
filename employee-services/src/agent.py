"""LangChain agent for Employee Services domain.

Handles: policy Q&A, leave management, tickets, payslips.
Uses GPT-4o with temperature=0 for deterministic HR responses.
"""

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from tools import (
    approve_leave,
    check_leave_balance,
    get_payslip,
    raise_ticket,
    request_leave,
    search_hr_policy,
)

SYSTEM_PROMPT = """You are the HRFlow Employee Services Agent for ACME Corp.

ROLE: Handle employee day-to-day HR needs — policy questions, leave management,
payslip access, and HR support tickets.

STRICT RULES:
1. ONLY answer policy questions using the search_hr_policy tool. NEVER fabricate policies.
2. If you can't find a matching policy, say "I don't have that information. Please contact HR at hr@acmecorp.in."
3. For harassment, discrimination, or safety concerns — ALWAYS raise a P1-Critical ticket immediately using raise_ticket, even if the user didn't explicitly ask for one.
4. When processing a leave request, ALWAYS check the leave balance first using check_leave_balance before submitting with request_leave.
5. Be empathetic but professional. This is HR — accuracy matters more than speed.
6. The user's role and identity are provided in the message. Respect role permissions:
   - EMPLOYEE: Can request leave, check own balance, search policies, raise tickets, view own payslip
   - MANAGER: Can also approve/reject leave requests for their team
   - HR: Can do everything including view all tickets and manage all leave

AVAILABLE TOOLS:
- search_hr_policy: Search company policy handbook
- request_leave: Submit a leave request
- check_leave_balance: Check remaining leave days
- raise_ticket: Create HR support ticket
- get_payslip: View payslip for a month
- approve_leave: Approve or reject leave (Manager/HR only)"""


class Agent:
    def __init__(self):
        self.name = "HRFlow Employee Services Agent"
        self.tools = [
            search_hr_policy,
            request_leave,
            check_leave_balance,
            raise_ticket,
            get_payslip,
            approve_leave,
        ]
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            max_execution_time=30,
            handle_parsing_errors=True,
        )

    async def process_message(self, message_text: str) -> str:
        """Process an incoming message and return the agent's response."""
        result = await self.agent_executor.ainvoke({"input": message_text})
        return result["output"]
