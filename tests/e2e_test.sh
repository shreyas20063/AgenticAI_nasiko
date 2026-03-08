#!/usr/bin/env bash
# End-to-end parallel test suite for HRFlow AI
# parallel_group() accepts triplets: label text pattern  (3 args per test)
# Sequential tests use run_test() for state-mutating calls.

BASE="http://localhost:5000"
PASS=0; FAIL=0; TOTAL=0
FAILURES=()

# ── build JSON body (text passed as CLI arg, not stdin) ──────────────────────
mkbody() {
  python3 -c "
import json, sys
t = sys.argv[1]
print(json.dumps({
  'jsonrpc': '2.0', 'id': 't', 'method': 'message/send',
  'params': {'message': {'role': 'user', 'parts': [{'kind': 'text', 'text': t}]}}
}))
" "$1"
}

# ── call orchestrator, return plain text response ────────────────────────────
call() {
  local body
  body=$(mkbody "$1")
  curl -s -X POST "$BASE/" \
    -H "Content-Type: application/json" \
    -d "$body" \
    --max-time 60 \
  | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d['result']['artifacts'][0]['parts'][0]['text'])
except Exception as e:
    print('PARSE_ERROR: ' + str(e))
"
}

# ── run one test inline (sequential) ────────────────────────────────────────
run_test() {
  local label="$1" text="$2" pattern="$3"
  TOTAL=$((TOTAL+1))
  local out
  out=$(call "$text" 2>&1)
  if echo "$out" | grep -qiE "$pattern"; then
    PASS=$((PASS+1))
    printf "  [PASS] %s\n         -> %s\n" "$label" "${out:0:110}"
  else
    FAIL=$((FAIL+1))
    FAILURES+=("[$label] pattern=/$pattern/  got=${out:0:200}")
    printf "  [FAIL] %s\n         -> %s\n" "$label" "${out:0:110}"
  fi
}

# ── run tests in parallel; args are triplets: label text pattern ─────────────
parallel_group() {
  local group_name="$1"; shift
  echo ""
  echo "══════════════════════════════════════════════════════════════"
  echo "  GROUP: $group_name"
  echo "══════════════════════════════════════════════════════════════"

  local tmpdir
  tmpdir=$(mktemp -d)
  local idx=0
  local pids=()

  while [[ $# -ge 3 ]]; do
    local label="$1" text="$2" pattern="$3"
    shift 3
    local i=$idx
    (
      out=$(call "$text" 2>&1)
      printf '%s' "$label" > "$tmpdir/$i.label"
      printf '%s' "${out}" | tr '\n' ' ' | cut -c1-200 > "$tmpdir/$i.out"
      if printf '%s' "$out" | grep -qiE "$pattern"; then
        printf 'PASS' > "$tmpdir/$i.status"
      else
        printf 'FAIL' > "$tmpdir/$i.status"
      fi
    ) &
    pids+=($!)
    idx=$((idx+1))
  done

  for pid in "${pids[@]}"; do wait "$pid"; done

  for ((i=0; i<idx; i++)); do
    local st lbl out
    st=$(cat "$tmpdir/$i.status" 2>/dev/null || echo "FAIL")
    lbl=$(cat "$tmpdir/$i.label" 2>/dev/null || echo "unknown")
    out=$(cat "$tmpdir/$i.out" 2>/dev/null || echo "no output")
    TOTAL=$((TOTAL+1))
    if [[ "$st" == "PASS" ]]; then
      PASS=$((PASS+1))
      printf "  [PASS] %s\n         -> %s\n" "$lbl" "${out:0:110}"
    else
      FAIL=$((FAIL+1))
      FAILURES+=("[$lbl] -> ${out:0:200}")
      printf "  [FAIL] %s\n         -> %s\n" "$lbl" "${out:0:110}"
    fi
  done
  rm -rf "$tmpdir"
}

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         HRFlow AI — End-to-End Parallel Test Suite          ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ── G1: Orchestrator routing ─────────────────────────────────────────────────
parallel_group "ORCHESTRATOR — routing & edge inputs" \
  "No role prefix" \
    "What is the leave policy?" \
    "Unknown role" \
  "Unknown role INTERN" \
    "Role: INTERN (INT-001). What is the leave policy?" \
    "Unknown role" \
  "Empty message" \
    "   " \
    "didn.t receive|how can I help" \
  "Role only no question" \
    "Role: EMPLOYEE (EMP-001)." \
    "assist|help|HR needs"

# ── G2: Policy Q&A ──────────────────────────────────────────────────────────
parallel_group "EMPLOYEE — policy Q&A (all 11 policies)" \
  "Annual leave" \
    "Role: EMPLOYEE (EMP-001). What is the annual leave policy?" \
    "20 days|annual leave" \
  "Sick leave" \
    "Role: EMPLOYEE (EMP-001). How many sick days do I get?" \
    "10 days|sick leave" \
  "Remote work" \
    "Role: EMPLOYEE (EMP-001). What is the remote work policy?" \
    "hybrid|remote work" \
  "Parental leave" \
    "Role: EMPLOYEE (EMP-001). What is the parental leave policy?" \
    "26 weeks|182 days|parental" \
  "Dress code" \
    "Role: EMPLOYEE (EMP-001). What is the dress code policy?" \
    "business casual|dress code" \
  "Harassment policy" \
    "Role: EMPLOYEE (EMP-001). What is the harassment policy?" \
    "harassment|zero.tolerance|discrimination" \
  "Expense reimbursement" \
    "Role: EMPLOYEE (EMP-001). What is the expense reimbursement policy?" \
    "reimburs|30 days|business expense" \
  "Performance review" \
    "Role: EMPLOYEE (EMP-001). How does the performance review work?" \
    "bi-annually|april|october|performance" \
  "Probation period" \
    "Role: EMPLOYEE (EMP-003). What is the probation period?" \
    "6.month|probation" \
  "Code of conduct" \
    "Role: EMPLOYEE (EMP-001). What is the code of conduct?" \
    "integrity|conduct|professionalism" \
  "Non-existent policy" \
    "Role: EMPLOYEE (EMP-001). What is the stock options vesting cliff policy?" \
    "stock options|I don.t have|contact HR"

# ── G3: Leave balance ────────────────────────────────────────────────────────
parallel_group "EMPLOYEE — leave balance" \
  "Own balance EMP-001" \
    "Role: EMPLOYEE (EMP-001). What is my leave balance?" \
    "annual|sick|days" \
  "Cross-check denied EMP-001->010" \
    "Role: EMPLOYEE (EMP-001). Check leave balance for EMP-010." \
    "only check your own" \
  "Invalid EMP-999 denied" \
    "Role: EMPLOYEE (EMP-001). Check leave balance for EMP-999." \
    "only check your own" \
  "HR checks EMP-007" \
    "Role: HR. Check leave balance for EMP-007." \
    "annual|sick|EMP-007|Anjali" \
  "MANAGER checks EMP-001" \
    "Role: MANAGER (EMP-010). Check the leave balance for EMP-001." \
    "annual|sick|days|Priya"

# ── G4: Leave requests (sequential — mutates state) ─────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  GROUP: EMPLOYEE — leave requests (sequential)"
echo "══════════════════════════════════════════════════════════════"
run_test "Annual leave valid EMP-002" \
  "Role: EMPLOYEE (EMP-002). I want annual leave from 2026-03-22 to 2026-03-23. Reason: Personal." \
  "submitted|pending|LR-"
run_test "Sick leave valid EMP-004" \
  "Role: EMPLOYEE (EMP-004). I need sick leave from 2026-03-16 to 2026-03-16. Reason: Fever." \
  "submitted|pending|LR-"
run_test "Invalid leave type sabbatical" \
  "Role: EMPLOYEE (EMP-001). I want sabbatical leave from 2026-03-20 to 2026-03-21. Reason: Travel." \
  "sabbatical|not available|not found|contact HR"
run_test "End date before start" \
  "Role: EMPLOYEE (EMP-005). I want annual leave from 2026-03-25 to 2026-03-20. Reason: Error." \
  "start date|end date|before|error|invalid"
run_test "Exceeds balance EMP-007 (4 days left, requesting 10)" \
  "Role: EMPLOYEE (EMP-007). I want annual leave from 2026-03-16 to 2026-03-27. Reason: Vacation." \
  "exceed|insufficient|only have|4 days|cannot"
run_test "Unpaid leave EMP-006" \
  "Role: EMPLOYEE (EMP-006). I want unpaid leave from 2026-04-01 to 2026-04-03. Reason: Trip." \
  "submitted|pending|unpaid|LR-"
run_test "Parental leave zero balance EMP-001" \
  "Role: EMPLOYEE (EMP-001). I need parental leave from 2026-04-01 to 2026-04-03. Reason: Baby." \
  "0 days|no.*parental|cannot|insufficient"

# ── G5: Leave approval (sequential — mutates state) ─────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  GROUP: LEAVE approval/rejection (sequential)"
echo "══════════════════════════════════════════════════════════════"
run_test "EMPLOYEE cannot approve" \
  "Role: EMPLOYEE (EMP-001). Approve leave request LR-001." \
  "only managers|only.*HR|cannot approve|denied"
run_test "MANAGER approves LR-004" \
  "Role: MANAGER (EMP-010). Approve leave request LR-004 with comment: Approved." \
  "approved|LR-004|success"
run_test "MANAGER rejects LR-005" \
  "Role: MANAGER (EMP-010). Reject leave request LR-005 with comment: Busy period." \
  "rejected|LR-005|success"
run_test "Approve non-existent LR-999" \
  "Role: HR. Approve leave request LR-999 with comment: Ok." \
  "not found|LR-999|verify"
run_test "Approve already-approved LR-002" \
  "Role: HR. Approve leave request LR-002 with comment: Again." \
  "already approved|no further|cannot"
run_test "HR approves LR-006" \
  "Role: HR. Approve leave request LR-006 with comment: Confirmed." \
  "approved|LR-006|success"

# ── G6: Payslips ────────────────────────────────────────────────────────────
parallel_group "EMPLOYEE — payslips" \
  "Own payslip EMP-001 Feb-2026" \
    "Role: EMPLOYEE (EMP-001). Show me my payslip for 2026-02." \
    "gross|net|deductions|100,000" \
  "Cross-view denied EMP-001->002" \
    "Role: EMPLOYEE (EMP-001). Show me the payslip for EMP-002 for 2026-02." \
    "only view your own" \
  "Unavailable month 2025-12" \
    "Role: EMPLOYEE (EMP-001). Show me my payslip for 2025-12." \
    "not available|2025-12" \
  "HR views EMP-010 Jan-2026" \
    "Role: HR. Show me the payslip for EMP-010 for 2026-01." \
    "208,333|Arjun|EMP-010" \
  "Payslip EMP-999 not found" \
    "Role: HR. Show me the payslip for EMP-999 for 2026-01." \
    "not found|EMP-999" \
  "EMP-007 own payslip Feb-2026" \
    "Role: EMPLOYEE (EMP-007). Show me my payslip for 2026-02." \
    "87,500|Anjali|gross" \
  "EMP-009 HR Director own payslip" \
    "Role: EMPLOYEE (EMP-009). Show me my payslip for 2026-01." \
    "125,000|Meera|gross" \
  "EMP-005 own payslip Jan-2026" \
    "Role: EMPLOYEE (EMP-005). Show me my payslip for 2026-01." \
    "gross|net|deductions" \
  "MANAGER views own payslip" \
    "Role: MANAGER (EMP-010). Show me my payslip for 2026-01." \
    "208,333|Arjun|gross"

# ── G7: Support tickets ──────────────────────────────────────────────────────
parallel_group "EMPLOYEE — support tickets" \
  "General ticket P3" \
    "Role: EMPLOYEE (EMP-001). My access card is not working. Raise a general ticket P3 priority." \
    "TK-|general|P3" \
  "Payroll ticket P2" \
    "Role: EMPLOYEE (EMP-002). My payslip shows wrong HRA. Raise a payroll ticket P2." \
    "TK-|payroll|P2" \
  "Benefits ticket P2" \
    "Role: EMPLOYEE (EMP-005). I have not received my health insurance card. Raise a benefits ticket P2." \
    "TK-|benefits|P2" \
  "Documents ticket P3" \
    "Role: EMPLOYEE (EMP-008). I need an employment verification letter. Raise a documents ticket P3." \
    "TK-|documents|P3" \
  "Harassment P1 auto-escalate" \
    "Role: EMPLOYEE (EMP-003). My manager is harassing me. Raise a harassment ticket." \
    "TK-|P1|harassment|escalat|HR Director" \
  "Safety P1 auto-escalate" \
    "Role: EMPLOYEE (EMP-004). Fire hazard in operations. Raise a workplace safety ticket." \
    "TK-|P1|safety|escalat" \
  "Invalid employee EMP-999" \
    "Role: HR. Raise a general ticket for EMP-999 with P4 priority about access issues." \
    "not found|EMP-999|verify"

# ── G8: Applicant access control ─────────────────────────────────────────────
parallel_group "RECRUITMENT — applicant access control" \
  "CAND-001 own status" \
    "Role: APPLICANT (CAND-001). What is the status of my application?" \
    "Python Developer|screening|applied|offer" \
  "CAND cross-check denied" \
    "Role: APPLICANT (CAND-001). What is the status of CAND-002?" \
    "only check your own" \
  "Applicant screen denied" \
    "Role: APPLICANT (CAND-001). Can you screen my resume for Python Developer?" \
    "cannot screen|applicants cannot" \
  "Applicant rank denied" \
    "Role: APPLICANT (CAND-001). Show me ranked candidates." \
    "cannot view|applicants cannot" \
  "Applicant schedule denied" \
    "Role: APPLICANT (CAND-001). Schedule an interview for me." \
    "handled by HR|cannot schedule" \
  "Applicant offer denied" \
    "Role: APPLICANT (CAND-001). Send me an offer letter." \
    "only HR|cannot send" \
  "Non-existent CAND-999" \
    "Role: APPLICANT (CAND-999). What is the status of my application?" \
    "not found|CAND-999|verify"

# ── G9: HR resume & ranking ──────────────────────────────────────────────────
parallel_group "RECRUITMENT — HR resume screening & ranking" \
  "Screen Python Dev resume" \
    "Role: HR. Screen this resume for Python Developer: John has 4 years Python Django FastAPI REST APIs PostgreSQL Docker Git experience." \
    "score|match|100|proceed" \
  "Screen non-existent role" \
    "Role: HR. Screen this resume for Blockchain Engineer: Alice has solidity experience." \
    "not found|not available|open positions" \
  "Rank Python Developer" \
    "Role: HR. Rank all candidates for Python Developer." \
    "CAND-|score|ranked" \
  "Rank DevOps Engineer" \
    "Role: HR. Rank all candidates for DevOps Engineer." \
    "CAND-|score|ranked" \
  "Rank non-existent Data Scientist" \
    "Role: HR. Rank all candidates for Data Scientist." \
    "no candidates|not found" \
  "MANAGER views Python Dev candidates" \
    "Role: MANAGER (EMP-010). Show me ranked candidates for Python Developer." \
    "CAND-|score|ranked"

# ── G10: Interview scheduling (sequential) ───────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  GROUP: RECRUITMENT — interview scheduling (sequential)"
echo "══════════════════════════════════════════════════════════════"
run_test "Schedule CAND-003 valid date" \
  "Role: HR. Schedule an interview for CAND-003 with Priya Sharma on 2026-03-20." \
  "scheduled|CAND-003|2026-03-20|interview"
run_test "Schedule already-scheduled CAND-002" \
  "Role: HR. Schedule an interview for CAND-002 with Priya Sharma on 2026-03-18." \
  "already|cannot schedule|interview_scheduled|current status"
run_test "Schedule rejected CAND-006" \
  "Role: HR. Schedule an interview for CAND-006 with Vikram Singh on 2026-03-17." \
  "cannot schedule|rejected|current status"
run_test "Schedule unavailable date 2026-06-15" \
  "Role: HR. Schedule an interview for CAND-007 with Arjun Desai on 2026-06-15." \
  "not available|no.*slot|available dates"
run_test "MANAGER schedules CAND-007" \
  "Role: MANAGER (EMP-010). Schedule an interview for CAND-007 with Neha Kulkarni on 2026-03-25." \
  "scheduled|CAND-007|2026-03-25|interview"

# ── G11: Offer/rejection decisions (sequential) ──────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  GROUP: RECRUITMENT — decisions (sequential)"
echo "══════════════════════════════════════════════════════════════"
run_test "HR sends offer CAND-004" \
  "Role: HR. Send an offer to CAND-004. Message: We are pleased to offer you the position." \
  "offer|sent|CAND-004|Suresh"
run_test "HR sends rejection CAND-008" \
  "Role: HR. Send a rejection to CAND-008. Message: We regret we moved forward with others." \
  "rejection|sent|CAND-008|Nikhil"
run_test "HR invalid decision counter-offer" \
  "Role: HR. Send a counter-offer to CAND-001. Message: Revised terms." \
  "only send|offer.*rejection|not supported|counter"
run_test "MANAGER cannot send offer" \
  "Role: MANAGER (EMP-010). Send an offer to CAND-001." \
  "only HR|cannot send|not.*permission"
run_test "HR checks hired CAND-005" \
  "Role: HR. What is the status of CAND-005?" \
  "hired|offer|CAND-005|Pooja"
run_test "HR checks rejected CAND-006" \
  "Role: HR. What is the status of CAND-006?" \
  "rejected|CAND-006|Arun"

# ── G12: Analytics CEO ───────────────────────────────────────────────────────
parallel_group "ANALYTICS — CEO" \
  "CEO total headcount" \
    "Role: CEO. What is our total company headcount?" \
    "247|headcount|total" \
  "CEO Engineering headcount" \
    "Role: CEO. What is the headcount in Engineering?" \
    "98|engineering|headcount" \
  "CEO invalid dept Logistics" \
    "Role: CEO. What is the headcount in Logistics?" \
    "not found|logistics|available" \
  "CEO attrition report" \
    "Role: CEO. What is our attrition rate?" \
    "8\.2%|attrition|voluntary" \
  "CEO Marketing attrition" \
    "Role: CEO. What is the attrition in Marketing?" \
    "12\.5%|marketing|attrition" \
  "CEO hiring pipeline" \
    "Role: CEO. How is our hiring pipeline looking?" \
    "open positions|pipeline|12|offer acceptance" \
  "CEO Sales dept stats" \
    "Role: CEO. Give me full stats on the Sales department." \
    "sales|headcount|attrition" \
  "CEO Logistics invalid stats" \
    "Role: CEO. Give me stats on the Logistics department." \
    "not found|logistics|available" \
  "CEO full company overview" \
    "Role: CEO. How is the company doing? Give me a complete overview." \
    "headcount|attrition|pipeline"

# ── G13: Analytics access control ───────────────────────────────────────────
parallel_group "ANALYTICS — role access control" \
  "EMPLOYEE analytics denied" \
    "Role: EMPLOYEE (EMP-001). What is the company headcount?" \
    "contact HR|don.t have|not have" \
  "APPLICANT analytics denied" \
    "Role: APPLICANT (CAND-001). What is the company attrition rate?" \
    "own application|cannot|applicant" \
  "MANAGER headcount allowed" \
    "Role: MANAGER (EMP-010). What is the total company headcount?" \
    "247|headcount" \
  "MANAGER own dept stats" \
    "Role: MANAGER (EMP-010). Give me stats on the Engineering department." \
    "engineering|98|headcount|attrition" \
  "HR full attrition report" \
    "Role: HR. Give me the full attrition report." \
    "8\.2%|attrition|voluntary" \
  "HR Engineering hiring pipeline" \
    "Role: HR. Show me the hiring pipeline for Engineering." \
    "engineering|python developer|devops|open positions"

# ── G14: Cross-role routing ──────────────────────────────────────────────────
parallel_group "CROSS-ROLE routing edge cases" \
  "CEO leave policy -> analytics default" \
    "Role: CEO. What is the leave policy?" \
    "contact HR|don.t have|analytics" \
  "HR hiring + analytics dual" \
    "Role: HR. How many candidates do we have and what is our attrition rate?" \
    "candidate|attrition|pipeline" \
  "EMPLOYEE headcount restricted" \
    "Role: EMPLOYEE (EMP-001). Give me a headcount report." \
    "contact HR|don.t have|not have" \
  "MANAGER team leave balance" \
    "Role: MANAGER (EMP-010). Check the leave balance for EMP-001." \
    "annual|sick|days|Priya"

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                        RESULTS                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
printf "  Total : %d\n  PASS  : %d\n  FAIL  : %d\n" "$TOTAL" "$PASS" "$FAIL"

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  echo ""
  echo "══ FAILURES ════════════════════════════════════════════════════"
  for f in "${FAILURES[@]}"; do
    echo "  $f"
    echo "  ──────────────────────────────────────────────────────────"
  done
fi
echo ""
