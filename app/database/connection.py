"""Database connection, session management, and SQLite pragmas."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from app.config.settings import DB_PATH
from app.utilities.logger import logger

Base = declarative_base()

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign keys and WAL mode for all SQLite connections."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()


def get_engine(db_path: Optional[Path] = None) -> Engine:
    """Get or create the SQLAlchemy engine."""
    global _engine, _SessionFactory
    target_path = Path(db_path) if db_path else DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    url = f"sqlite:///{target_path.as_posix()}"
    if _engine is None or str(_engine.url) != url:
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        _SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
        logger.info(f"Connected to SQLite database at {target_path}")
    return _engine


def get_session_factory(engine: Optional[Engine] = None) -> sessionmaker:
    """Get the session factory."""
    global _SessionFactory
    if _SessionFactory is None or (engine and _SessionFactory.kw.get("bind") != engine):
        eng = engine or get_engine()
        _SessionFactory = sessionmaker(bind=eng, autocommit=False, autoflush=False)
    return _SessionFactory


@contextmanager
def get_db_session(engine: Optional[Engine] = None) -> Generator[Session, None, None]:
    """Provide a transactional database session scope."""
    factory = get_session_factory(engine)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction rolled back due to error: {e}")
        raise
    finally:
        session.close()


def check_database_integrity(db_path: Optional[Path] = None) -> bool:
    """Run SQLite integrity check."""
    target_path = Path(db_path) if db_path else DB_PATH
    if not target_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(target_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        conn.close()
        return result is not None and result[0] == "ok"
    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        return False


def backup_database_file(source_path: Optional[Path], destination_path: Path) -> bool:
    """Safely back up an active SQLite database using the SQLite Online Backup API."""
    src = Path(source_path) if source_path else DB_PATH
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        src_conn = sqlite3.connect(str(src))
        dst_conn = sqlite3.connect(str(destination_path))
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        dst_conn.close()
        src_conn.close()
        logger.info(f"Database backed up to {destination_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to back up database: {e}")
        return False
