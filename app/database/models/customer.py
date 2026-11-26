"""Customer, Customer Category, and Delivery Route models."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.base import TimestampMixin
from app.utilities.dates import now_colombo


class CustomerCategory(Base, TimestampMixin):
    __tablename__ = "customer_categories"

    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    customers = relationship("Customer", back_populates="category")


class DeliveryRoute(Base, TimestampMixin):
    __tablename__ = "delivery_routes"

    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(20), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    customers = relationship("Customer", back_populates="delivery_route")


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    code = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    business_name = Column(String(150), nullable=True)
    phone = Column(String(50), nullable=False, index=True)
    alt_phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    area = Column(String(100), nullable=True, index=True)
    delivery_route_id = Column(Integer, ForeignKey("delivery_routes.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("customer_categories.id"), nullable=True)
    credit_limit_cents = Column(Integer, default=5000000, nullable=False)  # Rs. 50,000.00
    credit_period_days = Column(Integer, default=30, nullable=False)
    opening_balance_cents = Column(Integer, default=0, nullable=False)    # Positive = customer owes us
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    category = relationship("CustomerCategory", back_populates="customers")
    delivery_route = relationship("DeliveryRoute", back_populates="customers")
    invoices = relationship("SalesInvoice", back_populates="customer")
    payments = relationship("CustomerPayment", back_populates="customer")
    ledger_entries = relationship("CustomerLedgerEntry", back_populates="customer")
    bottle_ledger_entries = relationship("CustomerBottleLedger", back_populates="customer")
    special_prices = relationship("CustomerPrice", back_populates="customer")


class CustomerPrice(Base, TimestampMixin):
    __tablename__ = "customer_prices"

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    packaging_unit_id = Column(Integer, ForeignKey("packaging_units.id"), nullable=True)
    agreed_price_cents = Column(Integer, nullable=False)
    effective_date = Column(DateTime, default=now_colombo, nullable=False)
    notes = Column(String(255), nullable=True)

    customer = relationship("Customer", back_populates="special_prices")
    product = relationship("Product")
