"""19 L Returnable Bottle Management unit tests."""

import pytest
from app.database.models.product import Product
from app.config.constants import BottleState, BottleMovementType
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.services.bottle_service import BottleService
from app.services.refill_service import RefillService


def test_bottle_states_and_reconciliation(db_session):
    # Set initial states
    BottleService.move_bottles(db_session, from_state=None, to_state=BottleState.FULL_AVAILABLE, quantity=50, movement_type=BottleMovementType.OPENING_BALANCE)
    BottleService.move_bottles(db_session, from_state=None, to_state=BottleState.EMPTY_AVAILABLE, quantity=30, movement_type=BottleMovementType.OPENING_BALANCE)

    counts = BottleService.get_all_state_counts(db_session)
    assert counts[BottleState.FULL_AVAILABLE.value] == 50
    assert counts[BottleState.EMPTY_AVAILABLE.value] == 30

    recon = BottleService.reconcile_bottles(db_session)
    assert recon["is_reconciled"] is True
    assert recon["active_total"] == 80


def test_empty_return_without_purchase(db_session):
    cust = CustomerService.create_customer(db_session, name="Grand Hotel", phone="0112345678")
    # Customer currently holds 10 bottles
    BottleService.record_customer_bottle_movement(
        session=db_session,
        customer_id=cust.id,
        movement_type="OPENING",
        full_issued=10,
        empty_returned=0
    )
    BottleService.move_bottles(db_session, from_state=None, to_state=BottleState.HELD_BY_CUSTOMERS, quantity=10, movement_type=BottleMovementType.OPENING_BALANCE)

    # Customer returns 4 empty bottles without buying water
    BottleService.return_empty_without_purchase(db_session, cust.id, quantity=4)

    summary = CustomerService.get_customer_financial_summary(db_session, cust.id)
    assert summary["outstanding_bottles_19l"] == 6
    assert BottleService.get_state_quantity(db_session, BottleState.EMPTY_AVAILABLE) == 4
    assert BottleService.get_state_quantity(db_session, BottleState.HELD_BY_CUSTOMERS) == 6


def test_refill_batch_with_costing(db_session):
    # 20 empty bottles in warehouse
    BottleService.move_bottles(db_session, from_state=None, to_state=BottleState.EMPTY_AVAILABLE, quantity=20, movement_type=BottleMovementType.OPENING_BALANCE)

    # Refill: 18 successfully refilled, 2 damaged
    # Costs: Treatment = Rs. 900, Caps = Rs. 360, Labour = Rs. 540 -> Total = Rs. 1,800
    # Unit cost = Rs. 1,800 / 18 = Rs. 100 per bottle
    refill = RefillService.execute_refill_batch(
        session=db_session,
        empty_bottles_selected=20,
        bottles_refilled=18,
        bottles_rejected_damaged=2,
        water_treatment_cost_cents=90000,
        cap_seal_cost_cents=36000,
        labour_cost_cents=54000
    )

    assert refill.bottles_refilled == 18
    assert refill.bottles_rejected_damaged == 2
    assert refill.unit_cost_cents == 10000

    assert BottleService.get_state_quantity(db_session, BottleState.EMPTY_AVAILABLE) == 0
    assert BottleService.get_state_quantity(db_session, BottleState.FULL_AVAILABLE) == 18
    assert BottleService.get_state_quantity(db_session, BottleState.DAMAGED) == 2

    # Product stock for W19000
    p = db_session.query(Product).filter_by(code="W19000").first()
    assert InventoryService.get_available_stock(db_session, p.id) == 18
