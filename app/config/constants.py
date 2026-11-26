"""Application-wide constants and business definitions."""

from enum import Enum


class UserRole(str, Enum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class StockMovementType(str, Enum):
    PURCHASE = "PURCHASE"
    SALE = "SALE"
    PRODUCTION = "PRODUCTION"
    OPENING = "OPENING"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"
    DAMAGE = "DAMAGE"
    EXPIRED = "EXPIRED"
    LOST = "LOST"
    SALES_RETURN = "SALES_RETURN"
    SUPPLIER_RETURN = "SUPPLIER_RETURN"
    REFILL_IN = "REFILL_IN"


class BottleState(str, Enum):
    FULL_AVAILABLE = "FULL_AVAILABLE"          # 1. Full bottles ready in warehouse
    EMPTY_AVAILABLE = "EMPTY_AVAILABLE"        # 2. Empty bottles in warehouse ready for refill
    IN_CLEANING_REFILL = "IN_CLEANING_REFILL"  # 3. Bottles currently undergoing washing/refill
    HELD_BY_CUSTOMERS = "HELD_BY_CUSTOMERS"    # 4. Bottles with customers
    DAMAGED = "DAMAGED"                        # 5. Damaged bottles awaiting inspection/disposal
    LOST_WRITTEN_OFF = "LOST_WRITTEN_OFF"      # 6. Lost or written off
    PERMANENTLY_SOLD = "PERMANENTLY_SOLD"      # 7. Sold outright


class BottleMovementType(str, Enum):
    DELIVERY_FULL = "DELIVERY_FULL"            # Sent full bottle to customer (+customer, -full)
    RETURN_EMPTY = "RETURN_EMPTY"              # Customer returned empty bottle (-customer, +empty)
    RETURN_FULL = "RETURN_FULL"                # Customer returned unused full bottle (-customer, +full)
    REFILL_START = "REFILL_START"              # Sent empty to cleaning/refill (-empty, +cleaning)
    REFILL_FINISH = "REFILL_FINISH"            # Refill success (+full, -cleaning)
    REFILL_REJECT = "REFILL_REJECT"            # Refill rejected/damaged (+damaged, -cleaning)
    DAMAGE_EMPTY = "DAMAGE_EMPTY"              # Empty damaged in warehouse (-empty, +damaged)
    DAMAGE_FULL = "DAMAGE_FULL"                # Full damaged in warehouse (-full, +damaged)
    CUSTOMER_LOST = "CUSTOMER_LOST"            # Customer lost container (-customer, +lost)
    WAREHOUSE_LOST = "WAREHOUSE_LOST"          # Warehouse lost container (+lost)
    PERMANENT_SALE = "PERMANENT_SALE"          # Sold container outright (+sold)
    PURCHASE_CONTAINER = "PURCHASE_CONTAINER"  # Acquired new empty bottles (+empty)
    OPENING_BALANCE = "OPENING_BALANCE"        # Initial container stock


class PaymentMethod(str, Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    CHEQUE = "CHEQUE"
    CARD = "CARD"
    CREDIT = "CREDIT"
    CUSTOMER_ADVANCE = "CUSTOMER_ADVANCE"
    MIXED = "MIXED"


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class CustomerCategory(str, Enum):
    INDIVIDUAL = "Individual"
    RETAIL_SHOP = "Retail Shop"
    WHOLESALE = "Wholesale Customer"
    RESTAURANT = "Restaurant"
    HOTEL = "Hotel"
    OFFICE = "Office"
    DISTRIBUTOR = "Distributor"
    OTHER = "Other"


# Default 5 Bottled Water Products as per requirements
DEFAULT_PRODUCTS = [
    {
        "code": "W0500",
        "name": "500 ml Water Bottle",
        "category": "Bottled Water",
        "bottle_size": "500 ml",
        "uom": "Bottle",
        "default_selling_price_cents": 6000,   # Rs. 60.00
        "min_stock_level": 100,
        "is_returnable": False,
        "description": "500 ml PET non-returnable drinking water bottle"
    },
    {
        "code": "W1000",
        "name": "1 L Water Bottle",
        "category": "Bottled Water",
        "bottle_size": "1 L",
        "uom": "Bottle",
        "default_selling_price_cents": 10000,  # Rs. 100.00
        "min_stock_level": 50,
        "is_returnable": False,
        "description": "1 L PET non-returnable drinking water bottle"
    },
    {
        "code": "W1500",
        "name": "1.5 L Water Bottle",
        "category": "Bottled Water",
        "bottle_size": "1.5 L",
        "uom": "Bottle",
        "default_selling_price_cents": 14000,  # Rs. 140.00
        "min_stock_level": 50,
        "is_returnable": False,
        "description": "1.5 L PET non-returnable drinking water bottle"
    },
    {
        "code": "W5000",
        "name": "5 L Water Bottle",
        "category": "Bottled Water",
        "bottle_size": "5 L",
        "uom": "Bottle",
        "default_selling_price_cents": 35000,  # Rs. 350.00
        "min_stock_level": 20,
        "is_returnable": False,
        "description": "5 L dispenser/handle water bottle"
    },
    {
        "code": "W19000",
        "name": "19 L Returnable Water Bottle",
        "category": "Returnable Water",
        "bottle_size": "19 L",
        "uom": "Bottle",
        "default_selling_price_cents": 30000,  # Rs. 300.00
        "min_stock_level": 20,
        "is_returnable": True,
        "description": "19 L heavy-duty polycarbonate reusable water bottle"
    }
]

# Standard packaging units
DEFAULT_PACKAGING_UNITS = [
    {"name": "Bottle", "factor": 1, "is_base": True},
    {"name": "Case of 12", "factor": 12, "is_base": False},
    {"name": "Case of 24", "factor": 24, "is_base": False},
]

# Default Expense Categories
DEFAULT_EXPENSE_CATEGORIES = [
    "Electricity",
    "Water Treatment & Testing",
    "Fuel",
    "Transport & Delivery",
    "Vehicle Maintenance",
    "Salaries & Wages",
    "Rent",
    "Bottle Washing & Cleaning",
    "Repairs & Maintenance",
    "Packaging Materials (Caps, Seals, Labels)",
    "Office Expenses",
    "Telephone & Internet",
    "Other Operating Expenses"
]
