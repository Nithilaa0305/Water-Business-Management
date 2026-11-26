"""Authentication, User, Business Profile and System Setting models."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from app.database.connection import Base
from app.database.models.base import TimestampMixin
from app.config.constants import UserRole


class User(Base, TimestampMixin):
    __tablename__ = "users"

    username = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    pin_hash = Column(String(255), nullable=True)
    role = Column(String(20), default=UserRole.OWNER.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    remember_token = Column(String(128), nullable=True)


class BusinessProfile(Base, TimestampMixin):
    __tablename__ = "business_profile"

    business_name = Column(String(150), default="Pure Life Water Distribution", nullable=False)
    address = Column(Text, default="123 Main Street, Colombo, Sri Lanka")
    phone = Column(String(50), default="+94 11 234 5678")
    email = Column(String(100), default="info@watermanager.lk")
    logo_path = Column(String(255), nullable=True)
    currency = Column(String(10), default="Rs.")
    invoice_prefix = Column(String(10), default="INV-")
    receipt_prefix = Column(String(10), default="RCP-")
    purchase_prefix = Column(String(10), default="PUR-")
    language = Column(String(10), default="en")  # 'en' or 'ta'
    bottle_deposit_cents = Column(Integer, default=150000)  # Rs. 1,500.00
    allow_below_cost_sales = Column(Boolean, default=True)  # True = warn, False = block
    credit_limit_policy = Column(String(20), default="WARN")  # 'WARN' or 'BLOCK'
    default_payment_allocation = Column(String(30), default="CURRENT_INVOICE", nullable=False)  # 'CURRENT_INVOICE' or 'OLDEST_INVOICE'
    auto_login_enabled = Column(Boolean, default=True, nullable=False)  # User-friendly auto-login
    last_backup_at = Column(DateTime, nullable=True)
    backup_folder = Column(String(255), nullable=True)  # Custom backup storage directory
    is_setup_completed = Column(Boolean, default=False)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    key = Column(String(50), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
