"""Database initialization, schema creation, and seeding service."""

import hashlib
from typing import Optional
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
import argon2
from app.database.connection import Base, get_engine, get_db_session
import app.database.models as models
from app.config.constants import (
    DEFAULT_PRODUCTS, DEFAULT_PACKAGING_UNITS, DEFAULT_EXPENSE_CATEGORIES,
    CustomerCategory as CustCatEnum, BottleState, UserRole
)
from app.utilities.logger import logger

# Initialize Argon2 Password Hasher
_argon2_hasher = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16
)


def hash_password(plain: str) -> str:
    """Hash password or PIN securely using Argon2id."""
    return _argon2_hasher.hash(plain)


def verify_password(plain: str, hashed: Optional[str]) -> bool:
    """
    Verify password against Argon2id hash with fallback to legacy SHA-256.
    Ensures existing installations and test fixtures continue working seamlessly.
    """
    if not hashed or not plain:
        return False
    if hashed.startswith("$argon2"):
        try:
            return _argon2_hasher.verify(hashed, plain)
        except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.VerificationError):
            return False
    # Legacy SHA-256 salt fallback
    salt = "WaterBusinessSalt2026"
    legacy_hash = hashlib.sha256(f"{salt}{plain}".encode("utf-8")).hexdigest()
    return legacy_hash == hashed


def init_database(engine: Optional[Engine] = None, seed_defaults: bool = True) -> None:
    """Create all tables and perform non-destructive schema evolution."""
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)
    logger.info("Database tables verified/created successfully.")
    
    # Safe non-destructive schema evolution
    inspector = inspect(eng)
    tables = inspector.get_table_names()

    # 1. business_profile migrations
    if "business_profile" in tables:
        cols = {c["name"] for c in inspector.get_columns("business_profile")}
        with eng.connect() as conn:
            if "backup_folder" not in cols:
                conn.execute(text("ALTER TABLE business_profile ADD COLUMN backup_folder VARCHAR(255);"))
            if "default_payment_allocation" not in cols:
                conn.execute(text("ALTER TABLE business_profile ADD COLUMN default_payment_allocation VARCHAR(50) DEFAULT 'CURRENT_INVOICE';"))
            if "auto_login_enabled" not in cols:
                conn.execute(text("ALTER TABLE business_profile ADD COLUMN auto_login_enabled BOOLEAN DEFAULT 0;"))
            if "last_backup_at" not in cols:
                conn.execute(text("ALTER TABLE business_profile ADD COLUMN last_backup_at DATETIME;"))
            conn.commit()

    # 2. users migrations
    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        with eng.connect() as conn:
            if "failed_login_attempts" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;"))
            if "locked_until" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN locked_until DATETIME;"))
            if "remember_token" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN remember_token VARCHAR(255);"))
            conn.commit()

    # 3. product_price_history migrations
    if "product_price_history" in tables:
        cols = {c["name"] for c in inspector.get_columns("product_price_history")}
        with eng.connect() as conn:
            if "packaging_unit_id" not in cols:
                conn.execute(text("ALTER TABLE product_price_history ADD COLUMN packaging_unit_id INTEGER;"))
            if "unit_factor" not in cols:
                conn.execute(text("ALTER TABLE product_price_history ADD COLUMN unit_factor INTEGER DEFAULT 1;"))
            if "equivalent_bottle_price_cents" not in cols:
                conn.execute(text("ALTER TABLE product_price_history ADD COLUMN equivalent_bottle_price_cents INTEGER;"))
            conn.commit()

    if seed_defaults:
        seed_default_data(eng)


def seed_default_data(engine: Optional[Engine] = None) -> None:
    """Populate default reference categories, default products, units, and admin user."""
    with get_db_session(engine) as session:
        # 1. Business Profile
        profile = session.query(models.BusinessProfile).first()
        if not profile:
            profile = models.BusinessProfile(
                business_name="Pure Life Bottled Water Wholesale",
                address="123 Galle Road, Colombo 03, Sri Lanka",
                phone="+94 11 234 5678",
                email="sales@purelifewater.lk",
                currency="Rs.",
                invoice_prefix="INV-",
                receipt_prefix="RCP-",
                purchase_prefix="PUR-",
                language="en",
                bottle_deposit_cents=150000,  # Rs. 1,500
                allow_below_cost_sales=True,
                is_setup_completed=False
            )
            session.add(profile)

        # 2. Default Owner User
        owner = session.query(models.User).filter_by(username="admin").first()
        if not owner:
            owner = models.User(
                username="admin",
                full_name="Business Owner",
                password_hash=hash_password("admin123"),
                pin_hash=hash_password("1234"),
                role=UserRole.OWNER.value,
                is_active=True
            )
            session.add(owner)

        # 3. Product Categories
        categories = ["Bottled Water", "Returnable Water", "Accessories & Consumables"]
        cat_map = {}
        for cat_name in categories:
            cat = session.query(models.ProductCategory).filter_by(name=cat_name).first()
            if not cat:
                cat = models.ProductCategory(name=cat_name, description=f"{cat_name} category")
                session.add(cat)
                session.flush()
            cat_map[cat_name] = cat.id

        # 4. Packaging Units
        for unit_def in DEFAULT_PACKAGING_UNITS:
            unit = session.query(models.PackagingUnit).filter_by(name=unit_def["name"]).first()
            if not unit:
                unit = models.PackagingUnit(
                    name=unit_def["name"],
                    factor=unit_def["factor"],
                    is_base=unit_def["is_base"]
                )
                session.add(unit)

        # 5. Default 5 Water Products (W0500, W1000, W1500, W5000, W19000)
        for p_def in DEFAULT_PRODUCTS:
            prod = session.query(models.Product).filter_by(code=p_def["code"]).first()
            if not prod:
                cat_id = cat_map.get(p_def["category"], list(cat_map.values())[0])
                prod = models.Product(
                    code=p_def["code"],
                    name=p_def["name"],
                    category_id=cat_id,
                    bottle_size=p_def["bottle_size"],
                    uom=p_def["uom"],
                    default_selling_price_cents=p_def["default_selling_price_cents"],
                    min_stock_level=p_def["min_stock_level"],
                    is_active=True,
                    is_returnable=p_def["is_returnable"],
                    description=p_def["description"]
                )
                session.add(prod)

        # 6. Customer Categories
        for cat_enum in CustCatEnum:
            c_cat = session.query(models.CustomerCategory).filter_by(name=cat_enum.value).first()
            if not c_cat:
                c_cat = models.CustomerCategory(name=cat_enum.value, description=f"{cat_enum.value} category")
                session.add(c_cat)

        # 7. Delivery Routes
        default_routes = [
            ("Route 1 - Colombo Central", "R-CENTRAL"),
            ("Route 2 - Colombo North & Suburbs", "R-NORTH"),
            ("Route 3 - Colombo South & Coastal", "R-SOUTH")
        ]
        for r_name, r_code in default_routes:
            route = session.query(models.DeliveryRoute).filter_by(name=r_name).first()
            if not route:
                route = models.DeliveryRoute(name=r_name, code=r_code)
                session.add(route)

        # 8. 7 Bottle States in bottle_inventory (all initialized to 0)
        for state in BottleState:
            b_inv = session.query(models.BottleInventory).filter_by(state=state.value).first()
            if not b_inv:
                b_inv = models.BottleInventory(state=state.value, quantity=0)
                session.add(b_inv)

        # 9. Expense Categories
        for exp_cat in DEFAULT_EXPENSE_CATEGORIES:
            ec = session.query(models.ExpenseCategory).filter_by(name=exp_cat).first()
            if not ec:
                ec = models.ExpenseCategory(name=exp_cat, is_operating=True)
                session.add(ec)

        # 10. Financial Accounts for General Ledger
        default_accounts = [
            ("1010", "Cash on Hand", "ASSET"),
            ("1020", "Bank Account", "ASSET"),
            ("1100", "Accounts Receivable (Customer Credit)", "ASSET"),
            ("1200", "Water Inventory Asset", "ASSET"),
            ("1300", "Returnable Bottle Asset", "ASSET"),
            ("2010", "Accounts Payable (Supplier Credit)", "LIABILITY"),
            ("2100", "Refundable Bottle Deposits", "LIABILITY"),
            ("2200", "Customer Advance Payments", "LIABILITY"),
            ("3010", "Owner's Capital", "EQUITY"),
            ("4010", "Water Sales Revenue", "REVENUE"),
            ("5010", "Cost of Goods Sold (COGS)", "EXPENSE"),
            ("6010", "Operating Expenses", "EXPENSE"),
        ]
        for code, name, acct_type in default_accounts:
            acct = session.query(models.FinancialAccount).filter_by(code=code).first()
            if not acct:
                acct = models.FinancialAccount(code=code, name=name, account_type=acct_type, is_active=True)
                session.add(acct)

        logger.info("Default seed data initialized.")
