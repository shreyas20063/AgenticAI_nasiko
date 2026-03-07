"""Recruitment tools — 5 tools for hiring workflows.

Resume screening, candidate ranking, interview scheduling,
offer/rejection decisions, and application status checking.
"""

from datetime import date, datetime

from langchain_core.tools import tool

from mock_data import CALENDAR_SLOTS, CANDIDATES, JOB_OPENINGS


@tool
def screen_resume(resume_text: str, job_role: str) -> str:
    """Screen a candidate resume against job requirements. Extracts skill matches
    and scores the candidate 0-100 based on keyword overlap with job requirements.
    Use when HR asks to evaluate, review, or screen a resume.

    Args:
        resume_text: The candidate's resume as plain text
        job_role: The job title to screen against (e.g., 'Python Developer')

    Returns:
        Match score, matched skills, missing skills, and recommendation.
    """
    try:
        # Find matching job opening
        job = None
        for jid, j in JOB_OPENINGS.items():
            if j["title"].lower() == job_role.lower():
                job = j
                break

        if not job:
            available = ", ".join(j["title"] for j in JOB_OPENINGS.values())
            return (
                f"Job role '{job_role}' not found in open positions. "
                f"Available positions: {available}"
            )

        # Score based on keyword overlap
        resume_lower = resume_text.lower()
        requirements = job["requirements"]
        matched = []
        missing = []

        for req in requirements:
            # Check for each requirement keyword in resume
            req_words = req.lower().split()
            if any(word in resume_lower for word in req_words if len(word) > 2):
                matched.append(req)
            else:
                missing.append(req)

        # Calculate score: base on match percentage + experience bonus
        match_pct = (len(matched) / len(requirements)) * 100 if requirements else 0

        # Experience bonus: check for years mentioned
        exp_bonus = 0
        for word in resume_lower.split():
            if "year" in word:
                try:
                    idx = resume_lower.split().index(word)
                    if idx > 0:
                        prev = resume_lower.split()[idx - 1]
                        years = int(prev) if prev.isdigit() else 0
                        if years >= 3:
                            exp_bonus = 10
                except (ValueError, IndexError):
                    pass

        score = min(100, int(match_pct + exp_bonus))

        # Recommendation
        if score >= 75:
            recommendation = "PROCEED — Strong match. Recommend technical interview."
        elif score >= 50:
            recommendation = "REVIEW — Partial match. Consider phone screening first."
        else:
            recommendation = "PASS — Significant skill gaps for this role."

        matched_str = ", ".join(matched) if matched else "None"
        missing_str = ", ".join(missing) if missing else "None"

        return (
            f"Resume Screening Results for '{job['title']}'\n"
            f"{'=' * 45}\n"
            f"Match Score: {score}/100\n\n"
            f"Matched Skills ({len(matched)}/{len(requirements)}):\n"
            f"  {matched_str}\n\n"
            f"Missing Skills:\n"
            f"  {missing_str}\n\n"
            f"Experience Required: {job['experience_required']}\n"
            f"Recommendation: {recommendation}"
        )

    except Exception as e:
        return f"Error screening resume: {str(e)}"


@tool
def rank_candidates(job_role: str) -> str:
    """Get a ranked list of all candidates for a specific job role, sorted by
    match score (highest first). Use when HR wants to see top candidates or
    compare applicants for a position.

    Args:
        job_role: The job title to get candidates for (e.g., 'Python Developer')

    Returns:
        Formatted ranked list with name, score, status, and applied date.
    """
    try:
        # Filter candidates by job role
        matches = []
        for cid, cand in CANDIDATES.items():
            if cand["applied_for"].lower() == job_role.lower():
                matches.append((cid, cand))

        if not matches:
            available_roles = set(c["applied_for"] for c in CANDIDATES.values())
            return (
                f"No candidates found for '{job_role}'. "
                f"Roles with candidates: {', '.join(sorted(available_roles))}"
            )

        # Sort: scored candidates first (by score desc), then unscored (by date)
        def sort_key(item):
            cand = item[1]
            score = cand.get("score") or 0
            return (-score, cand.get("applied_date", ""))

        matches.sort(key=sort_key)

        lines = [f"Candidates for '{job_role}' ({len(matches)} total):", "=" * 50]
        for rank, (cid, cand) in enumerate(matches, 1):
            score_str = f"{cand['score']}/100" if cand.get("score") else "Not scored"
            lines.append(
                f"{rank}. {cand['name']} ({cid})\n"
                f"   Score: {score_str} | Status: {cand['status']} | Applied: {cand['applied_date']}"
            )
            if cand.get("notes"):
                lines.append(f"   Notes: {cand['notes']}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error ranking candidates: {str(e)}"


@tool
def schedule_interview(candidate_id: str, interviewer: str, preferred_date: str) -> str:
    """Schedule an interview between a candidate and an interviewer.
    Checks available calendar slots for the preferred date and books the first match.

    Args:
        candidate_id: Candidate ID (e.g., 'CAND-001')
        interviewer: Name of the interviewer
        preferred_date: Preferred date in YYYY-MM-DD format

    Returns:
        Confirmation with candidate, interviewer, date, time, and location.
    """
    try:
        if candidate_id not in CANDIDATES:
            return f"Candidate {candidate_id} not found. Please check the ID."

        candidate = CANDIDATES[candidate_id]

        # Check candidate is eligible for interview
        eligible_statuses = ["applied", "screening"]
        if candidate["status"] not in eligible_statuses:
            return (
                f"Cannot schedule interview for {candidate['name']}. "
                f"Current status: {candidate['status']}. "
                f"Interviews can only be scheduled for candidates in 'applied' or 'screening' status."
            )

        # Check calendar availability
        if preferred_date not in CALENDAR_SLOTS:
            available_dates = ", ".join(sorted(CALENDAR_SLOTS.keys()))
            return (
                f"No calendar slots available for {preferred_date}. "
                f"Available dates: {available_dates}"
            )

        slots = CALENDAR_SLOTS[preferred_date]
        if not slots:
            return f"All slots are booked for {preferred_date}. Please try another date."

        # Book first available slot
        booked_time = slots.pop(0)

        # Update candidate
        candidate["status"] = "interview_scheduled"
        candidate["interview_date"] = preferred_date
        candidate["interviewer"] = interviewer

        return (
            f"Interview Scheduled Successfully\n"
            f"{'=' * 35}\n"
            f"Candidate: {candidate['name']} ({candidate_id})\n"
            f"Position: {candidate['applied_for']}\n"
            f"Interviewer: {interviewer}\n"
            f"Date: {preferred_date}\n"
            f"Time: {booked_time}\n"
            f"Location: Conference Room B, 3rd Floor\n\n"
            f"Calendar invites will be sent to both parties."
        )

    except Exception as e:
        return f"Error scheduling interview: {str(e)}"


@tool
def send_decision(candidate_id: str, decision: str, message: str) -> str:
    """Send an offer or rejection notification to a candidate.
    Creates a mock email record with the decision.

    Args:
        candidate_id: Candidate ID (e.g., 'CAND-001')
        decision: Either 'offer' or 'rejection'
        message: Custom message to include in the email

    Returns:
        Confirmation that the email was sent with a preview of the subject line.
    """
    try:
        if candidate_id not in CANDIDATES:
            return f"Candidate {candidate_id} not found. Please check the ID."

        valid_decisions = ["offer", "rejection"]
        if decision not in valid_decisions:
            return f"Invalid decision '{decision}'. Must be 'offer' or 'rejection'."

        candidate = CANDIDATES[candidate_id]

        # Update status
        if decision == "offer":
            candidate["status"] = "offer_extended"
            subject = f"Job Offer — {candidate['applied_for']} at ACME Corp"
        else:
            candidate["status"] = "rejected"
            subject = f"Application Update — {candidate['applied_for']} at ACME Corp"

        # Mock email record
        email = {
            "to": candidate["email"],
            "subject": subject,
            "body": message,
            "sent_at": datetime.now().isoformat(),
        }

        candidate["notes"] = (
            f"{candidate.get('notes', '') or ''} "
            f"Decision: {decision} sent on {date.today().isoformat()}"
        ).strip()

        return (
            f"Decision Email Sent\n"
            f"{'=' * 30}\n"
            f"To: {candidate['name']} ({candidate['email']})\n"
            f"Subject: {subject}\n"
            f"Decision: {decision.upper()}\n"
            f"Status updated to: {candidate['status']}\n\n"
            f"The candidate has been notified via email."
        )

    except Exception as e:
        return f"Error sending decision: {str(e)}"


@tool
def get_application_status(candidate_id: str) -> str:
    """Check the current status of a job application. Returns the candidate's
    stage in the hiring pipeline, timeline, and next steps.
    Use when an applicant asks about their application.

    Args:
        candidate_id: Candidate ID (e.g., 'CAND-001')

    Returns:
        Application status with timeline and next steps.
    """
    try:
        if candidate_id not in CANDIDATES:
            return (
                f"Candidate {candidate_id} not found. "
                f"Please verify your candidate ID and try again."
            )

        cand = CANDIDATES[candidate_id]

        # Build timeline
        timeline = [f"Applied on {cand['applied_date']} for {cand['applied_for']}"]

        if cand.get("score") is not None:
            timeline.append(f"Resume screened — Score: {cand['score']}/100")

        if cand.get("interview_date"):
            timeline.append(
                f"Interview {'scheduled' if cand['status'] == 'interview_scheduled' else 'completed'} "
                f"on {cand['interview_date']} with {cand.get('interviewer', 'TBD')}"
            )

        # Next steps based on status
        next_steps = {
            "applied": "Your application is under review. You will hear back within 5-7 business days.",
            "screening": "Your resume is being evaluated by our hiring team. Results expected within 3 business days.",
            "interview_scheduled": f"Your interview is scheduled for {cand.get('interview_date', 'TBD')}. Please check your email for details.",
            "offer_extended": "An offer has been sent to your email. Please respond within 5 business days.",
            "rejected": "Unfortunately, we have decided not to move forward at this time. We encourage you to apply for future openings.",
            "hired": "Congratulations! Welcome to ACME Corp. HR will reach out with onboarding details.",
        }

        status_display = cand["status"].replace("_", " ").title()

        return (
            f"Application Status for {cand['name']} ({candidate_id})\n"
            f"{'=' * 45}\n"
            f"Position: {cand['applied_for']}\n"
            f"Current Status: {status_display}\n\n"
            f"Timeline:\n" +
            "\n".join(f"  - {t}" for t in timeline) +
            f"\n\nNext Steps: {next_steps.get(cand['status'], 'Please contact HR for more information.')}"
        )

    except Exception as e:
        return f"Error checking application status: {str(e)}"
