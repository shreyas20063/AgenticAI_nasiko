"""Session token and user-context header utilities for HRFlow AI.

Sessions lock a user's role + identity server-side so the message text
cannot be used to impersonate a different role or user.

Flow:
  1. Client calls POST /session/create with {"role": "employee", "user_id": "EMP-001"}
  2. Gets back {"session_token": "<signed_token>"}
  3. Includes X-Session-Token header on every POST / request
  4. Orchestrator verifies token → locked role/user_id override message text
  5. Orchestrator forwards X-User-Context header (also HMAC-signed) to sub-agents
  6. Sub-agents verify context and inject locked identity into agent execution
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

# Session TTL: 24 hours
SESSION_TTL = 86400

# Valid roles
VALID_ROLES = {"employee", "applicant", "hr", "manager", "ceo"}


def _sign(payload_b64: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()


def create_session_token(role: str, user_id: str, secret: str) -> str:
    """Create a signed session token encoding role + user_id."""
    payload = {
        "role": role.lower(),
        "user_id": user_id,
        "exp": int(time.time()) + SESSION_TTL,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = _sign(payload_b64, secret)
    return f"{payload_b64}.{sig}"


def verify_session_token(token: str, secret: str) -> Optional[dict]:
    """Verify session token signature and expiry. Returns payload or None."""
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected = _sign(payload_b64, secret)
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def create_user_context_header(role: str, user_id: str, secret: str) -> str:
    """Create a signed X-User-Context header value for sub-agent forwarding."""
    payload = {"role": role.lower(), "user_id": user_id, "ts": int(time.time())}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = _sign(payload_b64, secret)
    return f"{payload_b64}.{sig}"


def verify_user_context_header(header_value: str, secret: str) -> Optional[dict]:
    """Verify X-User-Context header. Returns {role, user_id} or None."""
    try:
        payload_b64, sig = header_value.rsplit(".", 1)
        expected = _sign(payload_b64, secret)
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        # Context headers expire after 5 minutes (replay protection)
        if abs(time.time() - payload.get("ts", 0)) > 300:
            return None
        return {"role": payload["role"], "user_id": payload["user_id"]}
    except Exception:
        return None
