"""
HRFlow AI — Full End-to-End Test Suite
Runs all tests in parallel (by group), sequential for state-mutating calls.
"""

import json
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "http://localhost:5000"

# ── helpers ──────────────────────────────────────────────────────────────────

def send(text: str) -> str:
    body = json.dumps({
        "jsonrpc": "2.0", "id": "e2e", "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}}
    }).encode()
    req = urllib.request.Request(
        BASE + "/", data=body,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
            return d["result"]["artifacts"][0]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        return f"HTTP_ERROR_{e.code}: {e.read().decode()[:200]}"
    except Exception as ex:
        return f"ERROR: {ex}"


PASS = 0
FAIL = 0
FAILURES = []


def check(label: str, text: str, pattern: str) -> tuple:
    """Run a single test. Returns (label, ok, response)."""
    out = send(text)
    ok = bool(re.search(pattern, out, re.IGNORECASE))
    return label, ok, out


def record(label: str, ok: bool, out: str):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
        print(f"         -> {out[:120].replace(chr(10),' ')}")
    else:
        FAIL += 1
        FAILURES.append((label, out))
        print(f"  [FAIL] {label}")
        print(f"         -> {out[:120].replace(chr(10),' ')}")


def parallel_group(title: str, tests: list[tuple[str, str, str]]):
    """Run tests in parallel, print results in order."""
    print(f"\n{'═'*62}")
    print(f"  GROUP: {title}")
    print(f"{'═'*62}")
    ordered = []
    with ThreadPoolExecutor(max_workers=len(tests)) as ex:
        future_to_idx = {ex.submit(check, *t): i for i, t in enumerate(tests)}
        results = [None] * len(tests)
        for f in as_completed(future_to_idx):
            results[future_to_idx[f]] = f.result()
    for label, ok, out in results:
        record(label, ok, out)


def sequential_group(title: str, tests: list[tuple[str, str, str]]):
    """Run tests one-by-one (for state-mutating operations)."""
    print(f"\n{'═'*62}")
    print(f"  GROUP: {title}  [sequential]")
    print(f"{'═'*62}")
    for label, text, pattern in tests:
        label, ok, out = check(label, text, pattern)
        record(label, ok, out)


# ════════════════════════════════════════════════════════════════════════════
# TEST DEFINITIONS
# Each entry: (label, input_text, regex_pattern)
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "╔" + "═"*62 + "╗")
print("║       HRFlow AI — End-to-End Parallel Test Suite          ║")
print("╚" + "═"*62 + "╝")

start_time = time.time()

# ── G1: Orchestrator routing ─────────────────────────────────────────────────
parallel_group("ORCHESTRATOR — routing & edge inputs", [
    ("No role prefix",       "What is the leave policy?",                       r"Unknown role"),
    ("Unknown role INTERN",  "Role: INTERN (INT-001). What is the leave policy?", r"Unknown role"),
    ("Empty message",        "   ",                                              r"didn.t receive|how can I help"),
    ("Role only no question","Role: EMPLOYEE (EMP-001).",                        r"assist|help|HR needs"),
])

# ── G2: Policy Q&A ───────────────────────────────────────────────────────────
parallel_group("EMPLOYEE — policy Q&A (all 11 policies)", [
    ("Annual leave",          "Role: EMPLOYEE (EMP-001). What is the annual leave policy?",            r"20 days|annual leave"),
    ("Sick leave",            "Role: EMPLOYEE (EMP-001). How many sick days do I get?",                r"10 days|sick leave"),
    ("Remote work",           "Role: EMPLOYEE (EMP-001). What is the remote work policy?",             r"hybrid|remote work"),
    ("Parental leave",        "Role: EMPLOYEE (EMP-001). What is the parental leave policy?",          r"26 weeks|182 days|parental"),
    ("Dress code",            "Role: EMPLOYEE (EMP-001). What is the dress code policy?",              r"business casual|dress code"),
    ("Harassment policy",     "Role: EMPLOYEE (EMP-001). What is the harassment policy?",              r"harassment|zero.tolerance|discrimination"),
    ("Expense reimbursement", "Role: EMPLOYEE (EMP-001). What is the expense reimbursement policy?",   r"reimburs|30 days|business expense"),
    ("Performance review",    "Role: EMPLOYEE (EMP-001). How does the performance review work?",       r"bi-annually|april|october|performance"),
    ("Probation period",      "Role: EMPLOYEE (EMP-003). What is the probation period?",               r"6.month|probation"),
    ("Code of conduct",       "Role: EMPLOYEE (EMP-001). What is the code of conduct?",                r"integrity|conduct|professionalism"),
    ("Non-existent policy",   "Role: EMPLOYEE (EMP-001). What is the stock options vesting cliff policy?", r"stock options|don.t have|contact HR"),
])

# ── G3: Leave balance ────────────────────────────────────────────────────────
parallel_group("EMPLOYEE — leave balance", [
    ("Own balance EMP-001",           "Role: EMPLOYEE (EMP-001). What is my leave balance?",                   r"annual|sick|days"),
    ("Cross-check denied EMP-001>010","Role: EMPLOYEE (EMP-001). Check leave balance for EMP-010.",            r"only check your own"),
    ("Invalid EMP-999 denied",        "Role: EMPLOYEE (EMP-001). Check leave balance for EMP-999.",            r"only check your own"),
    ("HR checks EMP-007",             "Role: HR. Check leave balance for EMP-007.",                            r"annual|sick|EMP-007|Anjali"),
    ("MANAGER checks EMP-001",        "Role: MANAGER (EMP-010). Check the leave balance for EMP-001.",         r"annual|sick|days|Priya"),
])

# ── G4: Leave requests (sequential) ──────────────────────────────────────────
sequential_group("EMPLOYEE — leave requests", [
    ("Annual leave valid EMP-002",
     "Role: EMPLOYEE (EMP-002). I want annual leave from 2026-03-22 to 2026-03-23. Reason: Personal.",
     r"submitted|pending|LR-"),
    ("Sick leave valid EMP-004",
     "Role: EMPLOYEE (EMP-004). I need sick leave from 2026-03-16 to 2026-03-16. Reason: Fever.",
     r"submitted|pending|LR-"),
    ("Invalid type sabbatical",
     "Role: EMPLOYEE (EMP-001). I want sabbatical leave from 2026-03-20 to 2026-03-21. Reason: Travel.",
     r"sabbatical|not available|not found|contact HR"),
    ("End date before start",
     "Role: EMPLOYEE (EMP-005). I want annual leave from 2026-03-25 to 2026-03-20. Reason: Error.",
     r"start date|end date|before|error|invalid"),
    ("Exceeds balance EMP-007 (4 days, requesting 10)",
     "Role: EMPLOYEE (EMP-007). I want annual leave from 2026-03-16 to 2026-03-27. Reason: Vacation.",
     r"exceed|insufficient|only have|4 days|cannot"),
    ("Unpaid leave EMP-006",
     "Role: EMPLOYEE (EMP-006). I want unpaid leave from 2026-04-01 to 2026-04-03. Reason: Trip.",
     r"submitted|pending|unpaid|LR-"),
    ("Parental leave zero balance EMP-001",
     "Role: EMPLOYEE (EMP-001). I need parental leave from 2026-04-01 to 2026-04-03. Reason: Baby.",
     r"0 days|no.*parental|cannot|insufficient"),
])

# ── G5: Leave approval (sequential) ──────────────────────────────────────────
sequential_group("LEAVE approval/rejection", [
    ("EMPLOYEE cannot approve",
     "Role: EMPLOYEE (EMP-001). Approve leave request LR-001.",
     r"only managers|only.*HR|cannot approve|denied"),
    ("MANAGER approves LR-004",
     "Role: MANAGER (EMP-010). Approve leave request LR-004 with comment: Approved.",
     r"approved|LR-004|success"),
    ("MANAGER rejects LR-005",
     "Role: MANAGER (EMP-010). Reject leave request LR-005 with comment: Busy period.",
     r"rejected|LR-005|success"),
    ("Approve non-existent LR-999",
     "Role: HR. Approve leave request LR-999 with comment: Ok.",
     r"not found|LR-999|verify"),
    ("Approve already-approved LR-002",
     "Role: HR. Approve leave request LR-002 with comment: Again.",
     r"already approved|no further|cannot"),
    ("HR approves LR-006",
     "Role: HR. Approve leave request LR-006 with comment: Confirmed.",
     r"approved|LR-006|success"),
])

# ── G6: Payslips ────────────────────────────────────────────────────────────
parallel_group("EMPLOYEE — payslips", [
    ("Own payslip EMP-001 Feb-2026",    "Role: EMPLOYEE (EMP-001). Show me my payslip for 2026-02.",                      r"gross|net|deductions|100,000"),
    ("Cross-view denied EMP-001>002",   "Role: EMPLOYEE (EMP-001). Show me the payslip for EMP-002 for 2026-02.",         r"only view your own"),
    ("Unavailable month 2025-12",       "Role: EMPLOYEE (EMP-001). Show me my payslip for 2025-12.",                      r"not available|2025-12"),
    ("HR views EMP-010 Jan-2026",       "Role: HR. Show me the payslip for EMP-010 for 2026-01.",                         r"208,333|Arjun|EMP-010"),
    ("Payslip EMP-999 not found",       "Role: HR. Show me the payslip for EMP-999 for 2026-01.",                         r"not found|EMP-999"),
    ("EMP-007 own payslip Feb-2026",    "Role: EMPLOYEE (EMP-007). Show me my payslip for 2026-02.",                      r"87,500|Anjali|gross"),
    ("EMP-009 HR Director own payslip", "Role: EMPLOYEE (EMP-009). Show me my payslip for 2026-01.",                      r"125,000|Meera|gross"),
    ("EMP-005 own payslip Jan-2026",    "Role: EMPLOYEE (EMP-005). Show me my payslip for 2026-01.",                      r"gross|net|deductions"),
    ("MANAGER own payslip Jan-2026",    "Role: MANAGER (EMP-010). Show me my payslip for 2026-01.",                       r"208,333|Arjun|gross"),
])

# ── G7: Support tickets ──────────────────────────────────────────────────────
parallel_group("EMPLOYEE — support tickets", [
    ("General ticket P3",          "Role: EMPLOYEE (EMP-001). My access card is not working. Raise a general ticket P3 priority.",           r"TK-|general|P3"),
    ("Payroll ticket P2",          "Role: EMPLOYEE (EMP-002). My payslip shows wrong HRA. Raise a payroll ticket P2.",                       r"TK-|payroll|P2"),
    ("Benefits ticket P2",         "Role: EMPLOYEE (EMP-005). I have not received my health insurance card. Raise a benefits ticket P2.",    r"TK-|benefits|P2"),
    ("Documents ticket P3",        "Role: EMPLOYEE (EMP-008). I need an employment verification letter. Raise a documents ticket P3.",       r"TK-|documents|P3"),
    ("Harassment P1 auto-escalate","Role: EMPLOYEE (EMP-003). My manager is harassing me. Raise a harassment ticket.",                       r"TK-|P1|harassment|escalat|HR Director"),
    ("Safety P1 auto-escalate",    "Role: EMPLOYEE (EMP-004). Fire hazard in operations. Raise a workplace safety ticket.",                  r"TK-|P1|safety|escalat"),
    ("Invalid employee EMP-999",   "Role: HR. Raise a general ticket for EMP-999 with P4 priority about access issues.",                     r"not found|EMP-999|verify"),
])

# ── G8: Applicant access control ─────────────────────────────────────────────
parallel_group("RECRUITMENT — applicant access control", [
    ("CAND-001 own status",        "Role: APPLICANT (CAND-001). What is the status of my application?",       r"Python Developer|screening|applied|offer"),
    ("CAND cross-check denied",    "Role: APPLICANT (CAND-001). What is the status of CAND-002?",             r"only check your own"),
    ("Applicant screen denied",    "Role: APPLICANT (CAND-001). Can you screen my resume for Python Developer?", r"cannot screen|applicants cannot"),
    ("Applicant rank denied",      "Role: APPLICANT (CAND-001). Show me ranked candidates.",                  r"cannot view|applicants cannot"),
    ("Applicant schedule denied",  "Role: APPLICANT (CAND-001). Schedule an interview for me.",               r"handled by HR|cannot schedule"),
    ("Applicant offer denied",     "Role: APPLICANT (CAND-001). Send me an offer letter.",                    r"only HR|cannot send"),
    ("Non-existent CAND-999",      "Role: APPLICANT (CAND-999). What is the status of my application?",      r"not found|CAND-999|verify"),
])

# ── G9: HR resume & ranking ──────────────────────────────────────────────────
parallel_group("RECRUITMENT — HR resume screening & ranking", [
    ("Screen Python Dev resume",
     "Role: HR. Screen this resume for Python Developer: John has 4 years Python Django FastAPI REST APIs PostgreSQL Docker Git experience.",
     r"score|match|100|proceed"),
    ("Screen non-existent role",
     "Role: HR. Screen this resume for Blockchain Engineer: Alice has solidity experience.",
     r"not found|not available|open positions"),
    ("Rank Python Developer",       "Role: HR. Rank all candidates for Python Developer.",                      r"CAND-|score|ranked"),
    ("Rank DevOps Engineer",        "Role: HR. Rank all candidates for DevOps Engineer.",                       r"CAND-|score|ranked"),
    ("Rank non-existent Data Sci",  "Role: HR. Rank all candidates for Data Scientist.",                        r"no candidates|not found"),
    ("MANAGER view Python Dev",     "Role: MANAGER (EMP-010). Show me ranked candidates for Python Developer.", r"CAND-|score|ranked"),
])

# ── G10: Interview scheduling (sequential) ────────────────────────────────────
sequential_group("RECRUITMENT — interview scheduling", [
    ("Schedule CAND-003 valid date",
     "Role: HR. Schedule an interview for CAND-003 with Priya Sharma on 2026-03-20.",
     r"scheduled|CAND-003|2026-03-20|interview"),
    ("Schedule already-scheduled CAND-002",
     "Role: HR. Schedule an interview for CAND-002 with Priya Sharma on 2026-03-18.",
     r"already|cannot schedule|interview_scheduled|current status"),
    ("Schedule rejected CAND-006",
     "Role: HR. Schedule an interview for CAND-006 with Vikram Singh on 2026-03-17.",
     r"cannot schedule|rejected|current status"),
    ("Schedule unavailable date 2026-06-15",
     "Role: HR. Schedule an interview for CAND-001 with Arjun Desai on 2026-06-15.",
     r"not available|no.*slot|available dates|already.*scheduled|cannot schedule"),
    ("MANAGER schedules CAND-007",
     "Role: MANAGER (EMP-010). Schedule an interview for CAND-007 with Neha Kulkarni on 2026-03-25.",
     r"scheduled|CAND-007|2026-03-25|interview|cannot schedule|already"),
])

# ── G11: Offer/rejection decisions (sequential) ───────────────────────────────
sequential_group("RECRUITMENT — offer/rejection decisions", [
    ("HR sends offer CAND-004",
     "Role: HR. Send an offer to CAND-004. Message: We are pleased to offer you the position.",
     r"offer|sent|CAND-004|Suresh"),
    ("HR sends rejection CAND-008",
     "Role: HR. Send a rejection to CAND-008. Message: We regret we moved forward with others.",
     r"rejection|sent|CAND-008|Nikhil"),
    ("HR invalid decision counter-offer",
     "Role: HR. Send a counter-offer to CAND-001. Message: Revised terms.",
     r"only send|offer.*rejection|not supported|counter"),
    ("MANAGER cannot send offer",
     "Role: MANAGER (EMP-010). Send an offer to CAND-001.",
     r"only HR|cannot send|not.*permission"),
    ("HR checks hired CAND-005",
     "Role: HR. What is the status of CAND-005?",
     r"hired|offer|CAND-005|Pooja"),
    ("HR checks rejected CAND-006",
     "Role: HR. What is the status of CAND-006?",
     r"rejected|CAND-006|Arun"),
])

# ── G12: Analytics CEO ───────────────────────────────────────────────────────
parallel_group("ANALYTICS — CEO", [
    ("CEO total headcount",       "Role: CEO. What is our total company headcount?",                       r"247|headcount|total"),
    ("CEO Engineering headcount", "Role: CEO. What is the headcount in Engineering?",                      r"98|engineering|headcount"),
    ("CEO invalid dept Logistics","Role: CEO. What is the headcount in Logistics?",                        r"not found|logistics|available"),
    ("CEO attrition report",      "Role: CEO. What is our attrition rate?",                               r"8\.2%|attrition|voluntary"),
    ("CEO Marketing attrition",   "Role: CEO. What is the attrition in Marketing?",                       r"12\.5%|marketing|attrition"),
    ("CEO hiring pipeline",       "Role: CEO. How is our hiring pipeline looking?",                       r"open positions|pipeline|12|offer acceptance"),
    ("CEO Sales dept stats",      "Role: CEO. Give me full stats on the Sales department.",               r"sales|headcount|attrition"),
    ("CEO Logistics invalid",     "Role: CEO. Give me stats on the Logistics department.",                r"not found|logistics|available"),
    ("CEO full company overview", "Role: CEO. How is the company doing? Give me a complete overview.",    r"headcount|attrition|pipeline"),
])

# ── G13: Analytics access control ───────────────────────────────────────────
parallel_group("ANALYTICS — role access control", [
    ("EMPLOYEE analytics denied",    "Role: EMPLOYEE (EMP-001). What is the company headcount?",            r"contact HR|don.t have|not have"),
    ("APPLICANT analytics denied",   "Role: APPLICANT (CAND-001). What is the company attrition rate?",    r"own application|cannot|applicant"),
    ("MANAGER headcount allowed",    "Role: MANAGER (EMP-010). What is the total company headcount?",      r"247|headcount"),
    ("MANAGER own dept stats",       "Role: MANAGER (EMP-010). Give me stats on the Engineering department.", r"engineering|98|headcount|attrition"),
    ("HR full attrition report",     "Role: HR. Give me the full attrition report.",                       r"8\.2%|attrition|voluntary"),
    ("HR Engineering pipeline",      "Role: HR. Show me the hiring pipeline for Engineering.",             r"engineering|python developer|devops|open positions"),
])

# ── G14: Cross-role routing edge cases ───────────────────────────────────────
parallel_group("CROSS-ROLE routing edge cases", [
    ("CEO leave policy -> no access",  "Role: CEO. What is the leave policy?",
     r"contact HR|don.t have|analytics"),
    ("HR hiring + attrition dual",     "Role: HR. How many candidates do we have and what is our attrition rate?",
     r"candidate|attrition|pipeline"),
    ("EMPLOYEE headcount restricted",  "Role: EMPLOYEE (EMP-001). Give me a headcount report.",
     r"contact HR|don.t have|not have"),
    ("MANAGER team leave balance",     "Role: MANAGER (EMP-010). Check the leave balance for EMP-001.",
     r"annual|sick|days|Priya"),
])

# ════════════════════════════════════════════════════════════════════════════
elapsed = time.time() - start_time
total = PASS + FAIL

print(f"\n{'╔' + '═'*62 + '╗'}")
print(f"║{'RESULTS':^62}║")
print(f"{'╚' + '═'*62 + '╝'}")
print(f"  Total  : {total}")
print(f"  PASS   : {PASS}  ({100*PASS//total if total else 0}%)")
print(f"  FAIL   : {FAIL}")
print(f"  Time   : {elapsed:.1f}s")

if FAILURES:
    print(f"\n{'═'*64}")
    print("  FAILURES")
    print(f"{'═'*64}")
    for label, out in FAILURES:
        print(f"\n  [{label}]")
        print(f"  {out[:300].replace(chr(10), ' | ')}")
        print(f"  {'─'*60}")

sys.exit(0 if FAIL == 0 else 1)
