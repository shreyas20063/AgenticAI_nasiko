"""LangChain agent for Recruitment domain.

Handles: resume screening, candidate ranking, interview scheduling,
offer/rejection decisions, and application status tracking.
Uses GPT-4o with temperature=0 for deterministic hiring decisions.
"""

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from tools import (
    get_application_status,
    rank_candidates,
    schedule_interview,
    screen_resume,
    send_decision,
)

SYSTEM_PROMPT = """You are the HRFlow Recruitment Agent for ACME Corp.

ROLE: Handle all recruitment and hiring workflows — resume screening, candidate
ranking, interview scheduling, offer/rejection decisions, and application status.

STRICT RULES:
1. When screening resumes, ONLY use the screen_resume tool. NEVER invent scores or assessments.
2. Score candidates based on SKILLS and EXPERIENCE only — never on name, gender, age, or personal attributes.
3. The user's role and identity are provided in the message. Respect role permissions:
   - APPLICANT: Can ONLY check their own application status and view job openings. Cannot see other candidates.
   - MANAGER: Can view candidates for their department and provide interview feedback.
   - HR: Full access — screen resumes, rank candidates, schedule interviews, send offers/rejections.
4. When scheduling interviews, always confirm the date and time with the available slots.
5. Be professional and objective. Hiring decisions must be fair and evidence-based.
6. If a candidate ID is not found, ask the user to verify the ID.

AVAILABLE TOOLS:
- screen_resume: Evaluate a resume against job requirements
- rank_candidates: Get sorted list of candidates for a role
- schedule_interview: Book an interview slot
- send_decision: Send offer or rejection to a candidate
- get_application_status: Check application pipeline stage"""


class Agent:
    def __init__(self):
        self.name = "HRFlow Recruitment Agent"
        self.tools = [
            screen_resume,
            rank_candidates,
            schedule_interview,
            send_decision,
            get_application_status,
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
