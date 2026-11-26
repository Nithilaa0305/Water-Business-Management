"""Customer Credit, Advance Payments, and Aging unit tests."""

import pytest
from app.database.models.product import Product
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.services.sales_service import SalesService
from app.services.payment_service import PaymentService
from app.services.credit_service import CreditService


def test_payment_allocation_to_oldest_invoice(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    InventoryService.add_batch(db_session, p.id, quantity=500, unit_cost_cents=3500)
    cust = CustomerService.create_customer(db_session, name="Sunil Grocery", phone="0773344556")

    # Invoice 1: Rs. 10,000 (1,000,000 cents)
    inv1 = SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 100, "unit_price_cents": 10000}],
        customer_id=cust.id,
        payment_method="CREDIT"
    )

    # Invoice 2: Rs. 5,000 (500,000 cents)
    inv2 = SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 50, "unit_price_cents": 10000}],
        customer_id=cust.id,
        payment_method="CREDIT"
    )

    # Customer pays Rs. 12,000
    PaymentService.record_customer_payment(
        session=db_session,
        customer_id=cust.id,
        amount_cents=1200000,
        payment_method="BANK_TRANSFER"
    )

    # Invoice 1 should be fully settled (paid Rs. 10,000)
    assert inv1.amount_paid_cents == 1000000

    # Invoice 2 should have Rs. 2,000 allocated (leaving Rs. 3,000 due)
    assert inv2.amount_paid_cents == 200000

    # Total remaining debt should be Rs. 3,000
    summary = CustomerService.get_customer_financial_summary(db_session, cust.id)
    assert summary["running_balance_cents"] == 300000


def test_customer_overpayment_creates_advance(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    InventoryService.add_batch(db_session, p.id, quantity=100, unit_cost_cents=3500)
    cust = CustomerService.create_customer(db_session, name="Lanka Cafe", phone="0774455667")

    # Invoice for Rs. 5,000
    inv = SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 50, "unit_price_cents": 10000}],
        customer_id=cust.id,
        payment_method="CREDIT"
    )
    assert inv.total_amount_cents == 500000

    # Customer pays Rs. 6,500 (overpayment of Rs. 1,500)
    pay = PaymentService.record_customer_payment(
        session=db_session,
        customer_id=cust.id,
        amount_cents=650000,
        payment_method="CASH"
    )

    assert pay.unallocated_amount_cents == 150000  # Rs. 1,500 advance

    summary = CustomerService.get_customer_financial_summary(db_session, cust.id)
    assert summary["running_balance_cents"] == -150000  # Business owes customer Rs. 1,500
    assert summary["is_advance"] is True
    assert summary["advance_cents"] == 150000
