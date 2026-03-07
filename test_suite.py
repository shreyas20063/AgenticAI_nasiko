"""Comprehensive edge case test suite for HRFlow AI."""

import json
import sys
import time
import concurrent.futures
import urllib.request
import urllib.error

BASE_URL = "http://localhost:5000"
results = []
api_calls = [0]

def send(test_id, label, text):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": test_id,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}]
            }
        }
    }).encode()

    try:
        req = urllib.request.Request(
            BASE_URL + "/",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            api_calls[0] += 1
            text_out = data.get("result", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("text", "")
            return (test_id, label, "OK", text_out)
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        api_calls[0] += 1
        return (test_id, label, f"HTTP {e.code}", str(body))
    except Exception as ex:
        return (test_id, label, "ERROR", str(ex))


TESTS = [
    # ── ORCHESTRATOR EDGE CASES ─────────────────────────────────
    ("t001", "No role prefix",
     "What is the leave policy?"),
    ("t002", "Unknown role INTERN",
     "Role: INTERN (INT-001). What is the leave policy?"),
    ("t003", "Empty text",
     ""),
    ("t004", "Role only, no question",
     "Role: EMPLOYEE (EMP-001)."),

    # ── EMPLOYEE: POLICY SEARCH ──────────────────────────────────
    ("t010", "Annual leave policy",
     "Role: EMPLOYEE (EMP-001). What is the annual leave policy?"),
    ("t011", "Sick leave policy",
     "Role: EMPLOYEE (EMP-001). How many sick days do I get?"),
    ("t012", "Remote work policy",
     "Role: EMPLOYEE (EMP-001). What is the remote work policy?"),
    ("t013", "Parental leave policy",
     "Role: EMPLOYEE (EMP-001). What is the parental leave policy?"),
    ("t014", "Dress code policy",
     "Role: EMPLOYEE (EMP-001). What is the dress code policy?"),
    ("t015", "Harassment policy",
     "Role: EMPLOYEE (EMP-001). What is the harassment policy?"),
    ("t016", "Expense reimbursement policy",
     "Role: EMPLOYEE (EMP-001). What is the expense reimbursement policy?"),
    ("t017", "Performance review policy",
     "Role: EMPLOYEE (EMP-001). How does the performance review work?"),
    ("t018", "Probation policy",
     "Role: EMPLOYEE (EMP-003). What is the probation period?"),
    ("t019", "Code of conduct",
     "Role: EMPLOYEE (EMP-001). What is the code of conduct?"),
    ("t020", "Non-existent policy",
     "Role: EMPLOYEE (EMP-001). What is the stock options vesting cliff policy?"),

    # ── EMPLOYEE: LEAVE BALANCE ──────────────────────────────────
    ("t030", "Check leave balance valid",
     "Role: EMPLOYEE (EMP-001). What is my leave balance?"),
    ("t031", "Check leave balance another employee (EMP-010)",
     "Role: EMPLOYEE (EMP-001). Check leave balance for EMP-010."),
    ("t032", "Check balance invalid employee",
     "Role: EMPLOYEE (EMP-001). Check leave balance for EMP-999."),
    ("t033", "HR checking any employee balance",
     "Role: HR. Check leave balance for EMP-007."),

    # ── EMPLOYEE: LEAVE REQUESTS ─────────────────────────────────
    ("t040", "Request annual leave valid",
     "Role: EMPLOYEE (EMP-001). I want to take annual leave from 2026-03-20 to 2026-03-21. Reason: Personal."),
    ("t041", "Request sick leave valid",
     "Role: EMPLOYEE (EMP-003). I need sick leave from 2026-03-15 to 2026-03-15. Reason: Fever."),
    ("t042", "Request leave invalid type",
     "Role: EMPLOYEE (EMP-001). I want to take sabbatical leave from 2026-03-20 to 2026-03-21. Reason: Travel."),
    ("t043", "Request leave end before start",
     "Role: EMPLOYEE (EMP-004). I want annual leave from 2026-03-25 to 2026-03-20. Reason: Error."),
    ("t044", "Request leave exceeding balance (EMP-007 has 4 annual days, requesting 10)",
     "Role: EMPLOYEE (EMP-007). I want annual leave from 2026-03-16 to 2026-03-27. Reason: Vacation."),
    ("t045", "Request unpaid leave",
     "Role: EMPLOYEE (EMP-006). I want unpaid leave from 2026-04-01 to 2026-04-03. Reason: Personal trip."),
    ("t046", "Request parental leave",
     "Role: EMPLOYEE (EMP-001). I need parental leave from 2026-04-01 to 2026-04-03. Reason: New baby."),

    # ── EMPLOYEE: APPROVE LEAVE (ROLE ENFORCEMENT) ───────────────
    ("t050", "EMPLOYEE tries to approve leave (should be denied)",
     "Role: EMPLOYEE (EMP-001). Approve leave request LR-001."),
    ("t051", "MANAGER approves leave",
     "Role: MANAGER (EMP-010). Approve leave request LR-003 with comment: Approved, enjoy your vacation."),
    ("t052", "MANAGER rejects leave",
     "Role: MANAGER (EMP-010). Reject leave request LR-001 with comment: Cannot approve during sprint."),
    ("t053", "Approve non-existent leave request",
     "Role: HR. Approve leave request LR-999 with comment: Approved."),
    ("t054", "Approve already-approved leave request",
     "Role: HR. Approve leave request LR-002 with comment: Approved again."),

    # ── EMPLOYEE: PAYSLIPS ───────────────────────────────────────
    ("t060", "View own payslip",
     "Role: EMPLOYEE (EMP-001). Show me my payslip for 2026-02."),
    ("t061", "View another employee payslip (should be denied)",
     "Role: EMPLOYEE (EMP-001). Show me the payslip for EMP-002 for 2026-02."),
    ("t062", "Payslip unavailable month",
     "Role: EMPLOYEE (EMP-001). Show me my payslip for 2025-12."),
    ("t063", "HR views any payslip",
     "Role: HR. Show me the payslip for EMP-010 for 2026-01."),
    ("t064", "Payslip for employee with no records (EMP-999)",
     "Role: HR. Show me the payslip for EMP-999 for 2026-01."),
    ("t065", "EMP-007 views own payslip (on leave employee)",
     "Role: EMPLOYEE (EMP-007). Show me my payslip for 2026-02."),
    ("t066", "EMP-009 (HR Director) views own payslip",
     "Role: EMPLOYEE (EMP-009). Show me my payslip for 2026-01."),

    # ── EMPLOYEE: RAISE TICKETS ──────────────────────────────────
    ("t070", "Raise general ticket",
     "Role: EMPLOYEE (EMP-001). I need help with my access card not working. Please raise a general ticket with P3 priority."),
    ("t071", "Raise payroll ticket P2",
     "Role: EMPLOYEE (EMP-002). My payslip shows wrong HRA. Raise a payroll ticket P2."),
    ("t072", "Raise harassment ticket (auto-escalate)",
     "Role: EMPLOYEE (EMP-003). My manager is harassing me verbally. Raise a harassment ticket."),
    ("t073", "Raise workplace safety ticket (auto-escalate)",
     "Role: EMPLOYEE (EMP-004). There is a fire hazard in the operations area. Raise a workplace safety ticket."),
    ("t074", "Raise benefits ticket",
     "Role: EMPLOYEE (EMP-005). I have not received my health insurance card. Raise a benefits ticket P2."),
    ("t075", "Raise documents ticket",
     "Role: EMPLOYEE (EMP-008). I need an employment verification letter. Raise a documents ticket P3."),
    ("t076", "Raise ticket for invalid employee",
     "Role: HR. Raise a general ticket for EMP-999 with P4 priority about access issues."),

    # ── RECRUITMENT: APPLICANTS ──────────────────────────────────
    ("t080", "Applicant checks own status",
     "Role: APPLICANT (CAND-001). What is the status of my application?"),
    ("t081", "Applicant checks another applicant status (should be denied)",
     "Role: APPLICANT (CAND-001). What is the status of CAND-002?"),
    ("t082", "Applicant tries to screen resume (should be denied)",
     "Role: APPLICANT (CAND-001). Can you screen my resume for Python Developer?"),
    ("t083", "Applicant tries to rank candidates (should be denied)",
     "Role: APPLICANT (CAND-001). Show me the ranked candidates for Python Developer."),
    ("t084", "Applicant tries to schedule interview (should be denied)",
     "Role: APPLICANT (CAND-001). Schedule an interview for me."),
    ("t085", "Applicant tries to send offer (should be denied)",
     "Role: APPLICANT (CAND-001). Send me an offer letter."),
    ("t086", "Non-existent applicant status",
     "Role: APPLICANT (CAND-999). What is the status of my application?"),

    # ── RECRUITMENT: HR ACTIONS ──────────────────────────────────
    ("t090", "HR screens resume",
     "Role: HR. Screen this resume for Python Developer: John has 4 years Python Django FastAPI REST APIs PostgreSQL Docker Git experience."),
    ("t091", "HR screens resume for non-existent role",
     "Role: HR. Screen this resume for Blockchain Engineer: Alice has solidity experience."),
    ("t092", "HR ranks candidates for Python Developer",
     "Role: HR. Rank all candidates for Python Developer."),
    ("t093", "HR ranks candidates for DevOps Engineer",
     "Role: HR. Rank all candidates for DevOps Engineer."),
    ("t094", "HR ranks candidates for non-existent role",
     "Role: HR. Rank all candidates for Data Scientist."),
    ("t095", "HR schedules interview for valid candidate",
     "Role: HR. Schedule an interview for CAND-001 with Arjun Desai on 2026-03-17."),
    ("t096", "HR schedules interview for already-scheduled candidate",
     "Role: HR. Schedule an interview for CAND-002 with Priya Sharma on 2026-03-18."),
    ("t097", "HR schedules interview for rejected candidate",
     "Role: HR. Schedule an interview for CAND-006 with Vikram Singh on 2026-03-17."),
    ("t098", "HR schedules interview on unavailable date",
     "Role: HR. Schedule an interview for CAND-001 with Arjun Desai on 2026-05-15."),
    ("t099", "HR sends offer",
     "Role: HR. Send an offer to CAND-004 for DevOps Engineer. Message: We are pleased to offer you the position."),
    ("t100", "HR sends rejection",
     "Role: HR. Send a rejection to CAND-008. Message: We regret to inform you we have moved forward with other candidates."),
    ("t101", "HR sends invalid decision",
     "Role: HR. Send a counter-offer to CAND-001. Message: Here is a revised offer."),
    ("t102", "MANAGER views candidates",
     "Role: MANAGER (EMP-010). Show me ranked candidates for Python Developer."),
    ("t103", "MANAGER tries to send offer (should be denied)",
     "Role: MANAGER (EMP-010). Send an offer to CAND-001."),
    ("t104", "Get application status - hired candidate",
     "Role: HR. What is the status of CAND-005?"),
    ("t105", "Get application status - rejected candidate",
     "Role: HR. What is the status of CAND-006?"),

    # ── ANALYTICS: CEO ───────────────────────────────────────────
    ("t110", "CEO gets company headcount",
     "Role: CEO. What is our total company headcount?"),
    ("t111", "CEO gets Engineering headcount",
     "Role: CEO. What is the headcount in Engineering?"),
    ("t112", "CEO gets invalid department headcount",
     "Role: CEO. What is the headcount in Logistics?"),
    ("t113", "CEO gets attrition report",
     "Role: CEO. What is our attrition rate?"),
    ("t114", "CEO gets Marketing attrition",
     "Role: CEO. What is the attrition in Marketing?"),
    ("t115", "CEO gets hiring pipeline",
     "Role: CEO. How is our hiring pipeline looking?"),
    ("t116", "CEO gets department stats - Sales",
     "Role: CEO. Give me full stats on the Sales department."),
    ("t117", "CEO gets full company overview (multi-tool)",
     "Role: CEO. How is the company doing? Give me a complete overview."),
    ("t118", "CEO gets invalid department stats",
     "Role: CEO. Give me stats on the Logistics department."),

    # ── ANALYTICS: ACCESS CONTROL ────────────────────────────────
    ("t120", "EMPLOYEE tries analytics (should be denied)",
     "Role: EMPLOYEE (EMP-001). What is the company headcount?"),
    ("t121", "APPLICANT tries analytics (should be denied)",
     "Role: APPLICANT (CAND-001). What is the company attrition rate?"),
    ("t122", "MANAGER gets company headcount",
     "Role: MANAGER (EMP-010). What is the total company headcount?"),
    ("t123", "MANAGER gets own department stats",
     "Role: MANAGER (EMP-010). Give me stats on the Engineering department."),
    ("t124", "HR gets full analytics",
     "Role: HR. Give me the full attrition report."),
    ("t125", "HR gets hiring pipeline",
     "Role: HR. Show me the hiring pipeline for Engineering."),

    # ── CROSS-ROLE ROUTING EDGE CASES ────────────────────────────
    ("t130", "CEO asks about leave policy (should route to analytics as default, or employee-svc via keyword)",
     "Role: CEO. What is the leave policy?"),
    ("t131", "HR asks about hiring AND analytics in same message",
     "Role: HR. How many candidates do we have and what is our attrition rate?"),
    ("t132", "EMPLOYEE asks about headcount (should route to employee-svc due to restriction)",
     "Role: EMPLOYEE (EMP-001). Give me a headcount report."),
    ("t133", "MANAGER asks about leave for their team",
     "Role: MANAGER (EMP-010). Check the leave balance for EMP-001."),
]

def run_test(t):
    tid, label, text = t
    start = time.time()
    result = send(tid, label, text)
    elapsed = time.time() - start
    return result + (elapsed,)

print(f"Running {len(TESTS)} tests...\n")
print(f"{'ID':<6} {'Label':<55} {'Status':<8} {'Time':>6}  Response Preview")
print("─" * 160)

# Run tests sequentially to avoid hammering
bugs = []
for t in TESTS:
    tid, label, text = t
    r = run_test(t)
    test_id, lbl, status, response, elapsed = r
    preview = response[:100].replace('\n', ' ')
    flag = ""

    # Auto-detect potential bugs
    if status != "OK":
        flag = " ⚠ NON-200"
        bugs.append((test_id, lbl, status, response[:300]))
    elif "error" in response.lower() and "not found" not in response.lower() and "invalid" not in response.lower():
        if "unexpected error" in response.lower() or "agent error" in response.lower():
            flag = " 🐛 AGENT ERROR"
            bugs.append((test_id, lbl, status, response[:300]))

    print(f"{test_id:<6} {lbl:<55} {status:<8} {elapsed:>5.1f}s  {preview}{flag}")

print(f"\n{'─' * 160}")
print(f"Total API calls used: {api_calls[0]}/130")
print(f"\n{'═' * 60}")
print(f"BUGS / ANOMALIES DETECTED: {len(bugs)}")
print(f"{'═' * 60}")
for bug_id, bug_label, bug_status, bug_resp in bugs:
    print(f"\n[{bug_id}] {bug_label}")
    print(f"Status: {bug_status}")
    print(f"Response: {bug_resp}")
    print("─" * 60)
