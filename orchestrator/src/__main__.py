"""HRFlow AI Orchestrator — Central routing hub for all HR agents.

Serves on port 5000. Routes user requests to the correct sub-agent
based on role + intent classification. Pure Python routing, NO LLM.

Exposes:
- GET  /health                  -> health check
- GET  /.well-known/agent.json  -> AgentCard
- POST /                        -> A2A JSON-RPC message/send
"""

import json
import logging
import os

import click
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("orchestrator")

app = FastAPI(title="HRFlow AI Orchestrator")

# ── A2A Clients (initialized at startup) ───────────────────────

recruitment_client = A2AClient(
    base_url=os.getenv("RECRUITMENT_AGENT_URL", "http://recruitment-agent:8001"),
    agent_name="Recruitment Agent",
)

employee_services_client = A2AClient(
    base_url=os.getenv("EMPLOYEE_SERVICES_URL", "http://employee-services:8002"),
    agent_name="Employee Services Agent",
)

analytics_client = A2AClient(
    base_url=os.getenv("ANALYTICS_AGENT_URL", "http://analytics-agent:8003"),
    agent_name="Analytics Agent",
)

# Map agent keys to clients
AGENT_CLIENTS = {
    RECRUITMENT: recruitment_client,
    EMPLOYEE_SERVICES: employee_services_client,
    ANALYTICS: analytics_client,
}

# ── AgentCard loader ────────────────────────────────────────────

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
            _agent_card = {
                "name": "HRFlow AI Orchestrator",
                "status": "active",
            }
    return _agent_card


# ── Endpoints ───────────────────────────────────────────────────


@app.on_event("startup")
async def startup():
    logger.info("HRFlow AI Orchestrator starting on port 5000...")
    logger.info(
        f"  Recruitment Agent:      {recruitment_client.base_url}"
    )
    logger.info(
        f"  Employee Services Agent: {employee_services_client.base_url}"
    )
    logger.info(
        f"  Analytics Agent:        {analytics_client.base_url}"
    )


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/.well-known/agent.json")
async def agent_card():
    return get_agent_card()


VALID_ROLES = {"employee", "applicant", "hr", "manager", "ceo"}


@app.post("/")
async def handle_a2a(request: Request):
    """Handle incoming A2A JSON-RPC requests and route to sub-agents."""
    body = None
    try:
        body = await request.json()
        rpc_request = JsonRpcRequest(**body)
        request_id = rpc_request.id

        # Guard: Unknown JSON-RPC method
        if rpc_request.method != "message/send":
            logger.warning(
                f"[ORCHESTRATOR] Unknown method: {rpc_request.method}"
            )
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: '{rpc_request.method}'. "
                               f"Only 'message/send' is supported.",
                },
            }, status_code=400)

        # Extract text from message parts
        text_parts = [
            part.text
            for part in rpc_request.params.message.parts
            if part.kind == "text" and part.text
        ]
        message_text = " ".join(text_parts).strip()

        # Guard: Empty message
        if not message_text:
            logger.warning("[ORCHESTRATOR] Empty message received")
            response = create_completed_task(
                "I didn't receive a message. How can I help you today?\n\n"
                "Please start your message with your role, for example:\n"
                "  Role: EMPLOYEE (EMP-001). What is the remote work policy?",
                request_id,
            )
            return JSONResponse(content=response.model_dump())

        logger.info(f"[ORCHESTRATOR] Received: \"{message_text[:150]}\"")

        # Step 1: Extract role from message
        role, user_id, clean_message = extract_role_from_message(message_text)

        # Guard: Invalid or missing role
        if role.lower() not in VALID_ROLES:
            logger.warning(
                f"[ORCHESTRATOR] Invalid role: '{role}'"
            )
            response = create_completed_task(
                f"Unknown role '{role}'. Please specify your role by starting "
                f"your message with one of:\n"
                f"  Role: EMPLOYEE (your-id). your question\n"
                f"  Role: APPLICANT (your-id). your question\n"
                f"  Role: HR. your question\n"
                f"  Role: MANAGER (your-id). your question\n"
                f"  Role: CEO. your question",
                request_id,
            )
            return JSONResponse(content=response.model_dump())

        # Step 2: Classify intent and pick target agent
        agent_key, reasoning = classify_intent(clean_message, role)

        logger.info(
            f"[ROUTER] Role={role} | Agent={agent_key} | Reason={reasoning}"
        )

        # Step 3: Build contextualized message for sub-agent
        contextualized = build_contextualized_message(
            clean_message, role, user_id
        )

        # Step 4: Forward to sub-agent via A2A
        client = AGENT_CLIENTS[agent_key]
        result = await client.send_message(contextualized)

        # Step 5: Return response
        if result["status"] == "completed":
            logger.info(
                f"[ORCHESTRATOR] \u2713 Response from {client.agent_name} "
                f"({len(result['text'])} chars)"
            )
            response = create_completed_task(result["text"], request_id)
            return JSONResponse(content=response.model_dump())
        else:
            # Return graceful message as "completed" so user sees text, not error
            logger.warning(
                f"[ORCHESTRATOR] \u2717 {client.agent_name} returned "
                f"status={result['status']}"
            )
            graceful_msg = (
                f"I'm sorry, the {client.agent_name} is temporarily "
                f"unavailable. Your request has been noted. "
                f"Please try again shortly."
            )
            if result.get("text"):
                graceful_msg = result["text"]
            response = create_completed_task(graceful_msg, request_id)
            return JSONResponse(content=response.model_dump())

    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Error: {str(e)}", exc_info=True)
        request_id = "unknown"
        if body:
            try:
                request_id = body.get("id", "unknown")
            except Exception:
                pass
        error_response = create_completed_task(
            "I encountered an unexpected error processing your request. "
            "Please try again or contact support.",
            request_id,
        )
        return JSONResponse(content=error_response.model_dump())


# ── CLI entry point ─────────────────────────────────────────────


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=5000, help="Port to listen on")
def main(host: str, port: int):
    """Start the HRFlow AI Orchestrator."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
