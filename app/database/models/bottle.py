"""Special 19 L Returnable Bottle Management models."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.base import TimestampMixin
from app.utilities.dates import now_colombo


class BottleInventory(Base, TimestampMixin):
    """Current snapshot quantities for each of the 7 bottle states."""
    __tablename__ = "bottle_inventory"

    state = Column(String(50), unique=True, nullable=False)  # FULL_AVAILABLE, EMPTY_AVAILABLE, etc.
    quantity = Column(Integer, default=0, nullable=False)
    notes = Column(String(255), nullable=True)


class BottleMovement(Base, TimestampMixin):
    """Auditable physical container movement ledger between bottle states."""
    __tablename__ = "bottle_movements"

    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    movement_type = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    from_state = Column(String(50), nullable=True)
    to_state = Column(String(50), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=True)
    refill_batch_id = Column(Integer, nullable=True)
    reason = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class CustomerBottleLedger(Base, TimestampMixin):
    """Independent bottle obligation ledger per customer."""
    __tablename__ = "customer_bottle_ledger"

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    movement_type = Column(String(50), nullable=False)  # DELIVERY, RETURN, EXCHANGE, LOST, PERMANENT_SALE, OPENING
    full_issued = Column(Integer, default=0, nullable=False)
    empty_returned = Column(Integer, default=0, nullable=False)
    running_bottle_balance = Column(Integer, nullable=False)  # Running count of bottles customer holds
    invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="bottle_ledger_entries")


class RefillBatch(Base, TimestampMixin):
    """19 L bottle cleaning and refilling batch."""
    __tablename__ = "refill_batches"

    refill_batch_number = Column(String(50), unique=True, nullable=False, index=True)
    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    empty_bottles_selected = Column(Integer, nullable=False)
    bottles_cleaned = Column(Integer, default=0, nullable=False)
    bottles_refilled = Column(Integer, nullable=False)       # Successfully refilled
    bottles_rejected_damaged = Column(Integer, default=0, nullable=False)
    
    # Direct production & refill costs in cents
    water_treatment_cost_cents = Column(Integer, default=0, nullable=False)
    cleaning_cost_cents = Column(Integer, default=0, nullable=False)
    cap_seal_cost_cents = Column(Integer, default=0, nullable=False)
    labour_cost_cents = Column(Integer, default=0, nullable=False)
    other_cost_cents = Column(Integer, default=0, nullable=False)
    total_cost_cents = Column(Integer, default=0, nullable=False)
    unit_cost_cents = Column(Integer, default=0, nullable=False)  # total_cost_cents / bottles_refilled
    
    inventory_batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)


class BottleDeposit(Base, TimestampMixin):
    """Refundable bottle deposit liability tracking."""
    __tablename__ = "bottle_deposits"

    deposit_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=True)
    bottle_count = Column(Integer, nullable=False)
    deposit_per_bottle_cents = Column(Integer, nullable=False)
    total_deposit_cents = Column(Integer, nullable=False)
    refunded_deposit_cents = Column(Integer, default=0, nullable=False)
    balance_deposit_cents = Column(Integer, nullable=False)  # total - refunded
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, REFUNDED, FORFEITED
    date = Column(DateTime, default=now_colombo, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    transactions = relationship("BottleDepositTransaction", back_populates="deposit", cascade="all, delete-orphan")


class BottleDepositTransaction(Base, TimestampMixin):
    __tablename__ = "bottle_deposit_transactions"

    deposit_id = Column(Integer, ForeignKey("bottle_deposits.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    transaction_type = Column(String(30), nullable=False)  # COLLECTED, REFUNDED, FORFEITED
    amount_cents = Column(Integer, nullable=False)
    bottle_count = Column(Integer, nullable=False)
    date = Column(DateTime, default=now_colombo, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    deposit = relationship("BottleDeposit", back_populates="transactions")
