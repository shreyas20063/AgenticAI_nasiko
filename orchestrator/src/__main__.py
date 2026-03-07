"""HRFlow AI Orchestrator — Central routing hub for all HR agents.

Serves on port 5000. Routes user requests to the correct sub-agent
using LLM-based intent classification.

Security features:
- Rate limiting (30 req/min per IP)
- Prompt injection detection
- Input sanitization (max 2000 chars)
- Structured audit logging
- Internal shared-secret header injected to sub-agents
- Session-based role+identity locking (X-Session-Token)
- Tamper-proof user context forwarded to sub-agents (X-User-Context)

Exposes:
- GET  /health                  -> health check
- GET  /.well-known/agent.json  -> AgentCard
- POST /session/create          -> create a role-locked session token
- POST /                        -> A2A JSON-RPC message/send
"""

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import click
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from a2a_client import A2AClient
from a2a_models import JsonRpcRequest, create_completed_task, create_failed_task
from router import (
    ANALYTICS,
    EMPLOYEE_SERVICES,
    RECRUITMENT,
    build_contextualized_message,
    classify_intent,
    extract_role_from_message,
)
from security import audit, check_rate_limit, detect_prompt_injection, sanitize_input
from session import (
    VALID_ROLES,
    create_session_token,
    create_user_context_header,
    verify_session_token,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("orchestrator")

INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "hrflow-internal-secret-change-me")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HRFlow AI Orchestrator starting on port 5000...")
    logger.info(f"  Recruitment Agent:       {recruitment_client.base_url}")
    logger.info(f"  Employee Services Agent: {employee_services_client.base_url}")
    logger.info(f"  Analytics Agent:         {analytics_client.base_url}")
    logger.info(f"  Internal secret:         {'SET' if INTERNAL_SECRET != 'hrflow-internal-secret-change-me' else 'DEFAULT (change in prod!)'}")
    yield


app = FastAPI(title="HRFlow AI Orchestrator", lifespan=lifespan)

# ── A2A Clients ─────────────────────────────────────────────────

recruitment_client = A2AClient(
    base_url=os.getenv("RECRUITMENT_AGENT_URL", "http://recruitment-agent:8001"),
    agent_name="Recruitment Agent",
    internal_secret=INTERNAL_SECRET,
)
employee_services_client = A2AClient(
    base_url=os.getenv("EMPLOYEE_SERVICES_URL", "http://employee-services:8002"),
    agent_name="Employee Services Agent",
    internal_secret=INTERNAL_SECRET,
)
analytics_client = A2AClient(
    base_url=os.getenv("ANALYTICS_AGENT_URL", "http://analytics-agent:8003"),
    agent_name="Analytics Agent",
    internal_secret=INTERNAL_SECRET,
)

AGENT_CLIENTS = {
    RECRUITMENT: recruitment_client,
    EMPLOYEE_SERVICES: employee_services_client,
    ANALYTICS: analytics_client,
}

# ── AgentCard ────────────────────────────────────────────────────

_agent_card = None


def get_agent_card():
    global _agent_card
    if _agent_card is None:
        card_path = os.path.join(os.path.dirname(__file__), "..", "AgentCard.json")
        if not os.path.exists(card_path):
            card_path = os.path.join(os.path.dirname(__file__), "AgentCard.json")
        if os.path.exists(card_path):
            with open(card_path) as f:
                _agent_card = json.load(f)
        else:
            _agent_card = {"name": "HRFlow AI Orchestrator", "status": "active"}
    return _agent_card


# ── Endpoints ────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/.well-known/agent.json")
async def agent_card():
    return get_agent_card()


class SessionCreateRequest(BaseModel):
    role: str
    user_id: str = "unknown"


@app.post("/session/create")
async def session_create(body: SessionCreateRequest):
    """Create a signed session token that locks the caller's role and user_id.

    The token should be included as the X-Session-Token header on all POST /
    requests. When present, the role and user_id embedded in the token override
    any role prefix in the message text, preventing impersonation.
    """
    role = body.role.strip().lower()
    if role not in VALID_ROLES:
        return JSONResponse(
            content={
                "error": (
                    f"Invalid role '{role}'. "
                    f"Valid roles: {', '.join(sorted(VALID_ROLES))}"
                )
            },
            status_code=400,
        )
    token = create_session_token(role, body.user_id.strip(), INTERNAL_SECRET)
    logger.info(f"[SESSION] Created session: role={role} user_id={body.user_id}")
    return {"session_token": token, "role": role, "user_id": body.user_id.strip()}


@app.post("/")
async def handle_a2a(request: Request):
    """Handle incoming A2A JSON-RPC requests with full security pipeline."""
    start_time = time.time()
    request_id = "unknown"
    role = "unknown"
    user_id = "unknown"
    agent_routed = "none"
    body = None
    ip = request.client.host if request.client else "unknown"

    try:
        # ── Security: Rate limiting ──────────────────────────────
        allowed, remaining = check_rate_limit(ip)
        if not allowed:
            logger.warning(f"[SECURITY] Rate limit hit for IP {ip}")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32029,
                        "message": "Rate limit exceeded. Please wait before sending more requests.",
                    },
                },
                status_code=429,
                headers={"Retry-After": "60"},
            )

        # ── Parse request ────────────────────────────────────────
        body = await request.json()
        rpc_request = JsonRpcRequest(**body)
        request_id = rpc_request.id

        if rpc_request.method != "message/send":
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: '{rpc_request.method}'. Only 'message/send' is supported.",
                    },
                },
                status_code=400,
            )

        text_parts = [
            part.text
            for part in rpc_request.params.message.parts
            if part.kind == "text" and part.text
        ]
        raw_text = " ".join(text_parts).strip()

        if not raw_text:
            response = create_completed_task(
                "I didn't receive a message. Please start with your role:\n"
                "  Role: EMPLOYEE (EMP-001). What is the remote work policy?",
                request_id,
            )
            return JSONResponse(content=response.model_dump())

        # ── Security: Sanitize input ─────────────────────────────
        message_text, truncation_note = sanitize_input(raw_text)
        if truncation_note:
            logger.info(f"[SECURITY] {truncation_note}")

        # ── Security: Prompt injection detection ─────────────────
        if detect_prompt_injection(message_text):
            latency = (time.time() - start_time) * 1000
            audit(
                request_id=request_id, ip=ip, role=role, user_id=user_id,
                agent_routed_to=agent_routed, message_preview=message_text,
                latency_ms=latency, status="blocked",
                blocked_reason="prompt_injection",
            )
            response = create_completed_task(
                "Your request was flagged as potentially unsafe and cannot be processed. "
                "Please rephrase your question.",
                request_id,
            )
            return JSONResponse(content=response.model_dump())

        logger.info(f"[ORCHESTRATOR] [{ip}] Received: \"{message_text[:150]}\"")

        # ── Step 1: Session token check (role+identity locking) ──
        session_token = request.headers.get("X-Session-Token", "")
        locked_identity = None
        if session_token:
            locked_identity = verify_session_token(session_token, INTERNAL_SECRET)
            if locked_identity is None:
                logger.warning(f"[SECURITY] Invalid/expired session token from {ip}")
                response = create_completed_task(
                    "Your session token is invalid or expired. "
                    "Please create a new session via POST /session/create.",
                    request_id,
                )
                return JSONResponse(content=response.model_dump(), status_code=401)

        # ── Step 2: Extract role from message or locked session ──
        msg_role, msg_user_id, clean_message = extract_role_from_message(message_text)

        if locked_identity:
            role = locked_identity["role"]
            user_id = locked_identity["user_id"]
            if msg_role.lower() not in ("none", role):
                logger.warning(
                    f"[SECURITY] Session role={role} overrides message role={msg_role} from {ip}"
                )
        else:
            role = msg_role
            user_id = msg_user_id

        if role.lower() not in VALID_ROLES:
            # No role prefix in message — treat as general HR inquiry (HR role, full access)
            logger.info(f"[ORCHESTRATOR] No role prefix detected, defaulting to hr for: '{message_text[:80]}'")
            role = "hr"
            user_id = "unknown"
            clean_message = message_text

        # ── Step 3: LLM intent classification ───────────────────
        agent_key, reasoning = await classify_intent(clean_message, role)
        agent_routed = agent_key
        logger.info(f"[ROUTER] Role={role} | Agent={agent_key} | Reason={reasoning}")

        # ── Step 4: Build contextualized message ─────────────────
        contextualized = build_contextualized_message(clean_message, role, user_id)

        # ── Step 5: Forward to sub-agent with locked identity ────
        user_context = create_user_context_header(role, user_id, INTERNAL_SECRET)
        client = AGENT_CLIENTS[agent_key]
        result = await client.send_message(contextualized, user_context=user_context)

        # ── Step 6: Return response ──────────────────────────────
        latency = (time.time() - start_time) * 1000
        final_text = result.get("text", "")
        if not final_text and result["status"] != "completed":
            final_text = (
                f"I'm sorry, the {client.agent_name} is temporarily unavailable. "
                "Please try again shortly."
            )

        audit(
            request_id=request_id, ip=ip, role=role, user_id=user_id,
            agent_routed_to=agent_routed, message_preview=clean_message,
            latency_ms=latency, status=result["status"],
        )

        if result["status"] == "completed":
            logger.info(f"[ORCHESTRATOR] ✓ {client.agent_name} | {latency:.0f}ms | {len(final_text)} chars")
        else:
            logger.warning(f"[ORCHESTRATOR] ✗ {client.agent_name} status={result['status']}")

        response = create_completed_task(final_text, request_id)
        return JSONResponse(content=response.model_dump())

    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Error: {str(e)}", exc_info=True)
        if body:
            try:
                request_id = body.get("id", request_id)
            except Exception:
                pass
        latency = (time.time() - start_time) * 1000
        audit(
            request_id=request_id, ip=ip, role=role, user_id=user_id,
            agent_routed_to=agent_routed, message_preview="",
            latency_ms=latency, status="error", blocked_reason=str(e)[:80],
        )
        error_response = create_completed_task(
            "I encountered an unexpected error processing your request. "
            "Please try again or contact support.",
            request_id,
        )
        return JSONResponse(content=error_response.model_dump())


# ── CLI ──────────────────────────────────────────────────────────


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=5000, help="Port to listen on")
def main(host: str, port: int):
    """Start the HRFlow AI Orchestrator."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
