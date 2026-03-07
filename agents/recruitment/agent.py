"""
Recruitment Agent - handles candidate screening, ranking, and interview coordination.
"""

from agents.base_agent import BaseAgent, AgentContext, AgentResponse
from agents.recruitment.prompts import (
    RECRUITMENT_SYSTEM_PROMPT,
    RESUME_PARSER_PROMPT,
    SCREENING_PROMPT_TEMPLATE,
)
from tools.email_tool import EmailTool
from tools.calendar_tool import CalendarTool, ScheduleInterviewTool
from tools.candidate_tools import UpdateCandidateStatusTool
from security.pii_detector import redact_candidate_for_blind
from security.prompt_guard import validate_user_input
from config import get_settings
import json
import re
import structlog

logger = structlog.get_logger()
settings = get_settings()


async def _fetch_jobs_and_candidates(db, tenant_id: str) -> tuple[list, dict]:
    """Fetch jobs and their candidates from the database."""
    if not db:
        return [], {}

    from sqlalchemy import select
    from models.job import Job
    from models.candidate import Candidate

    # Fetch open jobs
    result = await db.execute(
        select(Job).where(Job.tenant_id == tenant_id, Job.status == "open")
    )
    jobs = result.scalars().all()

    # Fetch candidates per job
    candidates_by_job = {}
    for job in jobs:
        result = await db.execute(
            select(Candidate).where(
                Candidate.tenant_id == tenant_id,
                Candidate.job_id == job.id,
            )
        )
        candidates = result.scalars().all()
        candidates_by_job[job.id] = {
            "job": {
                "id": job.id,
                "title": job.title,
                "department": job.department,
                "description": job.description[:500],
                "required_skills": job.required_skills,
                "preferred_skills": job.preferred_skills,
                "min_experience_years": job.min_experience_years,
                "education_requirement": job.education_requirement,
                "blind_screening": job.blind_screening,
            },
            "candidates": [
                {
                    "id": c.id,
                    "full_name": c.full_name if not job.blind_screening else "[BLIND]",
                    "email": c.email if not job.blind_screening else "[BLIND]",
                    "years_experience": c.years_experience,
                    "education_level": c.education_level,
                    "current_title": c.current_title,
                    "current_company": c.current_company if not job.blind_screening else "[BLIND]",
                    "location": c.location,
                    "resume_summary": (c.resume_text or "")[:600],
                    "skills": [
                        {"name": s.skill_name, "proficiency": s.proficiency, "years": s.years}
                        for s in c.skills
                    ],
                    "status": c.status,
                    "screening_score": c.screening_score,
                }
                for c in candidates
            ],
        }

    return jobs, candidates_by_job


class RecruitmentAgent(BaseAgent):
    name = "recruitment_agent"
    description = "Handles recruitment workflows: screening, ranking, scheduling"
    system_prompt = RECRUITMENT_SYSTEM_PROMPT

    def __init__(self):
        super().__init__()
        self.available_tools = {
            "send_email": EmailTool(),
            "create_calendar_event": CalendarTool(),
            "schedule_interview": ScheduleInterviewTool(),
            "update_candidate_status": UpdateCandidateStatusTool(),
        }

    async def process(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Route recruitment requests to the appropriate sub-workflow."""
        text_lower = user_input.lower()

        if any(kw in text_lower for kw in ["parse resume", "parse cv", "extract from resume"]):
            return await self._parse_resume(user_input, context)
        elif any(kw in text_lower for kw in ["schedule interview", "book interview"]):
            return await self._schedule_interview(user_input, context)
        else:
            # Screen, rank, shortlist, show candidates, or general recruitment
            return await self._screen_candidates(user_input, context)

    async def _parse_resume(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Parse a resume from text input."""
        response = AgentResponse()

        messages = [
            {"role": "system", "content": RESUME_PARSER_PROMPT},
        ]

        # Inject conversation history for multi-turn awareness
        if hasattr(context, 'conversation_history') and context.conversation_history:
            for hist_msg in context.conversation_history[-6:]:
                role = hist_msg.get("role", "user")
                content = hist_msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:1000]})

        messages.append({"role": "user", "content": user_input})

        llm_response = await self._call_llm(messages, temperature=0.1)
        content = llm_response.choices[0].message.content

        try:
            parsed = json.loads(content.strip().strip("```json").strip("```"))
            response.message = (
                f"Resume parsed successfully.\n\n"
                f"**Name:** {parsed.get('full_name', 'N/A')}\n"
                f"**Title:** {parsed.get('current_title', 'N/A')} at {parsed.get('current_company', 'N/A')}\n"
                f"**Experience:** {parsed.get('years_experience', 'N/A')} years\n"
                f"**Skills:** {', '.join(s['name'] for s in parsed.get('skills', []))}\n"
                f"**Education:** {', '.join(e['degree'] + ' - ' + e['institution'] for e in parsed.get('education', []))}\n\n"
                f"**Summary:** {parsed.get('summary', 'N/A')}"
            )
            response.actions_taken.append({
                "tool": "parse_resume",
                "success": True,
                "result": parsed,
            })
        except json.JSONDecodeError:
            response.message = f"Resume analysis:\n\n{content}"

        return response

    async def _screen_candidates(self, user_input: str, context: AgentContext) -> AgentResponse:
        """
        Screen and rank candidates. Fetches real data from DB,
        passes it to the LLM for analysis (no tool calling needed).
        """
        response = AgentResponse()

        # Validate input
        is_safe, sanitized, warning = validate_user_input(user_input)
        if not is_safe:
            response.message = f"I cannot process this request. {warning}"
            return response

        # Fetch actual job and candidate data from database
        jobs, candidates_by_job = await _fetch_jobs_and_candidates(
            context.db, context.tenant_id
        )

        if not jobs:
            response.message = "No open job positions found. Please create a job posting first."
            return response

        # Build context with real data
        data_context = ""
        for job_id, data in candidates_by_job.items():
            job = data["job"]
            candidates = data["candidates"]
            data_context += f"\n## Job: {job['title']} ({job['department']})\n"
            data_context += f"Required Skills: {json.dumps(job['required_skills'])}\n"
            data_context += f"Preferred Skills: {json.dumps(job['preferred_skills'])}\n"
            data_context += f"Min Experience: {job['min_experience_years']} years\n"
            data_context += f"Education: {job['education_requirement']}\n"
            data_context += f"Blind Screening: {'Yes' if job['blind_screening'] else 'No'}\n\n"
            data_context += f"### Candidates ({len(candidates)} total):\n"
            for i, c in enumerate(candidates, 1):
                data_context += (
                    f"\n**Candidate {i}** (ID: {c['id'][:8]}...)\n"
                    f"- Name: {c['full_name']}\n"
                    f"- Experience: {c['years_experience']} years | Title: {c['current_title']}\n"
                    f"- Education: {c['education_level']}\n"
                    f"- Skills: {', '.join(s['name'] + ' (' + str(s.get('years', '?')) + 'y)' for s in c['skills'])}\n"
                    f"- Resume: {c['resume_summary'][:300]}...\n"
                    f"- Status: {c['status']}\n"
                )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": (
                "Below is the ACTUAL job and candidate data from the database. "
                "Use this data to answer the user's question. "
                "Score candidates 0-100 using the methodology in your system prompt. "
                "Provide clear explanations for your rankings.\n\n"
                "DATA:\n" + data_context
            )},
        ]

        # Inject conversation history for multi-turn awareness
        if hasattr(context, 'conversation_history') and context.conversation_history:
            for hist_msg in context.conversation_history[-6:]:
                role = hist_msg.get("role", "user")
                content = hist_msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:1000]})

        messages.append({"role": "user", "content": sanitized})

        llm_response = await self._call_llm(messages, temperature=0.2)
        llm_content = llm_response.choices[0].message.content
        response.message = llm_content

        # ---- PERSIST SCREENING SCORES TO DATABASE ----
        # Parse scores from the LLM response and write them back to candidate records
        scores_persisted = 0
        if context.db:
            try:
                from sqlalchemy import select
                from models.candidate import Candidate

                for job_id, data in candidates_by_job.items():
                    for cand in data["candidates"]:
                        cand_id = cand["id"]
                        # Try to extract score for this candidate from LLM output
                        parsed_score = self._extract_candidate_score(llm_content, cand["full_name"], cand_id)
                        if parsed_score is not None:
                            result = await context.db.execute(
                                select(Candidate).where(Candidate.id == cand_id)
                            )
                            db_cand = result.scalar_one_or_none()
                            if db_cand and db_cand.screening_score is None:
                                db_cand.screening_score = parsed_score
                                db_cand.screening_explanation = f"AI screening score: {parsed_score}/100"
                                if db_cand.status == "new":
                                    db_cand.status = "screened"
                                scores_persisted += 1
                                logger.info(
                                    "screening_score_persisted",
                                    candidate_id=cand_id,
                                    score=parsed_score,
                                    name=cand["full_name"],
                                )
                # Commit the screening scores to the database
                if scores_persisted > 0:
                    await context.db.commit()
                    logger.info("screening_scores_committed", count=scores_persisted)
            except Exception as e:
                logger.warning("screening_score_persist_failed", error=str(e))

        response.actions_taken.append({
            "tool": "screen_candidates",
            "success": True,
            "result": {
                "jobs_analyzed": len(jobs),
                "total_candidates": sum(len(d["candidates"]) for d in candidates_by_job.values()),
                "scores_persisted": scores_persisted,
            },
        })

        return response

    @staticmethod
    def _extract_candidate_score(llm_text: str, candidate_name: str, candidate_id: str) -> float | None:
        """
        Try to extract a numerical score (0-100) for a candidate from the LLM screening output.
        Looks for patterns like "Score: 85", "85/100", "rating: 85" near the candidate's name.
        """
        if not llm_text or not candidate_name:
            return None

        # Search in the region around the candidate's name mention
        name_pattern = re.escape(candidate_name)
        short_id = candidate_id[:8] if candidate_id else ""

        # Find positions where candidate is mentioned
        for pattern in [name_pattern, short_id]:
            if not pattern:
                continue
            matches = list(re.finditer(pattern, llm_text, re.IGNORECASE))
            for match in matches:
                # Look at the surrounding text (300 chars after the name)
                start = match.start()
                region = llm_text[start:start + 400]

                # Try common score patterns
                score_patterns = [
                    r'(?:score|rating|overall)[:\s]*(\d{1,3})(?:/100|\s*%|\s*out of 100)?',
                    r'(\d{1,3})\s*/\s*100',
                    r'(?:score|rating)[:\s]*(\d{1,3})',
                    r'\*\*(\d{1,3})\*\*\s*/\s*100',
                    r'\*\*(\d{1,3})/100\*\*',
                ]
                for sp in score_patterns:
                    m = re.search(sp, region, re.IGNORECASE)
                    if m:
                        try:
                            score = float(m.group(1))
                            if 0 <= score <= 100:
                                return score
                        except (ValueError, IndexError):
                            continue

        return None

    async def _schedule_interview(self, user_input: str, context: AgentContext) -> AgentResponse:
        """Schedule interviews - uses tool calling for email/calendar."""
        return await self._process_with_tools(
            user_input, context,
            "Help schedule interviews. Always confirm details before creating events."
        )

    async def screen_candidate(
        self,
        candidate_data: dict,
        job_requirements: dict,
        blind_mode: bool = False,
    ) -> dict:
        """
        Programmatic screening of a single candidate.
        Used by the orchestrator for batch processing.
        """
        profile = candidate_data
        if blind_mode:
            profile = redact_candidate_for_blind(candidate_data)

        prompt = SCREENING_PROMPT_TEMPLATE.format(
            job_requirements=json.dumps(job_requirements, indent=2),
            candidate_profile=json.dumps(profile, indent=2),
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        llm_response = await self._call_llm(messages, temperature=0.2)
        content = llm_response.choices[0].message.content

        try:
            result = json.loads(content.strip().strip("```json").strip("```"))
            return result
        except json.JSONDecodeError:
            return {
                "total_score": 0,
                "recommendation": "error",
                "summary": "Failed to parse screening result",
                "raw_response": content,
            }
