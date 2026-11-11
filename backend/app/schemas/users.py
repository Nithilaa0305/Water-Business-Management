# ============================================================
# FILE: backend/app/schemas/users.py
# PURPOSE: Request and response validation models for users.
# ============================================================

from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime
from uuid import UUID

# Roles allowed in the system: defined by database constraint chk_user_role
UserRole = Literal["owner", "manager", "employee"]


class UserCreateRequest(BaseModel):
    """
    Data required to create a new user.
    Only the owner is allowed to call this endpoint.
    """
    full_name: str = Field(..., min_length=2, max_length=150, description="User's full real name")
    username: str = Field(..., min_length=3, max_length=50, description="Unique login username")
    pin: str = Field(..., min_length=4, max_length=8, pattern=r"^\d{4,8}$", description="4 to 8 digit personal PIN")
    role: UserRole = Field(..., description="Role: 'owner', 'manager', or 'employee'")


class UserResponse(BaseModel):
    """
    Data returned when viewing user information.
    NOTE: 'pin_hash' is strictly excluded for security!
    """
    user_id: UUID
    full_name: str
    username: str
    user_role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserStatusUpdate(BaseModel):
    """
    Used by the owner to activate or deactivate an existing user.
    """
    is_active: bool
