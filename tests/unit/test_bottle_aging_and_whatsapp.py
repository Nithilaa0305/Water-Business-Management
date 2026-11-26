"""Unit tests for FIFO Bottle Aging calculation and WhatsApp Invoice Sharing."""

import pytest
from datetime import timedelta
from app.services.bottle_service import BottleService
from app.services.customer_service import CustomerService
from app.database.models.bottle import CustomerBottleLedger
from app.utilities.dates import now_colombo
from app.utilities.whatsapp import clean_sri_lankan_phone, generate_invoice_whatsapp_text, generate_whatsapp_url


def test_fifo_bottle_aging(db_session):
    cust = CustomerService.create_customer(session=db_session, name="Hilton Colombo", phone="0773344556")
    now = now_colombo()

    # Event 1: 70 days ago -> 20 bottles issued
    e1 = CustomerBottleLedger(
        customer_id=cust.id,
        date=now - timedelta(days=70),
        movement_type="DELIVERY",
        full_issued=20,
        empty_returned=0,
        running_bottle_balance=20
    )
    # Event 2: 25 days ago -> 15 bottles issued (total issued = 35)
    e2 = CustomerBottleLedger(
        customer_id=cust.id,
        date=now - timedelta(days=25),
        movement_type="DELIVERY",
        full_issued=15,
        empty_returned=0,
        running_bottle_balance=35
    )
    # Event 3: 5 days ago -> 5 bottles issued (total issued = 40)
    e3 = CustomerBottleLedger(
        customer_id=cust.id,
        date=now - timedelta(days=5),
        movement_type="DELIVERY",
        full_issued=5,
        empty_returned=0,
        running_bottle_balance=40
    )
    # Event 4: 2 days ago -> Customer returns 15 empty bottles (FIFO offsets the oldest 15 from Event 1)
    # Remaining from Event 1 (70 days old): 5 bottles
    # Remaining from Event 2 (25 days old): 15 bottles
    # Remaining from Event 3 (5 days old): 5 bottles
    # Total remaining: 25 bottles
    e4 = CustomerBottleLedger(
        customer_id=cust.id,
        date=now - timedelta(days=2),
        movement_type="RETURN",
        full_issued=0,
        empty_returned=15,
        running_bottle_balance=25
    )
    db_session.add_all([e1, e2, e3, e4])
    db_session.commit()

    aging_list = BottleService.get_customer_bottle_aging(db_session, customer_id=cust.id)
    assert len(aging_list) == 1
    res = aging_list[0]

    assert res["total_held"] == 25
    assert res["d0_7"] == 5        # Event 3 (5 days ago)
    assert res["d8_30"] == 15      # Event 2 (25 days ago)
    assert res["d31_60"] == 0
    assert res["over_60"] == 5     # Remaining from Event 1 (70 days ago)


def test_whatsapp_phone_and_url():
    # Sri Lankan phone format variations
    assert clean_sri_lankan_phone("077 123 4567") == "94771234567"
    assert clean_sri_lankan_phone("+94 77 123 4567") == "94771234567"
    assert clean_sri_lankan_phone("0712345678") == "94712345678"
    assert clean_sri_lankan_phone("771234567") == "94771234567"

    # Message generator
    txt = generate_invoice_whatsapp_text(
        business_name="Pure Life Water",
        invoice_number="INV-202611-0001",
        date_str="2026-11-26",
        customer_name="John Stores",
        items=[{"product_name": "500 ml Water Bottle", "quantity": 24, "line_total_display": "Rs. 1,440.00"}],
        total_display="Rs. 1,440.00",
        paid_display="Rs. 1,440.00",
        balance_display="Rs. 0.00",
        bottles_19l_returned=5
    )
    assert "INV-202611-0001" in txt
    assert "19 L Empty Bottles Returned" in txt

    # URL generation
    url = generate_whatsapp_url("0771234567", txt)
    assert url.startswith("https://wa.me/94771234567?text=")
