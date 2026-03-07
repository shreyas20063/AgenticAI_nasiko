"""
Prompt Injection Detection & Defense.
Validates user inputs before they reach the LLM to prevent
instruction override, data exfiltration, and jailbreak attempts.
"""

import re
from typing import Optional


# ============================================================
# Injection Patterns (ordered by severity)
# ============================================================

INJECTION_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # Direct instruction override
    ("instruction_override", re.compile(
        r'(?:ignore|disregard|forget|override|bypass)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions?|prompts?|rules?|constraints?)',
        re.IGNORECASE,
    ), "high"),

    # Role hijacking
    ("role_hijack", re.compile(
        r'(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be|from\s+now\s+on\s+you\s+are|switch\s+to|enter)\s+(?:a\s+)?(?:different|new|DAN|unrestricted|admin)',
        re.IGNORECASE,
    ), "high"),

    # Data exfiltration
    ("data_exfiltration", re.compile(
        r'(?:show|reveal|display|output|print|return|list|dump|export)\s+(?:all|every|the)\s+(?:data|records?|users?|employees?|candidates?|passwords?|secrets?|keys?|tokens?)',
        re.IGNORECASE,
    ), "high"),

    # System prompt extraction
    ("prompt_extraction", re.compile(
        r'(?:show|reveal|print|repeat|output|what\s+(?:is|are))\s+(?:your|the|system)\s+(?:system\s+)?(?:prompt|instructions?|rules?|configuration)',
        re.IGNORECASE,
    ), "medium"),

    # Encoding tricks
    ("encoding_trick", re.compile(
        r'(?:base64|rot13|hex|unicode|url[\s-]?encode|decode)',
        re.IGNORECASE,
    ), "low"),

    # SQL injection in natural language
    ("sql_injection", re.compile(
        r'(?:DROP\s+TABLE|DELETE\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|UNION\s+SELECT|;\s*--|OR\s+1\s*=\s*1)',
        re.IGNORECASE,
    ), "high"),

    # Bulk operations without authorization context
    ("bulk_operation", re.compile(
        r'(?:send\s+(?:email|message)\s+to\s+(?:all|every)|delete\s+all|update\s+all|mass\s+(?:email|message|delete))',
        re.IGNORECASE,
    ), "medium"),

    # Privilege escalation
    ("privilege_escalation", re.compile(
        r'(?:grant|give|set)\s+(?:me|my)\s+(?:admin|superadmin|root|full)\s+(?:access|permissions?|role|privileges?)',
        re.IGNORECASE,
    ), "high"),
]


class PromptGuardResult:
    def __init__(self):
        self.is_safe: bool = True
        self.threats: list[dict] = []
        self.risk_level: str = "none"
        self.sanitized_input: Optional[str] = None

    def add_threat(self, threat_type: str, matched_text: str, severity: str):
        self.is_safe = False
        self.threats.append({
            "type": threat_type,
            "matched": matched_text,
            "severity": severity,
        })
        # Escalate risk level
        severity_order = {"none": 0, "low": 1, "medium": 2, "high": 3}
        if severity_order.get(severity, 0) > severity_order.get(self.risk_level, 0):
            self.risk_level = severity


def check_prompt_injection(user_input: str) -> PromptGuardResult:
    """
    Analyze user input for prompt injection attempts.
    Returns a result with threat details and risk assessment.
    """
    result = PromptGuardResult()

    if not user_input or not user_input.strip():
        return result

    for threat_type, pattern, severity in INJECTION_PATTERNS:
        matches = pattern.findall(user_input)
        for match_text in matches:
            result.add_threat(threat_type, match_text, severity)

    # Check for excessive length (potential context stuffing)
    if len(user_input) > 10000:
        result.add_threat("context_stuffing", f"Input length: {len(user_input)}", "medium")

    # Check for hidden Unicode or control characters
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', user_input):
        result.add_threat("hidden_characters", "Control characters detected", "medium")

    return result


def sanitize_input(user_input: str) -> str:
    """
    Basic sanitization: strip control chars, normalize whitespace.
    Does NOT alter meaning, just removes steganographic tricks.
    """
    # Remove zero-width characters and control chars
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b\u200c\u200d\ufeff]', '', user_input)
    # Normalize excessive whitespace
    cleaned = re.sub(r'\s{3,}', '  ', cleaned)
    return cleaned.strip()


def validate_user_input(user_input: str) -> tuple[bool, str, Optional[str]]:
    """
    Full validation pipeline: sanitize then check for injection.
    Returns (is_safe, sanitized_input, rejection_reason).
    """
    sanitized = sanitize_input(user_input)
    result = check_prompt_injection(sanitized)

    if result.risk_level == "high":
        return False, sanitized, (
            f"Input blocked due to detected security threat: "
            f"{', '.join(t['type'] for t in result.threats)}"
        )

    if result.risk_level == "medium":
        # Allow but flag for monitoring
        return True, sanitized, (
            f"Warning: potential issues detected ({', '.join(t['type'] for t in result.threats)}). "
            f"Proceeding with enhanced monitoring."
        )

    return True, sanitized, None
