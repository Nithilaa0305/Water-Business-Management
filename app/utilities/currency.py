"""Currency and financial arithmetic utilities.
All internal monetary values are stored and calculated as exact integer cents
(minor currency units) to eliminate binary floating-point rounding errors.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def to_cents(amount: Union[int, float, str, Decimal, None]) -> int:
    """Convert any monetary representation to integer cents (e.g. 125.50 -> 12550)."""
    if amount is None:
        return 0
    if isinstance(amount, int):
        # If already an integer, check whether caller passed raw rupees or cents
        return amount
    # Use Decimal for safe representation
    d = Decimal(str(amount))
    cents = (d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def from_cents(cents: int) -> Decimal:
    """Convert integer cents back to Decimal rupees (e.g. 12550 -> Decimal('125.50'))."""
    if cents is None:
        cents = 0
    return (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_currency(cents: Union[int, Decimal, float], symbol: str = "Rs. ") -> str:
    """Format integer cents as professional Sri Lankan Rupee string (e.g. Rs. 12,500.00)."""
    if cents is None:
        cents = 0
    if not isinstance(cents, int):
        cents = to_cents(cents)
    
    is_negative = cents < 0
    abs_cents = abs(cents)
    rupees = abs_cents // 100
    sub_cents = abs_cents % 100
    
    formatted_rupees = f"{rupees:,}"
    formatted_cents = f"{sub_cents:02d}"
    
    prefix = "-" if is_negative else ""
    return f"{prefix}{symbol}{formatted_rupees}.{formatted_cents}"


def multiply_cents(cents: int, quantity: Union[int, Decimal, float]) -> int:
    """Safely multiply unit price in cents by a quantity with half-up rounding."""
    if cents == 0 or quantity == 0:
        return 0
    q = Decimal(str(quantity))
    c = Decimal(cents)
    total = (c * q).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(total)


def calculate_discount(subtotal_cents: int, discount_pct_or_amount: Union[int, float, Decimal], is_percentage: bool = False) -> int:
    """Calculate discount in cents."""
    if is_percentage:
        pct = Decimal(str(discount_pct_or_amount)) / Decimal("100")
        disc = (Decimal(subtotal_cents) * pct).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return min(subtotal_cents, int(disc))
    else:
        disc = to_cents(discount_pct_or_amount)
        return min(subtotal_cents, disc)
