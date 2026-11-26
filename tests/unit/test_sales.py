"""Sales Billing and Invoicing unit tests."""

import pytest
from app.database.models.product import Product
from app.database.models.customer import Customer
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.services.sales_service import SalesService
from app.config.constants import InvoiceStatus


def test_cash_sale(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    InventoryService.add_batch(db_session, p.id, quantity=100, unit_cost_cents=3500)

    # Walk-in cash sale of 10 bottles @ Rs. 60
    items = [{"product_id": p.id, "quantity": 10, "unit_price_cents": 6000}]
    inv = SalesService.create_invoice(
        session=db_session,
        items_data=items,
        customer_id=None,
        payment_method="CASH",
        amount_paid_cents=60000
    )

    assert inv.total_amount_cents == 60000  # Rs. 600.00
    assert inv.amount_paid_cents == 60000
    assert inv.status == InvoiceStatus.POSTED.value
    assert InventoryService.get_available_stock(db_session, p.id) == 90


def test_credit_sale_and_credit_limit(db_session):
    p = db_session.query(Product).filter_by(code="W1000").first()
    InventoryService.add_batch(db_session, p.id, quantity=100, unit_cost_cents=5500)

    cust = CustomerService.create_customer(db_session, name="Perera Stores", phone="0779988776")

    # Full credit sale of 20 bottles @ Rs. 100 = Rs. 2,000 (200,000 cents)
    items = [{"product_id": p.id, "quantity": 20, "unit_price_cents": 10000}]
    inv = SalesService.create_invoice(
        session=db_session,
        items_data=items,
        customer_id=cust.id,
        payment_method="CREDIT",
        amount_paid_cents=0
    )

    assert inv.total_amount_cents == 200000
    assert inv.amount_paid_cents == 0

    summary = CustomerService.get_customer_financial_summary(db_session, cust.id)
    assert summary["running_balance_cents"] == 200000
    assert summary["is_debt"] is True


def test_invoice_cancellation_reverses_stock(db_session):
    p = db_session.query(Product).filter_by(code="W1500").first()
    b = InventoryService.add_batch(db_session, p.id, quantity=50, unit_cost_cents=8000)
    assert InventoryService.get_available_stock(db_session, p.id) == 50

    items = [{"product_id": p.id, "quantity": 10, "unit_price_cents": 14000}]
    inv = SalesService.create_invoice(
        session=db_session,
        items_data=items,
        customer_id=None,
        payment_method="CASH",
        amount_paid_cents=140000
    )
    assert InventoryService.get_available_stock(db_session, p.id) == 40

    # Cancel invoice
    SalesService.cancel_invoice(db_session, inv.id, reason="Customer cancelled order before dispatch")
    assert inv.status == InvoiceStatus.CANCELLED.value
    assert InventoryService.get_available_stock(db_session, p.id) == 50
    assert b.remaining_qty == 50
