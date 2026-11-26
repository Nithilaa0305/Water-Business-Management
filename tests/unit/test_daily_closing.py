"""Unit tests for Daily Cash Closing, Drawer Reconciliation, and Denominations."""

import pytest
from datetime import date
from app.services.daily_closing_service import DailyClosingService, SL_DENOMINATIONS
from app.services.sales_service import SalesService
from app.services.inventory_service import InventoryService
from app.database.models.product import Product
from app.database.models.operations import DailyCashClosing


def test_sl_denominations_counting():
    counts = {
        "5000": 2,  # 10,000 Rs
        "1000": 5,  # 5,000 Rs
        "500": 4,   # 2,000 Rs
        "100": 10,  # 1,000 Rs
        "50": 6,    # 300 Rs
        "20": 5,    # 100 Rs
        "10": 10,   # 100 Rs
    }
    total_cents = DailyClosingService.calculate_counted_from_denominations(counts)
    # Expected: 10000 + 5000 + 2000 + 1000 + 300 + 100 + 100 = 18,500 Rs = 1,850,000 cents
    assert total_cents == 1850000


def test_daily_closing_reconciliation(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    InventoryService.add_batch(
        session=db_session,
        product_id=p.id,
        quantity=200,
        unit_cost_cents=4000,
        suggested_selling_price_cents=7000
    )

    # Cash sale of Rs. 3,500
    SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 50, "unit_price_cents": 7000}],
        payment_method="CASH",
        amount_paid_cents=350000
    )

    c_date = date.today()
    summary = DailyClosingService.calculate_daily_summary(
        session=db_session,
        closing_date=c_date,
        opening_cash_cents=1000000  # Rs. 10,000 float
    )

    assert summary["opening_cash_cents"] == 1000000
    assert summary["cash_sales_cents"] == 350000
    # Expected cash: 10,000 + 3,500 = 13,500 Rs = 1,350,000 cents
    assert summary["expected_cash_cents"] == 1350000

    # Test BALANCED closing
    closing_bal = DailyClosingService.record_daily_closing(
        session=db_session,
        closing_date=c_date,
        opening_cash_cents=1000000,
        actual_cash_cents=1350000,
        denominations_counts={"1000": 13, "500": 1}
    )
    assert closing_bal.status == "BALANCED"
    assert closing_bal.difference_cents == 0

    # Test report text generation
    report = DailyClosingService.generate_closing_report_text(closing_bal)
    assert "WATER BUSINESS MANAGER" in report
    assert "BALANCED" in report
    assert "EXPECTED DRAWER CASH" in report
