"""Employee Services tools — 6 tools for policy, leave, tickets, payslips.

All tools return str and never raise exceptions.
Mock data is imported from mock_data.py (copied into src/ at build time).
"""

import re
from datetime import date
from typing import Tuple

from langchain_core.tools import tool

from mock_data import EMPLOYEES, LEAVE_REQUESTS, PAYSLIPS, POLICIES, TICKETS


# ── Role extraction helper ──────────────────────────────────────

_ROLE_RE = re.compile(
    r"Role:\s*(\w+)\s*(?:\(([^)]+)\))?", re.IGNORECASE
)


def _parse_role(text: str) -> Tuple[str, str]:
    """Extract (role, user_id) from message text. Returns ('unknown','unknown') if not found."""
    m = _ROLE_RE.search(text)
    if m:
        return m.group(1).upper(), (m.group(2) or "unknown").strip()
    return "UNKNOWN", "unknown"


@tool
def search_hr_policy(query: str) -> str:
    """Search the company HR policy handbook for answers to policy questions.
    Use when anyone asks about company rules, leave policies, remote work,
    benefits, dress code, harassment reporting, expenses, or any HR policy.

    Args:
        query: Natural language question about HR policies (e.g., 'remote work policy')

    Returns:
        Matching policy title, section number, and full text. Or a 'not found' message.
    """
    try:
        query_lower = query.lower()
        matches = []

        for key, policy in POLICIES.items():
            key_words = key.replace("_", " ")
            if (
                query_lower in key_words
                or key_words in query_lower
                or any(word in query_lower for word in key_words.split())
                or any(word in policy["text"].lower() for word in query_lower.split() if len(word) > 3)
            ):
                matches.append(policy)

        if not matches:
            return (
                "No matching policy found for your query. "
                "Please contact HR directly at hr@acmecorp.in for assistance."
            )

        results = []
        for p in matches:
            results.append(
                f"**{p['title']}** (Section {p['section_number']})\n{p['text']}"
            )

        response = "\n\n---\n\n".join(results)

        if any(term in query_lower for term in ["harassment", "discrimination", "safety", "abuse", "bully"]):
            response += (
                "\n\n⚠️ IMPORTANT: For urgent harassment, discrimination, or safety concerns, "
                "contact HR Director Meera Joshi at meera.joshi@acmecorp.in or call the "
                "confidential hotline: 1800-555-0199. You can also email icc@acmecorp.in."
            )

        return response

    except Exception as e:
        return f"Error searching policies: {str(e)}"


@tool
def request_leave(
    employee_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str,
) -> str:
    """Submit a leave request for an employee. Creates a pending request
    that requires manager approval. Always check leave balance first.

    Args:
        employee_id: Employee ID (e.g., 'EMP-001')
        leave_type: Type of leave — one of: annual, sick, parental, unpaid
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        reason: Reason for the leave request

    Returns:
        Confirmation with request ID and remaining balance, or error message.
    """
    try:
        if employee_id not in EMPLOYEES:
            return f"Employee {employee_id} not found. Please check the ID."

        valid_types = ["annual", "sick", "parental", "unpaid"]
        if leave_type not in valid_types:
            return f"Invalid leave type '{leave_type}'. Must be one of: {', '.join(valid_types)}"

        employee = EMPLOYEES[employee_id]

        # Calculate number of days
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            num_days = (end - start).days + 1
            if num_days <= 0:
                return "End date must be on or after start date."
        except ValueError:
            return "Invalid date format. Use YYYY-MM-DD."

        # Check balance (unpaid doesn't need balance)
        if leave_type != "unpaid":
            balance = employee["leave_balance"].get(leave_type, 0)
            if balance < num_days:
                return (
                    f"Insufficient {leave_type} leave balance. "
                    f"Requested: {num_days} days, Available: {balance} days."
                )

        # Create leave request
        new_id = f"LR-{len(LEAVE_REQUESTS) + 1:03d}"
        LEAVE_REQUESTS[new_id] = {
            "request_id": new_id,
            "employee_id": employee_id,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "status": "pending",
            "manager_comment": None,
            "created_at": date.today().isoformat(),
        }

        # Deduct balance
        if leave_type != "unpaid":
            employee["leave_balance"][leave_type] -= num_days

        manager_id = employee.get("manager_id")
        manager_name = EMPLOYEES[manager_id]["name"] if manager_id and manager_id in EMPLOYEES else "HR"

        remaining = employee["leave_balance"].get(leave_type, "N/A")
        return (
            f"Leave request {new_id} submitted successfully.\n"
            f"Type: {leave_type} | Dates: {start_date} to {end_date} ({num_days} day{'s' if num_days > 1 else ''})\n"
            f"Reason: {reason}\n"
            f"Status: Pending approval from {manager_name}.\n"
            f"Remaining {leave_type} balance: {remaining} days."
        )

    except Exception as e:
        return f"Error submitting leave request: {str(e)}"


@tool
def check_leave_balance(employee_id: str) -> str:
    """Check remaining leave balance for an employee. Shows annual, sick,
    and parental leave days remaining for the current year.

    Args:
        employee_id: Employee ID (e.g., 'EMP-001')

    Returns:
        Formatted leave balance breakdown, or error if employee not found.
    """
    try:
        if employee_id not in EMPLOYEES:
            return f"Employee {employee_id} not found. Please check the ID."

        emp = EMPLOYEES[employee_id]
        bal = emp["leave_balance"]

        return (
            f"Leave Balance for {emp['name']} ({employee_id}):\n"
            f"  Annual Leave:   {bal['annual']} days remaining\n"
            f"  Sick Leave:     {bal['sick']} days remaining\n"
            f"  Parental Leave: {bal['parental']} days remaining\n"
            f"  Total Available: {bal['annual'] + bal['sick'] + bal['parental']} days"
        )

    except Exception as e:
        return f"Error checking leave balance: {str(e)}"


@tool
def raise_ticket(
    employee_id: str,
    category: str,
    description: str,
    priority: str,
) -> str:
    """Raise an HR support ticket for an employee query or complaint.
    Harassment and workplace safety tickets are auto-escalated to P1-Critical.

    Args:
        employee_id: Employee ID (e.g., 'EMP-001')
        category: Ticket category — one of: payroll, benefits, harassment, workplace_safety, documents, general
        description: Detailed description of the issue
        priority: Priority level — P1-Critical, P2-High, P3-Medium, or P4-Low

    Returns:
        Ticket ID, assigned team, expected SLA, and escalation info if applicable.
    """
    try:
        if employee_id not in EMPLOYEES:
            return f"Employee {employee_id} not found. Please check the ID."

        valid_categories = ["payroll", "benefits", "harassment", "workplace_safety", "documents", "general"]
        if category not in valid_categories:
            return f"Invalid category '{category}'. Must be one of: {', '.join(valid_categories)}"

        # Auto-escalate harassment and workplace safety
        if category in ("harassment", "workplace_safety"):
            priority = "P1"

        new_id = f"TK-{len(TICKETS) + 1:03d}"
        TICKETS[new_id] = {
            "ticket_id": new_id,
            "employee_id": employee_id,
            "category": category,
            "description": description,
            "priority": priority,
            "status": "open",
            "assigned_to": "EMP-009",  # HR Director Meera Joshi
            "created_at": date.today().isoformat(),
        }

        sla_map = {"P1": "4 hours", "P2": "24 hours", "P3": "3 business days", "P4": "5 business days"}
        sla = sla_map.get(priority, "5 business days")

        response = (
            f"Ticket {new_id} created successfully.\n"
            f"Category: {category} | Priority: {priority}\n"
            f"Assigned to: HR Team (Meera Joshi)\n"
            f"Expected resolution: within {sla}."
        )

        if category in ("harassment", "workplace_safety"):
            response += (
                f"\n\n🚨 This ticket has been auto-escalated to P1-Critical.\n"
                f"HR Director Meera Joshi (meera.joshi@acmecorp.in) has been notified.\n"
                f"Confidential Hotline: 1800-555-0199\n"
                f"Internal Complaints Committee: icc@acmecorp.in\n"
                f"All reports are treated confidentially and investigated within 48 hours."
            )

        return response

    except Exception as e:
        return f"Error creating ticket: {str(e)}"


@tool
def get_payslip(employee_id: str, month: str) -> str:
    """Retrieve payslip data for an employee for a specific month.
    Returns gross salary, deductions breakdown, and net pay.

    Args:
        employee_id: Employee ID (e.g., 'EMP-001')
        month: Month in YYYY-MM format (e.g., '2026-02')

    Returns:
        Formatted payslip with salary breakdown, or 'not available' message.
    """
    try:
        if employee_id not in EMPLOYEES:
            return f"Employee {employee_id} not found. Please check the ID."

        if employee_id not in PAYSLIPS:
            return f"No payslip records available for {employee_id}."

        if month not in PAYSLIPS[employee_id]:
            available = ", ".join(sorted(PAYSLIPS[employee_id].keys()))
            return (
                f"Payslip not available for {month}. "
                f"Available months: {available}"
            )

        emp = EMPLOYEES[employee_id]
        slip = PAYSLIPS[employee_id][month]
        ded = slip["deductions"]
        total_deductions = ded["pf"] + ded["tax"] + ded["insurance"]

        return (
            f"Payslip for {emp['name']} ({employee_id}) — {month}\n"
            f"{'─' * 40}\n"
            f"Gross Salary:      ₹{slip['gross_salary']:,}\n"
            f"  Basic:           ₹{slip['basic']:,}\n"
            f"  HRA:             ₹{slip['hra']:,}\n"
            f"  Special Allow.:  ₹{slip['special_allowance']:,}\n"
            f"{'─' * 40}\n"
            f"Deductions:        ₹{total_deductions:,}\n"
            f"  Provident Fund:  ₹{ded['pf']:,}\n"
            f"  Income Tax:      ₹{ded['tax']:,}\n"
            f"  Insurance:       ₹{ded['insurance']:,}\n"
            f"{'─' * 40}\n"
            f"Net Salary:        ₹{slip['net_salary']:,}"
        )

    except Exception as e:
        return f"Error retrieving payslip: {str(e)}"


@tool
def approve_leave(request_id: str, decision: str, manager_comment: str) -> str:
    """Approve or reject a pending leave request. Only accessible to Manager
    and HR roles. Updates the leave request status and optionally restores
    leave balance if rejected.

    Args:
        request_id: Leave request ID (e.g., 'LR-001')
        decision: Either 'approved' or 'rejected'
        manager_comment: Comment explaining the decision

    Returns:
        Confirmation of the approval/rejection with updated status.
    """
    try:
        if request_id not in LEAVE_REQUESTS:
            return f"Leave request {request_id} not found."

        request = LEAVE_REQUESTS[request_id]

        if request["status"] != "pending":
            return f"Leave request {request_id} is already {request['status']}. Cannot modify."

        valid_decisions = ["approved", "rejected"]
        if decision not in valid_decisions:
            return f"Invalid decision '{decision}'. Must be 'approved' or 'rejected'."

        request["status"] = decision
        request["manager_comment"] = manager_comment

        emp_id = request["employee_id"]
        emp_name = EMPLOYEES.get(emp_id, {}).get("name", emp_id)

        # Restore balance if rejected
        if decision == "rejected" and request["leave_type"] != "unpaid":
            start = date.fromisoformat(request["start_date"])
            end = date.fromisoformat(request["end_date"])
            num_days = (end - start).days + 1
            if emp_id in EMPLOYEES:
                EMPLOYEES[emp_id]["leave_balance"][request["leave_type"]] += num_days

        return (
            f"Leave request {request_id} has been {decision}.\n"
            f"Employee: {emp_name} ({emp_id})\n"
            f"Type: {request['leave_type']} | "
            f"Dates: {request['start_date']} to {request['end_date']}\n"
            f"Manager Comment: {manager_comment}"
        )

    except Exception as e:
        return f"Error processing leave approval: {str(e)}"
