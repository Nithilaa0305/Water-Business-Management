"""Unit tests for Delivery Sheets (no double-decrement) and Stocktake Physical Audit."""

import pytest
from app.services.delivery_service import DeliveryService
from app.services.stocktake_service import StocktakeService
from app.services.sales_service import SalesService
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.services.bottle_service import BottleService
from app.config.constants import BottleState
from app.database.models.product import Product


def test_delivery_sheet_prevents_double_decrement(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    b = InventoryService.add_batch(
        session=db_session,
        product_id=p.id,
        quantity=300,
        unit_cost_cents=4000,
        suggested_selling_price_cents=7000
    )

    cust = CustomerService.create_customer(session=db_session, name="Galle Hotel", phone="0779988776")

    # 1. Invoice is created -> Inventory decrements from 300 to 200
    inv = SalesService.create_invoice(
        session=db_session,
        items_data=[{"product_id": p.id, "quantity": 100, "unit_price_cents": 7000}],
        customer_id=cust.id,
        payment_method="CREDIT"
    )
    stock_after_inv = InventoryService.get_available_stock(db_session, p.id)
    assert stock_after_inv == 200

    # 2. Add to delivery sheet linked to this invoice
    sheet = DeliveryService.create_delivery_sheet(
        session=db_session,
        driver_name="Sunil Perera",
        vehicle_number="WP-CAB-1234"
    )
    item = DeliveryService.add_delivery_item(
        session=db_session,
        sheet_id=sheet.id,
        customer_id=cust.id,
        invoice_id=inv.id,
        stop_number=1,
        full_19l_delivered=10
    )

    # 3. Mark delivery completed -> Stock must STAY 200 (strictly prevents double-decrement)
    DeliveryService.update_item_status(db_session, item.id, status="DELIVERED")
    stock_after_delivery = InventoryService.get_available_stock(db_session, p.id)
    assert stock_after_delivery == 200

    # Check sheet report output
    sheet_text = DeliveryService.generate_sheet_text(db_session, sheet.id)
    assert "DELIVERY RUN SHEET" in sheet_text
    assert "Sunil Perera" in sheet_text


def test_stocktake_audit_and_adjustment(db_session):
    p = db_session.query(Product).filter_by(code="W1000").first()
    # System has 100 bottles
    InventoryService.add_batch(
        session=db_session,
        product_id=p.id,
        quantity=100,
        unit_cost_cents=5000,
        suggested_selling_price_cents=9000
    )
    assert InventoryService.get_available_stock(db_session, p.id) == 100

    # Stocktake counts 95 bottles (shortage of 5)
    audit = StocktakeService.create_stocktake_audit(
        session=db_session,
        counts_data=[{"product_id": p.id, "counted_qty": 95, "reason": "Physical count audit"}],
        notes="Monthly inventory stocktake",
        auto_apply_adjustments=True
    )

    assert audit.status == "COMPLETED"
    assert audit.items[0].difference_qty == -5
    assert audit.items[0].is_adjusted is True

    # System stock must now reflect counted stock (95)
    assert InventoryService.get_available_stock(db_session, p.id) == 95

    # Direct 19L container physical adjustment
    res = StocktakeService.adjust_19l_container_state(
        session=db_session,
        state=BottleState.FULL_AVAILABLE,
        counted_qty=50,
        reason="Physical 19L warehouse count"
    )
    assert res["new_qty"] == 50
    assert BottleService.get_state_quantity(db_session, BottleState.FULL_AVAILABLE) == 50
