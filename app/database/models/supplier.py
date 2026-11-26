"""Supplier and Supplier Ledger models."""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.base import TimestampMixin


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    name = Column(String(150), unique=True, nullable=False, index=True)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=False)
    email = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    opening_balance_cents = Column(Integer, default=0, nullable=False)  # Positive = we owe supplier
    credit_period_days = Column(Integer, default=30, nullable=False)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    purchases = relationship("PurchaseInvoice", back_populates="supplier")
    payments = relationship("SupplierPayment", back_populates="supplier")
    ledger_entries = relationship("SupplierLedgerEntry", back_populates="supplier")
