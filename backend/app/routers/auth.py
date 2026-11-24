# ============================================================
# FILE: backend/app/routers/auth.py
# PURPOSE: Authentication endpoints — sign in and sign out.
#
# Endpoints:
#   POST /auth/sign-in   → Returns a JWT token
#   POST /auth/sign-out  → Invalidates the session
#   GET  /auth/me        → Returns current logged-in user info
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection

from app.database import get_db
from app.security import (
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.schemas.auth import SignInRequest, TokenResponse, SignOutRequest
from datetime import timedelta

# APIRouter groups related endpoints together.
# prefix="/auth" means all URLs in this file start with /auth
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/sign-in", response_model=TokenResponse)
async def sign_in(body: SignInRequest, db: AsyncConnection = Depends(get_db)):
    """
    Sign in with username (or role) and PIN.

    - Supports username/pin as well as role/pin from the POS frontend
    - Calls the database function: sign_in(username, pin)
    - Returns JWT token and user info
    """
    try:
        username = None
        if body.username:
            username = body.username.lower().strip()
        elif body.role:
            role_target = body.role.lower().strip()
            # Find user with matching role and matching PIN hash
            user_match = await db.execute(
                """
                SELECT username FROM app_users
                WHERE user_role = %s AND is_active AND pin_hash = crypt(%s, pin_hash)
                LIMIT 1
                """,
                (role_target, body.pin)
            )
            matched_row = await user_match.fetchone()
            if matched_row:
                username = matched_row["username"]
            else:
                fallback = await db.execute(
                    "SELECT username FROM app_users WHERE (user_role = %s OR username = %s) AND is_active LIMIT 1",
                    (role_target, role_target)
                )
                fallback_row = await fallback.fetchone()
                if fallback_row:
                    username = fallback_row["username"]
                else:
                    raise HTTPException(status_code=401, detail=f"No user found for role '{body.role}'")
        else:
            raise HTTPException(status_code=400, detail="Must provide username or role")

        # Step 1: Call the database sign_in() function
        result = await db.execute(
            "SELECT sign_in(%s, %s) AS session_id",
            (username, body.pin)
        )
        row = await result.fetchone()
        session_id = str(row["session_id"])

        # Step 2: Get the user's details
        user_result = await db.execute(
            "SELECT user_id, full_name, user_role, username FROM app_users WHERE username = %s AND is_active",
            (username,)
        )
        user = await user_result.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="User not found after sign-in")

        # Step 3: Create the JWT token
        token_data = {
            "user_id": str(user["user_id"]),
            "session_id": session_id,
            "role": user["user_role"],
            "full_name": user["full_name"]
        }
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        await db.commit()
        # Step 4: Return the token and user info to the frontend
        return TokenResponse(
            access_token=access_token,
            user_id=str(user["user_id"]),
            full_name=user["full_name"],
            role=user["user_role"],
            user={
                "id": str(user["user_id"]),
                "name": user["full_name"],
                "full_name": user["full_name"],
                "role": user["user_role"],
                "username": user["username"]
            }
        )

    except HTTPException:
        raise  # Re-raise our own HTTP errors unchanged
    except Exception as e:
        # If the DB says "Wrong username or PIN", pass that message to the client
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/sign-out")
async def sign_out(
    body: SignOutRequest = SignOutRequest(),
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    """
    Sign out the currently logged-in user.

    - Reads the session_id from the JWT token (automatically via Depends)
    - Calls the database sign_out() function to close the session
    - The activity log records who signed out and when
    """
    try:
        session_id = current_user.get("session_id")
        await db.execute(
            "SELECT sign_out(%s, %s)",
            (session_id, body.reason)
        )
        await db.commit()
        return {"message": f"Signed out successfully. Goodbye, {current_user.get('full_name')}!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Returns information about the currently logged-in user.
    The frontend can call this to show the user's name and role.

    The token identifies the session; the dependency checks current role and access.
    """
    return {
        "user_id": current_user.get("user_id"),
        "full_name": current_user.get("full_name"),
        "role": current_user.get("role")
    }

