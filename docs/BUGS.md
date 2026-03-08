# BUG TRACKER — HRFlow AI

> **Instructions:** Log every bug here immediately when found. Include root cause and fix.
> This file prevents the same bug from recurring and gives Claude Code memory across sessions.

---

## Template

```
## BUG-XXX: [Short title]
- **Phase:** [Which checkpoint phase]
- **Found in:** [file:line or component]
- **Symptom:** [What the user/developer saw]
- **Root cause:** [Why it actually happened]
- **Fix applied:** [Exact change made]
- **Files changed:** [List of files]
- **Prevention:** [Rule to avoid recurrence]
- **Status:** ✅ Fixed / 🔄 In Progress / ❌ Won't Fix
```

---

## Active Bugs

(none yet)

---

## Resolved Bugs

(none yet)

---

## Known Risks (Pre-identified from pitfalls_guide.md)

### RISK-001: agent_scratchpad missing from prompt
- **Likelihood:** HIGH (most common LangChain beginner bug)
- **Impact:** Agent enters infinite loop, never returns response
- **Mitigation:** CLAUDE.md rule #1 — always include MessagesPlaceholder("agent_scratchpad")

### RISK-002: localhost used instead of Docker service name
- **Likelihood:** HIGH (beginner Docker mistake)
- **Impact:** Container-to-container communication fails silently
- **Mitigation:** CLAUDE.md Docker rule #3 — always use service names

### RISK-003: LangChain import path wrong (0.1.x vs 0.2.x)
- **Likelihood:** HIGH (most tutorials show old imports)
- **Impact:** ModuleNotFoundError at startup
- **Mitigation:** CLAUDE.md LangChain rules #6-8 — use exact import paths

### RISK-004: Pydantic v1 vs v2 conflict
- **Likelihood:** MEDIUM (LangChain uses v1 internally, FastAPI uses v2)
- **Impact:** ValidationError on model instantiation
- **Mitigation:** Use langchain_core.pydantic_v1 for LangChain models, regular pydantic for FastAPI

### RISK-005: Docker agents-net network doesn't exist
- **Likelihood:** HIGH (external network must be pre-created)
- **Impact:** docker compose up fails immediately
- **Mitigation:** README step 1: `docker network create agents-net`

### RISK-006: Sub-agent not ready when orchestrator starts
- **Likelihood:** MEDIUM
- **Impact:** First request to orchestrator fails with connection refused
- **Mitigation:** healthcheck + depends_on with condition: service_healthy

### RISK-007: Tool docstrings too vague
- **Likelihood:** HIGH (tempting to write short descriptions)
- **Impact:** LLM picks wrong tool or calls tools unnecessarily
- **Mitigation:** Every docstring must say WHEN to use, WHAT args mean, WHAT returns

### RISK-008: GPT-4o hallucinates HR policies
- **Likelihood:** HIGH if no retrieval grounding
- **Impact:** Agent confidently states fake policies
- **Mitigation:** System prompt: "ONLY answer from retrieved policy text. Never fabricate."

### RISK-009: Temperature > 0 causes inconsistent resume scoring
- **Likelihood:** MEDIUM (default is often 0.7)
- **Impact:** Same resume gets different scores on different runs
- **Mitigation:** CLAUDE.md rule: temperature=0 for all agents

### RISK-010: JSON-RPC missing required fields
- **Likelihood:** MEDIUM
- **Impact:** -32600 Invalid Request error from sub-agent
- **Mitigation:** A2A client must always send jsonrpc, id, method, params
