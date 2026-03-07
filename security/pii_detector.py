"""
PII Detection & Redaction Pipeline.
Detects and redacts personally identifiable information in text
before logging or when blind screening is active.

Supports: names, emails, phones, SSNs, credit cards, IBANs,
national IDs (US/UK/EU/India), IP addresses, DOBs, addresses.
"""

import re
from typing import NamedTuple


class PIIMatch(NamedTuple):
    pii_type: str
    value: str
    start: int
    end: int


# ============================================================
# PII Detection Patterns (pre-compiled for performance)
# ============================================================

PII_PATTERNS: dict[str, re.Pattern] = {
    # Email addresses
    "email": re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ),

    # Phone numbers - international formats
    "phone": re.compile(
        r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
    ),

    # US Social Security Number
    "ssn": re.compile(
        r'\b\d{3}-\d{2}-\d{4}\b'
    ),

    # UK National Insurance Number
    "national_insurance": re.compile(
        r'\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b',
        re.IGNORECASE,
    ),

    # Indian Aadhaar Number (12 digits, often with spaces)
    "aadhaar": re.compile(
        r'\b\d{4}\s?\d{4}\s?\d{4}\b'
    ),

    # Indian PAN Card
    "pan_card": re.compile(
        r'\b[A-Z]{5}\d{4}[A-Z]\b'
    ),

    # Credit card numbers (with or without separators)
    "credit_card": re.compile(
        r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    ),

    # IBAN (International Bank Account Number)
    "iban": re.compile(
        r'\b[A-Z]{2}\d{2}\s?[\dA-Z]{4}\s?(?:[\dA-Z]{4}\s?){1,7}[\dA-Z]{1,4}\b'
    ),

    # Passport numbers (generic: 1-2 letters + 6-9 digits)
    "passport": re.compile(
        r'\b[A-Z]{1,2}\d{6,9}\b'
    ),

    # National ID (generic EU-style: 2 letters + 6-10 digits)
    "national_id": re.compile(
        r'\b[A-Z]{2}\d{6,10}\b'
    ),

    # IP addresses (IPv4)
    "ip_address": re.compile(
        r'\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
    ),

    # Date of birth (with explicit markers)
    "date_of_birth": re.compile(
        r'\b(?:DOB|Date of Birth|Born|Birthday|D\.O\.B)[\s:]*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b',
        re.IGNORECASE,
    ),

    # Physical addresses (US-style street addresses)
    "address": re.compile(
        r'\b\d{1,5}\s+[\w\s]{1,50}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl|Circle|Cir|Terrace|Ter|Highway|Hwy)\b',
        re.IGNORECASE,
    ),

    # Person names - heuristic: sequence of 2-4 capitalized words
    # not preceded by common non-name contexts
    "person_name": re.compile(
        r'(?<![./#@])\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?)?\s*[A-Z][a-z]{1,20}\s+(?:[A-Z]\.?\s+)?[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?\b'
    ),
}

# Common words that look like names but aren't (reduce false positives)
_NAME_FALSE_POSITIVES = {
    "human resources", "new york", "los angeles", "san francisco",
    "united states", "united kingdom", "south africa", "north america",
    "south america", "east coast", "west coast", "senior software",
    "software engineer", "project manager", "vice president",
    "chief executive", "general manager", "human resource",
    "monday morning", "tuesday afternoon", "annual leave",
    "sick leave", "personal leave", "health insurance",
    "dental plan", "executive officer", "blue cross",
}

# Fields to redact in blind screening mode
BLIND_SCREENING_FIELDS = {
    "full_name", "name", "first_name", "last_name",
    "email", "phone", "address", "date_of_birth",
    "gender", "age", "university", "college", "school",
    "photo", "national_id", "ssn", "passport",
    "nationality", "ethnicity", "race", "religion",
    "marital_status", "disability",
}


def detect_pii(text: str) -> list[PIIMatch]:
    """Detect all PII occurrences in text."""
    matches = []
    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group()

            # Filter out name false positives
            if pii_type == "person_name":
                if value.lower().strip() in _NAME_FALSE_POSITIVES:
                    continue
                # Skip very short matches (likely not names)
                if len(value.strip()) < 5:
                    continue

            matches.append(PIIMatch(
                pii_type=pii_type,
                value=value,
                start=match.start(),
                end=match.end(),
            ))
    return matches


def redact_pii(text: str, replacement: str = "[REDACTED]") -> str:
    """Replace all detected PII with a redaction marker."""
    matches = detect_pii(text)
    if not matches:
        return text

    # Sort by start position descending so replacements don't shift indices
    matches.sort(key=lambda m: m.start, reverse=True)

    # Deduplicate overlapping matches (keep longer match)
    filtered = []
    for match in matches:
        if not filtered or match.end <= filtered[-1].start:
            filtered.append(match)

    redacted = text
    for match in filtered:
        label = f"[{match.pii_type.upper()}_REDACTED]"
        redacted = redacted[:match.start] + label + redacted[match.end:]
    return redacted


def redact_for_logging(text: str) -> str:
    """Aggressively redact PII for audit log storage."""
    return redact_pii(text)


def redact_candidate_for_blind(candidate_data: dict) -> dict:
    """
    Remove PII fields from candidate data for blind screening.
    Returns a new dict with sensitive fields removed or masked.
    """
    redacted = {}
    for key, value in candidate_data.items():
        if key.lower() in BLIND_SCREENING_FIELDS:
            continue  # completely omit the field
        if isinstance(value, str):
            redacted[key] = redact_pii(value)
        else:
            redacted[key] = value
    return redacted


def contains_pii(text: str) -> bool:
    """Quick check if text contains any PII."""
    return len(detect_pii(text)) > 0
