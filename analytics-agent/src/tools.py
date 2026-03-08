"""Analytics & Insights tools — 4 read-only tools for company metrics.

All tools return str and never raise exceptions.
Mock data is imported from mock_data.py (copied into src/ at build time).
"""

from collections import Counter

from langchain_core.tools import tool

from mock_data import (
    CANDIDATES,
    COMPANY_METRICS,
    EMPLOYEES,
    JOB_OPENINGS,
    TICKETS,
)


@tool
def get_headcount(department: str = "all") -> str:
    """Get headcount breakdown for the company or a specific department.
    Use when asked about employee count, workforce size, department sizes,
    or active vs on-leave staff.

    Args:
        department: Department name (e.g., 'Engineering') or 'all' for company-wide breakdown.

    Returns:
        Formatted headcount data with department breakdown and key metrics.
    """
    try:
        departments = COMPANY_METRICS["departments"]

        if department.lower() == "all":
            lines = [
                "COMPANY HEADCOUNT OVERVIEW",
                f"{'=' * 50}",
                f"Total Headcount:          {COMPANY_METRICS['total_headcount']}",
                f"Average Salary:           \u20b9{COMPANY_METRICS['avg_salary']:,}",
                f"Average Tenure:           {COMPANY_METRICS['avg_tenure']}",
                f"Satisfaction Score:        {COMPANY_METRICS['employee_satisfaction_score']}/5.0",
                f"Leave Utilization:         {COMPANY_METRICS['leave_utilization_rate']}",
                "",
                "DEPARTMENT BREAKDOWN",
                f"{'-' * 50}",
                f"{'Department':<15} {'Total':>7} {'Active':>7} {'On Leave':>9} {'Avg Salary':>12}",
                f"{'-' * 50}",
            ]

            for dept_name, stats in departments.items():
                lines.append(
                    f"{dept_name:<15} {stats['headcount']:>7} {stats['active']:>7} "
                    f"{stats['on_leave']:>9} \u20b9{stats['avg_salary']:>11,}"
                )

            total_active = sum(d["active"] for d in departments.values())
            total_on_leave = sum(d["on_leave"] for d in departments.values())
            lines.append(f"{'-' * 50}")
            lines.append(
                f"{'TOTAL':<15} {COMPANY_METRICS['total_headcount']:>7} "
                f"{total_active:>7} {total_on_leave:>9}"
            )

            return "\n".join(lines)

        # Specific department lookup
        dept_key = None
        for key in departments:
            if key.lower() == department.lower():
                dept_key = key
                break

        if dept_key is None:
            available = ", ".join(departments.keys())
            return f"Department '{department}' not found. Available departments: {available}"

        stats = departments[dept_key]
        return (
            f"{dept_key} DEPARTMENT HEADCOUNT\n"
            f"{'=' * 40}\n"
            f"Total Headcount:    {stats['headcount']}\n"
            f"Active Employees:   {stats['active']}\n"
            f"On Leave:           {stats['on_leave']}\n"
            f"Average Salary:     \u20b9{stats['avg_salary']:,}\n"
            f"Attrition Rate:     {stats['attrition_rate']}\n"
            f"Satisfaction Score:  {stats['satisfaction_score']}/5.0"
        )

    except Exception as e:
        return f"Error retrieving headcount data: {str(e)}"


@tool
def get_attrition_report(department: str = "all") -> str:
    """Get attrition and retention analytics for the company or a department.
    Use when asked about employee turnover, attrition rates, resignation trends,
    retention concerns, or why employees are leaving.

    Args:
        department: Department name (e.g., 'Engineering') or 'all' for company-wide report.

    Returns:
        Formatted attrition report with trends, reasons, and breakdown.
    """
    try:
        departments = COMPANY_METRICS["departments"]
        breakdown = COMPANY_METRICS["attrition_breakdown"]

        if department.lower() == "all":
            months = [
                "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
            ]
            trend_str = "  ".join(
                f"{m}:{v}" for m, v in zip(months, breakdown["monthly_trend"])
            )

            lines = [
                "COMPANY ATTRITION REPORT",
                f"{'=' * 50}",
                f"Overall Attrition Rate:   {COMPANY_METRICS['attrition_rate']}",
                f"Voluntary Exits:          {breakdown['voluntary']}",
                f"Involuntary Exits:        {breakdown['involuntary']}",
                f"Top Reason:               {breakdown['top_reason']}",
                f"Most Affected Group:      {breakdown['most_affected']}",
                "",
                "MONTHLY DEPARTURES (Last 12 Months)",
                f"{'-' * 50}",
                trend_str,
                f"Total Departures:         {sum(breakdown['monthly_trend'])}",
                "",
                "DEPARTMENT ATTRITION RATES",
                f"{'-' * 50}",
                f"{'Department':<15} {'Attrition':>10} {'Satisfaction':>13}",
                f"{'-' * 50}",
            ]

            for dept_name, stats in departments.items():
                lines.append(
                    f"{dept_name:<15} {stats['attrition_rate']:>10} "
                    f"{stats['satisfaction_score']:>10}/5.0"
                )

            # Highlight high-risk departments
            high_risk = [
                name for name, stats in departments.items()
                if float(stats["attrition_rate"].replace("%", "")) > 10.0
            ]
            if high_risk:
                lines.append(f"\nHIGH-RISK DEPARTMENTS (>10%): {', '.join(high_risk)}")

            return "\n".join(lines)

        # Specific department
        dept_key = None
        for key in departments:
            if key.lower() == department.lower():
                dept_key = key
                break

        if dept_key is None:
            available = ", ".join(departments.keys())
            return f"Department '{department}' not found. Available departments: {available}"

        stats = departments[dept_key]
        company_avg = float(COMPANY_METRICS["attrition_rate"].replace("%", ""))
        dept_rate = float(stats["attrition_rate"].replace("%", ""))
        comparison = "above" if dept_rate > company_avg else "below"

        return (
            f"{dept_key} ATTRITION REPORT\n"
            f"{'=' * 40}\n"
            f"Department Attrition Rate:  {stats['attrition_rate']}\n"
            f"Company Average:            {COMPANY_METRICS['attrition_rate']}\n"
            f"Status:                     {abs(dept_rate - company_avg):.1f}% {comparison} company average\n"
            f"Satisfaction Score:          {stats['satisfaction_score']}/5.0\n"
            f"Headcount:                  {stats['headcount']} ({stats['active']} active, {stats['on_leave']} on leave)"
        )

    except Exception as e:
        return f"Error retrieving attrition data: {str(e)}"


@tool
def get_hiring_pipeline(department: str = "all") -> str:
    """Get hiring pipeline metrics showing candidates at each stage.
    Use when asked about recruitment progress, open positions, hiring funnel,
    candidate pipeline, time-to-hire, or offer acceptance rates.

    Args:
        department: Department name (e.g., 'Engineering') or 'all' for company-wide pipeline.

    Returns:
        Formatted hiring pipeline with stage counts and conversion metrics.
    """
    try:
        pipeline = COMPANY_METRICS["hiring_pipeline"]

        if department.lower() == "all":
            # Live candidate counts by status
            status_counts = Counter(c["status"] for c in CANDIDATES.values())

            lines = [
                "COMPANY HIRING PIPELINE",
                f"{'=' * 50}",
                f"Open Positions:           {pipeline['open_positions']}",
                f"Avg Time to Hire:         {pipeline['avg_time_to_hire']} days",
                f"Offer Acceptance Rate:    {pipeline['offer_acceptance_rate']}",
                "",
                "PIPELINE STAGES (Pre-computed)",
                f"{'-' * 50}",
                f"Applied:                  {pipeline['applied']}",
                f"Screening:                {pipeline['screening']}",
                f"Interview:                {pipeline['interview']}",
                f"Offer:                    {pipeline['offer']}",
                "",
                "LIVE CANDIDATE STATUS",
                f"{'-' * 50}",
            ]

            for status, count in sorted(status_counts.items()):
                lines.append(f"  {status:<20} {count:>3}")

            lines.append(f"  {'TOTAL':<20} {len(CANDIDATES):>3}")

            # Conversion rates
            if pipeline["applied"] > 0:
                screen_rate = pipeline["screening"] / pipeline["applied"] * 100
                interview_rate = pipeline["interview"] / pipeline["applied"] * 100
                offer_rate = pipeline["offer"] / pipeline["applied"] * 100
                lines.extend([
                    "",
                    "CONVERSION RATES",
                    f"{'-' * 50}",
                    f"Applied → Screening:      {screen_rate:.1f}%",
                    f"Applied → Interview:      {interview_rate:.1f}%",
                    f"Applied → Offer:          {offer_rate:.1f}%",
                ])

            return "\n".join(lines)

        # Department-specific pipeline
        departments = COMPANY_METRICS["departments"]
        dept_key = None
        for key in departments:
            if key.lower() == department.lower():
                dept_key = key
                break

        if dept_key is None:
            available = ", ".join(departments.keys())
            return f"Department '{department}' not found. Available departments: {available}"

        # Find job openings for this department
        dept_jobs = {
            jid: job for jid, job in JOB_OPENINGS.items()
            if job["department"].lower() == dept_key.lower()
        }

        if not dept_jobs:
            return f"No open positions found for {dept_key} department."

        # Get job titles to match candidates
        dept_titles = {job["title"].lower() for job in dept_jobs.values()}

        # Filter candidates by matching job titles
        dept_candidates = [
            c for c in CANDIDATES.values()
            if c["applied_for"].lower() in dept_titles
        ]
        status_counts = Counter(c["status"] for c in dept_candidates)

        total_openings = sum(job["openings_count"] for job in dept_jobs.values())

        lines = [
            f"{dept_key} HIRING PIPELINE",
            f"{'=' * 40}",
            f"Open Positions:  {total_openings}",
            "",
            "OPEN ROLES",
            f"{'-' * 40}",
        ]

        for jid, job in dept_jobs.items():
            lines.append(f"  {job['title']} ({job['openings_count']} opening{'s' if job['openings_count'] > 1 else ''})")

        lines.extend([
            "",
            "CANDIDATE STATUS",
            f"{'-' * 40}",
        ])

        for status, count in sorted(status_counts.items()):
            lines.append(f"  {status:<20} {count:>3}")

        lines.append(f"  {'TOTAL':<20} {len(dept_candidates):>3}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving hiring pipeline: {str(e)}"


@tool
def get_department_stats(department: str) -> str:
    """Get comprehensive statistics for a specific department including
    headcount, salary data, employee list, open positions, and tickets.
    Use when asked about a specific department's performance, health, or details.

    Args:
        department: Department name (e.g., 'Engineering'). Required — no default.

    Returns:
        Detailed department profile with metrics, employees, jobs, and tickets.
    """
    try:
        departments = COMPANY_METRICS["departments"]

        dept_key = None
        for key in departments:
            if key.lower() == department.lower():
                dept_key = key
                break

        if dept_key is None:
            available = ", ".join(departments.keys())
            return f"Department '{department}' not found. Available departments: {available}"

        stats = departments[dept_key]

        # Live employee list for this department
        dept_employees = [
            emp for emp in EMPLOYEES.values()
            if emp["department"].lower() == dept_key.lower()
        ]

        # Open job positions
        dept_jobs = [
            job for job in JOB_OPENINGS.values()
            if job["department"].lower() == dept_key.lower()
        ]

        # Open tickets for department employees
        dept_emp_ids = {emp["id"] for emp in dept_employees}
        dept_tickets = [
            t for t in TICKETS.values()
            if t["employee_id"] in dept_emp_ids and t["status"] == "open"
        ]

        lines = [
            f"{dept_key} DEPARTMENT — COMPREHENSIVE STATS",
            f"{'=' * 50}",
            "",
            "KEY METRICS",
            f"{'-' * 50}",
            f"Headcount:            {stats['headcount']}",
            f"Active Employees:     {stats['active']}",
            f"On Leave:             {stats['on_leave']}",
            f"Average Salary:       \u20b9{stats['avg_salary']:,}",
            f"Attrition Rate:       {stats['attrition_rate']}",
            f"Satisfaction Score:    {stats['satisfaction_score']}/5.0",
            "",
            f"EMPLOYEES ({len(dept_employees)} in mock data)",
            f"{'-' * 50}",
        ]

        for emp in dept_employees:
            status_tag = " [ON LEAVE]" if emp["status"] != "active" else ""
            lines.append(f"  {emp['id']} — {emp['name']} ({emp['role']}){status_tag}")

        if not dept_employees:
            lines.append("  No employees in mock data for this department.")

        lines.extend([
            "",
            f"OPEN POSITIONS ({len(dept_jobs)})",
            f"{'-' * 50}",
        ])

        for job in dept_jobs:
            lines.append(
                f"  {job['id']} — {job['title']} "
                f"({job['openings_count']} opening{'s' if job['openings_count'] > 1 else ''})"
            )

        if not dept_jobs:
            lines.append("  No open positions.")

        lines.extend([
            "",
            f"OPEN HR TICKETS ({len(dept_tickets)})",
            f"{'-' * 50}",
        ])

        for ticket in dept_tickets:
            lines.append(
                f"  {ticket['ticket_id']} — {ticket['category']} "
                f"(Priority: {ticket['priority']})"
            )

        if not dept_tickets:
            lines.append("  No open tickets.")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving department stats: {str(e)}"
