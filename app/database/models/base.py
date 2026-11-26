"""Base declarative model and common mixins."""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from app.utilities.dates import now_colombo
from app.database.connection import Base


class TimestampMixin:
    """Mixin that adds id and timestamp fields."""
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=now_colombo, nullable=False)
    updated_at = Column(DateTime, default=now_colombo, onupdate=now_colombo, nullable=False)
