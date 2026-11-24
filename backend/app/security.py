# ============================================================
# FILE: backend/app/security.py
# PURPOSE: Everything related to JWT tokens (login tokens).
#          Creates tokens, reads tokens, and rejects bad tokens.
# ============================================================

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt         # For creating and reading JWT tokens
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer  # Reads the token from the request header
from dotenv import load_dotenv
from psycopg import AsyncConnection

from app.database import get_db

load_dotenv()

# --- Settings (read from .env) ---
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = "HS256"                # The math algorithm used to sign the token
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# This tells FastAPI: "To get a token, send a POST to /auth/sign-in"
# It also automatically looks for the token in the "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/sign-in")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a JWT token (a long encoded string) that the frontend stores after login.
    The token contains the user's ID, session ID, and role.
    It expires after ACCESS_TOKEN_EXPIRE_MINUTES minutes.

    Example data: {"user_id": "abc-123", "session_id": "xyz-456", "role": "manager"}
    """
    to_encode = data.copy()

    # Set the expiry time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})  # Add expiry to the token data

    # Encode all the data into a compact signed string
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Reads and verifies a JWT token.
    If the token is expired, tampered with, or fake — raises an error.
    If valid, returns the data inside (user_id, session_id, role).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token is invalid or has expired. Please sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        return payload  # Returns the full dict: user_id, session_id, role
    except JWTError:
        raise credentials_exception


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncConnection = Depends(get_db)) -> dict:
    claims = decode_token(token)
    result = await db.execute("""
        SELECT u.user_role, u.full_name
        FROM user_sessions s JOIN app_users u USING (user_id)
        WHERE s.session_id::text = %s AND s.user_id::text = %s
          AND s.signed_out_at IS NULL AND u.is_active
    """, (claims.get("session_id"), claims.get("user_id")))
    user = await result.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Session ended. Please sign in again.")
    return {**claims, "role": user["user_role"], "full_name": user["full_name"]}


def require_role(*allowed_roles: str):
    """
    A role guard. Use this to block endpoints from certain roles.

    Usage:
        async def owner_only_endpoint(current_user = Depends(require_role("owner"))):
            ...

        async def manager_or_owner(current_user = Depends(require_role("owner", "manager"))):
            ...
    """
    async def check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role '{current_user.get('role')}' is not allowed to do this."
            )
        return current_user
    return check

