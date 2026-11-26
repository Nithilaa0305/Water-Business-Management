"""Shared test fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.connection import Base
from app.database.migrations.migration_manager import seed_default_data


@pytest.fixture
def db_session():
    """Create fresh isolated in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    seed_default_data(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    yield session
    session.close()
