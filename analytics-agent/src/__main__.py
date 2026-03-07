"""Analytics Agent — FastAPI app with A2A JSON-RPC handler.

Serves on port 8003. Exposes:
- GET  /health                  -> health check
- GET  /.well-known/agent.json  -> AgentCard
- POST /                        -> A2A JSON-RPC message/send
"""

import json
import logging
import os
from contextlib import asynccontextmanager

import click
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from a2a_models import JsonRpcRequest, create_completed_task, create_failed_task
from session import verify_user_context_header

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "hrflow-internal-secret-change-me")



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Analytics Agent starting on port 8003...")
    get_agent()
    yield


app = FastAPI(title="HRFlow Analytics Agent", lifespan=lifespan)

# Lazy-loaded agent instance
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        from agent import Agent
        _agent = Agent()
        logger.info("Analytics Agent initialized")
    return _agent


# Load AgentCard once
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
            _agent_card = {"name": "HRFlow Analytics Agent", "status": "active"}
    return _agent_card


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/.well-known/agent.json")
async def agent_card():
    return get_agent_card()


@app.post("/")
async def handle_a2a(request: Request):
    # ── Internal token validation ────────────────────────────────
    token = request.headers.get("X-Internal-Token", "")
    if token != INTERNAL_SECRET:
        logger.warning(f"[SECURITY] Rejected request with invalid internal token from {request.client.host if request.client else 'unknown'}")
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": "unknown", "error": {"code": -32003, "message": "Unauthorized: invalid internal token"}},
            status_code=403,
        )

    body = None
    try:
        body = await request.json()
        rpc_request = JsonRpcRequest(**body)

        # Extract text from message parts
        text_parts = [
            part.text
            for part in rpc_request.params.message.parts
            if part.kind == "text" and part.text
        ]
        message_text = " ".join(text_parts)

        # Extract locked identity from X-User-Context header
        user_context_header = request.headers.get("X-User-Context", "")
        locked_identity = None
        if user_context_header:
            locked_identity = verify_user_context_header(user_context_header, INTERNAL_SECRET)
            if locked_identity:
                logger.info(
                    f"[IDENTITY] Locked: role={locked_identity['role']} user_id={locked_identity['user_id']}"
                )
            else:
                logger.warning("[SECURITY] Invalid X-User-Context header — ignoring")

        logger.info(f"[REQUEST] id={rpc_request.id} | text={message_text[:200]}")

        # Process with agent
        agent = get_agent()
        response_text = await agent.process_message(message_text, locked_identity=locked_identity)

        logger.info(f"[RESPONSE] id={rpc_request.id} | text={response_text[:200]}")

        result = create_completed_task(response_text, rpc_request.id)
        return JSONResponse(content=result.model_dump())

    except Exception as e:
        logger.error(f"[ERROR] {str(e)}", exc_info=True)
        request_id = body.get("id", "unknown") if body else "unknown"
        error_response = create_failed_task(f"Agent error: {str(e)}", request_id)
        return JSONResponse(content=error_response.model_dump(), status_code=500)


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8003, help="Port to listen on")
def main(host: str, port: int):
    """Start the Analytics Agent."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
