"""Automated Acceptance Test: Section 38 Mandatory End-to-End Acceptance Scenario."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.connection import Base
from app.database.migrations.migration_manager import seed_default_data
from app.database.models.product import Product
from app.database.models.customer import Customer
from app.config.constants import BottleState, BottleMovementType, StockMovementType
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.services.sales_service import SalesService
from app.services.payment_service import PaymentService
from app.services.refill_service import RefillService
from app.services.bottle_service import BottleService
from app.services.accounting_service import AccountingService


@pytest.fixture
def test_db():
    """In-memory SQLite database for deterministic acceptance testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    seed_default_data(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    yield session
    session.close()


def test_mandatory_acceptance_scenario(test_db):
    """
    Execute Section 38 Mandatory End-to-End Scenario:
    1. Set up initial inventory:
       500 ml: 1,000
       1 L: 500
       1.5 L: 300
       5 L: 100
       19 L full: 100
       19 L empty: 50
    2. Create customer ABC Stores.
    3. Sale: 100 x 500ml @ Rs.60, 20 x 1L @ Rs.100, 10 x 19L @ Rs.300. Revenue = Rs. 11,000.
    4. Customer pays Rs. 5,000. Outstanding credit = Rs. 6,000.
    5. Returns 8 empty 19L bottles.
       Stock check:
       500ml: 900
       1L: 480
       1.5L: 300
       5L: 100
       19L full: 90
       19L empty: 58
       Customer bottle obligation: 2
    6. Customer pays Rs. 4,000.
       Outstanding credit: Rs. 2,000.
       Total money received: Rs. 9,000.
       Sales revenue remains: Rs. 11,000.
    7. Refill 30 empty bottles successfully.
       19L full: 120
       19L empty: 28
       Customer-held: 2
       Refill must NOT increase sales revenue.
    """
    session = test_db

    # 1. Look up products
    p_500 = session.query(Product).filter_by(code="W0500").first()
    p_1000 = session.query(Product).filter_by(code="W1000").first()
    p_1500 = session.query(Product).filter_by(code="W1500").first()
    p_5000 = session.query(Product).filter_by(code="W5000").first()
    p_19000 = session.query(Product).filter_by(code="W19000").first()

    # Add initial inventory batches
    InventoryService.add_batch(session, p_500.id, quantity=1000, unit_cost_cents=3500, movement_type=StockMovementType.OPENING)
    InventoryService.add_batch(session, p_1000.id, quantity=500, unit_cost_cents=5500, movement_type=StockMovementType.OPENING)
    InventoryService.add_batch(session, p_1500.id, quantity=300, unit_cost_cents=8000, movement_type=StockMovementType.OPENING)
    InventoryService.add_batch(session, p_5000.id, quantity=100, unit_cost_cents=18000, movement_type=StockMovementType.OPENING)
    InventoryService.add_batch(session, p_19000.id, quantity=100, unit_cost_cents=12000, movement_type=StockMovementType.OPENING)

    # Initialize 19L physical bottle states: 100 FULL, 50 EMPTY
    BottleService.move_bottles(session, from_state=None, to_state=BottleState.FULL_AVAILABLE, quantity=100, movement_type=BottleMovementType.OPENING_BALANCE)
    BottleService.move_bottles(session, from_state=None, to_state=BottleState.EMPTY_AVAILABLE, quantity=50, movement_type=BottleMovementType.OPENING_BALANCE)

    # Verify initial stock
    assert InventoryService.get_available_stock(session, p_500.id) == 1000
    assert InventoryService.get_available_stock(session, p_1000.id) == 500
    assert InventoryService.get_available_stock(session, p_1500.id) == 300
    assert InventoryService.get_available_stock(session, p_5000.id) == 100
    assert InventoryService.get_available_stock(session, p_19000.id) == 100
    assert BottleService.get_state_quantity(session, BottleState.FULL_AVAILABLE) == 100
    assert BottleService.get_state_quantity(session, BottleState.EMPTY_AVAILABLE) == 50

    # 2. Create customer ABC Stores
    customer = CustomerService.create_customer(session, name="ABC Stores", phone="0771122334", business_name="ABC Stores Wholesale")
    assert customer.id is not None

    # 3. Record Sale:
    # 100 x 500ml @ Rs. 60 (6,000 cents)
    # 20 x 1L @ Rs. 100 (10,000 cents)
    # 10 x 19L @ Rs. 300 (30,000 cents)
    # Total sales revenue = Rs. 11,000 (1,100,000 cents)
    # Customer pays Rs. 5,000 (500,000 cents)
    # Customer returns 8 empty 19L bottles
    items = [
        {"product_id": p_500.id, "quantity": 100, "unit_price_cents": 6000},
        {"product_id": p_1000.id, "quantity": 20, "unit_price_cents": 10000},
        {"product_id": p_19000.id, "quantity": 10, "unit_price_cents": 30000},
    ]

    invoice = SalesService.create_invoice(
        session=session,
        items_data=items,
        customer_id=customer.id,
        payment_method="MIXED",
        amount_paid_cents=500000,       # Rs. 5,000 paid
        empty_19l_returned=8,            # 8 empty bottles returned
        user_id=1
    )

    assert invoice.total_amount_cents == 1100000  # Rs. 11,000.00
    assert invoice.amount_paid_cents == 500000    # Rs. 5,000.00

    # Customer summary check:
    summary = CustomerService.get_customer_financial_summary(session, customer.id)
    assert summary["running_balance_cents"] == 600000  # Customer owes Rs. 6,000.00
    assert summary["outstanding_bottles_19l"] == 2     # Expected customer bottle obligation: 2 bottles

    # Expected stock quantities check:
    assert InventoryService.get_available_stock(session, p_500.id) == 900
    assert InventoryService.get_available_stock(session, p_1000.id) == 480
    assert InventoryService.get_available_stock(session, p_1500.id) == 300
    assert InventoryService.get_available_stock(session, p_5000.id) == 100
    assert InventoryService.get_available_stock(session, p_19000.id) == 90
    assert BottleService.get_state_quantity(session, BottleState.FULL_AVAILABLE) == 90
    assert BottleService.get_state_quantity(session, BottleState.EMPTY_AVAILABLE) == 58  # 50 + 8

    # 4. Customer later pays Rs. 4,000
    PaymentService.record_customer_payment(
        session=session,
        customer_id=customer.id,
        amount_cents=400000,
        payment_method="CASH",
        notes="Second payment installment"
    )

    # Check updated credit balance:
    summary2 = CustomerService.get_customer_financial_summary(session, customer.id)
    assert summary2["running_balance_cents"] == 200000  # Remaining credit: Rs. 2,000.00

    # Revenue and cash check:
    fin = AccountingService.get_financial_summary(session)
    assert fin["net_sales_revenue_cents"] == 1100000    # Sales revenue remains Rs. 11,000.00!
    assert fin["total_payments_received_cents"] == 900000  # Total cash received: Rs. 9,000.00!

    # 5. Refill 30 empty bottles successfully
    refill = RefillService.execute_refill_batch(
        session=session,
        empty_bottles_selected=30,
        bottles_refilled=30,
        bottles_rejected_damaged=0,
        water_treatment_cost_cents=150000,  # Rs. 1,500 total treatment
        cap_seal_cost_cents=60000,          # Rs. 600 caps
        labour_cost_cents=90000,            # Rs. 900 labour
        notes="Acceptance test refill batch"
    )

    assert refill.bottles_refilled == 30
    assert refill.total_cost_cents == 300000  # Rs. 3,000
    assert refill.unit_cost_cents == 10000    # Rs. 100 per bottle

    # Check final inventory:
    # 19 L full bottles: 120 (90 + 30)
    # 19 L empty bottles: 28 (58 - 30)
    # Customer-held returnable bottles: 2
    assert BottleService.get_state_quantity(session, BottleState.FULL_AVAILABLE) == 120
    assert InventoryService.get_available_stock(session, p_19000.id) == 120
    assert BottleService.get_state_quantity(session, BottleState.EMPTY_AVAILABLE) == 28
    assert BottleService.get_state_quantity(session, BottleState.HELD_BY_CUSTOMERS) == 2

    # Verify that refill did NOT increase sales revenue!
    fin_after_refill = AccountingService.get_financial_summary(session)
    assert fin_after_refill["net_sales_revenue_cents"] == 1100000  # Still Rs. 11,000!

    # Verify bottle reconciliation
    reconciliation = BottleService.reconcile_bottles(session)
    assert reconciliation["is_reconciled"] is True
    assert reconciliation["discrepancy"] == 0

    print("\n>>> MANDATORY ACCEPTANCE SCENARIO PASSED 100% WITH ALL FINANCIAL AND INVENTORY RECONCILIATIONS! <<<")
