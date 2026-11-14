# ============================================================
# FILE: backend/app/routers/lists.py
# PURPOSE: CRUD operations for drop-down lookup lists:
#          units, categories, areas, payment methods,
#          expense categories, and customer groups.
# ============================================================

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection

from app.database import get_db
from app.security import get_current_user, require_role
from app.schemas.lists import (
    ListItemCreate,
    ListItemResponse,
    CustomerGroupCreate,
    CustomerGroupResponse,
    AllListsBundleResponse
)

router = APIRouter(prefix="/lists", tags=["Lookup Lists"])


# Helper function for generic list queries
async def _get_items(table: str, id_col: str, name_col: str, db: AsyncConnection) -> List[ListItemResponse]:
    result = await db.execute(f"SELECT {id_col} AS id, {name_col} AS name, is_active FROM {table} ORDER BY {name_col} ASC")
    rows = await result.fetchall()
    return [ListItemResponse(**r) for r in rows]


async def _add_item(table: str, id_col: str, name_col: str, name: str, db: AsyncConnection) -> ListItemResponse:
    try:
        result = await db.execute(
            f"INSERT INTO {table} ({name_col}) VALUES (%s) RETURNING {id_col} AS id, {name_col} AS name, is_active",
            (name.strip(),)
        )
        row = await result.fetchone()
        return ListItemResponse(**row)
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"'{name}' already exists.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ------------------ Units ------------------
@router.get("/units", response_model=List[ListItemResponse])
async def list_units(current_user: dict = Depends(get_current_user), db: AsyncConnection = Depends(get_db)):
    """List all measurement units (e.g., piece, bottle, can, case)."""
    return await _get_items("units", "unit_id", "unit_name", db)


@router.post("/units", response_model=ListItemResponse, status_code=status.HTTP_201_CREATED)
async def create_unit(
    body: ListItemCreate,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """Add a new measurement unit (Manager or Owner)."""
    return await _add_item("units", "unit_id", "unit_name", body.name, db)


# ------------------ Categories ------------------
@router.get("/categories", response_model=List[ListItemResponse])
async def list_categories(current_user: dict = Depends(get_current_user), db: AsyncConnection = Depends(get_db)):
    """List all product categories."""
    return await _get_items("categories", "category_id", "category_name", db)


@router.post("/categories", response_model=ListItemResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: ListItemCreate,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """Add a new product category (Manager or Owner)."""
    return await _add_item("categories", "category_id", "category_name", body.name, db)


# ------------------ Areas / Delivery Routes ------------------
@router.get("/areas", response_model=List[ListItemResponse])
async def list_areas(current_user: dict = Depends(get_current_user), db: AsyncConnection = Depends(get_db)):
    """List delivery areas/routes."""
    return await _get_items("areas", "area_id", "area_name", db)


@router.post("/areas", response_model=ListItemResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    body: ListItemCreate,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """Add a new delivery area or route (Manager or Owner)."""
    return await _add_item("areas", "area_id", "area_name", body.name, db)


# ------------------ Payment Methods ------------------
@router.get("/payment-methods", response_model=List[ListItemResponse])
async def list_payment_methods(current_user: dict = Depends(get_current_user), db: AsyncConnection = Depends(get_db)):
    """List payment methods (Cash, Bank Transfer, Cheque, Card)."""
    return await _get_items("payment_methods", "method_id", "method_name", db)


@router.post("/payment-methods", response_model=ListItemResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_method(
    body: ListItemCreate,
    current_user: dict = Depends(require_role("owner")),
    db: AsyncConnection = Depends(get_db)
):
    """Add a new payment method (Owner only)."""
    return await _add_item("payment_methods", "method_id", "method_name", body.name, db)


# ------------------ Expense Categories ------------------
@router.get("/expense-categories", response_model=List[ListItemResponse])
async def list_expense_categories(current_user: dict = Depends(get_current_user), db: AsyncConnection = Depends(get_db)):
    """List expense categories (Fuel, Salary, Rent, Electricity...)."""
    return await _get_items("expense_categories", "expense_category_id", "expense_category_name", db)


@router.post("/expense-categories", response_model=ListItemResponse, status_code=status.HTTP_201_CREATED)
async def create_expense_category(
    body: ListItemCreate,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """Add an expense category (Manager or Owner)."""
    return await _add_item("expense_categories", "expense_category_id", "expense_category_name", body.name, db)


# ------------------ Customer Groups ------------------
@router.get("/customer-groups", response_model=List[CustomerGroupResponse])
async def list_customer_groups(current_user: dict = Depends(get_current_user), db: AsyncConnection = Depends(get_db)):
    """List all customer groups and their batch rules ('oldest' or 'newest')."""
    result = await db.execute("SELECT group_id, group_name, batch_rule, is_active FROM customer_groups ORDER BY group_name ASC")
    rows = await result.fetchall()
    return [CustomerGroupResponse(**r) for r in rows]


@router.post("/customer-groups", response_model=CustomerGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_customer_group(
    body: CustomerGroupCreate,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """Add a new customer group (Manager or Owner)."""
    try:
        result = await db.execute(
            """
            INSERT INTO customer_groups (group_name, batch_rule)
            VALUES (%s, %s)
            RETURNING group_id, group_name, batch_rule, is_active
            """,
            (body.group_name.strip(), body.batch_rule)
        )
        row = await result.fetchone()
        return CustomerGroupResponse(**row)
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Group '{body.group_name}' already exists.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ------------------ Combined Bundle ------------------
@router.get("/all", response_model=AllListsBundleResponse)
async def get_all_lists_bundle(current_user: dict = Depends(get_current_user), db: AsyncConnection = Depends(get_db)):
    """
    Returns ALL dropdown lookup lists in a single request.
    Optimizes frontend load time by fetching all selection options together.
    """
    units = await _get_items("units", "unit_id", "unit_name", db)
    categories = await _get_items("categories", "category_id", "category_name", db)
    areas = await _get_items("areas", "area_id", "area_name", db)
    payment_methods = await _get_items("payment_methods", "method_id", "method_name", db)
    expense_categories = await _get_items("expense_categories", "expense_category_id", "expense_category_name", db)

    groups_res = await db.execute("SELECT group_id, group_name, batch_rule, is_active FROM customer_groups ORDER BY group_name ASC")
    customer_groups = [CustomerGroupResponse(**r) for r in await groups_res.fetchall()]

    return AllListsBundleResponse(
        units=units,
        categories=categories,
        areas=areas,
        payment_methods=payment_methods,
        expense_categories=expense_categories,
        customer_groups=customer_groups
    )
