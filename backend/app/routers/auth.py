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
    Sign in with username and PIN.

    - Calls the database function: sign_in(username, pin)
    - The DB function checks the PIN using bcrypt (secure hashing)
    - If correct, the DB creates a session and returns a session_id
    - We then wrap that session_id in a JWT token and return it

    The frontend stores this token and sends it with every future request.
    """
    try:
        # Step 1: Call the database sign_in() function
        # This checks the PIN and creates a session in user_sessions table
        result = await db.execute(
            "SELECT sign_in(%s, %s) AS session_id",
            (body.username.lower().strip(), body.pin)
        )
        row = await result.fetchone()
        session_id = str(row["session_id"])

        # Step 2: Get the user's details (name, role) so we can put them in the token
        user_result = await db.execute(
            "SELECT user_id, full_name, user_role FROM app_users WHERE username = %s AND is_active",
            (body.username.lower().strip(),)
        )
        user = await user_result.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="User not found after sign-in")

        # Step 3: Create the JWT token
        # The token contains user_id, session_id, and role
        # The frontend will send this token in the Authorization header for all future requests
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

        # Step 4: Return the token and user info to the frontend
        return TokenResponse(
            access_token=access_token,
            user_id=str(user["user_id"]),
            full_name=user["full_name"],
            role=user["user_role"]
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
        return {"message": f"Signed out successfully. Goodbye, {current_user.get('full_name')}!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Returns information about the currently logged-in user.
    The frontend can call this to show the user's name and role.

    No DB query needed — all info is already in the JWT token.
    """
    return {
        "user_id": current_user.get("user_id"),
        "full_name": current_user.get("full_name"),
        "role": current_user.get("role")
    }

