# ============================================================
# FILE: backend/app/schemas/lists.py
# PURPOSE: Validation schemas for lookup lists (units, categories,
#          areas, payment methods, expense categories, groups).
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from uuid import UUID


class ListItemCreate(BaseModel):
    """Generic payload to add a new named entry in any lookup list."""
    name: str = Field(..., min_length=1, max_length=100, description="Name of the item")


class ListItemResponse(BaseModel):
    """Generic response representation of a lookup item."""
    id: UUID
    name: str
    is_active: bool


class CustomerGroupCreate(BaseModel):
    """Payload to create a customer group."""
    group_name: str = Field(..., min_length=1, max_length=100)
    batch_rule: Literal["oldest", "newest"] = Field(
        default="oldest",
        description="'oldest' for FIFO (regular customers), 'newest' for LIFO (new customers)"
    )


class CustomerGroupResponse(BaseModel):
    group_id: UUID
    group_name: str
    batch_rule: str
    is_active: bool


class AllListsBundleResponse(BaseModel):
    """
    Combined bundle of all system lookup lists.
    Allows frontend dropdowns to populate in a single API call!
    """
    units: List[ListItemResponse]
    categories: List[ListItemResponse]
    areas: List[ListItemResponse]
    payment_methods: List[ListItemResponse]
    expense_categories: List[ListItemResponse]
    customer_groups: List[CustomerGroupResponse]
