# ============================================================
# FILE: backend/app/schemas/auth.py
# PURPOSE: Defines the shape (structure) of data for auth requests
#          and responses. Pydantic checks all data automatically.
# ============================================================

from pydantic import BaseModel, Field


class SignInRequest(BaseModel):
    """
    What the frontend must send to sign in.
    Example JSON body:
        { "username": "kumar", "pin": "1234" }
    """
    username: str = Field(..., min_length=1, description="The user's username")
    pin: str = Field(..., min_length=4, max_length=8, pattern=r'^\d{4,8}$',
                     description="4 to 8 digit PIN")


class TokenResponse(BaseModel):
    """
    What the API sends back after a successful sign-in.
    Example response:
        {
            "access_token": "eyJhbGci...",
            "token_type": "bearer",
            "user_id": "abc-123",
            "full_name": "Kumar",
            "role": "employee"
        }
    """
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str


class SignOutRequest(BaseModel):
    """
    Optional body for sign-out.
    The frontend can say WHY the user is signing out.
    """
    reason: str = Field(default="manual",
                        description="Reason: 'manual', 'auto', or 'switched_user'")

