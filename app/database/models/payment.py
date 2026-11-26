"""Customer and Supplier Payments, Payment Allocations, and Customer/Supplier Ledgers."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.base import TimestampMixin
from app.utilities.dates import now_colombo


class CustomerPayment(Base, TimestampMixin):
    __tablename__ = "customer_payments"

    payment_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    payment_date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    payment_method = Column(String(30), default="CASH", nullable=False)
    reference_no = Column(String(100), nullable=True)  # Cheque #, bank tx ref
    unallocated_amount_cents = Column(Integer, default=0, nullable=False)  # Customer advance
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    customer = relationship("Customer", back_populates="payments")
    allocations = relationship("CustomerPaymentAllocation", back_populates="payment", cascade="all, delete-orphan")


class CustomerPaymentAllocation(Base, TimestampMixin):
    __tablename__ = "customer_payment_allocations"

    payment_id = Column(Integer, ForeignKey("customer_payments.id"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=False, index=True)
    allocated_amount_cents = Column(Integer, nullable=False)

    payment = relationship("CustomerPayment", back_populates="allocations")
    invoice = relationship("SalesInvoice", back_populates="payment_allocations")


class CustomerLedgerEntry(Base, TimestampMixin):
    """Immutable audit ledger of all customer financial transactions."""
    __tablename__ = "customer_ledger"

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False)  # OPENING, INVOICE, PAYMENT, CREDIT_NOTE, ADVANCE_USE, REFUND
    reference_no = Column(String(50), nullable=True, index=True)
    debit_cents = Column(Integer, default=0, nullable=False)   # Increases customer debt (e.g. Invoice)
    credit_cents = Column(Integer, default=0, nullable=False)  # Decreases customer debt (e.g. Payment)
    running_balance_cents = Column(Integer, nullable=False)     # Positive = owes us, Negative = advance
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="ledger_entries")


class SupplierPayment(Base, TimestampMixin):
    __tablename__ = "supplier_payments"

    payment_number = Column(String(50), unique=True, nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    payment_date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    payment_method = Column(String(30), default="CASH", nullable=False)
    reference_no = Column(String(100), nullable=True)
    unallocated_amount_cents = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    supplier = relationship("Supplier", back_populates="payments")
    allocations = relationship("SupplierPaymentAllocation", back_populates="payment", cascade="all, delete-orphan")


class SupplierPaymentAllocation(Base, TimestampMixin):
    __tablename__ = "supplier_payment_allocations"

    payment_id = Column(Integer, ForeignKey("supplier_payments.id"), nullable=False, index=True)
    purchase_invoice_id = Column(Integer, ForeignKey("purchase_invoices.id"), nullable=False, index=True)
    allocated_amount_cents = Column(Integer, nullable=False)

    payment = relationship("SupplierPayment", back_populates="allocations")
    purchase_invoice = relationship("PurchaseInvoice", back_populates="payment_allocations")


class SupplierLedgerEntry(Base, TimestampMixin):
    __tablename__ = "supplier_ledger"

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    date = Column(DateTime, default=now_colombo, nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False)  # OPENING, PURCHASE, PAYMENT, RETURN, ADJUSTMENT
    reference_no = Column(String(50), nullable=True, index=True)
    debit_cents = Column(Integer, default=0, nullable=False)   # Decreases our debt to supplier (e.g. Payment)
    credit_cents = Column(Integer, default=0, nullable=False)  # Increases our debt to supplier (e.g. Purchase)
    running_balance_cents = Column(Integer, nullable=False)     # Positive = we owe supplier
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    supplier = relationship("Supplier", back_populates="ledger_entries")
