"""
Demo data seeder. Creates a sample tenant, users, jobs, candidates, and policies.
All data is synthetic and safe for demo purposes.
"""

import uuid
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from models.tenant import Tenant, TenantConfig
from models.user import User, Role
from models.job import Job, JobRequirement
from models.candidate import Candidate, CandidateSkill
from models.employee import Employee
from models.policy_document import PolicyDocument
from models.consent import ConsentRecord
from models.ticket import Ticket
from models.onboarding import OnboardingPlan, OnboardingTask
from models.interview import ScheduledInterview, InterviewFeedback
from api.deps import hash_password

DATA_DIR = Path(__file__).parent


async def seed_all(db: AsyncSession):
    """Seed all demo data."""
    tenant = await _seed_tenant(db)
    users = await _seed_users(db, tenant.id)
    job = await _seed_jobs(db, tenant.id, users["recruiter"].id)
    candidate_ids = await _seed_candidates(db, tenant.id, job.id)
    await _seed_interviews(db, tenant.id, job.id, candidate_ids, users["recruiter"].id)
    await _seed_employees(db, tenant.id)
    await _seed_tickets(db, tenant.id, users)
    await _seed_onboarding_plans(db, tenant.id)
    await _seed_policies(db, tenant.id)


async def _seed_tenant(db: AsyncSession) -> Tenant:
    """Create demo tenant."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name="Acme Corporation",
        domain="acme.demo",
    )
    db.add(tenant)

    config = TenantConfig(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        blind_screening_enabled=True,
        bias_monitoring_enabled=True,
        allowed_tools=["send_email", "search_policies", "create_calendar_event", "schedule_interview"],
    )
    db.add(config)

    await db.flush()
    return tenant


async def _seed_users(db: AsyncSession, tenant_id: str) -> dict:
    """Create demo users across different roles."""
    users = {}
    demo_password = hash_password("demo12345")

    user_specs = [
        ("super_admin", "superadmin@acme.demo", "Alex SuperAdmin", Role.SUPER_ADMIN, "IT"),
        ("hr_admin", "admin@acme.demo", "Sarah Admin", Role.HR_ADMIN, "Human Resources"),
        ("recruiter", "recruiter@acme.demo", "Tom Recruiter", Role.RECRUITER, "Human Resources"),
        ("manager", "manager@acme.demo", "Jane Manager", Role.MANAGER, "Engineering"),
        ("employee", "employee@acme.demo", "John Employee", Role.EMPLOYEE, "Engineering"),
        ("hrbp", "hrbp@acme.demo", "Lisa HRBP", Role.HRBP, "Human Resources"),
    ]

    for key, email, name, role, dept in user_specs:
        user = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            email=email,
            hashed_password=demo_password,
            full_name=name,
            role=role,
            department=dept,
        )
        db.add(user)
        users[key] = user

    await db.flush()
    return users


async def _seed_jobs(db: AsyncSession, tenant_id: str, created_by: str) -> Job:
    """Create demo job posting."""
    job_data = json.loads((DATA_DIR / "sample_jobs" / "software_engineer.json").read_text())

    job = Job(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title=job_data["title"],
        department=job_data["department"],
        description=job_data["description"],
        location=job_data["location"],
        employment_type=job_data["employment_type"],
        salary_min=job_data["salary_min"],
        salary_max=job_data["salary_max"],
        required_skills=job_data["required_skills"],
        preferred_skills=job_data["preferred_skills"],
        min_experience_years=job_data["min_experience_years"],
        education_requirement=job_data["education_requirement"],
        blind_screening=job_data["blind_screening"],
        created_by=created_by,
        status="open",
    )
    db.add(job)

    # Add structured requirements
    for i, skill in enumerate(job_data["required_skills"]):
        req = JobRequirement(
            id=str(uuid.uuid4()),
            job_id=job.id,
            category="skill",
            requirement=f"{skill['skill']} ({skill['min_years']}+ years)",
            is_mandatory=True,
            weight=1.0,
        )
        db.add(req)

    await db.flush()
    return job


async def _seed_candidates(db: AsyncSession, tenant_id: str, job_id: str) -> list[str]:
    """Create demo candidates from sample resumes with varied statuses and scores."""
    resume_dir = DATA_DIR / "sample_resumes"
    candidate_ids = []

    # Pre-define statuses and scores for candidates to create a realistic pipeline
    pipeline_assignments = [
        {"status": "screened", "score": 92, "explanation": "Excellent match: strong Python, React skills, 8 years experience"},
        {"status": "interview", "score": 87, "explanation": "Strong candidate: solid full-stack skills, 5 years experience"},
        {"status": "shortlisted", "score": 78, "explanation": "Good match: meets core requirements, promising background"},
        {"status": "screened", "score": 65, "explanation": "Moderate match: some skill gaps in cloud infrastructure"},
        {"status": "new", "score": None, "explanation": None},
    ]

    for idx, resume_file in enumerate(sorted(resume_dir.glob("*.json"))):
        data = json.loads(resume_file.read_text())
        assignment = pipeline_assignments[idx % len(pipeline_assignments)]

        candidate = Candidate(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            job_id=job_id,
            full_name=data["full_name"],
            email=data["email"],
            phone=data.get("phone"),
            resume_text=data.get("resume_text"),
            years_experience=data.get("years_experience"),
            education_level=data.get("education", [{}])[0].get("degree") if data.get("education") else None,
            current_company=data.get("current_company"),
            current_title=data.get("current_title"),
            location=data.get("location"),
            status=assignment["status"],
            screening_score=assignment["score"],
            screening_explanation=assignment["explanation"],
            consent_given=True,
            consent_timestamp=datetime.utcnow(),
        )
        db.add(candidate)
        await db.flush()
        candidate_ids.append(candidate.id)

        # Add skills
        for skill in data.get("skills", []):
            cs = CandidateSkill(
                id=str(uuid.uuid4()),
                candidate_id=candidate.id,
                skill_name=skill["name"],
                proficiency=skill.get("proficiency"),
                years=skill.get("years"),
            )
            db.add(cs)

        # Create consent record
        consent = ConsentRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            subject_type="candidate",
            subject_id=candidate.id,
            subject_email=candidate.email,
            purpose="recruitment_processing",
            lawful_basis="consent",
            is_granted=True,
            granted_at=datetime.utcnow(),
        )
        db.add(consent)

    await db.flush()
    return candidate_ids


async def _seed_interviews(db: AsyncSession, tenant_id: str, job_id: str, candidate_ids: list[str], recruiter_id: str):
    """Seed demo interviews for candidates in the pipeline."""
    from datetime import timezone
    now = datetime.now(timezone.utc)

    if len(candidate_ids) < 2:
        return

    interview_specs = [
        {
            "candidate_id": candidate_ids[0],
            "scheduled_at": now + timedelta(days=1, hours=2),
            "duration_minutes": 60,
            "interview_type": "video",
            "status": "scheduled",
            "interviewer_names": ["Sarah Admin", "Jane Manager"],
        },
        {
            "candidate_id": candidate_ids[1],
            "scheduled_at": now + timedelta(days=2, hours=3),
            "duration_minutes": 45,
            "interview_type": "phone",
            "status": "scheduled",
            "interviewer_names": ["Tom Recruiter"],
        },
        {
            "candidate_id": candidate_ids[1],
            "scheduled_at": now - timedelta(days=3),
            "duration_minutes": 60,
            "interview_type": "video",
            "status": "completed",
            "interviewer_names": ["Jane Manager", "Lisa HRBP"],
        },
    ]

    interview_ids = []
    for spec in interview_specs:
        interview = ScheduledInterview(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            candidate_id=spec["candidate_id"],
            job_id=job_id,
            scheduled_at=spec["scheduled_at"],
            duration_minutes=spec["duration_minutes"],
            interview_type=spec["interview_type"],
            meeting_link=f"https://meet.nasiko.ai/{uuid.uuid4().hex[:8]}",
            interviewer_names=spec["interviewer_names"],
            interviewer_ids=[],
            created_by=recruiter_id,
            status=spec["status"],
        )
        db.add(interview)
        interview_ids.append(interview.id)

    await db.flush()

    # Add feedback for the completed interview
    if len(interview_ids) >= 3:
        feedback = InterviewFeedback(
            id=str(uuid.uuid4()),
            interview_id=interview_ids[2],
            interviewer_id=recruiter_id,
            interviewer_name="Jane Manager",
            overall_rating=4.0,
            technical_score=4.5,
            communication_score=3.5,
            culture_fit_score=4.0,
            problem_solving_score=4.0,
            strengths="Strong technical skills, great problem-solving approach, solid system design knowledge",
            weaknesses="Could improve communication of complex technical concepts",
            recommendation="hire",
            notes="Recommended for next round with engineering lead",
        )
        db.add(feedback)
        await db.flush()


async def _seed_employees(db: AsyncSession, tenant_id: str):
    """Create demo employees."""
    employees = [
        ("John Employee", "employee@acme.demo", "EMP001", "Engineering", "Software Engineer", "2024-01-15"),
        ("Jane Manager", "manager@acme.demo", "EMP002", "Engineering", "Engineering Manager", "2023-06-01"),
        ("Lisa HRBP", "hrbp@acme.demo", "EMP003", "Human Resources", "HR Business Partner", "2023-03-15"),
    ]

    for name, email, emp_id, dept, title, start in employees:
        emp = Employee(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            full_name=name,
            email=email,
            employee_id_number=emp_id,
            department=dept,
            title=title,
            start_date=date.fromisoformat(start),
            status="active",
            onboarding_complete=True,
        )
        db.add(emp)

    await db.flush()


async def _seed_tickets(db: AsyncSession, tenant_id: str, users: dict):
    """Create demo helpdesk tickets."""
    now = datetime.utcnow()
    ticket_specs = [
        {
            "requester_id": users["employee"].id,
            "category": "leave",
            "subject": "PTO request for next Friday",
            "status": "open",
            "priority": "medium",
            "created_at": now - timedelta(hours=3),
        },
        {
            "requester_id": users["employee"].id,
            "category": "payroll",
            "subject": "Payslip discrepancy for February",
            "status": "open",
            "priority": "high",
            "created_at": now - timedelta(hours=8),
        },
        {
            "requester_id": users["manager"].id,
            "category": "benefits",
            "subject": "Question about dental plan coverage",
            "status": "in_progress",
            "priority": "low",
            "assigned_to": users["hrbp"].id,
            "created_at": now - timedelta(days=1),
        },
        {
            "requester_id": users["employee"].id,
            "category": "policy",
            "subject": "Remote work policy clarification",
            "status": "open",
            "priority": "medium",
            "created_at": now - timedelta(hours=5),
        },
        {
            "requester_id": users["manager"].id,
            "category": "other",
            "subject": "Request for new team member laptop",
            "status": "resolved",
            "priority": "medium",
            "is_auto_resolved": True,
            "resolution_summary": "IT confirmed laptop will ship by end of week.",
            "resolved_at": now - timedelta(hours=2),
            "created_at": now - timedelta(days=2),
        },
    ]

    for spec in ticket_specs:
        ticket = Ticket(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            **spec,
        )
        db.add(ticket)

    await db.flush()


async def _seed_onboarding_plans(db: AsyncSession, tenant_id: str):
    """Create demo onboarding plans."""
    from sqlalchemy import select
    from models.employee import Employee

    result = await db.execute(
        select(Employee).where(Employee.tenant_id == tenant_id)
    )
    employees = {e.email: e for e in result.scalars().all()}

    now = datetime.utcnow()

    # Plan 1: Active plan for John Employee
    john = employees.get("employee@acme.demo")
    if john:
        plan1_id = str(uuid.uuid4())
        plan1 = OnboardingPlan(
            id=plan1_id,
            tenant_id=tenant_id,
            employee_id=john.id,
            template_name="engineering_onboarding",
            status="active",
            progress_pct=67,
            started_at=now - timedelta(days=15),
            target_completion=now + timedelta(days=15),
        )
        db.add(plan1)

        tasks1 = [
            ("Complete HR paperwork", "documentation", 1, True, 1),
            ("Set up workstation and accounts", "setup", 1, True, 2),
            ("Complete security training", "training", 3, True, 3),
            ("Meet with team lead", "meeting", 5, True, 4),
            ("Complete product overview training", "training", 10, False, 5),
            ("First code review submission", "setup", 14, False, 6),
        ]
        for title, cat, due, done, order in tasks1:
            task = OnboardingTask(
                id=str(uuid.uuid4()),
                plan_id=plan1_id,
                title=title,
                category=cat,
                due_day=due,
                is_completed=done,
                completed_at=now - timedelta(days=10) if done else None,
                order=order,
            )
            db.add(task)

    # Plan 2: Completed plan for Jane Manager
    jane = employees.get("manager@acme.demo")
    if jane:
        plan2_id = str(uuid.uuid4())
        plan2 = OnboardingPlan(
            id=plan2_id,
            tenant_id=tenant_id,
            employee_id=jane.id,
            template_name="manager_onboarding",
            status="completed",
            progress_pct=100,
            started_at=now - timedelta(days=90),
            target_completion=now - timedelta(days=60),
            completed_at=now - timedelta(days=62),
        )
        db.add(plan2)

        tasks2 = [
            ("Complete leadership orientation", "training", 1, True, 1),
            ("Review team structure and goals", "meeting", 3, True, 2),
            ("Complete compliance training", "training", 7, True, 3),
            ("Set up 1:1 meetings with direct reports", "meeting", 14, True, 4),
        ]
        for title, cat, due, done, order in tasks2:
            task = OnboardingTask(
                id=str(uuid.uuid4()),
                plan_id=plan2_id,
                title=title,
                category=cat,
                due_day=due,
                is_completed=done,
                completed_at=now - timedelta(days=65) if done else None,
                order=order,
            )
            db.add(task)

    await db.flush()


async def _seed_policies(db: AsyncSession, tenant_id: str):
    """Seed HR policy documents for RAG."""
    policies_dir = DATA_DIR / "policies"

    for policy_file in policies_dir.glob("*.md"):
        content = policy_file.read_text(encoding="utf-8")
        title = content.split("\n")[0].replace("#", "").strip()

        category_map = {
            "leave_policy": "leave",
            "benefits_policy": "benefits",
            "code_of_conduct": "conduct",
        }
        category = category_map.get(policy_file.stem, "general")

        doc = PolicyDocument(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            title=title,
            category=category,
            content=content,
            version=1,
            is_active=True,
        )
        db.add(doc)

    await db.flush()

    # Index policies into vector store
    try:
        from tools.vector_store import index_document
        from sqlalchemy import select
        from models.policy_document import PolicyDocument as PD

        result = await db.execute(select(PD).where(PD.tenant_id == tenant_id))
        policies = result.scalars().all()

        for policy in policies:
            chunks = await index_document(
                tenant_id=tenant_id,
                doc_id=policy.id,
                content=policy.content,
                metadata={
                    "title": policy.title,
                    "category": policy.category,
                },
            )
            policy.chunk_count = chunks
            policy.last_indexed_at = datetime.utcnow()

    except Exception as e:
        # Vector store indexing is optional for basic startup
        print(f"Warning: Could not index policies into vector store: {e}")
