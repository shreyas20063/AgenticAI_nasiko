# CLAUDE.md — HRFlow AI Master Context

## READ THESE FILES BEFORE EVERY TASK

Before doing ANYTHING, read these files in this order:
1. `docs/FINAL_ARCHITECTURE.md` — The architecture. Every decision is evidence-backed. Do NOT deviate.
2. `docs/pitfalls_guide.md` — 50+ failure modes. Check before writing any code.
3. `docs/agentic_ai_guide.md` — Background on A2A protocol, LangChain agents, tool calling.
4. `docs/BUGS.md` — Every bug encountered and its fix. Read before debugging.
5. `docs/MISTAKES.md` — Every wrong approach tried. Read before making decisions.
6. `docs/PROGRESS.md` — The phased build plan. Know which checkpoint you are on.

## TRACKER UPDATE RULES — MANDATORY

After EVERY coding task:
- If you hit a bug → APPEND to `docs/BUGS.md` using the format in that file
- If you tried a wrong approach → APPEND to `docs/MISTAKES.md`
- If you completed a checkpoint → update checkbox in `docs/PROGRESS.md` ([ ] → [x])
- NEVER delete tracker entries — they are cumulative project memory

## PROJECT: HRFlow AI

AI HR Automation Agent for Nasiko AI Agent Buildathon (24-hour hackathon).
- 1 Orchestrator (pure Python routing, NO LLM) + 3 Domain Sub-Agents (LangChain + GPT-4o)
- 5 user roles: Employee, Applicant, HR Admin, Manager, CEO
- Inter-agent communication via Google A2A protocol (JSON-RPC 2.0 over HTTP)
- Deployed on Nasiko infrastructure via Docker

## ARCHITECTURE — DO NOT CHANGE

```
User (any of 5 roles)
    │
    ▼
Orchestrator (port 5000) ──A2A──→ Recruitment Agent (port 8001)  [5 tools]
    │                     ──A2A──→ Employee Services (port 8002)  [6 tools]
    │                     ──A2A──→ Analytics Agent (port 8003)    [4 tools]
    │
    └── Orchestrator: pure Python keyword routing + LLM fallback.
        Injects user role into A2A messages. NOT a LangChain agent.
```

Role → Agent mapping:
- Applicant → Recruitment (check status, view openings)
- Employee → Employee Services (leave, policy, payslip, tickets)
- Manager → All three (approve leave, team metrics, interview feedback)
- HR Admin → All three (screen resumes, resolve tickets, dept analytics)
- CEO → Analytics (headcount, attrition, pipeline, company overview)

## EXACT TECH STACK — PIN THESE VERSIONS

```
Python:           3.11 (NOT 3.12)
langchain:        ==0.2.16
langchain-core:   >=0.2.38,<0.3.0
langchain-openai: >=0.1.0,<0.2.0
fastapi:          >=0.109.0
uvicorn:          >=0.27.0
pydantic:         >=2.6.0
httpx:            >=0.25.0
python-dotenv:    >=1.0.0
click:            >=8.1.7
Docker:           python:3.11-slim (NEVER Alpine)
```

## CRITICAL RULES

### LangChain 0.2.x Imports (MEMORIZE)
```python
from langchain_openai import ChatOpenAI                              # NOT langchain.chat_models
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # NOT langchain.prompts
from langchain_core.tools import tool                                 # NOT langchain.tools
from langchain.agents import AgentExecutor, create_tool_calling_agent
```

### Agent Setup (COPY THIS PATTERN)
```python
llm = ChatOpenAI(model="gpt-4o", temperature=0)
prompt = ChatPromptTemplate.from_messages([
    ("system", "Your system prompt here"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),  # REQUIRED — ALWAYS LAST
])
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(
    agent=agent, tools=tools, verbose=True,
    max_iterations=10, max_execution_time=30, handle_parsing_errors=True,
)
# In async endpoints use: await executor.ainvoke({"input": message})
```

### Pydantic v1 vs v2 (NEVER MIX IN SAME FILE)
```python
from pydantic import BaseModel               # FastAPI models (models.py)
from langchain_core.pydantic_v1 import BaseModel  # LangChain models (agent.py)
```

### Docker Networking
- Container URLs: `http://recruitment-agent:8001` (Docker service name, NOT localhost)
- Only orchestrator maps host port: `"5000:5000"`
- Create network first: `docker network create agents-net`
- Use `depends_on` + `condition: service_healthy`

### A2A Protocol
- Request: `{"jsonrpc":"2.0","id":"str","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"..."}]}}}`
- Response: `{"jsonrpc":"2.0","id":"str","result":{"id":"task-id","status":{"state":"completed"},"artifacts":[{"parts":[{"kind":"text","text":"..."}]}]}}`
- Every sub-agent: `GET /.well-known/agent.json` and `GET /health`
- Field names: camelCase (`messageId`, `contextId`)

### Tool Design Rules
- ALWAYS return `str`, never dict/list
- ALWAYS wrap in try/except, return error message string
- Docstring must explain WHEN to use the tool AND what each param means
- Keep tools focused: one tool = one responsibility

## FILE STRUCTURE

```
hrflow-ai/
├── CLAUDE.md                     ← YOU ARE HERE
├── docker-compose.yml            ← All 4 services
├── .env                          ← OPENAI_API_KEY (gitignored)
├── .gitignore
├── README.md
│
├── docs/                         ← Reference + tracker files
│   ├── agentic_ai_guide.md
│   ├── pitfalls_guide.md
│   ├── FINAL_ARCHITECTURE.md
│   ├── BUGS.md
│   ├── MISTAKES.md
│   └── PROGRESS.md
│
├── shared/                       ← Shared code (copied into each src/ before docker build)
│   ├── mock_data.py
│   └── a2a_models.py
│
├── orchestrator/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── AgentCard.json
│   ├── requirements.txt
│   └── src/
│       ├── __init__.py
│       ├── __main__.py
│       ├── router.py
│       ├── a2a_client.py
│       └── models.py
│
├── recruitment-agent/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── AgentCard.json
│   ├── requirements.txt
│   └── src/
│       ├── __init__.py
│       ├── __main__.py
│       ├── agent.py
│       ├── tools.py
│       └── models.py
│
├── employee-services/            (same structure as recruitment-agent)
├── analytics-agent/              (same structure as recruitment-agent)
```

## SHARED FILE COPY STRATEGY

Docker cannot COPY files from outside the build context. Use this approach:
**Before running `docker compose build`, run the copy script:**

```bash
# copy_shared.sh — run before every docker build
cp shared/mock_data.py orchestrator/src/mock_data.py
cp shared/a2a_models.py orchestrator/src/a2a_models.py
cp shared/mock_data.py recruitment-agent/src/mock_data.py
cp shared/a2a_models.py recruitment-agent/src/a2a_models.py
cp shared/mock_data.py employee-services/src/mock_data.py
cp shared/a2a_models.py employee-services/src/a2a_models.py
cp shared/mock_data.py analytics-agent/src/mock_data.py
cp shared/a2a_models.py analytics-agent/src/a2a_models.py
```

Add `copy_shared.sh` to the project root. The Makefile or README should say:
```bash
bash copy_shared.sh && docker compose up --build
```

## REQUIREMENTS.TXT

### Sub-agent requirements.txt (same for all 3):
```
langchain==0.2.16
langchain-core>=0.2.38,<0.3.0
langchain-openai>=0.1.0,<0.2.0
openai>=1.12.0
fastapi==0.109.2
uvicorn==0.27.0
pydantic>=2.6.0
python-dotenv>=1.0.0
click>=8.1.7
httpx>=0.25.0
```

### Orchestrator requirements.txt (NO langchain):
```
fastapi==0.109.2
uvicorn==0.27.0
pydantic>=2.6.0
python-dotenv>=1.0.0
httpx>=0.25.0
click>=8.1.7
```

## DOCKERFILE TEMPLATE (same pattern for all 4)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ /app/
ENV PYTHONUNBUFFERED=1
CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "PORT_NUMBER"]
```
Replace PORT_NUMBER: orchestrator=5000, recruitment=8001, employee-services=8002, analytics=8003.
For standalone Nasiko uploads, each agent uses port 5000 (Nasiko expects 5000). The `--port` CLI default handles this.

## TESTING

Role is passed IN the message text, not as metadata:
```bash
docker network create agents-net
docker compose up --build
curl http://localhost:5000/health
curl -X POST http://localhost:5000/ -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Role: EMPLOYEE (EMP-001). What is the remote work policy?"}]}}}'
```

## WHEN STUCK
1. Read docs/BUGS.md first
2. Read docs/MISTAKES.md second
3. Check CRITICAL RULES above
4. LangChain import error → exact imports above
5. Docker network fail → service names must match docker-compose
6. Agent infinite loop → check agent_scratchpad + max_iterations
7. Pydantic error → not mixing v1/v2 in same file?
