"""WhatsApp Invoice Sharing and URL formatting utility for Sri Lanka."""

import re
import urllib.parse
import webbrowser
from typing import List, Dict, Any, Optional


def clean_sri_lankan_phone(phone: str) -> str:
    """
    Format Sri Lankan phone numbers for WhatsApp international links:
    - 077 123 4567 -> 94771234567
    - +94 77 123 4567 -> 94771234567
    - 771234567 -> 94771234567
    """
    if not phone:
        return ""
    digits = re.sub(r"[^0-9]", "", phone)
    if digits.startswith("0") and len(digits) == 10:
        return "94" + digits[1:]
    elif digits.startswith("94"):
        return digits
    elif len(digits) == 9:
        return "94" + digits
    return digits


def generate_invoice_whatsapp_text(
    business_name: str,
    invoice_number: str,
    date_str: str,
    customer_name: str,
    items: List[Dict[str, Any]],
    total_display: str,
    paid_display: str,
    balance_display: str,
    bottles_19l_returned: int = 0
) -> str:
    """Format a clean, professional plain text invoice summary for WhatsApp."""
    lines = [
        f"💧 *{business_name}*",
        f"📄 *Invoice:* {invoice_number}",
        f"📅 *Date:* {date_str}",
        f"👤 *Customer:* {customer_name}",
        "------------------------------------",
    ]
    for it in items:
        p_name = it.get("product_name", "Item")
        qty = it.get("quantity", 1)
        tot_disp = it.get("line_total_display", "")
        lines.append(f"• {p_name} x {qty}: {tot_disp}")

    if bottles_19l_returned > 0:
        lines.append(f"🔄 *19 L Empty Bottles Returned:* {bottles_19l_returned}")

    lines.extend([
        "------------------------------------",
        f"💰 *Total Amount:* {total_display}",
        f"✅ *Amount Paid:* {paid_display}",
        f"📌 *Balance Due:* {balance_display}",
        "------------------------------------",
        "Thank you for choosing us!",
    ])
    return "\n".join(lines)


def generate_whatsapp_url(phone: str, text: str) -> str:
    """Generate universal wa.me link with URL-encoded message."""
    cleaned_phone = clean_sri_lankan_phone(phone)
    encoded_text = urllib.parse.quote(text)
    if cleaned_phone:
        return f"https://wa.me/{cleaned_phone}?text={encoded_text}"
    return f"https://wa.me/?text={encoded_text}"


def open_whatsapp_share(phone: str, text: str) -> bool:
    """Open WhatsApp Web / Desktop with pre-filled message."""
    try:
        url = generate_whatsapp_url(phone, text)
        webbrowser.open(url)
        return True
    except Exception:
        return False
