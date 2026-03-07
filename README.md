# HRFlow AI

AI-powered HR automation with multi-agent A2A architecture — serving 5 user roles through 3 specialized domain agents.

Built for the **Nasiko AI Agent Buildathon 2026**.

---

## Architecture

```
User (Employee | Applicant | HR Admin | Manager | CEO)
    |
    v
Orchestrator (port 5000) -- pure Python keyword routing, no LLM
    |
    |--A2A--> Recruitment Agent (port 8001)       [5 tools]
    |--A2A--> Employee Services Agent (port 8002)  [6 tools]
    |--A2A--> Analytics Agent (port 8003)          [4 tools]
```

The **Orchestrator** receives user messages, extracts the role, classifies intent via keyword rules, and forwards to the correct domain agent using Google's **A2A protocol** (JSON-RPC 2.0 over HTTP). Each sub-agent is a **LangChain + GPT-4o** agent with focused tools.

---

## Features by Role

| Role | Agent | Capabilities |
|------|-------|-------------|
| **Employee** | Employee Services | Policy Q&A, leave requests, leave balance, payslip access, HR support tickets |
| **Applicant** | Recruitment | Application status, job openings, interview schedule |
| **HR Admin** | All three | Resume screening, candidate ranking, interview scheduling, offer/rejection, ticket resolution, department analytics |
| **Manager** | Employee Svc + Analytics | Leave approvals, team metrics, interview feedback, department stats |
| **CEO** | Analytics | Company-wide headcount, attrition report, hiring pipeline, department comparisons |

---

## Tech Stack

- **Python 3.11** | **LangChain 0.2.16** | **GPT-4o** (temperature=0)
- **FastAPI** | **Uvicorn** | **Pydantic v2**
- **Docker** (python:3.11-slim) | **Docker Compose**
- **Google A2A Protocol** (JSON-RPC 2.0 over HTTP)
- **httpx** for async inter-agent communication

---

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- OpenAI API key

### Setup

```bash
git clone https://github.com/shreyas20063/AgenticAI_nasiko.git
cd AgenticAI_nasiko

# Add your OpenAI API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# Create Docker network
docker network create agents-net

# Copy shared files into each agent's build context
bash copy_shared.sh

# Build and start all 4 services
docker compose up --build
```

### Verify

```bash
# Check all services are healthy
docker compose ps

# Health check
curl http://localhost:5000/health
```

### Test

```bash
# Employee asks about remote work policy
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Role: EMPLOYEE (EMP-001). What is the remote work policy?"}]}}}'

# CEO requests company overview (triggers multiple tool calls)
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"2","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Role: CEO. How is the company doing? Give me a full overview."}]}}}'

# Applicant checks application status
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"3","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Role: APPLICANT (CAND-001). What is the status of my application?"}]}}}'
```

---

## API Reference

### Endpoint: `POST /`

**Protocol:** A2A JSON-RPC 2.0

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        {
          "kind": "text",
          "text": "Role: EMPLOYEE (EMP-001). What is the remote work policy?"
        }
      ]
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "result": {
    "id": "task-abc123",
    "kind": "task",
    "status": { "state": "completed" },
    "artifacts": [
      {
        "parts": [
          {
            "kind": "text",
            "text": "Remote Work Policy (Section 3):\nHybrid work model: 3 days office, 2 days remote..."
          }
        ]
      }
    ]
  }
}
```

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (`{"status": "healthy"}`) |
| `GET` | `/.well-known/agent.json` | A2A AgentCard discovery |

---

## A2A Protocol

Agents communicate using Google's **Agent-to-Agent (A2A) protocol** — a standardized JSON-RPC 2.0 format for inter-agent messaging.

**Flow:**
1. User sends message to Orchestrator (port 5000)
2. Orchestrator extracts role and classifies intent via keyword rules
3. Orchestrator forwards message to the correct sub-agent via HTTP POST
4. Sub-agent (LangChain + GPT-4o) processes the request using its tools
5. Sub-agent returns A2A response with artifacts
6. Orchestrator wraps and returns response to user

**Agent Discovery:** Each agent serves its AgentCard at `GET /.well-known/agent.json`.

---

## Project Structure

```
hrflow-ai/
├── CLAUDE.md                      # AI assistant context
├── README.md                      # This file
├── docker-compose.yml             # All 4 services (local dev)
├── copy_shared.sh                 # Copies shared code before build
├── .env.example                   # Environment template
├── .gitignore
│
├── docs/
│   ├── FINAL_ARCHITECTURE.md      # Architecture decisions
│   ├── pitfalls_guide.md          # 50+ failure modes
│   ├── agentic_ai_guide.md        # A2A protocol reference
│   ├── PROGRESS.md                # Build progress tracker
│   ├── BUGS.md                    # Bug log
│   └── MISTAKES.md                # Anti-patterns avoided
│
├── shared/
│   ├── mock_data.py               # 12 employees, 8 candidates, 10 policies
│   └── a2a_models.py              # Pydantic v2 A2A protocol models
│
├── orchestrator/                  # Port 5000 — request routing
│   ├── Dockerfile
│   ├── docker-compose.yml         # Standalone (Nasiko upload)
│   ├── AgentCard.json
│   ├── requirements.txt           # FastAPI, httpx (NO LangChain)
│   └── src/
│       ├── __main__.py            # FastAPI app + A2A handler
│       ├── router.py              # Keyword routing + role extraction
│       └── a2a_client.py          # Async HTTP A2A client
│
├── recruitment-agent/             # Port 8001 — hiring domain
│   ├── Dockerfile
│   ├── docker-compose.yml         # Standalone (Nasiko upload)
│   ├── AgentCard.json
│   ├── requirements.txt           # LangChain + FastAPI
│   └── src/
│       ├── __main__.py            # FastAPI app
│       ├── agent.py               # LangChain agent (GPT-4o)
│       └── tools.py               # 5 tools
│
├── employee-services/             # Port 8002 — employee HR domain
│   └── (same structure as recruitment-agent)
│
└── analytics-agent/               # Port 8003 — insights domain
    └── (same structure as recruitment-agent)
```

---

## 15 Tools Across 3 Agents

### Recruitment Agent (5 tools)
| Tool | Description |
|------|-------------|
| `screen_resume` | Score resume against job requirements (0-100) |
| `rank_candidates` | Sort candidates by score for a role |
| `schedule_interview` | Book interview from available calendar slots |
| `send_decision` | Send offer or rejection to candidate |
| `get_application_status` | Check candidate pipeline stage |

### Employee Services Agent (6 tools)
| Tool | Description |
|------|-------------|
| `search_hr_policy` | Keyword search across 10 HR policies |
| `request_leave` | Submit leave request with balance check |
| `check_leave_balance` | View remaining annual/sick/parental days |
| `raise_ticket` | Create HR support ticket (auto-escalates harassment) |
| `get_payslip` | Retrieve monthly payslip with deductions |
| `approve_leave` | Manager/HR approve or reject leave |

### Analytics Agent (4 tools)
| Tool | Description |
|------|-------------|
| `get_headcount` | Company or department headcount breakdown |
| `get_attrition_report` | Attrition rates, trends, reasons |
| `get_hiring_pipeline` | Candidate funnel with conversion rates |
| `get_department_stats` | Comprehensive department profile |

---

## Future Enhancements

- Real HRIS integration (BambooHR, SAP SuccessFactors)
- Google Calendar / Outlook integration for interview scheduling
- PDF resume parsing with OCR
- Multi-language support
- Slack / Teams bot interface
- Compliance and audit trail logging
- Performance review cycle management
- Real-time notifications via WebSockets

---

## Team

- Shreyas — Developer

---

*Built for the Nasiko AI Agent Buildathon 2026*
