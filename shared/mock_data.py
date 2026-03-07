"""Mock data for HRFlow AI — single source of truth for all agents.

All data is in-memory Python dicts. No external DB or API needed.
Copied into each container's src/ via copy_shared.sh before docker build.
"""

# ── EMPLOYEES (12 records) ──────────────────────────────────────

EMPLOYEES = {
    "EMP-001": {
        "id": "EMP-001",
        "name": "Priya Sharma",
        "email": "priya.sharma@acmecorp.in",
        "department": "Engineering",
        "role": "Senior Developer",
        "salary": 1200000,
        "manager_id": "EMP-010",
        "join_date": "2023-03-15",
        "leave_balance": {"annual": 12, "sick": 7, "parental": 0},
        "status": "active",
    },
    "EMP-002": {
        "id": "EMP-002",
        "name": "Rahul Verma",
        "email": "rahul.verma@acmecorp.in",
        "department": "Marketing",
        "role": "Marketing Lead",
        "salary": 950000,
        "manager_id": "EMP-011",
        "join_date": "2022-07-01",
        "leave_balance": {"annual": 8, "sick": 5, "parental": 0},
        "status": "active",
    },
    "EMP-003": {
        "id": "EMP-003",
        "name": "Sneha Iyer",
        "email": "sneha.iyer@acmecorp.in",
        "department": "Engineering",
        "role": "Junior Developer",
        "salary": 700000,
        "manager_id": "EMP-001",
        "join_date": "2025-01-10",
        "leave_balance": {"annual": 18, "sick": 10, "parental": 0},
        "status": "active",
    },
    "EMP-004": {
        "id": "EMP-004",
        "name": "Amit Patel",
        "email": "amit.patel@acmecorp.in",
        "department": "Sales",
        "role": "Sales Executive",
        "salary": 850000,
        "manager_id": "EMP-012",
        "join_date": "2023-11-20",
        "leave_balance": {"annual": 10, "sick": 8, "parental": 0},
        "status": "active",
    },
    "EMP-005": {
        "id": "EMP-005",
        "name": "Deepika Nair",
        "email": "deepika.nair@acmecorp.in",
        "department": "HR",
        "role": "HR Specialist",
        "salary": 780000,
        "manager_id": "EMP-009",
        "join_date": "2024-02-15",
        "leave_balance": {"annual": 15, "sick": 9, "parental": 0},
        "status": "active",
    },
    "EMP-006": {
        "id": "EMP-006",
        "name": "Karthik Menon",
        "email": "karthik.menon@acmecorp.in",
        "department": "Finance",
        "role": "Financial Analyst",
        "salary": 900000,
        "manager_id": "EMP-011",
        "join_date": "2023-06-01",
        "leave_balance": {"annual": 6, "sick": 4, "parental": 0},
        "status": "active",
    },
    "EMP-007": {
        "id": "EMP-007",
        "name": "Anjali Reddy",
        "email": "anjali.reddy@acmecorp.in",
        "department": "Operations",
        "role": "Operations Manager",
        "salary": 1050000,
        "manager_id": "EMP-010",
        "join_date": "2022-01-15",
        "leave_balance": {"annual": 4, "sick": 3, "parental": 0},
        "status": "on_leave",
    },
    "EMP-008": {
        "id": "EMP-008",
        "name": "Vikram Singh",
        "email": "vikram.singh@acmecorp.in",
        "department": "Engineering",
        "role": "DevOps Engineer",
        "salary": 1100000,
        "manager_id": "EMP-010",
        "join_date": "2023-09-01",
        "leave_balance": {"annual": 14, "sick": 10, "parental": 0},
        "status": "active",
    },
    "EMP-009": {
        "id": "EMP-009",
        "name": "Meera Joshi",
        "email": "meera.joshi@acmecorp.in",
        "department": "HR",
        "role": "HR Director",
        "salary": 1500000,
        "manager_id": "EMP-010",
        "join_date": "2021-04-01",
        "leave_balance": {"annual": 10, "sick": 6, "parental": 0},
        "status": "active",
    },
    "EMP-010": {
        "id": "EMP-010",
        "name": "Arjun Desai",
        "email": "arjun.desai@acmecorp.in",
        "department": "Engineering",
        "role": "VP of Engineering",
        "salary": 2500000,
        "manager_id": None,
        "join_date": "2020-01-15",
        "leave_balance": {"annual": 20, "sick": 10, "parental": 0},
        "status": "active",
    },
    "EMP-011": {
        "id": "EMP-011",
        "name": "Neha Kulkarni",
        "email": "neha.kulkarni@acmecorp.in",
        "department": "Finance",
        "role": "Finance Director",
        "salary": 1800000,
        "manager_id": "EMP-010",
        "join_date": "2021-08-01",
        "leave_balance": {"annual": 11, "sick": 7, "parental": 0},
        "status": "active",
    },
    "EMP-012": {
        "id": "EMP-012",
        "name": "Rohan Gupta",
        "email": "rohan.gupta@acmecorp.in",
        "department": "Sales",
        "role": "Sales Director",
        "salary": 1600000,
        "manager_id": "EMP-010",
        "join_date": "2021-03-01",
        "leave_balance": {"annual": 9, "sick": 5, "parental": 0},
        "status": "active",
    },
}


# ── CANDIDATES (8 records) ─────────────────────────────────────

CANDIDATES = {
    "CAND-001": {
        "id": "CAND-001",
        "name": "Ananya Patel",
        "email": "ananya.patel@gmail.com",
        "applied_for": "Python Developer",
        "status": "screening",
        "resume_text": (
            "Ananya Patel — Python Developer with 4 years of experience. "
            "B.Tech in Computer Science from IIT Bombay (2021). "
            "Currently at TCS as a Senior Software Engineer building REST APIs with "
            "Django and FastAPI. Proficient in Python, PostgreSQL, Redis, AWS (EC2, S3, Lambda). "
            "Led migration of monolithic app to microservices architecture serving 50K daily users. "
            "Contributed to open-source Django packages with 200+ GitHub stars. "
            "Certifications: AWS Solutions Architect Associate. "
            "Looking for a role with more ownership and technical challenges."
        ),
        "applied_date": "2026-02-20",
        "score": None,
        "interview_date": None,
        "interviewer": None,
        "notes": None,
    },
    "CAND-002": {
        "id": "CAND-002",
        "name": "Ravi Kumar",
        "email": "ravi.kumar@outlook.com",
        "applied_for": "Python Developer",
        "status": "interview_scheduled",
        "resume_text": (
            "Ravi Kumar — Full-stack Developer, 3 years experience. "
            "M.Sc Computer Science from BITS Pilani (2022). "
            "Currently at Wipro working on enterprise Python applications. "
            "Skills: Python, Flask, React, MongoDB, Docker, CI/CD with Jenkins. "
            "Built an internal analytics dashboard used by 500+ employees. "
            "Strong in data structures and algorithms (LeetCode 1800+ rating). "
            "Seeking a product-focused engineering role."
        ),
        "applied_date": "2026-02-15",
        "score": 75,
        "interview_date": "2026-03-12",
        "interviewer": "Priya Sharma",
        "notes": "Strong fundamentals, schedule technical round.",
    },
    "CAND-003": {
        "id": "CAND-003",
        "name": "Fatima Sheikh",
        "email": "fatima.sheikh@yahoo.com",
        "applied_for": "Marketing Analyst",
        "status": "screening",
        "resume_text": (
            "Fatima Sheikh — Marketing Analyst with 2 years experience. "
            "MBA Marketing from XLRI Jamshedpur (2023). "
            "Currently at Flipkart in the growth marketing team. "
            "Skills: Google Analytics, Tableau, SQL, A/B testing, SEO/SEM. "
            "Managed campaigns with a combined budget of INR 2 Cr, achieving 35% ROI improvement. "
            "Published 3 case studies on digital marketing strategies for e-commerce. "
            "Looking for a data-driven marketing role."
        ),
        "applied_date": "2026-02-25",
        "score": None,
        "interview_date": None,
        "interviewer": None,
        "notes": None,
    },
    "CAND-004": {
        "id": "CAND-004",
        "name": "Suresh Nair",
        "email": "suresh.nair@gmail.com",
        "applied_for": "DevOps Engineer",
        "status": "interview_scheduled",
        "resume_text": (
            "Suresh Nair — DevOps Engineer, 5 years experience. "
            "B.E. in IT from Anna University (2020). "
            "Currently at Infosys managing cloud infrastructure for banking clients. "
            "Skills: AWS, Kubernetes, Terraform, Docker, Ansible, Python, Bash. "
            "Reduced deployment time by 60% by implementing GitOps with ArgoCD. "
            "Managed 200+ node Kubernetes clusters with 99.9% uptime. "
            "AWS Certified DevOps Professional. "
            "Seeking a role in a product company with modern DevOps practices."
        ),
        "applied_date": "2026-02-10",
        "score": 88,
        "interview_date": "2026-03-11",
        "interviewer": "Vikram Singh",
        "notes": "Excellent DevOps background. Fast-track this candidate.",
    },
    "CAND-005": {
        "id": "CAND-005",
        "name": "Pooja Mehta",
        "email": "pooja.mehta@gmail.com",
        "applied_for": "Financial Analyst",
        "status": "offer_extended",
        "resume_text": (
            "Pooja Mehta — Financial Analyst, 3 years experience. "
            "CA from ICAI (2022), B.Com from Mumbai University. "
            "Currently at Deloitte in the audit and advisory division. "
            "Skills: Financial modeling, Excel (advanced), SAP, Tally, Power BI. "
            "Led quarterly reporting for 5 clients with combined revenue of INR 500 Cr."
        ),
        "applied_date": "2026-01-15",
        "score": 92,
        "interview_date": "2026-02-05",
        "interviewer": "Neha Kulkarni",
        "notes": "Outstanding candidate. Offer sent, awaiting response.",
    },
    "CAND-006": {
        "id": "CAND-006",
        "name": "Arun Krishnan",
        "email": "arun.k@gmail.com",
        "applied_for": "Python Developer",
        "status": "rejected",
        "resume_text": (
            "Arun Krishnan — Junior developer, 1 year experience. "
            "BCA from Christ University (2024). Intern at a local startup. "
            "Skills: Python basics, HTML/CSS, MySQL. "
            "Completed a personal project: todo app with Flask."
        ),
        "applied_date": "2026-02-01",
        "score": 35,
        "interview_date": None,
        "interviewer": None,
        "notes": "Insufficient experience for senior role. Rejected at screening.",
    },
    "CAND-007": {
        "id": "CAND-007",
        "name": "Divya Rao",
        "email": "divya.rao@outlook.com",
        "applied_for": "Marketing Analyst",
        "status": "applied",
        "resume_text": (
            "Divya Rao — Digital Marketing Specialist, 4 years experience. "
            "MBA from IIM Lucknow (2021). Currently at Amazon India in brand marketing. "
            "Skills: Campaign management, Google Ads, Meta Ads, Mixpanel, SQL. "
            "Managed a INR 5 Cr annual ad budget with 28% conversion rate improvement."
        ),
        "applied_date": "2026-03-05",
        "score": None,
        "interview_date": None,
        "interviewer": None,
        "notes": None,
    },
    "CAND-008": {
        "id": "CAND-008",
        "name": "Nikhil Jain",
        "email": "nikhil.jain@gmail.com",
        "applied_for": "DevOps Engineer",
        "status": "applied",
        "resume_text": (
            "Nikhil Jain — Cloud Engineer, 2 years experience. "
            "B.Tech from NIT Trichy (2023). Currently at Razorpay. "
            "Skills: GCP, Docker, Kubernetes, Terraform, Go, Python. "
            "Built internal deployment tool reducing release cycle from 2 days to 2 hours."
        ),
        "applied_date": "2026-03-06",
        "score": None,
        "interview_date": None,
        "interviewer": None,
        "notes": None,
    },
}


# ── JOB OPENINGS (4 positions) ─────────────────────────────────

JOB_OPENINGS = {
    "JOB-001": {
        "id": "JOB-001",
        "title": "Python Developer",
        "department": "Engineering",
        "requirements": [
            "Python 3.x", "Django or FastAPI", "REST APIs",
            "PostgreSQL", "Docker", "Git",
        ],
        "experience_required": "3-5 years",
        "salary_range": "900000-1400000",
        "openings_count": 2,
        "posted_date": "2026-02-01",
    },
    "JOB-002": {
        "id": "JOB-002",
        "title": "Marketing Analyst",
        "department": "Marketing",
        "requirements": [
            "Google Analytics", "SQL", "A/B testing",
            "Tableau or Power BI", "SEO/SEM",
        ],
        "experience_required": "2-4 years",
        "salary_range": "700000-1000000",
        "openings_count": 1,
        "posted_date": "2026-02-10",
    },
    "JOB-003": {
        "id": "JOB-003",
        "title": "DevOps Engineer",
        "department": "Engineering",
        "requirements": [
            "AWS or GCP", "Kubernetes", "Docker",
            "Terraform", "CI/CD", "Python or Bash",
        ],
        "experience_required": "3-6 years",
        "salary_range": "1000000-1600000",
        "openings_count": 1,
        "posted_date": "2026-01-20",
    },
    "JOB-004": {
        "id": "JOB-004",
        "title": "Financial Analyst",
        "department": "Finance",
        "requirements": [
            "Financial modeling", "Excel (advanced)",
            "SAP or Tally", "Power BI", "CA or CFA preferred",
        ],
        "experience_required": "2-5 years",
        "salary_range": "800000-1200000",
        "openings_count": 1,
        "posted_date": "2026-01-10",
    },
}


# ── POLICIES (10 entries) ──────────────────────────────────────

POLICIES = {
    "annual_leave": {
        "title": "Annual Leave Policy",
        "section_number": "3.1",
        "text": (
            "All full-time employees receive 20 days of paid annual leave per calendar year. "
            "Leave must be requested at least 2 weeks in advance via the HR portal. "
            "Unused leave up to 5 days can be carried forward to the next year. "
            "Leave beyond 5 consecutive days requires director-level approval."
        ),
    },
    "sick_leave": {
        "title": "Sick Leave Policy",
        "section_number": "3.2",
        "text": (
            "Employees are entitled to 10 days of paid sick leave per year. "
            "A medical certificate from a registered practitioner is required for absences "
            "exceeding 3 consecutive working days. Unused sick leave cannot be carried forward "
            "or encashed. Notify your manager before 10:00 AM on the day of absence."
        ),
    },
    "remote_work": {
        "title": "Remote Work Policy",
        "section_number": "4.2",
        "text": (
            "The company follows a hybrid model: 3 days in office (Tue-Thu) and 2 days "
            "remote (Mon, Fri) with manager approval. Employees must be available on Slack "
            "during core hours (10:00 AM - 6:00 PM IST). Fully remote work requires VP approval "
            "and is limited to 4 weeks per year. Employees must work from their registered "
            "country of residence."
        ),
    },
    "parental_leave": {
        "title": "Parental Leave Policy",
        "section_number": "3.5",
        "text": (
            "Primary caregivers receive 26 weeks (182 days) of paid parental leave. "
            "Secondary caregivers receive 4 weeks (28 days) of paid leave. "
            "Leave must be notified to HR at least 30 days before the expected date. "
            "Employees can opt for a phased return-to-work plan over 4 weeks after leave ends."
        ),
    },
    "dress_code": {
        "title": "Dress Code Policy",
        "section_number": "5.1",
        "text": (
            "Business casual dress code is required Monday through Thursday. "
            "Fridays are casual dress days. Client-facing meetings require formal business attire. "
            "Safety gear (hard hats, safety shoes) is mandatory in warehouse and factory areas. "
            "Religious and cultural attire is always welcome and respected."
        ),
    },
    "harassment": {
        "title": "Anti-Harassment and Discrimination Policy",
        "section_number": "7.1",
        "text": (
            "ACME Corp has zero tolerance for harassment, discrimination, or retaliation "
            "of any kind based on gender, race, religion, age, disability, or sexual orientation. "
            "All complaints are treated as P1-Critical priority and investigated within 48 hours. "
            "ESCALATION: Report to HR Director Meera Joshi (meera.joshi@acmecorp.in) or "
            "the anonymous hotline at 1800-555-0199. External complaints can be filed with "
            "the Internal Complaints Committee (ICC) at icc@acmecorp.in."
        ),
    },
    "expense_reimbursement": {
        "title": "Expense Reimbursement Policy",
        "section_number": "6.1",
        "text": (
            "Business expenses must be submitted within 30 days of incurrence with valid receipts. "
            "Pre-approval is required for expenses exceeding INR 5,000. Travel expenses follow "
            "the company travel matrix: Economy class for domestic flights, Business class for "
            "international flights over 6 hours. Hotel allowance: up to INR 5,000/night domestic, "
            "USD 200/night international. Reimbursements are processed within 15 business days."
        ),
    },
    "performance_review": {
        "title": "Performance Review Policy",
        "section_number": "8.1",
        "text": (
            "Performance reviews are conducted bi-annually in April and October. "
            "Reviews include self-assessment, manager assessment, and peer feedback (360-degree). "
            "Ratings: Exceptional (5), Exceeds Expectations (4), Meets Expectations (3), "
            "Needs Improvement (2), Unsatisfactory (1). Employees rated 2 or below enter a "
            "Performance Improvement Plan (PIP) for 90 days."
        ),
    },
    "code_of_conduct": {
        "title": "Code of Conduct",
        "section_number": "1.1",
        "text": (
            "All employees must act with integrity, respect, and professionalism. "
            "Conflicts of interest must be disclosed to HR within 7 days of awareness. "
            "Confidential company information must not be shared externally. "
            "Use of company resources for personal gain is prohibited. "
            "Violation of the code of conduct may result in disciplinary action up to termination."
        ),
    },
    "probation": {
        "title": "Probation Policy",
        "section_number": "2.1",
        "text": (
            "All new hires undergo a 6-month probation period. During probation, the notice "
            "period is 15 days (vs 60 days for confirmed employees). Performance is reviewed "
            "at 3-month and 6-month marks. Probation may be extended by up to 3 months if "
            "performance is borderline. Benefits like health insurance start from Day 1; "
            "stock options vest only after probation confirmation."
        ),
    },
}


# ── LEAVE REQUESTS (5 records) ─────────────────────────────────

LEAVE_REQUESTS = {
    "LR-001": {
        "request_id": "LR-001",
        "employee_id": "EMP-001",
        "leave_type": "annual",
        "start_date": "2026-03-13",
        "end_date": "2026-03-13",
        "reason": "Family wedding ceremony",
        "status": "pending",
        "manager_comment": None,
        "created_at": "2026-03-07",
    },
    "LR-002": {
        "request_id": "LR-002",
        "employee_id": "EMP-003",
        "leave_type": "sick",
        "start_date": "2026-03-03",
        "end_date": "2026-03-04",
        "reason": "Fever and cold",
        "status": "approved",
        "manager_comment": "Get well soon. Take rest.",
        "created_at": "2026-03-03",
    },
    "LR-003": {
        "request_id": "LR-003",
        "employee_id": "EMP-004",
        "leave_type": "annual",
        "start_date": "2026-03-20",
        "end_date": "2026-03-25",
        "reason": "Family vacation to Goa",
        "status": "pending",
        "manager_comment": None,
        "created_at": "2026-03-06",
    },
    "LR-004": {
        "request_id": "LR-004",
        "employee_id": "EMP-002",
        "leave_type": "annual",
        "start_date": "2026-02-14",
        "end_date": "2026-02-14",
        "reason": "Personal day",
        "status": "approved",
        "manager_comment": "Approved.",
        "created_at": "2026-02-10",
    },
    "LR-005": {
        "request_id": "LR-005",
        "employee_id": "EMP-006",
        "leave_type": "annual",
        "start_date": "2026-03-10",
        "end_date": "2026-03-21",
        "reason": "Extended vacation",
        "status": "rejected",
        "manager_comment": "Cannot approve 10 days during quarter-end. Please reschedule.",
        "created_at": "2026-03-01",
    },
}


# ── TICKETS (4 records) ────────────────────────────────────────

TICKETS = {
    "TK-001": {
        "ticket_id": "TK-001",
        "employee_id": "EMP-002",
        "category": "payroll",
        "description": "February payslip shows incorrect HRA amount. Expected 40% of basic but received 30%.",
        "priority": "P2",
        "status": "open",
        "assigned_to": "EMP-005",
        "created_at": "2026-03-05",
    },
    "TK-002": {
        "ticket_id": "TK-002",
        "employee_id": "EMP-008",
        "category": "documents",
        "description": "Need updated employment verification letter for home loan application.",
        "priority": "P3",
        "status": "in_progress",
        "assigned_to": "EMP-005",
        "created_at": "2026-03-04",
    },
    "TK-003": {
        "ticket_id": "TK-003",
        "employee_id": "EMP-003",
        "category": "benefits",
        "description": "Health insurance card not received after 2 months of joining. Need for upcoming hospital visit.",
        "priority": "P2",
        "status": "open",
        "assigned_to": "EMP-009",
        "created_at": "2026-03-06",
    },
    "TK-004": {
        "ticket_id": "TK-004",
        "employee_id": "EMP-004",
        "category": "general",
        "description": "Request to change reporting manager from EMP-012 to EMP-010 after team restructuring.",
        "priority": "P4",
        "status": "resolved",
        "assigned_to": "EMP-009",
        "created_at": "2026-02-28",
    },
}


# ── CALENDAR SLOTS (5 business days) ──────────────────────────

CALENDAR_SLOTS = {
    "2026-03-09": ["09:00", "10:30", "14:00", "15:30"],
    "2026-03-10": ["09:00", "11:00", "14:00", "16:00"],
    "2026-03-11": ["10:00", "11:30", "14:00", "15:30"],
    "2026-03-12": ["09:00", "10:30", "13:00", "15:00", "16:30"],
    "2026-03-13": ["09:30", "11:00", "14:30", "16:00"],
}


# ── COMPANY METRICS (pre-computed for analytics agent) ─────────

COMPANY_METRICS = {
    "total_headcount": 247,
    "avg_salary": 1050000,
    "attrition_rate": "8.2%",
    "avg_tenure": "3.4 years",
    "leave_utilization_rate": "68%",
    "open_tickets_count": 14,
    "employee_satisfaction_score": 4.1,
    "departments": {
        "Engineering": {
            "headcount": 98,
            "active": 95,
            "on_leave": 3,
            "avg_salary": 1150000,
            "attrition_rate": "6.1%",
            "satisfaction_score": 4.3,
        },
        "Marketing": {
            "headcount": 34,
            "active": 32,
            "on_leave": 2,
            "avg_salary": 820000,
            "attrition_rate": "12.5%",
            "satisfaction_score": 3.8,
        },
        "Sales": {
            "headcount": 45,
            "active": 43,
            "on_leave": 2,
            "avg_salary": 780000,
            "attrition_rate": "10.3%",
            "satisfaction_score": 3.9,
        },
        "HR": {
            "headcount": 12,
            "active": 12,
            "on_leave": 0,
            "avg_salary": 880000,
            "attrition_rate": "4.2%",
            "satisfaction_score": 4.5,
        },
        "Finance": {
            "headcount": 28,
            "active": 27,
            "on_leave": 1,
            "avg_salary": 950000,
            "attrition_rate": "7.1%",
            "satisfaction_score": 4.0,
        },
        "Operations": {
            "headcount": 30,
            "active": 28,
            "on_leave": 2,
            "avg_salary": 720000,
            "attrition_rate": "9.8%",
            "satisfaction_score": 3.7,
        },
    },
    "hiring_pipeline": {
        "open_positions": 12,
        "applied": 67,
        "screening": 23,
        "interview": 8,
        "offer": 3,
        "avg_time_to_hire": 34,
        "offer_acceptance_rate": "78%",
    },
    "attrition_breakdown": {
        "voluntary": "82%",
        "involuntary": "18%",
        "top_reason": "Career growth (42%)",
        "most_affected": "Mid-level engineers (3-5 yr tenure)",
        "monthly_trend": [2, 1, 3, 2, 1, 2, 3, 1, 2, 1, 2, 1],
    },
}


# ── PAYSLIPS (nested: employee_id → month → data) ─────────────

PAYSLIPS = {
    "EMP-001": {
        "2026-01": {
            "gross_salary": 100000,
            "basic": 50000,
            "hra": 20000,
            "special_allowance": 30000,
            "deductions": {"pf": 6000, "tax": 8333, "insurance": 1500},
            "net_salary": 84167,
        },
        "2026-02": {
            "gross_salary": 100000,
            "basic": 50000,
            "hra": 20000,
            "special_allowance": 30000,
            "deductions": {"pf": 6000, "tax": 8333, "insurance": 1500},
            "net_salary": 84167,
        },
    },
    "EMP-002": {
        "2026-01": {
            "gross_salary": 79167,
            "basic": 39583,
            "hra": 15833,
            "special_allowance": 23751,
            "deductions": {"pf": 4750, "tax": 5500, "insurance": 1500},
            "net_salary": 67417,
        },
        "2026-02": {
            "gross_salary": 79167,
            "basic": 39583,
            "hra": 15833,
            "special_allowance": 23751,
            "deductions": {"pf": 4750, "tax": 5500, "insurance": 1500},
            "net_salary": 67417,
        },
    },
    "EMP-003": {
        "2026-01": {
            "gross_salary": 58333,
            "basic": 29167,
            "hra": 11667,
            "special_allowance": 17499,
            "deductions": {"pf": 3500, "tax": 2917, "insurance": 1500},
            "net_salary": 50416,
        },
        "2026-02": {
            "gross_salary": 58333,
            "basic": 29167,
            "hra": 11667,
            "special_allowance": 17499,
            "deductions": {"pf": 3500, "tax": 2917, "insurance": 1500},
            "net_salary": 50416,
        },
    },
    "EMP-006": {
        "2026-01": {
            "gross_salary": 75000,
            "basic": 37500,
            "hra": 15000,
            "special_allowance": 22500,
            "deductions": {"pf": 4500, "tax": 5000, "insurance": 1500},
            "net_salary": 64000,
        },
        "2026-02": {
            "gross_salary": 75000,
            "basic": 37500,
            "hra": 15000,
            "special_allowance": 22500,
            "deductions": {"pf": 4500, "tax": 5000, "insurance": 1500},
            "net_salary": 64000,
        },
    },
}
