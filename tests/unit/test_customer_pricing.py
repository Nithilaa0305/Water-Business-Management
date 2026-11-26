"""Unit tests for Customer Agreed Pricing, billing with pre-set prices, and on-the-fly modifications."""

import pytest
from app.database.models.product import Product
from app.database.models.customer import Customer, CustomerPrice
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.services.sales_service import SalesService
from app.utilities.currency import to_cents


def test_customer_pre_set_agreed_prices(db_session):
    p500 = db_session.query(Product).filter_by(code="W0500").first()
    p19l = db_session.query(Product).filter_by(code="W19000").first()

    cust = CustomerService.create_customer(db_session, name="Grand Hotel", phone="0771122334")

    # Default prices
    assert p500.default_selling_price_cents == 6000   # Rs. 60.00
    assert p19l.default_selling_price_cents == 30000  # Rs. 300.00

    # Before setting agreed price: suggested price is standard price
    assert CustomerService.get_suggested_price(db_session, cust.id, p500.id) == 6000
    assert CustomerService.get_suggested_price(db_session, cust.id, p19l.id) == 30000

    # 1. Pre-set agreed price: Hotel gets 500ml @ Rs. 50 (5000 cents) and 19L @ Rs. 310 (31000 cents)
    CustomerService.set_customer_agreed_price(
        session=db_session,
        customer_id=cust.id,
        product_id=p500.id,
        price_cents=5000,
        notes="Wholesale agreement"
    )
    CustomerService.set_customer_agreed_price(
        session=db_session,
        customer_id=cust.id,
        product_id=p19l.id,
        price_cents=31000,
        notes="Corporate contract"
    )

    # 2. Billing uses the pre-set agreed prices automatically!
    assert CustomerService.get_suggested_price(db_session, cust.id, p500.id) == 5000
    assert CustomerService.get_suggested_price(db_session, cust.id, p19l.id) == 31000

    # Other customer still gets standard price
    other_cust = CustomerService.create_customer(db_session, name="Small Cafe", phone="0779988112")
    assert CustomerService.get_suggested_price(db_session, other_cust.id, p500.id) == 6000
    assert CustomerService.get_suggested_price(db_session, other_cust.id, p19l.id) == 30000


def test_billing_with_pre_set_price_and_on_the_fly_change(db_session):
    p500 = db_session.query(Product).filter_by(code="W0500").first()
    InventoryService.add_batch(db_session, p500.id, quantity=200, unit_cost_cents=3500)

    cust = CustomerService.create_customer(db_session, name="Royal Resort", phone="0712345678")

    # Feed custom price in advance: Rs. 55.00 (5500 cents)
    CustomerService.set_customer_agreed_price(
        session=db_session,
        customer_id=cust.id,
        product_id=p500.id,
        price_cents=5500
    )

    # Cashier bills with the pre-set price
    sugg_price = CustomerService.get_suggested_price(db_session, cust.id, p500.id)
    assert sugg_price == 5500

    items_1 = [{"product_id": p500.id, "quantity": 20, "unit_price_cents": sugg_price}]
    inv_1 = SalesService.create_invoice(
        session=db_session,
        items_data=items_1,
        customer_id=cust.id,
        payment_method="CASH",
        amount_paid_cents=20 * 5500
    )
    assert inv_1.total_amount_cents == 110000  # Rs. 1,100.00

    # Now cashier changes price on the fly for next bill: special one-time deal @ Rs. 52.00 (5200 cents)
    items_2 = [{"product_id": p500.id, "quantity": 10, "unit_price_cents": 5200}]
    inv_2 = SalesService.create_invoice(
        session=db_session,
        items_data=items_2,
        customer_id=cust.id,
        payment_method="CASH",
        amount_paid_cents=10 * 5200
    )
    assert inv_2.total_amount_cents == 52000  # Rs. 520.00

    # If the user chooses to update the pre-set price with the new billed price:
    CustomerService.set_customer_agreed_price(
        session=db_session,
        customer_id=cust.id,
        product_id=p500.id,
        price_cents=5200,
        notes="Updated from invoice"
    )
    # Next time, the new price is suggested automatically
    assert CustomerService.get_suggested_price(db_session, cust.id, p500.id) == 5200


def test_customer_price_listing_and_reset_to_standard(db_session):
    p500 = db_session.query(Product).filter_by(code="W0500").first()
    p1000 = db_session.query(Product).filter_by(code="W1000").first()

    cust = CustomerService.create_customer(db_session, name="Lakeside Inn", phone="0781234567")

    # Set custom price for W0500 only
    CustomerService.set_customer_agreed_price(
        session=db_session,
        customer_id=cust.id,
        product_id=p500.id,
        price_cents=4800,
        notes="Promotion"
    )

    # Get all prices list
    prices_list = CustomerService.get_all_customer_prices(db_session, cust.id)
    assert len(prices_list) >= 5

    p500_entry = next(item for item in prices_list if item["product_id"] == p500.id)
    assert p500_entry["has_custom_price"] is True
    assert p500_entry["agreed_price_cents"] == 4800
    assert p500_entry["notes"] == "Promotion"

    p1000_entry = next(item for item in prices_list if item["product_id"] == p1000.id)
    assert p1000_entry["has_custom_price"] is False
    assert p1000_entry["agreed_price_cents"] is None

    # Reset/Delete agreed price
    deleted = CustomerService.delete_customer_agreed_price(db_session, cust.id, p500.id)
    assert deleted is True

    # Reverts back to standard price
    assert CustomerService.get_suggested_price(db_session, cust.id, p500.id) == p500.default_selling_price_cents
