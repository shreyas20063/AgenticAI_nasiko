"""Security middleware and utilities for HRFlow AI Orchestrator.

Features:
- Rate limiting (per IP, sliding window)
- Prompt injection / jailbreak detection
- Input sanitization (length cap, control char stripping)
- Structured audit logging
"""

import logging
import re
import time
from collections import defaultdict, deque
from typing import Optional

logger = logging.getLogger("orchestrator.security")
audit_logger = logging.getLogger("orchestrator.audit")

# ── Config ──────────────────────────────────────────────────────
MAX_MESSAGE_LENGTH = 2000          # chars
RATE_LIMIT_REQUESTS = 30          # max requests
RATE_LIMIT_WINDOW = 60            # per N seconds (sliding window)

# ── Prompt injection patterns ───────────────────────────────────
_INJECTION_PATTERNS = [
    r"ignore (all |previous |prior |above )?instructions?",
    r"disregard (all |previous |prior |above )?instructions?",
    r"forget (everything|all|your instructions?|your role)",
    r"you are now",
    r"act as (if you are|a|an)",
    r"jailbreak",
    r"pretend (you are|to be|that)",
    r"do anything now",
    r"dan mode",
    r"developer mode",
    r"override (safety|guidelines|rules|instructions?)",
    r"system prompt",
    r"reveal (your|the) (system|original|hidden) (prompt|instructions?)",
    r"print (your|the) (system|original) (prompt|instructions?)",
    r"what (are|were) your instructions?",
    r"ignore (ethics|safety|guidelines)",
    r"bypass (safety|filter|restriction)",
]
_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS),
    re.IGNORECASE,
)

# ── Rate limiter (in-memory sliding window) ──────────────────────
_rate_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(ip: str) -> tuple[bool, int]:
    """Check if IP has exceeded the rate limit.

    Returns:
        (allowed: bool, requests_remaining: int)
    """
    now = time.time()
    window = _rate_windows[ip]

    # Evict timestamps outside the sliding window
    while window and window[0] < now - RATE_LIMIT_WINDOW:
        window.popleft()

    if len(window) >= RATE_LIMIT_REQUESTS:
        remaining = 0
        logger.warning(f"[SECURITY] Rate limit exceeded for IP {ip}")
        return False, remaining

    window.append(now)
    remaining = RATE_LIMIT_REQUESTS - len(window)
    return True, remaining


# ── Input sanitization ──────────────────────────────────────────

def sanitize_input(text: str) -> tuple[str, Optional[str]]:
    """Strip control characters and enforce length limit.

    Returns:
        (sanitized_text, error_message_or_None)
    """
    # Strip null bytes and control chars (keep newlines/tabs)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    if len(sanitized) > MAX_MESSAGE_LENGTH:
        return (
            sanitized[:MAX_MESSAGE_LENGTH],
            f"Message truncated to {MAX_MESSAGE_LENGTH} characters.",
        )

    return sanitized, None


# ── Prompt injection detection ──────────────────────────────────

def detect_prompt_injection(text: str) -> bool:
    """Return True if the message looks like a prompt injection attempt."""
    match = _INJECTION_RE.search(text)
    if match:
        logger.warning(
            f"[SECURITY] Prompt injection detected: '{match.group(0)}' "
            f"in: '{text[:100]}'"
        )
        return True
    return False


# ── Audit logging ───────────────────────────────────────────────

def audit(
    *,
    request_id: str,
    ip: str,
    role: str,
    user_id: str,
    agent_routed_to: str,
    message_preview: str,
    latency_ms: float,
    status: str,
    blocked_reason: Optional[str] = None,
) -> None:
    """Write a structured audit log entry for every request."""
    audit_logger.info(
        f"AUDIT | id={request_id} ip={ip} role={role} user={user_id} "
        f"agent={agent_routed_to} status={status} latency={latency_ms:.0f}ms"
        + (f" blocked={blocked_reason}" if blocked_reason else "")
        + f" | msg={message_preview[:80]!r}"
    )
