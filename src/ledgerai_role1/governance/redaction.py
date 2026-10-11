"""Redaction policies and PII safety controls for document intelligence."""

from __future__ import annotations

import re
from typing import Final

# Strict regex patterns for sensitive identifiers
_IBAN_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_CREDIT_CARD_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
_SSN_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_RAW_BANK_ACCOUNT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:account|acct|acc)\s*(?:#|no\.?|num)?\s*[:=]?\s*(\d{6,18})\b"
)
_EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)


def mask_bank_account_number(account_number: str) -> str:
    """Safely mask bank account number to retain only last 4 digits."""
    clean = re.sub(r"[\s-]", "", account_number)
    if len(clean) <= 4:
        return "****"
    return f"****{clean[-4:]}"


def sanitize_sensitive_text(text: str) -> str:
    """Redact sensitive personal identifiers, cards, and unmasked bank accounts from text."""
    redacted = _IBAN_PATTERN.sub("[REDACTED_IBAN]", text)
    redacted = _CREDIT_CARD_PATTERN.sub("[REDACTED_CARD]", redacted)
    redacted = _SSN_PATTERN.sub("[REDACTED_SSN]", redacted)
    redacted = _RAW_BANK_ACCOUNT_PATTERN.sub(
        lambda m: f"Account: ****{m.group(1)[-4:] if len(m.group(1)) >= 4 else '****'}",
        redacted,
    )
    return redacted


def assert_safe_for_dataset(text: str, field_name: str) -> None:
    """Assert that a field value does not contain forbidden unmasked secrets or credentials."""
    lowered = text.lower()
    forbidden_tokens = (
        "password",
        "secret",
        "private key",
        "bearer ",
        "aws_secret",
        "authorization: basic",
    )
    if any(token in lowered for token in forbidden_tokens):
        raise ValueError(f"Sensitive credential detected in field {field_name}")

    if _CREDIT_CARD_PATTERN.search(text):
        raise ValueError(f"Unmasked payment card number detected in field {field_name}")

    if _SSN_PATTERN.search(text):
        raise ValueError(f"Unmasked SSN detected in field {field_name}")
