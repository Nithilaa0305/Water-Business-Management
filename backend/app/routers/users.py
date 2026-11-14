# ============================================================
# FILE: backend/app/routers/users.py
# PURPOSE: Endpoints for managing system users (Owner only).
#
# Endpoints:
#   POST  /users              → Create a new user (Owner only)
#   GET   /users              → List all users (Owner / Manager)
#   GET   /users/{user_id}    → Get specific user details
#   PATCH /users/{user_id}/status → Activate / deactivate user (Owner only)
# ============================================================

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from psycopg import AsyncConnection

from app.database import get_db
from app.security import get_current_user, require_role
from app.schemas.users import UserCreateRequest, UserResponse, UserStatusUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    body: UserCreateRequest,
    current_user: dict = Depends(require_role("owner")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Create a new user in the system.
    Only the 'owner' role can create users.

    - Calls database stored function: create_user(full_name, username, pin, role, acting_user_id)
    - Hashes the PIN using pgcrypto (bcrypt) inside PostgreSQL
    - Automatically records the creation event in the activity log
    """
    try:
        # Step 1: Call the PostgreSQL function create_user(...)
        result = await db.execute(
            "SELECT create_user(%s, %s, %s, %s, %s) AS new_id",
            (
                body.full_name.strip(),
                body.username.lower().strip(),
                body.pin,
                body.role,
                current_user["user_id"]
            )
        )
        row = await result.fetchone()
        new_user_id = row["new_id"]

        # Step 2: Fetch the newly created record to return to caller
        user_result = await db.execute(
            """
            SELECT user_id, full_name, username, user_role, is_active, created_at, updated_at
              FROM app_users
             WHERE user_id = %s
            """,
            (new_user_id,)
        )
        user_row = await user_result.fetchone()
        return UserResponse(**user_row)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "unique constraint" in error_msg.lower() or "app_users_username_key" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{body.username}' is already taken."
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)


@router.get("", response_model=List[UserResponse])
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role: 'owner', 'manager', 'employee'"),
    active_only: bool = Query(False, description="If true, return only active users"),
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    List all registered users.
    Owner and Manager can view the user list.
    """
    query = """
        SELECT user_id, full_name, username, user_role, is_active, created_at, updated_at
          FROM app_users
         WHERE 1=1
    """
    params = []

    if role:
        query += " AND user_role = %s"
        params.append(role)

    if active_only:
        query += " AND is_active = true"

    query += " ORDER BY created_at ASC"

    result = await db.execute(query, tuple(params))
    rows = await result.fetchall()
    return [UserResponse(**r) for r in rows]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Get detailed information about a specific user by their user_id.
    """
    result = await db.execute(
        """
        SELECT user_id, full_name, username, user_role, is_active, created_at, updated_at
          FROM app_users
         WHERE user_id = %s
        """,
        (user_id,)
    )
    row = await result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} was not found."
        )
    return UserResponse(**row)


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: UUID,
    body: UserStatusUpdate,
    current_user: dict = Depends(require_role("owner")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Activate or deactivate a user account.
    Only the 'owner' role can change user status.
    Prevent deactivating oneself.
    """
    if str(user_id) == str(current_user["user_id"]) and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own owner account."
        )

    # Check if user exists
    check_res = await db.execute("SELECT full_name, user_role FROM app_users WHERE user_id = %s", (user_id,))
    target_user = await check_res.fetchone()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Update status
    result = await db.execute(
        """
        UPDATE app_users
           SET is_active = %s, updated_at = CURRENT_TIMESTAMP
         WHERE user_id = %s
        RETURNING user_id, full_name, username, user_role, is_active, created_at, updated_at
        """,
        (body.is_active, user_id)
    )
    updated_row = await result.fetchone()

    # Log activity into activity_log
    status_text = "activated" if body.is_active else "deactivated"
    action_desc = f"{current_user.get('full_name')} {status_text} user {target_user['full_name']} ({target_user['user_role']})"
    await db.execute(
        "SELECT log_activity(%s, 'user_status_changed', %s, 'user', %s)",
        (current_user["user_id"], action_desc, user_id)
    )

    return UserResponse(**updated_row)
