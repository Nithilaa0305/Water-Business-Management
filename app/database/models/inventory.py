"""Inventory batches, movements, and adjustment models."""

from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.base import TimestampMixin
from app.utilities.dates import now_colombo


class InventoryBatch(Base, TimestampMixin):
    __tablename__ = "inventory_batches"

    batch_number = Column(String(50), unique=True, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    production_batch_id = Column(Integer, nullable=True)
    received_date = Column(Date, nullable=False, index=True)
    mfg_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    original_qty = Column(Integer, nullable=False)      # In base units (bottles)
    remaining_qty = Column(Integer, nullable=False)     # In base units (bottles)
    unit_cost_cents = Column(Integer, nullable=False)   # Buying or production cost in cents
    suggested_selling_price_cents = Column(Integer, nullable=True)
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, EXHAUSTED, EXPIRED, ADJUSTED
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    product = relationship("Product", back_populates="batches")
    movements = relationship("StockMovement", back_populates="batch")
    allocations = relationship("SaleBatchAllocation", back_populates="batch")


class StockMovement(Base, TimestampMixin):
    __tablename__ = "stock_movements"

    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=True, index=True)
    movement_type = Column(String(30), nullable=False)  # PURCHASE, SALE, PRODUCTION, REFILL_IN, etc.
    quantity = Column(Integer, nullable=False)          # Signed or absolute depending on type
    unit_cost_cents = Column(Integer, default=0, nullable=False)
    reference_type = Column(String(50), nullable=True)  # INVOICE, PURCHASE, REFILL, ADJUSTMENT
    reference_id = Column(Integer, nullable=True)
    reason = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    batch = relationship("InventoryBatch", back_populates="movements")


class StockAdjustment(Base, TimestampMixin):
    __tablename__ = "stock_adjustments"

    date = Column(DateTime, default=now_colombo, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=True)
    adjustment_type = Column(String(30), nullable=False)  # IN, OUT, DAMAGE, EXPIRED, LOST
    quantity = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)


class StocktakeAudit(Base, TimestampMixin):
    """Physical inventory count and audit session."""
    __tablename__ = "stocktake_audits"

    audit_number = Column(String(50), unique=True, nullable=False, index=True)
    audit_date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    status = Column(String(20), default="COMPLETED", nullable=False)  # DRAFT, COMPLETED, CANCELLED
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    items = relationship("StocktakeItem", back_populates="audit", cascade="all, delete-orphan")


class StocktakeItem(Base, TimestampMixin):
    """Line item comparing recorded vs counted quantity."""
    __tablename__ = "stocktake_items"

    audit_id = Column(Integer, ForeignKey("stocktake_audits.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=True)
    recorded_qty = Column(Integer, nullable=False)
    counted_qty = Column(Integer, nullable=False)
    difference_qty = Column(Integer, nullable=False)  # Counted - Recorded
    unit_cost_cents = Column(Integer, default=0, nullable=False)
    variance_value_cents = Column(Integer, default=0, nullable=False)
    reason = Column(String(255), nullable=True)
    is_adjusted = Column(Boolean, default=False, nullable=False)

    audit = relationship("StocktakeAudit", back_populates="items")
    product = relationship("Product")
    batch = relationship("InventoryBatch")

