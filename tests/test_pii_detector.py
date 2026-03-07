"""Unit tests for the PII Detection & Redaction module."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security.pii_detector import (
    detect_pii,
    redact_pii,
    redact_candidate_for_blind,
    contains_pii,
)


# ============================================================
# detect_pii
# ============================================================


class TestDetectPII:
    """Tests for the detect_pii function."""

    # -- Email detection --

    def test_detect_email_simple(self):
        matches = detect_pii("Contact me at alice@example.com for details.")
        types = [m.pii_type for m in matches]
        assert "email" in types

    def test_detect_email_value(self):
        matches = detect_pii("Email: bob.smith+hr@company.co.uk")
        email_matches = [m for m in matches if m.pii_type == "email"]
        assert len(email_matches) >= 1
        assert "bob.smith+hr@company.co.uk" in [m.value for m in email_matches]

    def test_detect_multiple_emails(self):
        text = "Send to alice@test.com and bob@test.com"
        matches = detect_pii(text)
        email_matches = [m for m in matches if m.pii_type == "email"]
        assert len(email_matches) == 2

    # -- Phone detection --

    def test_detect_phone_us_format(self):
        matches = detect_pii("Call me at (555) 123-4567")
        types = [m.pii_type for m in matches]
        assert "phone" in types

    def test_detect_phone_international(self):
        matches = detect_pii("Phone: +1-555-987-6543")
        types = [m.pii_type for m in matches]
        assert "phone" in types

    def test_detect_phone_with_dots(self):
        matches = detect_pii("Reach me at 555.123.4567")
        types = [m.pii_type for m in matches]
        assert "phone" in types

    # -- SSN detection --

    def test_detect_ssn(self):
        matches = detect_pii("My SSN is 123-45-6789")
        types = [m.pii_type for m in matches]
        assert "ssn" in types

    def test_detect_ssn_value(self):
        matches = detect_pii("SSN: 999-88-7777")
        ssn_matches = [m for m in matches if m.pii_type == "ssn"]
        assert len(ssn_matches) >= 1
        assert "999-88-7777" in [m.value for m in ssn_matches]

    # -- Credit card detection --

    def test_detect_credit_card_with_spaces(self):
        matches = detect_pii("Card: 4111 1111 1111 1111")
        types = [m.pii_type for m in matches]
        assert "credit_card" in types

    def test_detect_credit_card_with_dashes(self):
        matches = detect_pii("Card: 4111-1111-1111-1111")
        types = [m.pii_type for m in matches]
        assert "credit_card" in types

    def test_detect_credit_card_no_separators(self):
        matches = detect_pii("CC 4111111111111111")
        types = [m.pii_type for m in matches]
        assert "credit_card" in types

    # -- Address detection --

    def test_detect_address_street(self):
        matches = detect_pii("Lives at 123 Main Street")
        types = [m.pii_type for m in matches]
        assert "address" in types

    def test_detect_address_avenue(self):
        matches = detect_pii("Office at 456 Park Avenue")
        types = [m.pii_type for m in matches]
        assert "address" in types

    def test_detect_address_boulevard(self):
        matches = detect_pii("Located at 789 Sunset Blvd")
        types = [m.pii_type for m in matches]
        assert "address" in types

    def test_detect_address_drive(self):
        matches = detect_pii("Home: 10 Elm Drive")
        types = [m.pii_type for m in matches]
        assert "address" in types

    # -- IP address detection --

    def test_detect_ip_address(self):
        matches = detect_pii("Server IP is 192.168.1.100")
        types = [m.pii_type for m in matches]
        assert "ip_address" in types

    # -- Date of birth detection --

    def test_detect_dob(self):
        matches = detect_pii("DOB: 01/15/1990")
        types = [m.pii_type for m in matches]
        assert "date_of_birth" in types

    def test_detect_dob_verbose(self):
        matches = detect_pii("Date of Birth: 03-22-1985")
        types = [m.pii_type for m in matches]
        assert "date_of_birth" in types

    # -- Multiple PII types in one text --

    def test_detect_multiple_types(self):
        text = (
            "Name: John Doe, Email: john@example.com, "
            "SSN: 123-45-6789, Phone: (555) 123-4567"
        )
        matches = detect_pii(text)
        types = {m.pii_type for m in matches}
        assert "email" in types
        assert "ssn" in types
        assert "phone" in types

    # -- PIIMatch structure --

    def test_pii_match_has_start_end(self):
        matches = detect_pii("Email: test@example.com")
        email_matches = [m for m in matches if m.pii_type == "email"]
        assert len(email_matches) >= 1
        match = email_matches[0]
        assert match.start >= 0
        assert match.end > match.start
        assert match.value == "test@example.com"

    # -- Clean text --

    def test_clean_text_returns_no_matches(self):
        matches = detect_pii("Hello, how are you today?")
        assert len(matches) == 0

    def test_empty_string(self):
        matches = detect_pii("")
        assert len(matches) == 0


# ============================================================
# redact_pii
# ============================================================


class TestRedactPII:
    """Tests for the redact_pii function."""

    def test_redact_email(self):
        result = redact_pii("Contact alice@example.com please")
        assert "alice@example.com" not in result
        assert "[EMAIL_REDACTED]" in result

    def test_redact_ssn(self):
        result = redact_pii("SSN: 123-45-6789")
        assert "123-45-6789" not in result
        assert "[SSN_REDACTED]" in result

    def test_redact_phone(self):
        result = redact_pii("Call (555) 123-4567")
        assert "(555) 123-4567" not in result
        assert "[PHONE_REDACTED]" in result

    def test_redact_credit_card(self):
        result = redact_pii("Card: 4111 1111 1111 1111")
        assert "4111 1111 1111 1111" not in result
        assert "[CREDIT_CARD_REDACTED]" in result

    def test_redact_address(self):
        result = redact_pii("Lives at 123 Main Street")
        assert "123 Main Street" not in result
        assert "[ADDRESS_REDACTED]" in result

    def test_redact_multiple_types(self):
        text = "Email: test@test.com, SSN: 111-22-3333"
        result = redact_pii(text)
        assert "test@test.com" not in result
        assert "111-22-3333" not in result
        assert "[EMAIL_REDACTED]" in result
        assert "[SSN_REDACTED]" in result

    def test_redact_clean_text_unchanged(self):
        text = "This is a perfectly clean message."
        result = redact_pii(text)
        assert result == text

    def test_redact_preserves_surrounding_text(self):
        result = redact_pii("Hello test@test.com goodbye")
        assert result.startswith("Hello ")
        assert result.endswith(" goodbye")


# ============================================================
# redact_candidate_for_blind
# ============================================================


class TestRedactCandidateForBlind:
    """Tests for the redact_candidate_for_blind function."""

    def test_removes_full_name(self):
        data = {"full_name": "Alice Smith", "skills": "Python, SQL"}
        result = redact_candidate_for_blind(data)
        assert "full_name" not in result
        assert "skills" in result

    def test_removes_email_field(self):
        data = {"email": "alice@test.com", "experience": "5 years"}
        result = redact_candidate_for_blind(data)
        assert "email" not in result
        assert "experience" in result

    def test_removes_phone_field(self):
        data = {"phone": "+1-555-1234", "title": "Engineer"}
        result = redact_candidate_for_blind(data)
        assert "phone" not in result

    def test_removes_address_field(self):
        data = {"address": "123 Main St", "status": "active"}
        result = redact_candidate_for_blind(data)
        assert "address" not in result

    def test_removes_gender_field(self):
        data = {"gender": "Female", "skills": "Java"}
        result = redact_candidate_for_blind(data)
        assert "gender" not in result

    def test_removes_age_field(self):
        data = {"age": 30, "role": "Developer"}
        result = redact_candidate_for_blind(data)
        assert "age" not in result

    def test_removes_university_field(self):
        data = {"university": "MIT", "gpa": 3.8}
        result = redact_candidate_for_blind(data)
        assert "university" not in result

    def test_removes_photo_field(self):
        data = {"photo": "https://example.com/pic.jpg", "skills": "React"}
        result = redact_candidate_for_blind(data)
        assert "photo" not in result

    def test_removes_ssn_field(self):
        data = {"ssn": "123-45-6789", "skills": "Accounting"}
        result = redact_candidate_for_blind(data)
        assert "ssn" not in result

    def test_preserves_non_sensitive_fields(self):
        data = {
            "full_name": "Bob",
            "skills": "Python, Django",
            "experience_years": 7,
            "summary": "Skilled developer",
        }
        result = redact_candidate_for_blind(data)
        assert result["skills"] == "Python, Django"
        assert result["experience_years"] == 7
        assert result["summary"] == "Skilled developer"

    def test_redacts_pii_in_non_sensitive_string_fields(self):
        data = {
            "summary": "Contact alice@example.com for references",
            "skills": "Python",
        }
        result = redact_candidate_for_blind(data)
        assert "alice@example.com" not in result["summary"]
        assert "[EMAIL_REDACTED]" in result["summary"]

    def test_returns_new_dict(self):
        data = {"full_name": "Alice", "skills": "Python"}
        result = redact_candidate_for_blind(data)
        assert result is not data

    def test_empty_dict(self):
        result = redact_candidate_for_blind({})
        assert result == {}

    def test_case_insensitive_field_matching(self):
        # The code lowercases the key for comparison
        data = {"Full_Name": "Alice", "Email": "test@test.com", "skills": "SQL"}
        result = redact_candidate_for_blind(data)
        assert "Full_Name" not in result
        assert "Email" not in result
        assert "skills" in result


# ============================================================
# contains_pii
# ============================================================


class TestContainsPII:
    """Tests for the contains_pii boolean check."""

    def test_contains_pii_with_email(self):
        assert contains_pii("Reach me at test@example.com") is True

    def test_contains_pii_with_ssn(self):
        assert contains_pii("My SSN is 123-45-6789") is True

    def test_contains_pii_with_phone(self):
        assert contains_pii("Call (555) 123-4567") is True

    def test_contains_pii_with_credit_card(self):
        assert contains_pii("Card: 4111 1111 1111 1111") is True

    def test_no_pii_in_clean_text(self):
        assert contains_pii("Hello, how are you today?") is False

    def test_no_pii_in_empty_string(self):
        assert contains_pii("") is False

    def test_no_pii_in_generic_sentence(self):
        assert contains_pii("The quarterly report is ready for review.") is False
