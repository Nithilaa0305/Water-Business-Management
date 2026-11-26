"""Sales Invoices, Items, FIFO Batch Allocations, Returns and Credit Notes."""

from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.base import TimestampMixin
from app.utilities.dates import now_colombo


class SalesInvoice(Base, TimestampMixin):
    __tablename__ = "sales_invoices"

    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    invoice_date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)  # Null for walk-in cash
    status = Column(String(20), default="POSTED", nullable=False)  # DRAFT, POSTED, CANCELLED
    
    subtotal_cents = Column(Integer, default=0, nullable=False)
    discount_cents = Column(Integer, default=0, nullable=False)
    delivery_charge_cents = Column(Integer, default=0, nullable=False)
    tax_cents = Column(Integer, default=0, nullable=False)
    total_amount_cents = Column(Integer, default=0, nullable=False)  # subtotal - discount + delivery + tax
    amount_paid_cents = Column(Integer, default=0, nullable=False)
    
    payment_method = Column(String(30), default="CASH", nullable=False)
    due_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    prepared_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # 19L bottle stats on this invoice
    bottles_delivered_19l = Column(Integer, default=0, nullable=False)
    bottles_returned_19l = Column(Integer, default=0, nullable=False)
    bottle_deposit_cents = Column(Integer, default=0, nullable=False)
    
    cancellation_reason = Column(String(255), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="invoices")
    items = relationship("SalesInvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payment_allocations = relationship("CustomerPaymentAllocation", back_populates="invoice")


class SalesInvoiceItem(Base, TimestampMixin):
    __tablename__ = "sales_invoice_items"

    invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    packaging_unit_id = Column(Integer, ForeignKey("packaging_units.id"), nullable=True)
    unit_factor = Column(Integer, default=1, nullable=False)
    quantity = Column(Integer, nullable=False)       # Ordered packaging quantity
    base_quantity = Column(Integer, nullable=False)  # quantity * unit_factor in base bottles
    unit_price_cents = Column(Integer, nullable=False)  # Per packaging unit
    line_discount_cents = Column(Integer, default=0, nullable=False)
    line_total_cents = Column(Integer, nullable=False)
    cogs_total_cents = Column(Integer, default=0, nullable=False)  # Total cost of goods sold from FIFO

    invoice = relationship("SalesInvoice", back_populates="items")
    product = relationship("Product")
    packaging_unit = relationship("PackagingUnit")
    batch_allocations = relationship("SaleBatchAllocation", back_populates="invoice_item", cascade="all, delete-orphan")


class SaleBatchAllocation(Base, TimestampMixin):
    """Exact FIFO batch tracking per sale item."""
    __tablename__ = "sale_batch_allocations"

    invoice_item_id = Column(Integer, ForeignKey("sales_invoice_items.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=False, index=True)
    base_quantity = Column(Integer, nullable=False)  # Bottles taken from this batch
    unit_cost_cents = Column(Integer, nullable=False)  # Historical cost from this batch
    unit_price_cents = Column(Integer, nullable=False)

    invoice_item = relationship("SalesInvoiceItem", back_populates="batch_allocations")
    batch = relationship("InventoryBatch", back_populates="allocations")


class SalesReturn(Base, TimestampMixin):
    __tablename__ = "sales_returns"

    return_number = Column(String(50), unique=True, nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    return_date = Column(DateTime, default=now_colombo, nullable=False)
    refund_amount_cents = Column(Integer, default=0, nullable=False)
    reason = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    items = relationship("SalesReturnItem", back_populates="sales_return", cascade="all, delete-orphan")


class SalesReturnItem(Base, TimestampMixin):
    __tablename__ = "sales_return_items"

    sales_return_id = Column(Integer, ForeignKey("sales_returns.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price_cents = Column(Integer, nullable=False)
    is_saleable = Column(Boolean, default=True, nullable=False)

    sales_return = relationship("SalesReturn", back_populates="items")


class CreditNote(Base, TimestampMixin):
    __tablename__ = "credit_notes"

    credit_note_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=True)
    sales_return_id = Column(Integer, ForeignKey("sales_returns.id"), nullable=True)
    date = Column(DateTime, default=now_colombo, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
