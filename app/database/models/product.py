"""Product, category, packaging units, and price history models."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.base import TimestampMixin
from app.utilities.dates import now_colombo


class ProductCategory(Base, TimestampMixin):
    __tablename__ = "product_categories"

    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    products = relationship("Product", back_populates="category")


class PackagingUnit(Base, TimestampMixin):
    __tablename__ = "packaging_units"

    name = Column(String(50), unique=True, nullable=False)  # Bottle, Case of 12, Case of 24
    factor = Column(Integer, default=1, nullable=False)     # Quantity of base bottles
    is_base = Column(Boolean, default=False, nullable=False)


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    code = Column(String(20), unique=True, nullable=False, index=True)  # e.g. W0500, W1000
    name = Column(String(150), nullable=False)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    bottle_size = Column(String(50), nullable=False)   # 500 ml, 1 L, 1.5 L, 5 L, 19 L
    uom = Column(String(20), default="Bottle", nullable=False)
    default_selling_price_cents = Column(Integer, default=0, nullable=False)
    min_stock_level = Column(Integer, default=10, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_returnable = Column(Boolean, default=False, nullable=False)  # True for 19L
    barcode = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)

    category = relationship("ProductCategory", back_populates="products")
    batches = relationship("InventoryBatch", back_populates="product")
    price_history = relationship("ProductPriceHistory", back_populates="product")


class ProductPriceHistory(Base, TimestampMixin):
    __tablename__ = "product_price_history"

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=True)
    packaging_unit_id = Column(Integer, ForeignKey("packaging_units.id"), nullable=True)
    unit_factor = Column(Integer, default=1, nullable=False)
    price_type = Column(String(20), nullable=False)  # 'BUYING' or 'SELLING'
    old_price_cents = Column(Integer, nullable=False)
    new_price_cents = Column(Integer, nullable=False)
    equivalent_bottle_price_cents = Column(Integer, nullable=True)  # new_price_cents // unit_factor
    effective_date = Column(DateTime, default=now_colombo, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(String(255), nullable=True)

    product = relationship("Product", back_populates="price_history")
    packaging_unit = relationship("PackagingUnit")
