# ============================================================
# FILE: backend/app/schemas/auth.py
# PURPOSE: Defines the shape (structure) of data for auth requests
#          and responses. Pydantic checks all data automatically.
# ============================================================

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SignInRequest(BaseModel):
    """
    What the frontend can send to sign in.
    Supports either:
        { "username": "kumar", "pin": "3333" }
    or (from role-based UI):
        { "role": "employee", "pin": "3333" }
    """
    username: Optional[str] = Field(default=None, description="The user's username")
    role: Optional[str] = Field(default=None, description="The selected role (owner/manager/employee)")
    pin: str = Field(..., min_length=4, max_length=8, pattern=r'^\d{4,8}$',
                     description="4 to 8 digit PIN")


class TokenResponse(BaseModel):
    """
    What the API sends back after a successful sign-in.
    """
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str
    user: Optional[Dict[str, Any]] = None


class SignOutRequest(BaseModel):
    """
    Optional body for sign-out.
    The frontend can say WHY the user is signing out.
    """
    reason: str = Field(default="manual",
                        description="Reason: 'manual', 'auto', or 'switched_user'")
