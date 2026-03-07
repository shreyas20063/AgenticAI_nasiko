# Nasiko HR Automation Platform

An enterprise-grade, multi-agent AI system that automates key HR workflows: **Recruitment**, **Onboarding**, **HR Helpdesk**, and **Compliance & Governance**.

Built for the [Nasiko AI Agent Buildathon](https://nasiko.ai) hackathon.

---

## Architecture

```
                    ┌──────────────┐
                    │   Frontend   │
                    │  (HTML/JS)   │
                    └──────┬───────┘
                           │ REST API
                    ┌──────▼───────┐
                    │   FastAPI    │
                    │  Gateway &   │
                    │  Auth (JWT)  │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │   Orchestrator Agent    │
              │  (Intent Detection +   │
              │   Multi-Step Planner)  │
              └────┬───┬───┬───┬───────┘
                   │   │   │   │
         ┌─────────┘   │   │   └──────────┐
         ▼             ▼   ▼              ▼
   ┌───────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐
   │Recruitment│ │Onboard- │ │Helpdesk │ │Compliance │
   │  Agent    │ │ing Agent│ │  Agent  │ │  Agent    │
   └─────┬─────┘ └────┬────┘ └────┬────┘ └─────┬─────┘
         │             │          │             │
   ┌─────▼─────────────▼──────────▼─────────────▼─────┐
   │              Tool Layer (Connectors)              │
   │  Email │ Calendar │ HRIS │ Vector Store │ Files  │
   └───────────────────────┬───────────────────────────┘
                           │
   ┌───────────────────────▼───────────────────────────┐
   │                   Data Layer                      │
   │  SQLite/PostgreSQL │ ChromaDB │ Audit Logs        │
   └───────────────────────────────────────────────────┘
```

### Agents

| Agent | Responsibilities |
|-------|-----------------|
| **Orchestrator** | Intent detection, workflow planning, agent routing, human-in-the-loop |
| **Recruitment** | Resume parsing, candidate screening/ranking, interview scheduling, blind screening |
| **Onboarding** | Task checklists, document tracking, welcome messages, progress monitoring |
| **Helpdesk** | Policy Q&A (RAG), leave/benefits lookup, sensitive topic escalation |
| **Compliance** | Consent management, data subject rights (GDPR), audit logs, bias monitoring |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| LLM | OpenAI API (GPT-4o-mini, configurable) |
| Database | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy async |
| Vector Store | ChromaDB (persistent, cosine similarity) |
| Auth | JWT + bcrypt + RBAC |
| Frontend | Vanilla HTML/CSS/JS (no framework dependencies) |
| Deployment | Docker + Nasiko Infrastructure |

---

## Quick Start

### Prerequisites
- Python 3.11+
- An OpenAI API key (or compatible LLM endpoint)

### 1. Clone and Install

```bash
git clone <repository-url>
cd hr-automation-platform
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and set your LLM_API_KEY
```

### 3. Run

```bash
python main.py
```

The app starts at `http://localhost:8000`. Demo data is auto-seeded on first run.

### 4. Login with Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| HR Admin | admin@acme.demo | demo12345 |
| Recruiter | recruiter@acme.demo | demo12345 |
| Manager | manager@acme.demo | demo12345 |
| Employee | employee@acme.demo | demo12345 |
| HRBP | hrbp@acme.demo | demo12345 |

### Docker Deployment

```bash
# Set your API key
export LLM_API_KEY=your-key-here

# Build and run
docker-compose up --build
```

---

## Security & Compliance Design

### Identity & Access Control
- **RBAC** with 7 roles: Employee, Manager, Recruiter, HRBP, HR Admin, Security Admin, Super Admin
- **45+ granular permissions** mapped to roles
- **JWT authentication** with configurable expiry
- **Tenant isolation** via `tenant_id` on every table and query filter

### Data Protection
- **PII Detection & Redaction** - regex-based pipeline detects emails, phones, SSNs, credit cards, addresses, DOBs; redacts before logging
- **Blind Screening** - removes all PII from candidate data during evaluation to reduce hiring bias
- **Data Minimization** - agents only access fields needed for their task

### Prompt Injection Defense
- **8 detection patterns** covering: instruction override, role hijacking, data exfiltration, prompt extraction, encoding tricks, SQL injection, bulk operations, privilege escalation
- **Input sanitization** - strips zero-width characters, control chars, normalizes whitespace
- **Risk-level classification** - high-risk inputs are blocked; medium-risk proceed with monitoring

### Tool Call Guardrails
- **Agent tool allowlists** - each agent can only use specific tools
- **Parameter validation** - required fields, recipient limits, valid status transitions
- **Rate limiting** - per-tool hourly limits (e.g., max 10 emails/hour)
- **Human approval gates** - critical actions (email, delete, export) require human OK

### Compliance (GDPR-like)
- **Consent tracking** - per-subject, per-purpose consent records with timestamps
- **Data subject rights** - SAR (access), erasure, portability endpoints
- **Immutable audit log** - every agent action logged with who/when/what/why
- **Bias monitoring** - blind vs. non-blind screening comparison, selection rate tracking
- **Configurable retention** - per-tenant data retention periods

---

## Project Structure

```
hr-automation-platform/
├── main.py                    # FastAPI entry point
├── config.py                  # Environment configuration
├── database.py                # Async DB engine
├── models/                    # SQLAlchemy ORM models
│   ├── tenant.py              # Multi-tenant + config
│   ├── user.py                # Users + RBAC roles
│   ├── candidate.py           # Recruitment pipeline
│   ├── job.py                 # Job postings
│   ├── employee.py            # Employee records
│   ├── onboarding.py          # Onboarding plans & tasks
│   ├── ticket.py              # Helpdesk tickets
│   ├── audit_log.py           # Immutable audit trail
│   ├── consent.py             # GDPR consent records
│   └── policy_document.py     # HR policy docs
├── schemas/                   # Pydantic request/response models
├── api/                       # FastAPI route handlers
│   ├── auth.py                # Login, register, token
│   ├── chat.py                # Main chat endpoint
│   ├── recruitment.py         # Jobs & candidates CRUD
│   ├── compliance.py          # Audit logs, consent, metrics
│   └── admin.py               # Tenant mgmt, dashboard
├── orchestrator/              # Central coordinator
│   ├── coordinator.py         # Main routing logic
│   ├── intent_detector.py     # LLM + rule-based classification
│   └── planner.py             # Multi-step workflow plans
├── agents/                    # Specialized AI agents
│   ├── base_agent.py          # Base class with LLM + tools
│   ├── recruitment/agent.py   # Resume parsing, screening
│   ├── onboarding/agent.py    # Task management
│   ├── helpdesk/agent.py      # RAG-powered Q&A
│   └── compliance/agent.py    # Data rights, auditing
├── tools/                     # External connectors
│   ├── email_tool.py          # SMTP email sending
│   ├── calendar_tool.py       # Calendar/scheduling
│   ├── hris_connector.py      # Mock HRIS/ATS interface
│   ├── vector_store.py        # ChromaDB semantic search
│   └── file_storage.py        # Document storage
├── security/                  # Security middleware
│   ├── rbac.py                # Role-based access control
│   ├── pii_detector.py        # PII detection & redaction
│   ├── prompt_guard.py        # Prompt injection defense
│   ├── tool_guardrails.py     # Tool call validation
│   ├── audit.py               # Audit logging service
│   └── tenant_isolation.py    # Multi-tenant context
├── data/                      # Demo data & policies
│   ├── policies/              # HR policy documents (MD)
│   ├── sample_resumes/        # Synthetic candidate data
│   └── seed_data.py           # Database seeder
├── tests/                     # Unit tests (201 tests)
│   ├── test_rbac.py           # 54 RBAC tests
│   ├── test_pii_detector.py   # 51 PII tests
│   ├── test_prompt_guard.py   # 50 injection tests
│   └── test_tool_guardrails.py# 46 guardrail tests
├── frontend/                  # Single-page web UI
│   ├── index.html
│   └── static/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, returns JWT |
| POST | `/api/auth/register?tenant_domain=acme.demo` | Register user |
| GET | `/api/auth/me` | Current user profile |

### Chat (Main Agent Interface)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/` | Send message to AI agents |
| GET | `/api/chat/history/{id}` | Get conversation history |
| POST | `/api/chat/approve/{id}` | Approve/deny agent action |

### Recruitment
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/recruitment/jobs` | Create job posting |
| GET | `/api/recruitment/jobs` | List job postings |
| POST | `/api/recruitment/candidates` | Add candidate |
| GET | `/api/recruitment/candidates/{job_id}?blind=true` | List candidates |

### Compliance
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/compliance/audit-logs` | Query audit trail |
| GET | `/api/compliance/consent/{subject_id}` | Consent records |
| GET | `/api/compliance/metrics` | Compliance dashboard |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/health` | Health check |
| GET | `/api/admin/dashboard` | Admin metrics |
| POST | `/api/admin/tenants` | Create new tenant |

---

## Example Chat Interactions

**Recruitment:**
> "Screen these 3 candidates for the Senior Software Engineer role and rank them"
> "Parse this resume and extract skills"
> "Schedule interviews for the top 2 candidates"

**Onboarding:**
> "Create an onboarding plan for a new engineering hire starting March 15"
> "What's the onboarding status for the new hire?"

**Helpdesk:**
> "How many vacation days do I have left?"
> "What's our parental leave policy?"
> "I need to report a workplace concern" *(auto-escalates to human HR)*

**Compliance:**
> "I want to request deletion of my data"
> "Show me the audit logs for last week"
> "Generate a bias monitoring report for our recruitment"

---

## Deploying on Nasiko Infrastructure

1. Ensure your `.env` has `NASIKO_AGENT_ID` and `NASIKO_AGENT_TOKEN` set
2. Build the Docker image: `docker build -t nasiko-hr-platform .`
3. Push to your container registry
4. Deploy using Nasiko's deployment guidelines
5. Set environment variables via Nasiko's secret management

---

## Running Tests

```bash
cd hr-automation-platform
python -m pytest tests/ -v
```

201 tests covering RBAC, PII redaction, prompt injection defense, and tool guardrails.

---

## Plugging In Real Systems

The platform uses pluggable connectors. To integrate real systems:

| Component | Current | Production Replacement |
|-----------|---------|----------------------|
| Database | SQLite | PostgreSQL (change `DATABASE_URL`) |
| HRIS | Mock connector | Workday/BambooHR API |
| Email | Logged to console | SMTP/SendGrid/SES |
| Calendar | Mock events | Google Calendar/Microsoft Graph |
| Auth | JWT | Add SAML/OIDC via middleware |
| Vector Store | ChromaDB local | Pinecone/Weaviate/pgvector |

---

## License

Built for the Nasiko AI Agent Buildathon 2026.
