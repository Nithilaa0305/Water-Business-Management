"""Purchases, Production, Expenses, Financial Journal, and Audit models."""

from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.base import TimestampMixin
from app.utilities.dates import now_colombo


class PurchaseInvoice(Base, TimestampMixin):
    __tablename__ = "purchase_invoices"

    purchase_number = Column(String(50), unique=True, nullable=False, index=True)
    supplier_invoice_no = Column(String(100), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    purchase_date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    total_amount_cents = Column(Integer, nullable=False)
    amount_paid_cents = Column(Integer, default=0, nullable=False)
    payment_method = Column(String(30), default="CREDIT", nullable=False)
    status = Column(String(20), default="POSTED", nullable=False)
    due_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    supplier = relationship("Supplier", back_populates="purchases")
    items = relationship("PurchaseInvoiceItem", back_populates="purchase", cascade="all, delete-orphan")
    payment_allocations = relationship("SupplierPaymentAllocation", back_populates="purchase_invoice")


class PurchaseInvoiceItem(Base, TimestampMixin):
    __tablename__ = "purchase_invoice_items"

    purchase_id = Column(Integer, ForeignKey("purchase_invoices.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    packaging_unit_id = Column(Integer, ForeignKey("packaging_units.id"), nullable=True)
    unit_factor = Column(Integer, default=1, nullable=False)
    quantity = Column(Integer, nullable=False)
    base_quantity = Column(Integer, nullable=False)
    unit_cost_cents = Column(Integer, nullable=False)  # Cost per packaging unit
    total_cost_cents = Column(Integer, nullable=False)
    batch_number = Column(String(50), nullable=True)
    expiry_date = Column(Date, nullable=True)

    purchase = relationship("PurchaseInvoice", back_populates="items")
    product = relationship("Product")


class ProductionBatch(Base, TimestampMixin):
    """Production of non-returnable bottles (500ml, 1L, 1.5L, 5L)."""
    __tablename__ = "production_batches"

    batch_number = Column(String(50), unique=True, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    quantity_produced = Column(Integer, nullable=False)
    quantity_rejected = Column(Integer, default=0, nullable=False)
    
    direct_materials_cents = Column(Integer, default=0, nullable=False)
    packaging_costs_cents = Column(Integer, default=0, nullable=False)
    direct_labour_cents = Column(Integer, default=0, nullable=False)
    water_treatment_cents = Column(Integer, default=0, nullable=False)
    other_costs_cents = Column(Integer, default=0, nullable=False)
    total_cost_cents = Column(Integer, default=0, nullable=False)
    unit_cost_cents = Column(Integer, default=0, nullable=False)
    
    inventory_batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    product = relationship("Product")


class ExpenseCategory(Base, TimestampMixin):
    __tablename__ = "expense_categories"

    name = Column(String(100), unique=True, nullable=False)
    is_operating = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    expenses = relationship("Expense", back_populates="category")


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("expense_categories.id"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    payment_method = Column(String(30), default="CASH", nullable=False)
    payee = Column(String(150), nullable=True)
    reference_no = Column(String(100), nullable=True)
    is_paid = Column(Boolean, default=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    category = relationship("ExpenseCategory", back_populates="expenses")


class FinancialAccount(Base, TimestampMixin):
    __tablename__ = "financial_accounts"

    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    account_type = Column(String(20), nullable=False)  # ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    is_active = Column(Boolean, default=True, nullable=False)


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    entry_number = Column(String(50), unique=True, nullable=False, index=True)
    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    lines = relationship("JournalLine", back_populates="journal_entry", cascade="all, delete-orphan")


class JournalLine(Base, TimestampMixin):
    __tablename__ = "journal_lines"

    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("financial_accounts.id"), nullable=False)
    debit_cents = Column(Integer, default=0, nullable=False)
    credit_cents = Column(Integer, default=0, nullable=False)
    memo = Column(String(255), nullable=True)

    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("FinancialAccount")


class AuditLog(Base, TimestampMixin):
    """Append-only audit trail."""
    __tablename__ = "audit_logs"

    user_id = Column(Integer, nullable=True)
    user_name = Column(String(100), nullable=True)
    role = Column(String(20), nullable=True)
    timestamp = Column(DateTime, default=now_colombo, nullable=False, index=True)
    action_type = Column(String(50), nullable=False, index=True)  # INVOICE_CREATE, CANCEL, PAYMENT, REFILL, etc.
    entity_name = Column(String(50), nullable=False)              # SalesInvoice, Customer, Batch
    entity_id = Column(Integer, nullable=True)
    reference_no = Column(String(100), nullable=True, index=True)
    old_values = Column(Text, nullable=True)
    new_values = Column(Text, nullable=True)
    reason = Column(String(255), nullable=True)


class DailyCashClosing(Base, TimestampMixin):
    """Daily cash drawer physical reconciliation record."""
    __tablename__ = "daily_cash_closings"

    closing_number = Column(String(50), unique=True, nullable=False, index=True)
    closing_date = Column(Date, unique=True, nullable=False, index=True)
    opening_cash_cents = Column(Integer, default=0, nullable=False)
    cash_sales_cents = Column(Integer, default=0, nullable=False)
    credit_collections_cents = Column(Integer, default=0, nullable=False)
    customer_advances_cents = Column(Integer, default=0, nullable=False)
    deposits_collected_cents = Column(Integer, default=0, nullable=False)
    cash_expenses_cents = Column(Integer, default=0, nullable=False)
    supplier_payments_cents = Column(Integer, default=0, nullable=False)
    deposit_refunds_cents = Column(Integer, default=0, nullable=False)
    cash_withdrawals_cents = Column(Integer, default=0, nullable=False)
    expected_cash_cents = Column(Integer, default=0, nullable=False)
    counted_cash_cents = Column(Integer, default=0, nullable=False)
    difference_cents = Column(Integer, default=0, nullable=False)  # Counted - Expected
    status = Column(String(20), default="BALANCED", nullable=False)  # BALANCED, SHORTAGE, EXCESS
    denomination_json = Column(Text, nullable=True)  # JSON breakdown of note/coin counts
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class DeliverySheet(Base, TimestampMixin):
    """Daily delivery route sheet."""
    __tablename__ = "delivery_sheets"

    sheet_number = Column(String(50), unique=True, nullable=False, index=True)
    delivery_date = Column(Date, nullable=False, index=True)
    route_id = Column(Integer, ForeignKey("delivery_routes.id"), nullable=True)
    driver_name = Column(String(100), nullable=True)
    vehicle_number = Column(String(50), nullable=True)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, IN_PROGRESS, COMPLETED, CANCELLED
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    items = relationship("DeliverySheetItem", back_populates="sheet", cascade="all, delete-orphan")


class DeliverySheetItem(Base, TimestampMixin):
    """Line item in delivery sheet."""
    __tablename__ = "delivery_sheet_items"

    sheet_id = Column(Integer, ForeignKey("delivery_sheets.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=True)
    stop_number = Column(Integer, default=1, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, DELIVERED, CANCELLED, RESCHEDULED
    full_19l_delivered = Column(Integer, default=0, nullable=False)
    empty_19l_collected = Column(Integer, default=0, nullable=False)
    payment_collected_cents = Column(Integer, default=0, nullable=False)
    payment_method = Column(String(30), default="CASH", nullable=False)
    notes = Column(String(255), nullable=True)

    sheet = relationship("DeliverySheet", back_populates="items")
    customer = relationship("Customer")
    invoice = relationship("SalesInvoice")

