"""Unit tests for phone and field validators."""

from app.utilities.validators import validate_phone_number, validate_name


def test_valid_10_digit_phones():
    valid_numbers = [
        "0771234567",
        "0719876543",
        "0112345678",
        "077-123-4567",
        "(077) 1234567",
        "+94771234567",
        "0094771234567",
        "94771234567"
    ]
    for num in valid_numbers:
        is_valid, clean, err = validate_phone_number(num)
        assert is_valid is True, f"Failed for {num}: {err}"
        assert clean == "0771234567" or clean.startswith("0")
        assert len(clean) == 10


def test_invalid_phones():
    invalid_numbers = [
        ("", "Phone number is required."),
        ("12345", "exactly 10 digits"),
        ("077123456789", "exactly 10 digits"),
        ("077abcdefg", "only numeric digits"),
        ("7712345678", "start with 0"),
    ]
    for num, expected_substr in invalid_numbers:
        is_valid, clean, err = validate_phone_number(num)
        assert is_valid is False
        assert expected_substr.lower() in err.lower()


def test_optional_phone():
    is_valid, clean, err = validate_phone_number("", required=False)
    assert is_valid is True
    assert clean == ""


def test_name_validation():
    valid, val, err = validate_name("John Perera", "Customer Name")
    assert valid is True
    assert val == "John Perera"

    valid_empty, _, err_empty = validate_name("   ", "Customer Name")
    assert valid_empty is False
    assert "required" in err_empty

    valid_short, _, err_short = validate_name("A", "Customer Name", min_len=2)
    assert valid_short is False
    assert "at least 2 characters" in err_short
