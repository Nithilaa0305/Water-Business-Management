"""Financial P&L, Cashbook, and Revenue unit tests."""

import pytest
from app.database.models.product import Product
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.services.sales_service import SalesService
from app.services.payment_service import PaymentService
from app.services.expense_service import ExpenseService
from app.services.accounting_service import AccountingService


def test_financial_profit_and_cogs(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    # Batch: 100 bottles @ Rs. 35 cost (3500 cents)
    InventoryService.add_batch(db_session, p.id, quantity=100, unit_cost_cents=3500)

    # Sale: 50 bottles @ Rs. 60 (6000 cents)
    # Revenue = 50 * 60 = Rs. 3,000 (300,000 cents)
    # COGS = 50 * 35 = Rs. 1,750 (175,000 cents)
    # Gross profit = Rs. 1,250 (125,000 cents)
    SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 50, "unit_price_cents": 6000}],
        payment_method="CASH",
        amount_paid_cents=300000
    )

    # Operating expense: Rent = Rs. 250 (25,000 cents)
    ExpenseService.record_expense(
        session=db_session,
        category_id=1,
        description="Office maintenance",
        amount_cents=25000,
        payment_method="CASH"
    )

    fin = AccountingService.get_financial_summary(db_session)
    assert fin["net_sales_revenue_cents"] == 300000
    assert fin["cogs_cents"] == 175000
    assert fin["gross_profit_cents"] == 125000
    assert fin["operating_expenses_cents"] == 25000
    assert fin["net_operating_profit_cents"] == 100000  # Rs. 1,000.00 net operating profit!


def test_credit_collections_do_not_duplicate_revenue(db_session):
    p = db_session.query(Product).filter_by(code="W1000").first()
    InventoryService.add_batch(db_session, p.id, quantity=100, unit_cost_cents=5500)
    cust = CustomerService.create_customer(db_session, name="Silva Bakers", phone="0778899001")

    # Credit sale of Rs. 2,000 (200,000 cents)
    SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 20, "unit_price_cents": 10000}],
        customer_id=cust.id,
        payment_method="CREDIT",
        amount_paid_cents=0
    )

    # Customer pays credit debt of Rs. 2,000
    PaymentService.record_customer_payment(
        session=db_session,
        customer_id=cust.id,
        amount_cents=200000,
        payment_method="CASH"
    )

    fin = AccountingService.get_financial_summary(db_session)
    # Revenue must remain Rs. 2,000, NOT Rs. 4,000!
    assert fin["net_sales_revenue_cents"] == 200000
    assert fin["total_payments_received_cents"] == 200000
