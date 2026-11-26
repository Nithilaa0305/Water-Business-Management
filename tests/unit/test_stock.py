"""Stock and FIFO unit tests."""

import pytest
from app.database.models.product import Product, PackagingUnit
from app.services.inventory_service import InventoryService
from app.services.fifo_service import FIFOService
from app.config.constants import StockMovementType


def test_adding_purchase_increases_stock(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    initial_stock = InventoryService.get_available_stock(db_session, p.id)
    assert initial_stock == 0

    batch = InventoryService.add_batch(db_session, p.id, quantity=100, unit_cost_cents=3500)
    assert batch.remaining_qty == 100
    assert InventoryService.get_available_stock(db_session, p.id) == 100


def test_packaging_unit_conversion(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    pkg_case24 = db_session.query(PackagingUnit).filter_by(name="Case of 24").first()
    assert pkg_case24.factor == 24

    # 10 cases of 24 = 240 base bottles
    InventoryService.add_batch(db_session, p.id, quantity=240, unit_cost_cents=3500)
    summary = InventoryService.get_stock_by_packaging_unit(db_session, p.id, pkg_case24.id)
    assert summary["base_bottles"] == 240
    assert summary["packaging_qty"] == 10
    assert summary["loose_bottles"] == 0


def test_fifo_multi_batch_allocation(db_session):
    p = db_session.query(Product).filter_by(code="W1000").first()
    # Batch 1: 40 bottles @ Rs. 100 (10000 cents)
    b1 = InventoryService.add_batch(db_session, p.id, quantity=40, unit_cost_cents=10000)
    # Batch 2: 60 bottles @ Rs. 120 (12000 cents)
    b2 = InventoryService.add_batch(db_session, p.id, quantity=60, unit_cost_cents=12000)

    # Customer wants 60 bottles @ Rs. 150 (15000 cents)
    allocations = FIFOService.execute_fifo_allocation(
        session=db_session,
        product_id=p.id,
        required_base_qty=60,
        selling_price_cents=15000
    )

    # Expect: 40 from Batch 1, 20 from Batch 2
    assert len(allocations) == 2
    assert allocations[0]["batch_id"] == b1.id
    assert allocations[0]["quantity"] == 40
    assert allocations[0]["unit_cost_cents"] == 10000

    assert allocations[1]["batch_id"] == b2.id
    assert allocations[1]["quantity"] == 20
    assert allocations[1]["unit_cost_cents"] == 12000

    # Remaining in batches:
    assert b1.remaining_qty == 0
    assert b1.status == "EXHAUSTED"
    assert b2.remaining_qty == 40
    assert b2.status == "ACTIVE"


def test_insufficient_stock_prevents_sale(db_session):
    p = db_session.query(Product).filter_by(code="W1500").first()
    InventoryService.add_batch(db_session, p.id, quantity=15, unit_cost_cents=8000)

    with pytest.raises(ValueError, match="Cannot fulfill"):
        FIFOService.execute_fifo_allocation(db_session, p.id, required_base_qty=20, selling_price_cents=14000)


def test_damaged_stock_excluded_from_available(db_session):
    p = db_session.query(Product).filter_by(code="W5000").first()
    b = InventoryService.add_batch(db_session, p.id, quantity=50, unit_cost_cents=18000)
    assert InventoryService.get_available_stock(db_session, p.id) == 50

    # Record 5 damaged bottles
    InventoryService.adjust_stock(db_session, b.id, adjustment_type="DAMAGE", quantity=5, reason="Broken handle during unloading")
    assert InventoryService.get_available_stock(db_session, p.id) == 45
    assert b.remaining_qty == 45
