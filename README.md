# HRFlow AI

AI-powered HR Automation Agent built for the Nasiko AI Agent Buildathon. Uses 3 specialized domain agents communicating via Google's A2A protocol.

## Architecture

```
User (Employee | Applicant | HR Admin | Manager | CEO)
    |
    v
Orchestrator (port 5000) -- pure Python routing, no LLM
    |
    |--A2A--> Recruitment Agent (port 8001)    [5 tools]
    |--A2A--> Employee Services Agent (port 8002) [6 tools]
    |--A2A--> Analytics Agent (port 8003)      [4 tools]
```

- **Orchestrator**: Routes requests by role + intent. No LLM needed.
- **Recruitment Agent**: Resume screening, candidate ranking, interview scheduling, offer/rejection.
- **Employee Services Agent**: Leave management, policy search, payslips, support tickets.
- **Analytics Agent**: Headcount, attrition, hiring pipeline, department stats.

## Tech Stack

- Python 3.11, LangChain 0.2.16, GPT-4o
- FastAPI, Docker, Google A2A Protocol (JSON-RPC 2.0)

## Quick Start

```bash
# 1. Create Docker network
docker network create agents-net

# 2. Set your OpenAI API key
cp .env.example .env  # then edit .env with your key

# 3. Copy shared files and build
bash copy_shared.sh
docker compose up --build

# 4. Test
curl http://localhost:5000/health
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Role: EMPLOYEE (EMP-001). What is the remote work policy?"}]}}}'
```

## Project Structure

```
hrflow-ai/
├── docker-compose.yml          # All 4 services
├── copy_shared.sh              # Copies shared code before build
├── shared/                     # Shared mock data + A2A models
├── orchestrator/               # Port 5000 — request routing
├── recruitment-agent/          # Port 8001 — hiring domain
├── employee-services/          # Port 8002 — employee HR domain
└── analytics-agent/            # Port 8003 — insights domain
```

## Team

<!-- Add team members here -->
- TBD
