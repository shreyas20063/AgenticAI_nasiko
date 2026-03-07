# PROGRESS TRACKER — HRFlow AI

> **Instructions:** Update checkboxes after completing each item.
> This is the single source of truth for project status.

---

## Phase 0: Project Setup
- [x] Directory structure created
- [x] CLAUDE.md in project root
- [x] docs/ folder with all reference files
- [x] .gitignore created
- [x] .env file with OPENAI_API_KEY
- [x] Git repo initialized, first commit made
- [x] `docker network create agents-net` documented in README

## Phase 1: Shared Foundation
- [ ] shared/mock_data.py — all mock data (employees, candidates, policies, metrics)
- [ ] shared/a2a_models.py — Pydantic models for A2A protocol
- [ ] Mock data tested: can import and access all data structures
- [ ] Git commit: "feat: add shared mock data and A2A models"

## Phase 2: Employee Services Agent (Port 8002)
- [ ] src/__main__.py — FastAPI app with A2A JSON-RPC handler + /health + /.well-known/agent.json
- [ ] src/agent.py — LangChain agent with GPT-4o, temperature=0, max_iterations=10
- [ ] src/tools.py — 6 tools: search_hr_policy, request_leave, check_leave_balance, raise_ticket, get_payslip, approve_leave
- [ ] Dockerfile working
- [ ] docker-compose.yml (standalone)
- [ ] AgentCard.json
- [ ] Tested via curl: policy question returns correct answer
- [ ] Tested via curl: leave request creates pending request
- [ ] Tested via curl: harassment query triggers escalation
- [ ] Git commit: "feat: employee services agent with 6 tools"

## Phase 3: Recruitment Agent (Port 8001)
- [ ] src/__main__.py — FastAPI + A2A handler
- [ ] src/agent.py — LangChain agent
- [ ] src/tools.py — 5 tools: screen_resume, rank_candidates, schedule_interview, send_decision, get_application_status
- [ ] Dockerfile working
- [ ] docker-compose.yml (standalone)
- [ ] AgentCard.json
- [ ] Tested via curl: resume screening returns score + analysis
- [ ] Tested via curl: interview scheduling returns confirmed slot
- [ ] Tested via curl: applicant status check works
- [ ] Git commit: "feat: recruitment agent with 5 tools"

## Phase 4: Analytics Agent (Port 8003)
- [ ] src/__main__.py — FastAPI + A2A handler
- [ ] src/agent.py — LangChain agent
- [ ] src/tools.py — 4 tools: get_headcount, get_attrition_report, get_hiring_pipeline, get_department_stats
- [ ] Dockerfile working
- [ ] docker-compose.yml (standalone)
- [ ] AgentCard.json
- [ ] Tested via curl: CEO query returns full company overview
- [ ] Tested via curl: department breakdown works
- [ ] Git commit: "feat: analytics agent with 4 tools"

## Phase 5: Orchestrator (Port 5000) — THE CRITICAL INTEGRATION PHASE
- [ ] src/__main__.py — FastAPI + A2A handler (user-facing)
- [ ] src/router.py — Hybrid keyword + LLM fallback routing with role context injection
- [ ] src/a2a_client.py — HTTP client to call sub-agents via A2A JSON-RPC
- [ ] Dockerfile working
- [ ] docker-compose.yml (standalone for Nasiko)
- [ ] AgentCard.json (main agent card for Nasiko platform)
- [ ] Full docker-compose.yml (all 4 services)
- [ ] `docker compose up --build` — all 4 containers start and are healthy
- [ ] Tested: Employee role → leave request → Employee Services Agent → response
- [ ] Tested: Applicant role → status check → Recruitment Agent → response
- [ ] Tested: HR role → screen resume → Recruitment Agent → response
- [ ] Tested: CEO role → company overview → Analytics Agent → response
- [ ] Tested: Manager role → approve leave → Employee Services Agent → response
- [ ] A2A logging visible in orchestrator output
- [ ] Git commit: "feat: orchestrator with A2A routing to all 3 sub-agents"

## Phase 6: Hardening & Edge Cases
- [ ] Error handling: sub-agent timeout returns graceful message
- [ ] Error handling: invalid role returns helpful error
- [ ] Error handling: unknown intent routes to best-guess agent with disclaimer
- [ ] Role permission enforcement: employee can't approve leave
- [ ] Role permission enforcement: applicant can't see other applicants
- [ ] Role permission enforcement: CEO queries route only to analytics
- [ ] Tested 10+ diverse queries across all roles
- [ ] Git commit: "fix: add error handling and role permissions"

## Phase 7: Polish & Submission
- [ ] README.md complete (setup instructions, architecture diagram, team info)
- [ ] Code comments and docstrings complete
- [ ] docker-compose.yml validated for Nasiko deployment
- [ ] Each sub-agent has standalone docker-compose.yml for individual Nasiko upload
- [ ] 3-minute demo video recorded
- [ ] LinkedIn post drafted
- [ ] Final git push to public GitHub repo
- [ ] Live deployment on Nasiko infrastructure verified
- [ ] All submission requirements met (GitHub repo, video, LinkedIn, deployment)

---

## Current Phase: Phase 0 COMPLETE — Ready for Phase 1
## Blocker: None
## Notes: Phase 0 scaffolding complete. All directories, Dockerfiles, docker-compose files, AgentCards, and placeholder files created.
