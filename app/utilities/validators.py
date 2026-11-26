"""Input validation utilities for customer, supplier, and financial records."""

import re
from typing import Tuple


def validate_phone_number(raw_phone: str, required: bool = True) -> Tuple[bool, str, str]:
    """
    Validate and normalize phone numbers (Sri Lankan standard).
    Rules:
    - Must be 10 digits (e.g. 0771234567, 0112345678).
    - Can accept spaces, dashes, or international prefix (+94, 0094, 94) and normalizes to 0XXXXXXXXX.
    - Rejects letters, symbols, or incorrect digit counts.
    Returns:
        (is_valid, normalized_phone, error_message)
    """
    if not raw_phone or not raw_phone.strip():
        if required:
            return False, "", "Phone number is required."
        return True, "", ""

    # Strip whitespace, dashes, dots, brackets
    cleaned = re.sub(r"[\s\-\.\(\)]", "", raw_phone.strip())

    # Handle international prefixes (+94, 0094, 94)
    if cleaned.startswith("+94"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("0094"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("94") and len(cleaned) == 11:
        cleaned = "0" + cleaned[2:]

    if not cleaned.isdigit():
        return False, "", "Phone number must contain only numeric digits."

    if len(cleaned) != 10:
        return (
            False,
            "",
            f"Phone number must be exactly 10 digits (e.g. 0771234567). Current length: {len(cleaned)} digits."
        )

    if not cleaned.startswith("0"):
        return (
            False,
            "",
            "Standard phone number must start with 0 (e.g. 077, 071, 011, 031)."
        )

    return True, cleaned, ""


def validate_name(name: str, field_name: str = "Name", min_len: int = 2) -> Tuple[bool, str, str]:
    """Validate non-empty names with a minimum length."""
    val = (name or "").strip()
    if not val:
        return False, "", f"{field_name} is required."
    if len(val) < min_len:
        return False, "", f"{field_name} must be at least {min_len} characters."
    return True, val, ""
