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

    # 4. Teammate schema compatibility views
    create_teammate_compatibility_views(eng)


def create_teammate_compatibility_views(eng: Engine) -> None:
    """Create compatibility views and aliases matching teammate schema and reporting views."""
    # Drop existing views to allow clean recreation if definition changed
    drop_views_sql = [
        "DROP VIEW IF EXISTS v_today;",
        "DROP VIEW IF EXISTS v_monthly_summary;",
        "DROP VIEW IF EXISTS v_price_history;",
        "DROP VIEW IF EXISTS v_activity_timeline;",
        "DROP VIEW IF EXISTS v_supplier_balances;",
        "DROP VIEW IF EXISTS v_customer_containers;",
        "DROP VIEW IF EXISTS v_sale_item_details;",
        "DROP VIEW IF EXISTS v_sales_list;",
        "DROP VIEW IF EXISTS v_customer_statement;",
        "DROP VIEW IF EXISTS v_customer_balances;",
        "DROP VIEW IF EXISTS v_stock_by_type;",
        "DROP VIEW IF EXISTS v_batch_queue;",
        "DROP VIEW IF EXISTS customer_containers;",
        "DROP VIEW IF EXISTS activity_log;",
        "DROP VIEW IF EXISTS payments;",
        "DROP VIEW IF EXISTS sale_items;",
        "DROP VIEW IF EXISTS sales;",
        "DROP VIEW IF EXISTS stock_batches;",
        "DROP VIEW IF EXISTS app_users;",
        "DROP VIEW IF EXISTS payment_methods;",
        "DROP VIEW IF EXISTS areas;",
        "DROP VIEW IF EXISTS categories;",
        "DROP VIEW IF EXISTS units;"
    ]

    views_sql = [
        # Table Aliases / Views
        """CREATE VIEW IF NOT EXISTS units AS SELECT id AS unit_id, name AS unit_name, 1 AS is_active FROM packaging_units;""",
        """CREATE VIEW IF NOT EXISTS categories AS SELECT id AS category_id, name AS category_name, 1 AS is_active FROM product_categories;""",
        """CREATE VIEW IF NOT EXISTS areas AS SELECT id AS area_id, name AS area_name, 1 AS is_active FROM delivery_routes;""",
        """CREATE VIEW IF NOT EXISTS payment_methods AS SELECT 1 AS method_id, 'Cash' AS method_name, 1 AS is_active UNION SELECT 2, 'Bank Transfer', 1 UNION SELECT 3, 'Cheque', 1 UNION SELECT 4, 'Card', 1 UNION SELECT 5, 'Other', 1;""",
        """CREATE VIEW IF NOT EXISTS app_users AS SELECT id AS user_id, full_name, username, role AS user_role, password_hash AS pin_hash, is_active, created_at, updated_at FROM users;""",
        """CREATE VIEW IF NOT EXISTS stock_batches AS SELECT id AS batch_id, batch_number, product_id AS type_id, original_qty AS quantity_received, remaining_qty AS current_quantity, CAST(unit_cost_cents AS REAL) / 100.0 AS buying_price, NULL AS selling_price, received_date, expiry_date, created_at FROM inventory_batches;""",
        """CREATE VIEW IF NOT EXISTS sales AS SELECT id AS sale_id, invoice_number AS sale_number, customer_id, invoice_date AS sale_date, CAST(subtotal_cents AS REAL) / 100.0 AS subtotal, CAST(discount_cents AS REAL) / 100.0 AS discount, CAST(total_amount_cents AS REAL) / 100.0 AS total, CAST(amount_paid_cents AS REAL) / 100.0 AS amount_paid, CASE WHEN status = 'CANCELLED' THEN 'cancelled' ELSE 'completed' END AS status, notes, created_at FROM sales_invoices;""",
        """CREATE VIEW IF NOT EXISTS sale_items AS SELECT id AS sale_item_id, invoice_id AS sale_id, product_id AS type_id, NULL AS batch_id, quantity, CAST(unit_price_cents AS REAL) / 100.0 AS unit_price, CAST(cogs_total_cents AS REAL) / (100.0 * CASE WHEN quantity > 0 THEN quantity ELSE 1 END) AS buying_price, 0 AS returned_quantity, CAST(line_total_cents AS REAL) / 100.0 AS line_total FROM sales_invoice_items;""",
        """CREATE VIEW IF NOT EXISTS payments AS SELECT id AS payment_id, customer_id, payment_date, CAST(amount_cents AS REAL) / 100.0 AS amount, payment_method, notes, created_at FROM customer_payments;""",
        """CREATE VIEW IF NOT EXISTS activity_log AS SELECT id AS activity_id, user_id, timestamp AS action_time, action_type, COALESCE(reason, action_type) AS description, entity_name AS reference_type, entity_id AS reference_id FROM audit_logs;""",
        """CREATE VIEW IF NOT EXISTS customer_containers AS SELECT customer_id, 5 AS type_id, running_bottle_balance AS held FROM customer_bottle_ledger;""",

        # Reporting & Queue Views
        """CREATE VIEW IF NOT EXISTS v_batch_queue AS
        SELECT b.id AS batch_id, b.batch_number, b.product_id AS type_id,
               p.name AS item,
               b.received_date, b.remaining_qty AS current_quantity,
               CAST(b.unit_cost_cents AS REAL) / 100.0 AS buying_price,
               CAST(p.default_selling_price_cents AS REAL) / 100.0 AS selling_price,
               b.expiry_date,
               ROW_NUMBER() OVER (PARTITION BY b.product_id ORDER BY b.received_date, b.created_at, b.batch_number) AS queue_position,
               CASE ROW_NUMBER() OVER (PARTITION BY b.product_id ORDER BY b.received_date, b.created_at, b.batch_number)
                    WHEN 1 THEN 'Current' WHEN 2 THEN 'Next' ELSE 'Waiting' END AS batch_status
          FROM inventory_batches b
          JOIN products p ON p.id = b.product_id
         WHERE b.remaining_qty > 0;""",

        """CREATE VIEW IF NOT EXISTS v_stock_by_type AS
        SELECT p.id AS type_id, p.name AS product_name, p.bottle_size AS type_name,
               p.name AS item,
               p.uom AS unit_name,
               COALESCE(SUM(b.remaining_qty), 0) AS total_quantity,
               COUNT(b.id) AS batches_in_stock,
               (COALESCE(SUM(b.remaining_qty), 0) <= p.min_stock_level) AS low_stock
          FROM products p
          LEFT JOIN inventory_batches b ON b.product_id = p.id AND b.remaining_qty > 0
         GROUP BY p.id, p.name, p.bottle_size, p.uom, p.min_stock_level;""",

        """CREATE VIEW IF NOT EXISTS v_customer_balances AS
        SELECT c.id AS customer_id, c.name AS customer_name, c.phone, c.area AS area_name,
               cat.name AS group_name,
               CAST(c.credit_limit_cents AS REAL) / 100.0 AS credit_limit,
               CAST(COALESCE((SELECT running_balance_cents FROM customer_ledger WHERE customer_id = c.id ORDER BY id DESC LIMIT 1), c.opening_balance_cents) AS REAL) / 100.0 AS balance,
               CASE WHEN COALESCE((SELECT running_balance_cents FROM customer_ledger WHERE customer_id = c.id ORDER BY id DESC LIMIT 1), c.opening_balance_cents) > 0 THEN 'Customer owes you'
                    WHEN COALESCE((SELECT running_balance_cents FROM customer_ledger WHERE customer_id = c.id ORDER BY id DESC LIMIT 1), c.opening_balance_cents) < 0 THEN 'You owe customer'
                    ELSE 'Settled' END AS balance_note,
               ABS(CAST(COALESCE((SELECT running_balance_cents FROM customer_ledger WHERE customer_id = c.id ORDER BY id DESC LIMIT 1), c.opening_balance_cents) AS REAL) / 100.0) AS amount,
               (c.credit_limit_cents > 0 AND COALESCE((SELECT running_balance_cents FROM customer_ledger WHERE customer_id = c.id ORDER BY id DESC LIMIT 1), c.opening_balance_cents) > c.credit_limit_cents) AS over_limit
          FROM customers c
          LEFT JOIN customer_categories cat ON cat.id = c.category_id;""",

        """CREATE VIEW IF NOT EXISTS v_customer_statement AS
        SELECT l.customer_id, c.name AS customer_name, l.date AS entry_time,
               l.transaction_type AS entry_type, l.notes AS note,
               CAST(l.debit_cents AS REAL) / 100.0 AS debit,
               CAST(l.credit_cents AS REAL) / 100.0 AS credit,
               CAST(l.running_balance_cents AS REAL) / 100.0 AS running_balance,
               'System' AS entered_by
          FROM customer_ledger l
          JOIN customers c ON c.id = l.customer_id
         ORDER BY c.name, l.date;""",

        """CREATE VIEW IF NOT EXISTS v_sales_list AS
        SELECT s.id AS sale_id, s.invoice_number AS sale_number, s.invoice_date AS sale_date,
               c.name AS customer_name,
               CAST(s.subtotal_cents AS REAL) / 100.0 AS subtotal,
               CAST(s.discount_cents AS REAL) / 100.0 AS discount,
               CAST(s.total_amount_cents AS REAL) / 100.0 AS total,
               CAST(s.amount_paid_cents AS REAL) / 100.0 AS amount_paid,
               CAST(s.total_amount_cents - s.amount_paid_cents AS REAL) / 100.0 AS due,
               CASE WHEN s.status = 'CANCELLED' THEN 'cancelled' ELSE 'completed' END AS status,
               'Admin' AS made_by
          FROM sales_invoices s
          JOIN customers c ON c.id = s.customer_id
         ORDER BY s.created_at DESC;""",

        """CREATE VIEW IF NOT EXISTS v_sale_item_details AS
        SELECT s.invoice_number AS sale_number, s.invoice_date AS sale_date, c.name AS customer_name,
               p.name AS item,
               '' AS batch_number, i.quantity,
               CAST(i.unit_price_cents AS REAL) / 100.0 AS unit_price,
               CAST(i.line_total_cents AS REAL) / 100.0 AS line_total,
               CAST(i.cogs_total_cents AS REAL) / (100.0 * CASE WHEN i.quantity > 0 THEN i.quantity ELSE 1 END) AS buying_price,
               0 AS returned_quantity, i.id AS sale_item_id
          FROM sales_invoice_items i
          JOIN sales_invoices s ON s.id = i.invoice_id
          JOIN customers c ON c.id = s.customer_id
          JOIN products p ON p.id = i.product_id
         ORDER BY s.created_at DESC, p.name;""",

        """CREATE VIEW IF NOT EXISTS v_customer_containers AS
        SELECT cc.customer_id, c.name AS customer_name, '19 L Returnable Bottle' AS container, cc.running_bottle_balance AS held
          FROM customer_bottle_ledger cc
          JOIN customers c ON c.id = cc.customer_id;""",

        """CREATE VIEW IF NOT EXISTS v_supplier_balances AS
        SELECT s.id AS supplier_id, s.name AS supplier_name,
               CAST(s.opening_balance_cents AS REAL) / 100.0 AS you_owe
          FROM suppliers s;""",

        """CREATE VIEW IF NOT EXISTS v_activity_timeline AS
        SELECT a.timestamp AS action_time, DATE(a.timestamp) AS action_date,
               a.user_name AS person, a.role AS user_role, a.action_type, COALESCE(a.reason, a.action_type) AS description,
               a.entity_name AS reference_type, a.entity_id AS reference_id
          FROM audit_logs a
         ORDER BY a.timestamp DESC;""",

        """CREATE VIEW IF NOT EXISTS v_price_history AS
        SELECT h.effective_date AS changed_at, p.name AS item,
               h.price_type AS price_kind,
               CAST(h.old_price_cents AS REAL) / 100.0 AS old_price,
               CAST(h.new_price_cents AS REAL) / 100.0 AS new_price,
               b.batch_number, 'Admin' AS changed_by_person, h.reason AS note
          FROM product_price_history h
          JOIN products p ON p.id = h.product_id
          LEFT JOIN inventory_batches b ON b.id = h.batch_id
         ORDER BY h.effective_date DESC;""",

        """CREATE VIEW IF NOT EXISTS v_monthly_summary AS
        SELECT
            STRFTIME('%Y-%m', invoice_date) AS month,
            CAST(SUM(total_amount_cents) AS REAL) / 100.0 AS net_sales,
            0.0 AS cost_of_goods,
            CAST(SUM(total_amount_cents) AS REAL) / 100.0 AS gross_profit,
            0.0 AS expenses_total,
            CAST(SUM(total_amount_cents) AS REAL) / 100.0 AS net_profit,
            0.0 AS stock_purchased_value,
            CAST(SUM(amount_paid_cents) AS REAL) / 100.0 AS cash_collected
        FROM sales_invoices
        WHERE status != 'CANCELLED'
        GROUP BY STRFTIME('%Y-%m', invoice_date);""",

        """CREATE VIEW IF NOT EXISTS v_today AS
        SELECT
           COALESCE((SELECT SUM(total_amount_cents) FROM sales_invoices WHERE DATE(created_at) = DATE('now', 'localtime') AND status != 'CANCELLED'), 0) / 100.0 AS sales_today,
           COALESCE((SELECT SUM(amount_cents) FROM customer_payments WHERE DATE(created_at) = DATE('now', 'localtime')), 0) / 100.0 AS cash_received_today,
           COALESCE((SELECT SUM(COALESCE((SELECT running_balance_cents FROM customer_ledger WHERE customer_id = c.id ORDER BY id DESC LIMIT 1), c.opening_balance_cents)) FROM customers c WHERE COALESCE((SELECT running_balance_cents FROM customer_ledger WHERE customer_id = c.id ORDER BY id DESC LIMIT 1), c.opening_balance_cents) > 0), 0) / 100.0 AS owed_to_you,
           (SELECT COUNT(*) FROM products p LEFT JOIN (SELECT product_id, SUM(remaining_qty) AS rem FROM inventory_batches GROUP BY product_id) b ON b.product_id = p.id WHERE COALESCE(b.rem, 0) <= p.min_stock_level) AS low_stock_items;"""
    ]
    with eng.connect() as conn:
        for drop_sql in drop_views_sql:
            try:
                conn.execute(text(drop_sql))
            except Exception:
                pass
        for v in views_sql:
            try:
                conn.execute(text(v))
            except Exception as e:
                logger.warning(f"Note creating compatibility view: {e}")
        conn.commit()


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
