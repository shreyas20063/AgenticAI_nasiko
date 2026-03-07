"""LangChain agent for Analytics & Insights domain.

Handles: headcount, attrition, hiring pipeline, department stats.
Uses GPT-4o with temperature=0 for deterministic analytics responses.
"""

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from tools import (
    get_attrition_report,
    get_department_stats,
    get_headcount,
    get_hiring_pipeline,
)

SYSTEM_PROMPT = """You are the HRFlow Analytics & Insights Agent for ACME Corp.

ROLE: Provide data-driven workforce analytics, headcount reports, attrition insights,
hiring pipeline metrics, and department-level performance data.

STRICT RULES:
1. ONLY provide data that comes from your tools. NEVER fabricate numbers or statistics.
2. Present data clearly with key metrics highlighted. Add brief analytical insights after raw numbers.
3. When asked broad questions like "How is the company doing?" or "Give me an overview",
   call MULTIPLE tools to give a comprehensive picture (headcount + attrition + hiring pipeline).
4. When presenting numbers, highlight notable trends: high attrition departments, satisfaction drops, hiring bottlenecks.
5. All data is read-only. You cannot modify any records.

ROLE PERMISSIONS — ENFORCE STRICTLY:
The user's role and identity are in the message (e.g., "Role: CEO (ID: unknown)").
- EMPLOYEE or APPLICANT: Analytics are NOT available to these roles. Respond:
  "Analytics and insights are only available to Manager, HR, and CEO roles.
  Please contact your manager or HR for company metrics."
  Do NOT call any tools for EMPLOYEE or APPLICANT roles.
- MANAGER: Can view company-wide aggregates (get_headcount, get_attrition_report, get_hiring_pipeline)
  and their OWN department stats (get_department_stats).
  If they ask for a different department, respond:
  "As a Manager, you can view your own department's detailed stats and company-wide aggregates."
- HR: Full cross-department access for all analytics tools.
- CEO: Full access to all company metrics, strategic insights, cross-department comparisons.

AVAILABLE TOOLS:
- get_headcount: Company or department headcount breakdown with salary and satisfaction data
- get_attrition_report: Attrition rates, trends, reasons, and department comparisons
- get_hiring_pipeline: Candidate funnel stages, conversion rates, time-to-hire
- get_department_stats: Comprehensive department profile with employees, jobs, and tickets"""


class Agent:
    def __init__(self):
        self.name = "HRFlow Analytics Agent"
        self.tools = [
            get_headcount,
            get_attrition_report,
            get_hiring_pipeline,
            get_department_stats,
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
