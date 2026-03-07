# FINAL Architecture Decision Record v2
# HR Automation Agent — "HRFlow AI"

## The Core Insight: Roles ≠ Agents

You have **5 user roles** but you do NOT build 5 agents.
You build **3 domain agents** and the **orchestrator routes by role + intent**.

This is how every real HRIS works — SAP SuccessFactors, Workday, BambooHR all have
a single recruitment module, a single employee services module, etc. Different users
see different views of the SAME module based on their role permissions.

```
WHY NOT 5 AGENTS (one per role)?
─────────────────────────────────
- Employee "request leave" and Manager "approve leave" touch the SAME data
- HR "screen resume" and Applicant "check status" touch the SAME data
- 5 agents = massive code duplication across containers
- 5 containers = Docker networking hell for beginners in 24 hours
- DeepMind 2025: more agents degrades sequential tasks by 39-70%

WHY 3 DOMAIN AGENTS?
─────────────────────
- Maps to real HR department structure
- Each domain is self-contained with its own data
- Zero tool overlap between agents
- 4 total containers = manageable for beginners
- 3 A2A channels = plenty for judges to see
```

---

## Architecture Diagram

```
                         ┌─────────────────────┐
                         │    USER INTERFACE    │
                         │  (selects role at    │
                         │   start of session)  │
                         └──────────┬──────────┘
                                    │
                    ROLES: Employee | Applicant | HR | Manager | CEO
                                    │
                                    ▼
               ┌────────────────────────────────────────┐
               │         🎯 ORCHESTRATOR AGENT          │
               │            (Port 5000)                 │
               │                                        │
               │  1. Receives: message + user_role      │
               │  2. Classifies intent                  │
               │  3. Injects role context into request  │
               │  4. Routes to correct domain agent     │
               │  5. Returns response to user           │
               │                                        │
               │  ROUTING TABLE:                        │
               │  ┌──────────┬────────────────────────┐ │
               │  │ Intent   │ Routes To              │ │
               │  ├──────────┼────────────────────────┤ │
               │  │ hiring   │ → Recruitment Agent    │ │
               │  │ resume   │ → Recruitment Agent    │ │
               │  │ interview│ → Recruitment Agent    │ │
               │  │ leave    │ → Employee Svc Agent   │ │
               │  │ policy   │ → Employee Svc Agent   │ │
               │  │ complaint│ → Employee Svc Agent   │ │
               │  │ payslip  │ → Employee Svc Agent   │ │
               │  │ headcount│ → Analytics Agent      │ │
               │  │ attrition│ → Analytics Agent      │ │
               │  │ metrics  │ → Analytics Agent      │ │
               │  └──────────┴────────────────────────┘ │
               └──────┬──────────┬──────────┬───────────┘
                      │          │          │
            A2A       │    A2A   │    A2A   │
         message/send │          │          │
                      ▼          ▼          ▼
         ┌────────────────┐ ┌──────────────────┐ ┌──────────────────┐
         │ 📋 RECRUITMENT │ │ 👤 EMPLOYEE      │ │ 📊 ANALYTICS     │
         │    AGENT       │ │    SERVICES      │ │    & INSIGHTS    │
         │  (Port 8001)   │ │    AGENT         │ │    AGENT         │
         │                │ │  (Port 8002)     │ │  (Port 8003)     │
         │ LangChain +    │ │                  │ │                  │
         │ GPT-4o         │ │ LangChain +      │ │ LangChain +      │
         │                │ │ GPT-4o           │ │ GPT-4o           │
         │ Tools:         │ │                  │ │                  │
         │ · screen_resume│ │ Tools:           │ │ Tools:           │
         │ · rank_cands   │ │ · search_policy  │ │ · get_headcount  │
         │ · schedule_iv  │ │ · request_leave  │ │ · get_attrition  │
         │ · send_decision│ │ · raise_ticket   │ │ · get_hiring_pipe│
         │ · get_app_stat │ │ · get_payslip    │ │ · get_dept_stats │
         │                │ │ · approve_leave  │ │                  │
         └────────────────┘ └──────────────────┘ └──────────────────┘
```

---

## Role → Agent Mapping (The Key Table)

This is what the orchestrator uses. Each cell shows what that role
can DO through that agent:

```
┌─────────────┬──────────────────────┬──────────────────────┬──────────────────┐
│  USER ROLE  │  RECRUITMENT AGENT   │  EMPLOYEE SVC AGENT  │ ANALYTICS AGENT  │
│             │    (Port 8001)       │    (Port 8002)       │   (Port 8003)    │
├─────────────┼──────────────────────┼──────────────────────┼──────────────────┤
│             │                      │                      │                  │
│  APPLICANT  │ ✅ Check app status  │ ❌ No access         │ ❌ No access     │
│             │ ✅ View job openings │                      │                  │
│             │ ✅ Check IV schedule │                      │                  │
│             │                      │                      │                  │
├─────────────┼──────────────────────┼──────────────────────┼──────────────────┤
│             │                      │                      │                  │
│  EMPLOYEE   │ ❌ No access         │ ✅ Search policies   │ ❌ No access     │
│             │                      │ ✅ Request leave     │                  │
│             │                      │ ✅ Check leave bal.  │                  │
│             │                      │ ✅ Raise query/ticket│                  │
│             │                      │ ✅ Get payslip       │                  │
│             │                      │ ✅ Report issue      │                  │
│             │                      │                      │                  │
├─────────────┼──────────────────────┼──────────────────────┼──────────────────┤
│             │                      │                      │                  │
│  MANAGER    │ ✅ View candidates   │ ✅ Approve/reject    │ ✅ Team metrics  │
│             │    for their dept    │    leave requests    │ ✅ Team attrition│
│             │ ✅ Interview feedback│ ✅ View team queries │                  │
│             │                      │ ✅ Escalate issues   │                  │
│             │                      │                      │                  │
├─────────────┼──────────────────────┼──────────────────────┼──────────────────┤
│             │                      │                      │                  │
│  HR ADMIN   │ ✅ Screen resumes   │ ✅ View ALL queries  │ ✅ Dept analytics│
│             │ ✅ Rank candidates   │ ✅ Resolve tickets   │ ✅ Compliance    │
│             │ ✅ Schedule IV       │ ✅ Manage leave      │    stats         │
│             │ ✅ Send offer/reject │ ✅ Onboarding status │                  │
│             │                      │                      │                  │
├─────────────┼──────────────────────┼──────────────────────┼──────────────────┤
│             │                      │                      │                  │
│  CEO        │ ❌ No direct access  │ ❌ No direct access  │ ✅ ALL company   │
│             │ (gets hiring metrics │ (gets satisfaction   │    metrics       │
│             │  through Analytics)  │  scores thru Analyt.)│ ✅ Hiring pipe   │
│             │                      │                      │ ✅ Headcount     │
│             │                      │                      │ ✅ Attrition     │
│             │                      │                      │ ✅ Dept breakdown│
│             │                      │                      │ ✅ Cost insights │
│             │                      │                      │                  │
└─────────────┴──────────────────────┴──────────────────────┴──────────────────┘
```

---

## Why This Architecture (Evidence-Backed)

### EVIDENCE 1: Centralized > Decentralized for sequential HR tasks

Source: Kim et al., "Towards a Science of Scaling Agent Systems"
        Google DeepMind + MIT, December 2025 (arXiv:2512.08296)
        180 agent configurations tested across GPT, Gemini, Claude

Finding: "Centralized coordination improves performance by 80.8% on 
parallelizable tasks... Yet for sequential reasoning tasks, every 
multi-agent variant degraded performance by 39-70%."

Finding: "Independent agents amplify errors 17.2×, while centralized 
coordination contains this to 4.4×."

Application: HR workflows are mostly sequential (user asks → agent 
processes → returns answer). Our orchestrator provides centralized 
coordination. Sub-agents never talk to each other — only through
the orchestrator. This contains errors to 4.4× instead of 17.2×.


### EVIDENCE 2: Architecture-task alignment > number of agents

Source: Same DeepMind paper + Zhang et al. (2025)

Finding: "Architecture-task alignment matters more than team size... 
Zhang et al. achieve superior performance at 6-45% cost through 
query-dependent configurations."

Application: Our 3 agents map 1:1 to 3 HR domains. No overlap. No 
ambiguity. The orchestrator's routing table is deterministic for 90%+ 
of queries. This IS architecture-task alignment.


### EVIDENCE 3: Role-based routing mirrors real HRIS design

Source: SAP SuccessFactors, Workday, BambooHR architecture docs
        AIHR "HRIS 101" (2025)

Finding: "An HRIS operates as a centralized digital hub... HR teams, 
managers, payroll staff, and employees all use an HRIS to manage HR 
processes through role-based user interfaces."

Application: Our orchestrator injects role context into every A2A 
message. The sub-agent sees: "Role: EMPLOYEE. Request: I need to 
take leave next Friday." vs "Role: MANAGER. Request: Show me pending 
leave requests for my team." Same agent, same leave data, different 
response based on role. This is exactly how enterprise HRIS works.


### EVIDENCE 4: Anthropic's multi-agent research validated orchestrator pattern

Source: Hadfield et al., "How we built our multi-agent research system"
        Anthropic Engineering, 2025

Finding: Early versions "spent 80% more tokens than necessary" because 
sub-agents "duplicated work, left gaps, or failed to find necessary 
information" when given vague delegation instructions.

Application: Our orchestrator sends explicit, role-tagged requests 
to sub-agents. Never vague delegation like "handle this HR thing." 
Always: "Role: HR. Intent: screen_resume. Data: {candidate_json}."


### EVIDENCE 5: MetaGPT validated specialized sub-agents

Source: Hong et al., "MetaGPT: Meta Programming for A Multi-Agent 
Collaborative Framework", ICLR 2024

Finding: Meta-programming workflows where a central coordinator 
assigns specialized roles to sub-agents reduced hallucination 
cascades compared to unstructured multi-agent chat.

Application: Each sub-agent has a focused system prompt and 
domain-specific tools. The Recruitment Agent CANNOT answer policy 
questions. The Employee Services Agent CANNOT screen resumes. 
Specialization = fewer hallucinations.


### WHY NOT 2 SUB-AGENTS?

- Merging Recruitment + Employee Services = 8+ tools in one agent
- GPT-4o tool selection degrades past 6-7 tools (empirical finding
  from LangChain community — model gets confused choosing between
  too many similar-sounding tools)
- Loses the Analytics Agent entirely, which is the CEO's interface
- Less A2A surface area for judges

### WHY NOT 4+ SUB-AGENTS?

- DeepMind: "More agents often hits a ceiling and can even degrade 
  performance if not aligned with task properties"
- 5+ containers = Docker networking nightmare for beginners
- Each additional container adds ~30-45 min setup/debug time
- Diminishing returns on A2A showcase (3 channels is enough)

### WHY NOT AGENT-PER-ROLE (5 agents)?

- Employee "request leave" and Manager "approve leave" both need 
  the same leave data → code duplication
- HR "screen resume" and Applicant "check status" both need the 
  same applicant data → code duplication  
- Violates domain-driven design: functions that share data should 
  live in the same service
- 6 containers total = unrealistic for beginner team in 24 hours

---

## Sub-Agent Tool Specifications

### RECRUITMENT AGENT — Tools (5)

```python
@tool
def screen_resume(resume_text: str, job_role: str) -> str:
    """Screen a candidate resume against job requirements. Extracts 
    skills, experience, education and scores match quality 1-100.
    Use when HR asks to evaluate or review a resume.
    Args:
        resume_text: The candidate's resume as plain text
        job_role: The job title to screen against (e.g., 'Python Developer')
    """

@tool  
def rank_candidates(job_role: str) -> str:
    """Get ranked list of all candidates for a specific job role, 
    sorted by match score. Use when HR wants to see top candidates
    or compare applicants.
    Args:
        job_role: The job title to get candidates for
    """

@tool
def schedule_interview(candidate_id: str, interviewer: str, preferred_date: str) -> str:
    """Schedule an interview between a candidate and interviewer.
    Checks mock calendar for available slots and books the first match.
    Args:
        candidate_id: Candidate ID (e.g., 'CAND-001')
        interviewer: Name of the interviewer
        preferred_date: Preferred date in YYYY-MM-DD format
    """

@tool
def send_decision(candidate_id: str, decision: str, message: str) -> str:
    """Send an offer or rejection notification to a candidate.
    Creates a mock email record with the decision.
    Args:
        candidate_id: Candidate ID
        decision: Either 'offer' or 'rejection'
        message: Custom message to include in the email
    """

@tool
def get_application_status(candidate_id: str) -> str:
    """Check the current status of a job application. Returns stage
    (applied/screening/interview/offer/rejected), timeline, and next steps.
    Use when an applicant asks about their application.
    Args:
        candidate_id: Candidate ID (e.g., 'CAND-001')
    """
```

### EMPLOYEE SERVICES AGENT — Tools (6)

```python
@tool
def search_hr_policy(query: str) -> str:
    """Search company HR policy handbook. Returns matching policy text
    with section references. Use when anyone asks about company rules,
    leave policies, remote work, benefits, dress code, etc.
    Args:
        query: Natural language question about HR policies
    """

@tool
def request_leave(employee_id: str, leave_type: str, start_date: str, end_date: str, reason: str) -> str:
    """Submit a leave request on behalf of an employee. Creates a 
    pending request that requires manager approval.
    Args:
        employee_id: Employee ID (e.g., 'EMP-001')
        leave_type: Type of leave (annual/sick/parental/unpaid)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        reason: Reason for leave
    """

@tool
def check_leave_balance(employee_id: str) -> str:
    """Check remaining leave balance for an employee. Shows annual,
    sick, and parental leave days remaining for current year.
    Args:
        employee_id: Employee ID
    """

@tool
def raise_ticket(employee_id: str, category: str, description: str, priority: str) -> str:
    """Raise an HR support ticket for an employee query or complaint.
    Categories: payroll, benefits, harassment, workplace_safety, 
    documents, general. Harassment/safety auto-escalate to P1.
    Args:
        employee_id: Employee ID
        category: Ticket category
        description: Detailed description of the issue
        priority: P1-Critical / P2-High / P3-Medium / P4-Low
    """

@tool
def get_payslip(employee_id: str, month: str) -> str:
    """Retrieve payslip data for an employee for a specific month.
    Returns gross salary, deductions, net pay, and tax details.
    Args:
        employee_id: Employee ID
        month: Month in YYYY-MM format (e.g., '2026-02')
    """

@tool
def approve_leave(request_id: str, decision: str, manager_comment: str) -> str:
    """Approve or reject a pending leave request. Only accessible to
    Manager and HR roles. Updates the leave request status.
    Args:
        request_id: Leave request ID (e.g., 'LR-001')
        decision: 'approved' or 'rejected'
        manager_comment: Optional comment explaining the decision
    """
```

### ANALYTICS & INSIGHTS AGENT — Tools (4)

```python
@tool
def get_headcount(department: str = "all") -> str:
    """Get current headcount breakdown by department, role level,
    and employment type. Returns total, active, and on-leave counts.
    Args:
        department: Department name or 'all' for company-wide
    """

@tool
def get_attrition_report(period: str = "2025") -> str:
    """Get employee attrition/turnover report. Shows voluntary vs
    involuntary exits, department-wise breakdown, average tenure
    of departing employees, and trend comparison.
    Args:
        period: Year or quarter (e.g., '2025' or '2025-Q4')
    """

@tool
def get_hiring_pipeline(department: str = "all") -> str:
    """Get recruitment pipeline status. Shows open positions, 
    candidates in each stage, average time-to-hire, offer 
    acceptance rate, and cost-per-hire.
    Args:
        department: Department name or 'all'
    """

@tool
def get_department_stats(department: str) -> str:
    """Get detailed department statistics including headcount,
    average salary, leave utilization, open tickets, satisfaction
    score, and performance distribution.
    Args:
        department: Department name (e.g., 'Engineering')
    """
```

---

## Mock Data Strategy (NO external APIs — all in-memory Python dicts)

### Mock Employees (10-12 records)
```python
EMPLOYEES = {
    "EMP-001": {"name": "Priya Sharma", "dept": "Engineering", "role": "Senior Developer", 
                "salary": 1200000, "manager": "EMP-010", "join_date": "2023-03-15",
                "leave_balance": {"annual": 12, "sick": 7, "parental": 0}},
    "EMP-002": {"name": "Rahul Verma", "dept": "Marketing", "role": "Marketing Lead", ...},
    ...
}
```

### Mock Candidates (5-8 records)
```python
CANDIDATES = {
    "CAND-001": {"name": "Ananya Patel", "applied_for": "Python Developer",
                 "status": "screening", "resume_text": "...", "score": None, ...},
    ...
}
```

### Mock Policies (8-10 entries)
```python
POLICIES = {
    "annual_leave": {"title": "Annual Leave Policy", "section": "3.1", 
                     "text": "All full-time employees receive 20 days..."},
    ...
}
```

### Mock Analytics (pre-computed)
```python
COMPANY_METRICS = {
    "total_headcount": 247, "departments": {...}, 
    "attrition_rate": "8.2%", "avg_tenure": "3.4 years", ...
}
```

---

## How A2A Communication Flows (3 Examples)

### Example 1: Employee requests leave

```
USER (role=employee): "I want to take leave next Friday for a family event"

ORCHESTRATOR:
  [LOG] Role: EMPLOYEE | Intent: leave_request | Route: employee-services-agent
  [A2A] → POST http://employee-services:8002/
  {
    "jsonrpc": "2.0", "id": "req-042",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Role: EMPLOYEE (EMP-001). 
                   Request: I want to take leave next Friday for a family event.
                   Available tools: request_leave, check_leave_balance, search_hr_policy"}]
      }
    }
  }

EMPLOYEE SERVICES AGENT:
  [LangChain] Thought: User wants leave. Let me check balance first.
  [Tool Call] check_leave_balance("EMP-001") → "Annual: 12 days remaining"
  [Tool Call] request_leave("EMP-001", "annual", "2026-03-13", "2026-03-13", "Family event")
  [Response] "Leave request LR-047 submitted for March 13. You have 12 annual 
             leave days remaining (11 after this request). Your manager Vikram 
             will be notified for approval."

ORCHESTRATOR:
  [LOG] ← Task completed | Response received from employee-services-agent
  → Returns response to user
```

### Example 2: HR screens a candidate

```
USER (role=hr): "Can you review Ananya Patel's resume for the Python Developer position?"

ORCHESTRATOR:
  [LOG] Role: HR | Intent: screen_resume | Route: recruitment-agent
  [A2A] → POST http://recruitment-agent:8001/

RECRUITMENT AGENT:
  [Tool Call] screen_resume(resume_text="...", job_role="Python Developer")
  [Response] "Candidate CAND-001 Ananya Patel — Score: 82/100
             ✅ Strengths: 4 years Python, Django, REST APIs, AWS
             ⚠️ Gaps: No Kubernetes experience (required), no ML background
             📋 Recommendation: Proceed to technical interview with focus 
             on container orchestration skills."
```

### Example 3: CEO asks for company insights

```
USER (role=ceo): "Give me an overview of our company's health"

ORCHESTRATOR:
  [LOG] Role: CEO | Intent: company_metrics | Route: analytics-agent
  [A2A] → POST http://analytics-agent:8003/

ANALYTICS AGENT:
  [Tool Call] get_headcount("all")
  [Tool Call] get_attrition_report("2025")
  [Tool Call] get_hiring_pipeline("all")
  [Response] "📊 Company Health Dashboard — March 2026
             
             👥 Headcount: 247 employees across 6 departments
                Engineering: 98 | Marketing: 34 | Sales: 45 | HR: 12 | ...
             
             📉 Attrition: 8.2% annual (industry avg: 13.2%)
                Top reason: Career growth (42%)
                Most affected: Mid-level engineers (3-5 yr tenure)
             
             📋 Hiring Pipeline: 12 open positions
                Average time-to-hire: 34 days
                Offer acceptance rate: 78%
                Pipeline: 67 applied → 23 screening → 8 interview → 3 offer
             
             💡 Key Insight: Engineering attrition is below average but 
                hiring pipeline shows 34-day time-to-hire. Consider 
                fast-tracking senior developer candidates."
```

---

## Docker Compose (Final)

```yaml
services:
  hr-orchestrator:
    build: ./orchestrator
    container_name: hr-orchestrator
    ports:
      - "5000:5000"
    environment:
      - RECRUITMENT_AGENT_URL=http://recruitment-agent:8001
      - EMPLOYEE_SERVICES_URL=http://employee-services:8002
      - ANALYTICS_AGENT_URL=http://analytics-agent:8003
    env_file: .env
    depends_on:
      recruitment-agent:
        condition: service_healthy
      employee-services:
        condition: service_healthy
      analytics-agent:
        condition: service_healthy
    networks:
      - agents-net

  recruitment-agent:
    build: ./recruitment-agent
    container_name: recruitment-agent
    env_file: .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - agents-net

  employee-services:
    build: ./employee-services
    container_name: employee-services
    env_file: .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - agents-net

  analytics-agent:
    build: ./analytics-agent
    container_name: analytics-agent
    env_file: .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - agents-net

networks:
  agents-net:
    external: true
```

---

## File Structure (Final)

```
hrflow-ai/
├── docker-compose.yml
├── .env                          # OPENAI_API_KEY (gitignored)
├── .gitignore
├── README.md
│
├── shared/                       # Shared mock data (copied into each container)
│   ├── mock_data.py              # All mock employees, candidates, policies, metrics
│   └── models.py                 # Shared Pydantic models for A2A
│
├── orchestrator/                 # Container 1 — NO LLM, pure routing
│   ├── Dockerfile
│   ├── docker-compose.yml        # Standalone for Nasiko upload
│   ├── AgentCard.json
│   └── src/
│       ├── __init__.py
│       ├── __main__.py           # FastAPI + A2A JSON-RPC handler
│       ├── router.py             # Role + intent → agent routing
│       ├── a2a_client.py         # HTTP client to call sub-agents
│       └── models.py
│
├── recruitment-agent/            # Container 2 — Hiring domain
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── AgentCard.json
│   └── src/
│       ├── __init__.py
│       ├── __main__.py
│       ├── agent.py              # LangChain agent + GPT-4o
│       ├── tools.py              # 5 recruitment tools
│       ├── mock_data.py          # Candidates, jobs, calendar slots
│       └── models.py
│
├── employee-services/            # Container 3 — Day-to-day HR domain
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── AgentCard.json
│   └── src/
│       ├── __init__.py
│       ├── __main__.py
│       ├── agent.py
│       ├── tools.py              # 6 employee service tools
│       ├── mock_data.py          # Employees, policies, leave data, tickets
│       └── models.py
│
├── analytics-agent/              # Container 4 — Insights domain
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── AgentCard.json
│   └── src/
│       ├── __init__.py
│       ├── __main__.py
│       ├── agent.py
│       ├── tools.py              # 4 analytics tools
│       ├── mock_data.py          # Pre-computed company metrics
│       └── models.py
```

---

## Demo Script (3 Minutes — All 5 Roles)

### 0:00-0:20 — Hook
"HR teams juggle recruitment, employee services, and executive reporting
across disconnected tools. HRFlow AI unifies all three through intelligent
AI agents that communicate via Google's A2A protocol — one agent per
domain, serving all 5 user roles."

### 0:20-0:50 — Applicant Role
Select role: APPLICANT
"What's the status of my application?" 
→ Recruitment Agent responds with stage + next steps
Show A2A log: Orchestrator → Recruitment Agent → Response

### 0:50-1:20 — Employee Role  
Select role: EMPLOYEE
"I want to take leave next Friday. Also, what's our remote work policy?"
→ Employee Services Agent handles both: submits leave + returns policy
Show A2A log

### 1:20-1:50 — HR Role
Select role: HR
"Review Ananya's resume for the Python Developer role and schedule 
her interview for next week"
→ Recruitment Agent: screens resume (82/100) + books interview slot
Show A2A log with multi-tool chain

### 1:50-2:20 — CEO Role
Select role: CEO
"How's the company doing?"
→ Analytics Agent: headcount + attrition + hiring pipeline summary
Show rich formatted response with key insights

### 2:20-2:50 — Architecture + A2A
Flash architecture diagram showing 4 containers, 3 A2A channels
Show Docker terminal: `docker compose ps` — all 4 healthy
Show GitHub repo structure
"Built with: LangChain, GPT-4o, FastAPI, Docker, A2A Protocol"

### 2:50-3:00 — Future Vision
"Next: real HRIS integration, Slack/Teams bot, multi-language support,
compliance automation, performance review cycles."
Team credits.

---

## Decision Summary Table

| Decision            | Choice                          | Evidence                                          |
|---------------------|---------------------------------|---------------------------------------------------|
| Agent organization  | By domain, not by role          | Real HRIS architecture (SAP, Workday, BambooHR)   |
| Number of sub-agents| 3 (recruitment, employee, analytics)| DeepMind 2025: alignment > team size           |
| Coordination        | Centralized orchestrator        | DeepMind 2025: centralized = 4.4× error vs 17.2×  |
| Orchestrator LLM    | None (keyword routing + fallback)| Anthropic 2025: vague delegation = 80% more tokens|
| Role handling       | Orchestrator injects role context| HRIS standard: role-based access, shared modules  |
| Sub-agent isolation | Each has own tools + data       | MetaGPT ICLR 2024: specialization ↓ hallucination |
| Data                | In-memory Python dicts          | 24-hr constraint: no DB setup overhead             |
| LLM                 | GPT-4o, temperature=0           | Deterministic HR decisions required                |
| Communication       | A2A JSON-RPC 2.0                | Hackathon requirement + judge emphasis             |
| Docker containers   | 4 total (1 orchestrator + 3 agents)| Max feasible for beginner team in 24 hours      |
