"""Unit tests for payment allocation options: Current Invoice, Oldest Invoices, and Advances."""

import pytest
from app.services.sales_service import SalesService
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.database.models.sales import SalesInvoice
from app.database.models.payment import CustomerLedgerEntry, CustomerPayment
from app.database.models.product import Product


def test_payment_allocation_modes(db_session):
    # Setup stock
    p = db_session.query(Product).filter_by(code="W0500").first()
    InventoryService.add_batch(
        session=db_session,
        product_id=p.id,
        quantity=500,
        unit_cost_cents=4000,
        suggested_selling_price_cents=7000
    )

    # Setup customer
    cust = CustomerService.create_customer(
        session=db_session,
        name="Lanka Supermart",
        phone="0771234567",
        credit_limit_cents=20000000
    )

    # 1. First Invoice on pure CREDIT (net Rs. 7,000)
    inv1 = SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 100, "unit_price_cents": 7000}],
        customer_id=cust.id,
        payment_method="CREDIT",
        amount_paid_cents=0
    )
    assert inv1.total_amount_cents == 700000
    assert inv1.amount_paid_cents == 0
    # Customer debt = 7,000.00
    summary1 = CustomerService.get_customer_financial_summary(db_session, cust.id)
    assert summary1["current_balance_cents"] == 700000

    # 2. Second Invoice: Bill total = Rs. 3,500. Customer pays Rs. 3,500 cash
    # Mode: CURRENT_INVOICE (the default during billing)
    inv2 = SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 50, "unit_price_cents": 7000}],
        customer_id=cust.id,
        payment_method="CASH",
        amount_paid_cents=350000,
        payment_allocation_mode="CURRENT_INVOICE"
    )
    # The current bill must be marked fully PAID
    assert inv2.amount_paid_cents == 350000
    # The past invoice (inv1) must still be unpaid (0 paid)
    db_session.refresh(inv1)
    assert inv1.amount_paid_cents == 0

    # Verify explicit breakdown
    bd = inv2.payment_breakdown
    assert bd["previous_balance_cents"] == 700000
    assert bd["current_invoice_total_cents"] == 350000
    assert bd["payment_received_cents"] == 350000
    assert bd["allocated_to_current_cents"] == 350000
    assert bd["allocated_to_previous_cents"] == 0
    assert bd["remaining_customer_debt_cents"] == 700000

    # 3. Third Invoice: Bill total = Rs. 2,100. Customer pays Rs. 5,000 cash
    # Mode: OLDEST_INVOICES (wants payment to clear oldest debt first)
    inv3 = SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 30, "unit_price_cents": 7000}],
        customer_id=cust.id,
        payment_method="CASH",
        amount_paid_cents=500000,
        payment_allocation_mode="OLDEST_INVOICES"
    )
    # inv1 had 7,000 due -> gets Rs. 5,000 allocated!
    db_session.refresh(inv1)
    assert inv1.amount_paid_cents == 500000

    # 4. Fourth Invoice with Mode: ADVANCE
    inv4 = SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 10, "unit_price_cents": 7000}],
        customer_id=cust.id,
        payment_method="CASH",
        amount_paid_cents=100000,
        payment_allocation_mode="ADVANCE"
    )
    assert inv4.payment_breakdown["available_advance_cents"] == 100000
