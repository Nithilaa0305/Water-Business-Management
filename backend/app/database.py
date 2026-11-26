# ============================================================
# FILE: backend/app/database.py
# PURPOSE: Opens and closes the connection to PostgreSQL.
#          Every other file imports 'get_db' from here.
# ============================================================

import os
from psycopg.rows import dict_row          # Makes query results return as dicts
from psycopg_pool import AsyncConnectionPool  # Async connection pool
from dotenv import load_dotenv

# Load the .env file so os.getenv() can read DATABASE_URL
load_dotenv()

# Read the database URL from .env
# Format: postgresql+psycopg://username:password@host:port/database_name
DATABASE_URL = os.getenv("DATABASE_URL")

# Remove the driver prefix if present — psycopg_pool uses plain postgresql://
_conninfo = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://") if DATABASE_URL else ""

# The global connection pool — shared by the whole app
# It is created in init_db() and destroyed in close_db()
_pool: AsyncConnectionPool = None


async def init_db():
    """
    Called once when the FastAPI app starts up.
    Creates the connection pool — a set of ready-made DB connections.

    min_size=2  → Always keep 2 connections open (fast response)
    max_size=10 → Never allow more than 10 simultaneous connections
    """
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=_conninfo,
        min_size=2,
        max_size=10,
        open=False,                       # We will open manually with await pool.open()
        kwargs={"row_factory": dict_row}  # All rows returned as dict (key → value)
    )
    await _pool.open()   # Open the pool properly (async, no deprecation warning)
    await _pool.wait()   # Wait until at least min_size connections are ready


async def close_db():
    """
    Called once when the FastAPI app shuts down (Ctrl+C).
    Closes all database connections cleanly.
    """
    global _pool
    if _pool:
        await _pool.close()


async def get_db():
    """
    Called automatically by FastAPI for every API request (via Depends).
    Borrows one connection from the pool, gives it to the request,
    and returns it when the request finishes.

    Usage in any router:
        async def my_endpoint(db = Depends(get_db)):
            result = await db.execute("SELECT ...")
    """
    async with _pool.connection() as conn:
        yield conn
