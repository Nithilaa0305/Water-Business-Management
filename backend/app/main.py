# ============================================================
# FILE: backend/app/main.py
# PURPOSE: The entry point of the entire backend application.
#          Creates the FastAPI app, registers all routers,
#          and starts/stops the database connection.
# ============================================================

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, close_db
from app.routers import auth, users, lists, operations


# --- Lifespan: runs startup and shutdown code ---
# @asynccontextmanager means this function runs at start AND at end
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === STARTUP: runs when the server starts ===
    print("🚀 Starting up: connecting to database...")
    await init_db()
    print("✅ Database connected. Server is ready.")

    yield  # <-- The app runs here (between startup and shutdown)

    # === SHUTDOWN: runs when the server stops (Ctrl+C) ===
    print("🔌 Shutting down: closing database connections...")
    await close_db()
    print("✅ Database closed cleanly.")


# --- Create the FastAPI app ---
app = FastAPI(
    title="Wholesale Billing System API",
    description="Backend API for the wholesale shop billing and stock management system.",
    version="1.0.0",
    lifespan=lifespan
)

# --- CORS Middleware ---
# CORS = Cross-Origin Resource Sharing
# This allows the frontend (running on a different port or domain) to call our API.
# During development, we allow all origins ("*").
# Before going live, change "*" to the exact frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # During dev: allow all. Production: use specific URL
    allow_credentials=True,
    allow_methods=["*"],        # Allow GET, POST, PUT, PATCH, DELETE
    allow_headers=["*"],        # Allow all headers including Authorization
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal Server Error"}
    )

# --- Register routers (each router = one module) ---
# As we build more modules, we import and add them here.
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(lists.router)
app.include_router(operations.router)
# app.include_router(products.router)
# app.include_router(customers.router)
# etc.


# --- Root endpoint (health check) ---
@app.get("/", tags=["Health"])
async def root():
    """
    Simple health check. If you visit http://localhost:8000/
    and see this response, the server is running correctly.
    """
    return {
        "status": "running",
        "app": "Wholesale Billing System API",
        "version": "1.0.0",
        "docs": "http://localhost:8000/docs"
    }


@app.get("/health", tags=["Health"])
async def health():
    """Another health check endpoint."""
    return {"status": "healthy"}

