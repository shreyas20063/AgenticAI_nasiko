# Every pitfall your HR hackathon agent will face

**Your biggest risk isn't technical — it's architectural overreach.** Research across production multi-agent deployments, hackathon winner analyses, and LangChain community issues reveals that **79% of multi-agent system failures originate from specification and coordination problems**, not infrastructure bugs. For a beginner team building a sub-agentic HR agent in 24 hours, this means the orchestrator-to-sub-agent handoff, not the LLM itself, is where things break. The good news: every failure mode documented below has a concrete, hackathon-friendly fix. This report covers 50+ pitfalls organized by the exact order you'll encounter them — from architecture selection through final demo — with code examples tuned to your stack (LangChain 0.2.x, FastAPI, Docker, A2A protocol, GPT-4o).

---

## 1. The orchestrator routing problem will bite you first

The sub-agentic pattern introduces a critical decision point that doesn't exist in single-agent systems: the orchestrator must decide which sub-agent handles each request. In an HR context, this creates ambiguity that LLMs handle poorly.

**Misrouting is the #1 failure mode.** When a user asks "Can you help me prepare for my interview next Tuesday?", the orchestrator might route to the interview *scheduler* instead of a preparation advisor. The sub-agent then confidently executes the wrong task — attempting to reschedule a meeting nobody asked to change. The user receives a confirmation of a rescheduled meeting, and the error propagates silently. Research from Augment Code found that **41–86.7% of multi-agent LLM systems fail in production**, with the majority of problems rooted in exactly this kind of coordination mismatch.

**Silent failures are worse than crashes.** A resume screening sub-agent that returns a plausible-looking but biased shortlist is far more dangerous than one that throws an error. Brookings Institution research from 2025 found that in LLM-based resume screening, **white-associated names were preferred in 85.1% of cases**. In a multi-agent pipeline, the orchestrator has no mechanism to detect this — it trusts the sub-agent's output and passes a biased shortlist to the interview scheduler. The error compounds invisibly.

**Error propagation cascades fast.** When the resume screener sub-agent times out, a naive orchestrator retries three times. Each retry triggers internal retries within the sub-agent, creating a 9× load spike. Without circuit breakers, one slow sub-agent can cascade into a full system hang during your demo.

Here's how to prevent routing failures with a hybrid approach — deterministic rules for clear cases, LLM classification only for ambiguous ones:

```python
class HROrchestrator:
    def route_request(self, user_input: str) -> str:
        """Hybrid routing: rules first, LLM fallback for ambiguity."""
        input_lower = user_input.lower()
        
        # Deterministic routing for clear keywords
        policy_keywords = ["policy", "leave", "benefits", "salary", "remote", "dress code"]
        escalation_keywords = ["harassment", "complaint", "grievance", "discrimination", "urgent"]
        
        if any(kw in input_lower for kw in escalation_keywords):
            return "escalation_agent"  # Always escalate sensitive topics
        if any(kw in input_lower for kw in policy_keywords):
            return "policy_agent"
        
        # LLM classification only for ambiguous requests
        return self.llm_classify(user_input)
```

For error handling, implement a retry-with-fallback pattern at the orchestrator level:

```python
async def call_with_retry(self, agent_name, message, max_retries=2):
    for attempt in range(max_retries):
        try:
            result = await asyncio.wait_for(
                self.delegate_task(agent_name, message), timeout=30.0
            )
            if hasattr(result, 'status') and result.status.state == 'failed':
                continue  # Retry on explicit failure
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Timeout calling {agent_name}, attempt {attempt+1}")
    return {"status": "unavailable", "message": f"{agent_name} is temporarily unavailable. Please try again."}
```

**State management is the hidden complexity.** When a user says "Screen these 5 resumes" and then follows with "Schedule interviews with the top 3," the orchestrator needs context from the first sub-agent call to inform the second. Storing state implicitly in the conversation prompt — what HatchWorks calls the "prompt-driven state" anti-pattern — makes this fragile and unreproducible. Instead, persist shared state explicitly in a simple dictionary keyed by session ID:

```python
session_state = {}  # In production, use Redis; for hackathon, dict is fine

session_state["session-123"] = {
    "screened_candidates": [{"name": "Jane Smith", "score": 92}, ...],
    "current_step": "awaiting_scheduling",
}
```

---

## 2. A2A protocol mistakes that silently break Docker networking

The A2A protocol is JSON-RPC 2.0 over HTTP with a specific task lifecycle (submitted → working → completed/failed). Every A2A server must publish an AgentCard at `/.well-known/agent.json` describing its capabilities. Your orchestrator acts as the A2A *client*; your sub-agents act as A2A *servers*. This distinction is critical and frequently misunderstood.

**The single deadliest mistake: using `localhost` in AgentCard URLs inside Docker.** Inside a container, `localhost` resolves to *that container*, not the host or other containers. Your resume screener's AgentCard must use the Docker service name:

```python
# WRONG — will fail silently in Docker
agent_card = AgentCard(url="http://localhost:8001/", ...)

# CORRECT — Docker DNS resolves service names
agent_card = AgentCard(url="http://resume-screener:8001/", ...)
```

**JSON-RPC formatting errors beginners make every time.** The A2A spec requires four fields in every request: `jsonrpc`, `id`, `method`, and `params`. Missing any one produces a cryptic `-32600 Invalid Request` error. Message parts require a `kind` field (`"text"`, `"file"`, or `"data"`). And all JSON field names must be **camelCase** — `messageId`, not `message_id`:

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Screen this resume for Python developer role"}],
      "messageId": "msg-001"
    }
  }
}
```

**The task lifecycle trap.** Once an A2A task reaches a terminal state (completed, failed, canceled), it **cannot be restarted**. Any follow-up must create a new task using the same `contextId`. Beginners often try to send additional messages to a completed task and get `TaskNotFoundError`.

**AgentCard discovery must work or nothing works.** Each sub-agent must serve its AgentCard at the well-known endpoint. Add this to every FastAPI sub-agent:

```python
@app.get("/.well-known/agent.json")
def get_agent_card():
    return {
        "name": "HR Policy Q&A Agent",
        "description": "Answers employee questions about company HR policies",
        "url": f"http://{SERVICE_NAME}:{PORT}/",
        "version": "1.0.0",
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "capabilities": {"streaming": False},
        "skills": [{
            "id": "policy_qa",
            "name": "HR Policy Questions",
            "description": "Answer questions about leave, benefits, remote work, and other HR policies",
            "tags": ["hr", "policy"],
        }]
    }
```

**Port configuration for Nasiko.** Only the orchestrator should expose port 5000 to the host. Sub-agents communicate internally within the Docker network — they don't need host port mappings:

| Container | Internal Port | Host Exposed? | Purpose |
|---|---|---|---|
| Orchestrator | 5000 | Yes (`5000:5000`) | User-facing API, required by Nasiko |
| Policy Q&A Agent | 8001 | No | Internal A2A server |
| Escalation Agent | 8002 | No | Internal A2A server |

**The external network must exist before `docker compose up`.** The `agents-net` network declared as `external: true` means Docker expects it to already exist. Without it:

```
ERROR: Network agents-net declared as external, but could not be found.
```

Fix: run `docker network create agents-net` before launching. In your README, document this as a required setup step.

---

## 3. LangChain 0.2.x will break in five specific ways

LangChain 0.2.x underwent a major restructuring from 0.1.x, and most tutorials online reference the old imports. Your team will encounter import errors within the first hour of coding unless you know the exact correct patterns.

**The `agent_scratchpad` error is the #1 filed issue on LangChain GitHub.** If you use `create_openai_tools_agent` (the correct choice for GPT-4o), the prompt *must* include a `MessagesPlaceholder` named `agent_scratchpad`. Without it: `ValueError: Prompt missing required variables: {'agent_scratchpad'}`. Here is the correct, complete agent setup for LangChain 0.2.x:

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

llm = ChatOpenAI(model="gpt-4o", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an HR policy assistant for Acme Corp.
RULES:
1. ONLY answer using the provided tools — never from memory.
2. If no tool has the answer, say: "I don't have that information. Contact HR at hr@acme.com."
3. Never fabricate policies. Quote the source document.
4. For sensitive topics (harassment, discrimination), immediately escalate."""),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),  # REQUIRED — this is where reasoning steps go
])

agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(
    agent=agent, tools=tools,
    verbose=True,
    max_iterations=10,           # Prevents infinite loops
    max_execution_time=30,       # 30-second hard timeout
    handle_parsing_errors=True,  # Catches malformed LLM output instead of crashing
)
```

**Import errors will confuse you.** The 0.2.x restructuring moved classes to provider-specific packages. These are the correct imports — bookmark them:

```python
# CORRECT for LangChain 0.2.x:
from langchain_openai import ChatOpenAI          # NOT from langchain.chat_models
from langchain_core.prompts import ChatPromptTemplate  # NOT from langchain.prompts
from langchain_core.tools import tool              # NOT from langchain.tools
from langchain.agents import AgentExecutor, create_openai_tools_agent
```

**Pydantic v1 vs v2 will cause validation errors.** LangChain 0.2.x uses pydantic v1 internally but allows v2 to be installed (which FastAPI requires). If you pass a pydantic v2 `BaseModel` to a LangChain component, you get: `ValidationError: subclass of BaseModel expected`. Use the compatibility shim for any model that touches LangChain:

```python
# For LangChain models:
from langchain_core.pydantic_v1 import BaseModel, Field

# For FastAPI models (separate file):
from pydantic import BaseModel, Field
```

**Tool docstrings are the single most impactful factor in agent performance.** The `@tool` decorator uses the function's docstring as the description the LLM reads when deciding which tool to invoke. Vague descriptions cause wrong tool selection and infinite loops. By default, `@tool` does **not** include parameter descriptions from the docstring — only the function-level description:

```python
# BAD — vague, causes misrouting:
@tool
def lookup(query: str) -> str:
    """Look up information."""
    ...

# GOOD — specific, includes when/how to use:
@tool
def search_hr_policy(query: str) -> str:
    """Search the company HR policy handbook for leave, benefits, remote work,
    and workplace rules. Use this when employees ask about company policies.
    Returns the relevant policy text with section references."""
    ...
```

**Infinite agent loops** happen when the LLM can't find the right tool, gets ambiguous tool output, or when the scratchpad fills the context window. With GPT-4o's 128K context, this is less likely but still possible with many iterations. The combination of `max_iterations=10`, `max_execution_time=30`, and `handle_parsing_errors=True` prevents all three failure modes. Set `early_stopping_method="generate"` to get a best-effort answer when the budget runs out instead of an error.

**Pin your requirements.txt exactly.** Mixing LangChain package version families is the #1 cause of dependency resolution failures:

```
langchain==0.2.16
langchain-core>=0.2.38,<0.3.0
langchain-openai>=0.1.0,<0.2.0
fastapi>=0.100.0
uvicorn>=0.23.0
python-dotenv>=1.0.0
httpx>=0.25.0
```

---

## 4. Docker will fail at build, at network, and at startup order

**Use `python:3.11-slim`, not Alpine.** Alpine images break many Python packages because they use musl instead of glibc. You'll see `error: command 'gcc' not found` or `Failed building wheel`. The slim image is **130MB** and works with virtually everything. Avoid Python 3.12+ as well — some LangChain community packages have compatibility issues:

```dockerfile
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```

**Layer ordering saves 5+ minutes per rebuild.** Copy `requirements.txt` first and install dependencies *before* copying application code. Docker caches each layer — if only your code changes, the dependency installation layer stays cached. Reversing this order forces a full dependency reinstall on every code change.

**`depends_on` does NOT wait for readiness.** This is the most common Docker beginner misconception. `depends_on` only waits for the *container process to start*, not for your FastAPI server to be accepting connections. The orchestrator will crash trying to reach sub-agents that haven't finished booting. Fix this with health checks:

```yaml
services:
  policy-agent:
    build: ./policy-agent
    env_file: .env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
    networks:
      - agents-net

  orchestrator:
    build: ./orchestrator
    ports:
      - "5000:5000"
    env_file: .env
    depends_on:
      policy-agent:
        condition: service_healthy
      escalation-agent:
        condition: service_healthy
    networks:
      - agents-net

networks:
  agents-net:
    external: true
```

**Environment variables across containers.** Use a shared `.env` file referenced by every service via `env_file: .env`. Never commit this file to Git. Every service that calls GPT-4o needs `OPENAI_API_KEY`, and the orchestrator needs sub-agent URLs:

```bash
# .env
OPENAI_API_KEY=sk-...
POLICY_AGENT_URL=http://policy-agent:8001
ESCALATION_AGENT_URL=http://escalation-agent:8002
```

**The commands beginners forget.** After changing code: `docker compose up --build` (not just `up`). To see why a container crashed: `docker compose logs -f policy-agent`. To check status: `docker compose ps` (look for "Exit 1"). To validate your compose file syntax: `docker compose config`.

---

## 5. HR domain traps — hallucination, bias, and scope creep

**Policy Q&A hallucination is your biggest domain risk.** Without grounding, GPT-4o asked "What is our parental leave policy?" will confidently fabricate a specific number of weeks. Air Canada was legally required to honor a chatbot-hallucinated discount policy after a court ruling. For a hackathon, use a simple retrieval layer — keyword-based matching is sufficient and takes 30 minutes to build:

```python
POLICIES = {
    "annual_leave": "All full-time employees receive 20 days paid annual leave per year. Leave must be requested 2 weeks in advance via the HR portal.",
    "remote_work": "Hybrid work: 3 days office, 2 days remote with manager approval. Must be within country of residence.",
    "parental_leave": "Primary caregivers: 12 weeks paid. Secondary caregivers: 4 weeks paid. Must notify HR 30 days before expected leave date.",
    "sick_leave": "10 days paid sick leave per year. Doctor's note required for absences exceeding 3 consecutive days.",
    "harassment": "ESCALATION REQUIRED. All harassment reports must be filed with HR directly. Contact hr-confidential@acme.com or call the anonymous hotline at 1-800-555-0123.",
}

@tool
def search_hr_policy(query: str) -> str:
    """Search company HR policies for leave, benefits, remote work, and workplace rules."""
    query_lower = query.lower()
    matches = []
    for key, text in POLICIES.items():
        if any(word in query_lower for word in key.split("_")):
            matches.append(text)
    if not matches:
        return "No matching policy found. Please contact HR at hr@acme.com for assistance."
    return "\n\n".join(matches)
```

**Resume PDF parsing will fail on at least one test case.** Use `pdfplumber` over PyPDF2 — it preserves layout and handles multi-column resumes better. But for a hackathon, skip PDF parsing entirely and use plain-text sample resumes. This saves 2-3 hours of debugging encoding issues, scanned PDFs returning empty strings, and multi-column text garbling.

**Interview scheduling with real calendar APIs is a time sink.** OAuth2 setup for Google Calendar alone takes 2-4 hours including credential configuration, scope permissions, and error handling. Use mock data with realistic-looking slots. Judges care about the agent logic, not the API plumbing. Build a thin abstraction layer so your README can say "production-ready for real calendar integration":

```python
MOCK_CALENDAR = {
    "2026-03-10": [
        {"time": "09:00", "available": True},
        {"time": "11:00", "available": True},
        {"time": "14:00", "available": True},
    ],
    "2026-03-11": [
        {"time": "10:00", "available": True},
        {"time": "15:00", "available": True},
    ],
}
```

**Set temperature to 0 for all HR tasks.** Temperature 0 doesn't eliminate hallucination — the model can still confidently produce incorrect information — but it makes outputs deterministic and reproducible. For resume screening this is essential: the same resume should get the same score every time. For policy Q&A, consistency prevents conflicting answers to the same question from different employees.

---

## 6. Pick HR helpdesk, not recruitment — here's why

The domain you choose determines your success probability. After analyzing feasibility, demo appeal, and A2A showcase potential, **HR Helpdesk (Policy Q&A + Escalation) is the optimal choice** for this team.

**Why helpdesk beats recruitment for a 24-hour beginner sprint.** Policy Q&A is a well-understood RAG pattern — LangChain's sweet spot. You load policy documents, the agent answers questions. The escalation pathway is a *natural* sub-agent workflow: Sub-Agent 1 (Policy Q&A) handles questions and escalates when it detects sensitive topics or can't find answers; Sub-Agent 2 (Escalation/Ticket) receives escalated issues, creates structured tickets with priority and category, and confirms routing. The orchestrator manages the conversation and decides when escalation is needed.

**Demo appeal is decisive.** Judges can literally type questions and watch the system respond in real-time. A judge asking "What is our parental leave policy?" and getting a cited answer is powerful. Then asking "I'm being harassed by my manager" and watching it instantly escalate to a priority-1 ticket with the confidential HR contact — that's a winning demo moment. Interactive demos beat static output every time.

**Mock data is trivially easy.** You need 4-5 policy text strings and a ticket JSON schema. No complex resume formats, no calendar integrations, no PDF parsing. This alone saves 4-6 hours versus recruitment.

Recruitment (resume screening + interview scheduling) is riskier because resume parsing is fragile, screening introduces bias concerns, and calendar integration is a time sink — even with mocks. Onboarding is feasible but less dramatic in a demo. If you finish helpdesk early, add a lightweight resume screening capability to show extensibility.

---

## 7. How to win: the 24-hour timeline that actually works

Research across hackathon winner retrospectives reveals a consistent pattern: **winners prove their core idea works within 3 hours and assign one person to demo preparation from hour 12 onward.** The Klaviyo AI Hackathon Grand Prize winner emphasized that "technical sophistication without human relevance is just expensive showing off." A serial winner with 7+ hackathon victories recommends spending no more than 60-90 minutes on planning before coding.

**Hour-by-hour for a 4-person team:**

| Phase | Hours | Member 1 (Agent Lead) | Member 2 (Infra) | Member 3 (Sub-Agent 2) | Member 4 (Demo) |
|---|---|---|---|---|---|
| Foundation | 0–3 | Get basic RAG chain working with 1 policy doc | GitHub repo, Docker setup, `docker compose up` working | Write 4-5 policy documents, define ticket schema | README skeleton, architecture diagram |
| Parallel build | 3–8 | Build Policy Q&A sub-agent with A2A server | Dockerize all services, test networking | Build Escalation sub-agent with A2A server | Test agents as user, log bugs |
| Integration | 8–12 | Wire orchestrator routing to both sub-agents | Deploy to Nasiko/target platform | Help with A2A integration | Refine demo script, start recording tests |
| Polish | 12–18 | Fix bugs from testing, add edge case handling | Ensure deployment works end-to-end | Add A2A logging/visualization | **Full-time demo recording and editing** |
| Submit | 18–24 | Code cleanup, comments | Final deployment verification | LinkedIn post, submission form | Video upload, backup screenshots |

**Emergency rules that prevent disaster:**

- **Hour 3 checkpoint**: If basic RAG isn't working, debug it together. Nothing else matters until a policy question gets a correct answer.
- **Hour 12 rule**: If Sub-Agent 2 isn't functional, simplify it to a basic JSON ticket creator with hardcoded routing. A simple working escalation beats an ambitious broken one.
- **Hour 16 rule**: Stop adding features. Only fix bugs and polish the demo.
- **Hour 20 rule**: Stop coding entirely. Only work on submission materials — video, README, LinkedIn post, deployment verification.

**What makes judges most impressed.** Based on analysis of Microsoft AI Agents Hackathon (570 submissions), AWS AI Agent Hackathon, and multiple Devpost competitions, judges weight these factors in roughly this order:

- **Goal satisfaction** (does it actually work?): Pre-test with 10+ diverse questions. Every one must work or gracefully handle failure.
- **Agent performance** (reliability, correctness): Consistent responses, appropriate escalation triggers, cited sources in answers, graceful handling of out-of-scope questions.
- **Compliance** (meeting all requirements): A Devpost judge noted "It was surprising to see how many submissions did not fulfill the basic requirements." Meeting every requirement — Docker deployment, GitHub repo, 3-min video, LinkedIn post, live deployment — puts you ahead of **30%+ of teams**.
- **Code quality**: Clean file structure, meaningful names, basic error handling, working docker-compose, commit history showing progression (not one giant commit).

**Work splitting for 2-3 person teams.** With 2 members: one builds all agent logic, the other handles infrastructure + demo + deployment. With 3 members: add a dedicated Sub-Agent 2 builder who shifts to testing and demo support from hour 12.

---

## 8. The demo video decides your fate in 180 seconds

**Minute 0:00–0:30 — the hook.** State the problem and solution in one sentence: "HR teams answer the same policy questions 40+ times per week. Our AI agent handles this automatically and escalates sensitive issues." Flash the architecture diagram showing orchestrator + 2 sub-agents communicating via A2A.

**Minute 0:30–2:00 — live demo, not slides.** Show three scenarios in sequence: (1) simple policy question answered with citation, (2) complex question requiring multi-step reasoning, (3) sensitive topic triggering automatic escalation to a ticket. A McKinsey hackathon judge noted: "Many teams spend 2-3 minutes doing a startup pitch rather than showcasing the hack. Focus on demoing your project."

**Minute 2:00–2:30 — architecture and A2A.** Quick view of Docker deployment, the A2A message flow between agents (show logging output), and GitHub repo structure. Mention the tech stack: LangChain, GPT-4o, Docker, A2A protocol.

**Minute 2:30–3:00 — impact and future.** What this becomes with real HRIS integration, multi-language support, compliance tracking. Team credits and a strong closer.

**Making A2A visually impressive.** Add structured logging that prints the A2A message flow in real-time during the demo:

```
[ORCHESTRATOR] Received: "What is our remote work policy?"
[ORCHESTRATOR] Routing to: policy-agent (A2A message/send)
[POLICY-AGENT] Task status: working → completed
[POLICY-AGENT] Response: "Hybrid work: 3 days office, 2 days remote..."
[ORCHESTRATOR] Returning answer to user ✓
```

This makes the sub-agentic architecture tangible to judges who might not understand A2A protocol otherwise.

**If live deployment breaks during judging.** Have a pre-recorded video backup. Have screenshots of every key interaction. Prepare a walkthrough narrative using those screenshots. Judges appreciate honesty: "We encountered a deployment issue; here's our recorded demo showing full functionality." This is far better than a failing live demo.

**Pre-record the demo video.** Do not rely on live demo for the video submission. Record with the team member who has the best microphone. Upload to YouTube early — YouTube gives you a link before upload completes.

---

## Conclusion: the meta-strategy that ties everything together

The deepest insight from this research isn't any individual pitfall — it's that **multi-agent systems fail primarily at the boundaries between agents, not within them.** Anthropic found that their early research agents spent 80% more tokens than necessary because sub-agents "duplicated work, left gaps, or failed to find necessary information" when given vague delegation instructions. Google DeepMind evaluated 180 agent configurations and found that more agents "often hits a ceiling and can even degrade performance."

For your 24-hour hackathon, this means: **keep the architecture minimal, the boundaries explicit, and the routing deterministic.** Two sub-agents with crystal-clear responsibilities (policy Q&A and escalation) connected by rule-based routing will outperform a sophisticated multi-agent system with ambiguous boundaries. Use mock data to eliminate API integration risk. Assign one person full-time to demo from hour 12. Meet every compliance requirement — this alone beats 30% of submissions.

The winning formula is not the most impressive architecture. It's the one that works flawlessly during the 3-minute demo, with visible A2A communication that makes the sub-agentic pattern tangible to judges. Build the simplest thing that demonstrates the concept, make it bulletproof, and present it with clarity.