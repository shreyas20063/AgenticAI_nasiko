# MISTAKE TRACKER — HRFlow AI

> **Instructions:** Log every wrong approach, dead end, or incorrect assumption here.
> This is NOT for bugs (code errors) — it's for DESIGN and APPROACH mistakes.
> This file teaches Claude Code to avoid repeating strategic errors.

---

## Template

```
## MISTAKE-XXX: [Short title]
- **Phase:** [Which checkpoint]
- **What I tried:** [The approach that didn't work]
- **Time wasted:** [Approximate minutes lost]
- **Why it failed:** [Root cause analysis]
- **Correct approach:** [What actually works]
- **Lesson learned:** [One-line rule for the future]
```

---

## Logged Mistakes

(none yet — update as you go)

---

## Pre-loaded Anti-patterns (from pitfalls_guide.md)

> These are mistakes OTHER teams have made. Avoid them.

### ANTIPATTERN-001: Building agent-per-role instead of agent-per-domain
- **Wrong:** 5 agents (one for employee, applicant, HR, manager, CEO)
- **Why wrong:** Employee "request leave" and Manager "approve leave" need same data = code duplication
- **Correct:** 3 domain agents (recruitment, employee-services, analytics) with role-based context injection

### ANTIPATTERN-002: Using LLM for ALL routing decisions
- **Wrong:** Every user message goes through GPT-4o to decide which agent handles it
- **Why wrong:** Adds 1-3 seconds latency per request, costs tokens, occasionally misroutes
- **Correct:** Keyword rules handle 90%+ of routing deterministically; LLM only for ambiguous cases

### ANTIPATTERN-003: Trying to parse PDF resumes in a 24-hour hackathon
- **Wrong:** Implementing PyPDF2/pdfplumber to extract text from resume PDFs
- **Why wrong:** Multi-column layouts, scanned PDFs, encoding issues eat 3-4 hours of debugging
- **Correct:** Accept plain text resume input. Mention PDF support as "future enhancement" in README

### ANTIPATTERN-004: Setting up real Google Calendar OAuth for interview scheduling
- **Wrong:** Implementing full OAuth2 flow for Google Calendar API
- **Why wrong:** 2-4 hours for credential setup, scope permissions, token refresh handling
- **Correct:** Mock calendar data with realistic time slots. Judges evaluate agent logic, not API plumbing

### ANTIPATTERN-005: Letting sub-agents communicate with each other (peer-to-peer)
- **Wrong:** Recruitment agent directly calls Employee Services agent
- **Why wrong:** DeepMind 2025: decentralized degrades performance 39-70% on sequential tasks
- **Correct:** All communication goes through orchestrator (hub-and-spoke)

### ANTIPATTERN-006: Putting all tools in one agent
- **Wrong:** Single LangChain agent with 15 tools
- **Why wrong:** GPT-4o tool selection quality degrades past 6-7 tools
- **Correct:** Split across 3 specialized agents with 4-6 tools each

### ANTIPATTERN-007: Not pinning dependency versions
- **Wrong:** `langchain>=0.2.0` in requirements.txt
- **Why wrong:** Docker build pulls latest version which may conflict with langchain-openai version
- **Correct:** Pin exact versions: `langchain==0.2.16`

### ANTIPATTERN-008: Spending hours on UI before agent logic works
- **Wrong:** Building a React frontend before the agents respond correctly to curl
- **Why wrong:** Agents are the deliverable, not the UI. A broken agent with pretty UI scores 0
- **Correct:** Get all agents working via curl first. UI/frontend is a stretch goal

### ANTIPATTERN-009: One giant git commit at submission
- **Wrong:** Coding for 20 hours then `git add . && git commit -m "done"`
- **Why wrong:** Judges check commit history for progression. One commit looks like copied code
- **Correct:** Commit after each phase/checkpoint with descriptive messages

### ANTIPATTERN-010: Not testing the full A2A flow end-to-end before hour 16
- **Wrong:** Building all 3 agents independently then integrating at hour 20
- **Why wrong:** Integration bugs are the hardest to debug. Discovery at hour 20 = no time to fix
- **Correct:** Phase 5 (Integration) must complete by hour 12. Phases 6-7 are polish only
