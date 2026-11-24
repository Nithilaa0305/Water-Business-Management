# ============================================================
# FILE: backend/app/routers/operations.py
# PURPOSE: Secure, hardened endpoints for POS Invoicing,
#          Stock Management (Batches & Audits), Customer CRM & Ledgers,
#          Price Adjustments, Payments, Returns, Containers, and Reports.
# ============================================================

import json
import hashlib
import os
from zoneinfo import ZoneInfo
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import UUID
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Header, status
from psycopg import AsyncConnection
from pydantic import BaseModel, Field

from app.database import get_db
from app.security import get_current_user, require_role

router = APIRouter(tags=["Operations"])


# ------------------ Durable Idempotency Engine ------------------
async def check_idempotency(db: AsyncConnection, key: str, payload_str: str) -> Optional[Dict[str, Any]]:
    """
    Checks if an operation key has already been executed or is currently in flight.
    Uses PostgreSQL to ensure persistence across server restarts.
    """
    h = hashlib.sha256(payload_str.encode()).hexdigest()
    inserted = await db.execute(
        "INSERT INTO api_idempotency (key, payload_hash, status) VALUES (%s, %s, 'in_flight') "
        "ON CONFLICT (key) DO NOTHING RETURNING key", (key, h)
    )
    if await inserted.fetchone():
        return None
    res = await db.execute("SELECT payload_hash, status, response_body FROM api_idempotency WHERE key = %s", (key,))
    row = await res.fetchone()
    if not row:
        raise HTTPException(status_code=409, detail="Operation status unavailable; retry the same request.")

    # Key exists
    if row["payload_hash"] != h:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key reused with a different request payload."
        )
    if row["status"] == "in_flight":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operation currently in flight. Check whether it saved."
        )
    # Status is completed
    return dict(row["response_body"]) if row["response_body"] else {}


async def commit_idempotency(db: AsyncConnection, key: str, response_data: Dict[str, Any]):
    await db.execute(
        """
        UPDATE api_idempotency 
        SET status = 'completed', 
            response_code = 200, 
            response_body = %s::jsonb, 
            updated_at = clock_timestamp() 
        WHERE key = %s
        """,
        (json.dumps(response_data), key)
    )


# ------------------ Request Schemas ------------------
class SaleItem(BaseModel):
    product_id: Optional[Any] = None
    type_id: Optional[Any] = None
    batch_id: Optional[Any] = None
    quantity: int = 1
    price: Optional[float] = None


class CreateSaleRequest(BaseModel):
    operation_id: Optional[str] = None
    customer_id: Optional[Any] = None
    items: List[SaleItem] = []
    payment_type: Optional[str] = "cash"  # "cash", "credit", "split"
    cash_received: Optional[float] = None
    amount_paid: Optional[float] = None
    apply_to_old_debt: Optional[bool] = True
    debt_payment_amount: Optional[float] = None
    expected_previous_balance: Optional[float] = None
    discount: Optional[float] = 0.0
    notes: Optional[str] = None
    empty_cans_returned: int = Field(0, ge=0)
    return_container_type_id: Optional[UUID] = None


class StockReceiveRequest(BaseModel):
    product_id: Optional[Any] = None
    type_id: Optional[Any] = None
    quantity: int = 1
    buying_price: Optional[float] = None
    selling_price: Optional[float] = None
    supplier_id: Optional[Any] = None
    invoice_no: Optional[str] = None
    notes: Optional[str] = None


class StockAdjustRequest(BaseModel):
    product_id: Optional[Any] = None
    type_id: Optional[Any] = None
    batch_id: Optional[Any] = None
    quantity: Optional[int] = None
    delta: Optional[int] = None
    reason: Optional[str] = "Stock count correction"
    reason_type: Optional[str] = "adjustment"  # "adjustment", "damaged", "expired"


class PriceChangeRequest(BaseModel):
    product_id: Optional[Any] = None
    type_id: Optional[Any] = None
    new_price: Optional[float] = None
    selling_price: Optional[float] = None
    notes: Optional[str] = "Price updated via POS"


class CreateCustomerRequest(BaseModel):
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    area: Optional[str] = None
    credit_limit: Optional[float] = 0.0
    notes: Optional[str] = None


class UpdateCustomerRequest(BaseModel):
    customer_id: Any
    name: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    credit_limit: Optional[float] = 15000.0
    notes: Optional[str] = ""


class CustomerArchiveRequest(BaseModel):
    customer_id: Any
    action: str = "archive"  # "archive" or "restore"


class ProductArchiveRequest(BaseModel):
    type_id: Any
    action: str = "archive"  # "archive" or "restore"


class CustomerTransactionRequest(BaseModel):
    customer_id: Optional[Any] = None
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    notes: Optional[str] = None
    operation_id: Optional[str] = None
    payment_method: Optional[str] = "cash"


class PaymentCorrectionRequest(BaseModel):
    payment_id: str
    new_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    method_id: Optional[UUID] = None
    payment_method: Optional[str] = None
    reason: Optional[str] = "Correction of mistake entry"


class PaymentVoidRequest(BaseModel):
    payment_id: str
    reason: Optional[str] = "Mistake payment voided"


class CreateProductRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    tamil_name: Optional[str] = Field(None, max_length=150)
    selling_price: float = Field(0, ge=0, allow_inf_nan=False)
    buying_price: Optional[float] = Field(None, ge=0, allow_inf_nan=False)
    initial_stock: Optional[int] = Field(0, ge=0)
    unit: Optional[str] = "bottle"
    is_returnable: Optional[bool] = False
    sku: Optional[str] = None


class UpdateProductRequest(BaseModel):
    type_id: Any
    name: str = Field(min_length=1, max_length=150)
    tamil_name: Optional[str] = Field(None, max_length=150)
    selling_price: Optional[float] = None
    buying_price: Optional[float] = None
    sku: Optional[str] = None


class ContainerMovementRequest(BaseModel):
    customer_id: Any
    type_id: Optional[Any] = None
    quantity: int = 1
    action: Optional[str] = "return"  # "return" or "give"
    sale_id: Optional[Any] = None
    notes: Optional[str] = None
    operation_id: Optional[str] = None


class ReturnItemRequest(BaseModel):
    sale_item_id: str
    quantity: int
    reason: str
    restock: bool = False
    operation_id: Optional[str] = None


class CancelSaleRequest(BaseModel):
    sale_id: str
    reason: str


# ============================================================
# 1. PRODUCTS & CATALOG
# ============================================================
@router.get("/products")
@router.get("/products/list")
async def list_products(
    show_archived: bool = False,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    """
    Returns product types with live available stock.
    Buying prices are strictly allowlisted to Owner and Manager.
    """
    role = current_user.get("role")
    is_manager_or_owner = role in ("owner", "manager")
    active_clause = "WHERE NOT t.is_active" if show_archived else "WHERE t.is_active"

    res = await db.execute(f"""
        SELECT 
            t.type_id,
            t.type_name,
            t.sku,
            t.default_selling_price,
            t.default_buying_price, t.tamil_name, t.low_stock_limit,
            t.is_returnable_container,
            t.is_active,
            u.unit_name,
            COALESCE(SUM(b.current_quantity), 0) AS stock
        FROM product_types t
        LEFT JOIN units u ON u.unit_id = t.unit_id
        LEFT JOIN stock_batches b ON b.type_id = t.type_id AND b.current_quantity > 0
        {active_clause}
        GROUP BY t.type_id, t.type_name, t.sku, t.default_selling_price, t.is_returnable_container, t.is_active, u.unit_name
        ORDER BY 
            CASE 
                WHEN t.type_name ILIKE '%500%ml%' THEN 1
                WHEN (t.type_name ILIKE '1 L%' OR t.type_name ILIKE '1L%') AND NOT t.type_name ILIKE '1.5%' AND NOT t.type_name ILIKE '19%' THEN 2
                WHEN t.type_name ILIKE '1.5%l%' THEN 3
                WHEN t.type_name ILIKE '5%l%' AND NOT t.type_name ILIKE '%500%' THEN 4
                WHEN t.type_name ILIKE '%19%l%water%' OR (t.type_name ILIKE '%19%l%' AND NOT t.is_returnable_container) THEN 5
                WHEN t.type_name ILIKE '%empty%' OR t.is_returnable_container THEN 6
                ELSE 10
            END ASC,
            t.type_name ASC
    """)
    rows = await res.fetchall()

    tamil_names = {
        "500 ml Water": "500மிலி தண்ணீர்",
        "1 L Water": "1 லிட்டர் தண்ணீர்",
        "1.5 L Water": "1.5 லிட்டர் தண்ணீர்",
        "5 L Water": "5 லிட்டர் தண்ணீர்",
        "19 L Water (filled)": "19 லிட்டர் கேன் (நிரப்பியது)",
        "19 L Bottle (empty/new)": "19 லிட்டர் காலி கேன் (புதியது)",
    }

    products = []
    for idx, r in enumerate(rows, start=1):
        name = r["type_name"]
        ta = r["tamil_name"] or tamil_names.get(name, name)
        is_can = "can" in (r["unit_name"] or "").lower() or "19" in name or "5 L" in name
        item = {
            "id": idx,
            "type_id": str(r["type_id"]),
            "sku": r["sku"] or "",
            "name": name,
            "ta": ta,
            "price": float(r["default_selling_price"] or 0),
            "stock": int(r["stock"] or 0),
            "low_stock_limit": r["low_stock_limit"],
            "unit": r["unit_name"] or "bottle",
            "is_returnable": bool(r["is_returnable_container"]),
            "is_active": bool(r["is_active"]),
            "icon": "can" if is_can else "bottle",
            "buying_price": float(r["default_buying_price"]) if (is_manager_or_owner and r.get("default_buying_price") is not None) else None,
        }
        products.append(item)
    return products


def stock_type_id(body) -> str:
    # Older clients may send the UUID under product_id; never interpret it as a row number or label.
    try:
        return str(UUID(str(body.type_id or body.product_id)))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Select a valid product variant") from None


@router.post("/products/price")
@router.post("/stock/price")
async def change_price_endpoint(
    body: PriceChangeRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Updates the default selling price AND active batch prices.
    Atomic: if any batch price update fails, the entire transaction fails (no swallowed errors).
    """
    user_id = current_user.get("user_id")
    type_id = stock_type_id(body)

    price_val = body.new_price if body.new_price is not None else body.selling_price
    if price_val is None or not Decimal(str(price_val)).is_finite() or price_val < 0:
        raise HTTPException(status_code=400, detail="Enter a valid nonnegative price")
    new_price = float(price_val)

    # Update product_types default selling price
    updated = await db.execute(
        "UPDATE product_types SET default_selling_price = %s, updated_at = CURRENT_TIMESTAMP WHERE type_id = %s::uuid AND is_active RETURNING type_id",
        (new_price, type_id)
    )

    if not await updated.fetchone():
        raise HTTPException(status_code=404, detail="Active product not found")

    # Update active batches selling price via SQL function set_batch_selling_price
    batches_res = await db.execute(
        "SELECT batch_id FROM stock_batches WHERE type_id = %s::uuid AND current_quantity > 0 ORDER BY received_date DESC, created_at DESC",
        (type_id,)
    )
    b_rows = await batches_res.fetchall()
    for b in b_rows:
        await db.execute(
            "SELECT set_batch_selling_price(%s::uuid, %s::uuid, %s::numeric, %s::text)",
            (user_id, str(b["batch_id"]), new_price, body.notes or "Price updated via POS")
        )

    # Log activity
    pt_info = await db.execute("SELECT type_name FROM product_types WHERE type_id = %s::uuid", (type_id,))
    p_row = await pt_info.fetchone()
    p_name = p_row["type_name"] if p_row else "item"
    await db.execute(
        "INSERT INTO activity_log (user_id, action_type, description) VALUES (%s, 'price_changed', %s)",
        (user_id, f"Changed selling price of {p_name} to Rs. {new_price}")
    )

    await db.commit()
    return {
        "status": "success",
        "type_id": type_id,
        "new_price": new_price,
        "message": f"Selling price of {p_name} updated to Rs. {new_price}"
    }


@router.post("/products/create")
async def create_product_endpoint(
    body: CreateProductRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    user_id = current_user.get("user_id")

    prod_res = await db.execute("SELECT product_id FROM products LIMIT 1")
    p_row = await prod_res.fetchone()
    if not p_row:
        c_res = await db.execute("INSERT INTO products (product_name) VALUES ('Drinking Water') RETURNING product_id")
        p_row = await c_res.fetchone()
    product_id = str(p_row["product_id"])

    unit_name = (body.unit or "bottle").strip().lower()
    u_res = await db.execute("SELECT unit_id FROM units WHERE LOWER(unit_name) = %s LIMIT 1", (unit_name,))
    u_row = await u_res.fetchone()
    if not u_row:
        raise HTTPException(status_code=400, detail="Unsupported selling unit")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Product name is required")
    if body.initial_stock and (body.buying_price is None or body.selling_price <= 0):
        raise HTTPException(status_code=400, detail="Opening stock needs a buying cost and a positive selling price")
    import uuid
    sku = body.sku.strip() if (body.sku and body.sku.strip()) else f"SKU-{uuid.uuid4().hex[:10].upper()}"
    ins_res = await db.execute(
        """INSERT INTO product_types (product_id, type_name, tamil_name, sku, unit_id,
                   default_selling_price, default_buying_price, is_returnable_container)
           VALUES (%s::uuid,%s,%s,%s,%s::uuid,%s,%s,%s) RETURNING type_id""",
        (product_id, body.name.strip(), (body.tamil_name or "").strip() or None, sku, str(u_row["unit_id"]),
         body.selling_price, body.buying_price, body.is_returnable),
    )
    new_pt = await ins_res.fetchone()
    type_id = str(new_pt["type_id"])

    batch_id = None
    if body.initial_stock and body.initial_stock > 0:
        b_price = max(0.0, float(body.buying_price or 0.0))
        s_price = max(0.0, float(body.selling_price or 0.0))
        rec_res = await db.execute(
            """
            SELECT receive_stock(
                %s::uuid,
                %s::uuid,
                %s::integer,
                %s::numeric,
                %s::numeric,
                NULL::uuid,
                'INIT-001',
                NULL::date,
                CURRENT_DATE,
                'Initial stock upon product creation'
            )
            """,
            (user_id, type_id, int(body.initial_stock), b_price, s_price)
        )
        b_row = await rec_res.fetchone()
        batch_id = str(list(b_row.values())[0]) if b_row else None

    await db.commit()

    return {
        "status": "success",
        "type_id": type_id,
        "sku": sku,
        "batch_id": batch_id,
        "name": body.name,
        "message": f"Product '{body.name}' created successfully."
    }


@router.post("/products/update")
async def update_product_endpoint(
    body: UpdateProductRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    user_id = current_user.get("user_id")
    tid = str(body.type_id)

    updates = ["type_name = %s"]
    params = [body.name.strip()]

    if body.selling_price is not None:
        new_sp = max(0.0, float(body.selling_price))
        updates.append("default_selling_price = %s")
        params.append(new_sp)

    if body.sku is not None and body.sku.strip():
        updates.append("sku = %s")
        params.append(body.sku.strip())

    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Product name is required")
    if "tamil_name" in body.model_fields_set:
        updates.append("tamil_name = %s")
        params.append((body.tamil_name or "").strip() or None)
    if "buying_price" in body.model_fields_set:
        if body.buying_price is not None and (not Decimal(str(body.buying_price)).is_finite() or body.buying_price < 0):
            raise HTTPException(status_code=400, detail="Buying cost must not be negative")
        updates.append("default_buying_price = %s")
        params.append(body.buying_price)

    params.append(tid)
    updated = await db.execute(
        f"UPDATE product_types SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE type_id = %s::uuid RETURNING type_id",
        tuple(params),
    )
    if not await updated.fetchone():
        raise HTTPException(status_code=404, detail="Product not found")

    if body.selling_price is not None:
        new_sp = max(0.0, float(body.selling_price))
        batches_res = await db.execute(
            "SELECT batch_id FROM stock_batches WHERE type_id = %s::uuid AND current_quantity > 0",
            (tid,)
        )
        for b in await batches_res.fetchall():
            await db.execute(
                "SELECT set_batch_selling_price(%s::uuid, %s::uuid, %s::numeric, 'Price updated')",
                (user_id, str(b["batch_id"]), new_sp)
            )

    await db.commit()

    return {
        "status": "success",
        "message": f"Product '{body.name}' updated successfully"
    }


@router.post("/products/archive")
@router.post("/products/delete")
async def archive_product_endpoint(
    body: ProductArchiveRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Archives or restores a product.
    Prevents archiving if there is stock currently on hand.
    """
    tid = str(body.type_id)
    locked = await db.execute("SELECT customer_id FROM customers WHERE customer_id = %s::uuid FOR UPDATE", (cid,))
    if not await locked.fetchone():
        raise HTTPException(status_code=404, detail="Customer not found")
    if body.action not in ("archive", "restore"):
        raise HTTPException(status_code=400, detail="Invalid customer archive action")
    if body.action == "archive":
        st_res = await db.execute(
            "SELECT COALESCE(SUM(current_quantity), 0) AS total_stock FROM stock_batches WHERE type_id = %s::uuid AND current_quantity > 0",
            (tid,)
        )
        st_row = await st_res.fetchone()
        cur_stock = int(st_row["total_stock"] or 0)
        if cur_stock > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot archive product with stock on hand ({cur_stock} units remaining). Adjust or sell stock first."
            )
        await db.execute("UPDATE product_types SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE type_id = %s::uuid", (tid,))
        await db.commit()
        return {"status": "success", "message": "Product archived successfully"}
    else:
        await db.execute("UPDATE product_types SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP WHERE type_id = %s::uuid", (tid,))
        await db.commit()
        return {"status": "success", "message": "Product restored successfully"}


# ============================================================
# 2. CHECKOUT & INVOICING (ATOMIC SPLIT & IDEMPOTENCY)
# ============================================================
@router.post("/sales/create")
async def create_sale_endpoint(
    body: CreateSaleRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    """
    Executes an atomic checkout in ONE PostgreSQL transaction:
    1. Validates durable idempotency key.
    2. Validates live customer balance.
    3. Allocates stock batches in FIFO/group order.
    4. Handles tender split (invoice payment vs old debt payment vs cash change).
    5. Returns exact accounting breakdown for receipts.
    """
    key = body.operation_id or (idempotency_key if isinstance(idempotency_key, str) else None)
    op_key = f"sale:{current_user['user_id']}:{key}" if key else None
    if op_key:
        cached = await check_idempotency(db, op_key, body.model_dump_json())
        if cached:
            return cached

    user_id = current_user.get("user_id")

    try:
        customer_uuid = str(UUID(str(body.customer_id)))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Select a valid customer before saving the invoice")
    chk = await db.execute(
        "SELECT balance FROM customers WHERE customer_id = %s::uuid AND is_active FOR UPDATE", (customer_uuid,)
    )
    c_row = await chk.fetchone()
    if not c_row:
        raise HTTPException(status_code=400, detail="Selected customer is no longer active; choose a customer again")
    current_cust_balance = Decimal(c_row["balance"] or 0)

    # Check for stale balance conflict
    if body.expected_previous_balance is not None:
        if Decimal(str(body.expected_previous_balance)) != current_cust_balance:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "stale_balance",
                    "message": "Customer balance changed since review. Please confirm updated split.",
                    "current_balance": float(current_cust_balance)
                }
            )

    pt_res = await db.execute("SELECT type_id, type_name, default_selling_price, is_returnable_container FROM product_types WHERE is_active")
    all_types = await pt_res.fetchall()
    type_by_uuid = {str(r["type_id"]): r for r in all_types}

    db_items = []
    calc_total = Decimal(0)

    for itm in body.items:
        chosen_type = None
        if itm.type_id:
            if str(itm.type_id) in type_by_uuid:
                chosen_type = type_by_uuid[str(itm.type_id)]
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Product with type_id {itm.type_id} is no longer available or inactive"
                )
        elif itm.product_id:
            chosen_type = type_by_uuid.get(str(itm.product_id).strip())

        if not chosen_type:
            raise HTTPException(status_code=400, detail="Invalid product item in invoice")

        price = Decimal(chosen_type["default_selling_price"] or 0)
        if price <= 0:
            raise HTTPException(status_code=400, detail=f"Set a selling price for {chosen_type['type_name']} before billing")
        if itm.price is not None and Decimal(str(itm.price)) != price:
            raise HTTPException(status_code=409, detail=f"Price changed for {chosen_type['type_name']}; refresh before confirming")
        if itm.quantity <= 0:
            raise HTTPException(status_code=400, detail="Invoice quantity must be positive")
        if itm.batch_id and current_user.get("role") not in ("owner", "manager"):
            raise HTTPException(status_code=403, detail="Batch override requires an owner or manager")
        item_entry = {"type_id": str(chosen_type["type_id"]), "quantity": itm.quantity, "price": str(price)}
        if itm.batch_id:
            item_entry["batch_id"] = str(itm.batch_id)
        db_items.append(item_entry)
        calc_total += price * itm.quantity

    if not db_items:
        raise HTTPException(status_code=400, detail="No valid items in invoice")

    zero = Decimal(0)
    discount = Decimal(str(body.discount or 0))
    if not discount.is_finite() or not zero <= discount <= calc_total or discount != discount.quantize(Decimal("0.01")):
        raise HTTPException(status_code=400, detail="Invalid discount")
    final_total = calc_total - discount
    if body.payment_type == "credit":
        invoice_amount_paid = debt_payment = cash_change = cash_received = zero
    elif body.payment_type in ("cash", "split", "custom"):
        tender = body.cash_received if body.cash_received is not None else body.amount_paid
        cash_received = Decimal(str(tender)) if tender is not None else final_total
        if not cash_received.is_finite() or cash_received < 0 or cash_received != cash_received.quantize(Decimal("0.01")):
            raise HTTPException(status_code=400, detail="Invalid cash amount")
        invoice_amount_paid = min(final_total, cash_received)
        excess = cash_received - invoice_amount_paid
        max_debt = min(max(zero, current_cust_balance), excess) if body.apply_to_old_debt else zero
        desired = Decimal(str(body.debt_payment_amount)) if body.debt_payment_amount is not None else max_debt
        if not desired.is_finite() or not zero <= desired <= max_debt or desired != desired.quantize(Decimal("0.01")):
            raise HTTPException(status_code=400, detail="Invalid old-debt allocation")
        debt_payment = desired
        cash_change = excess - debt_payment
    else:
        raise HTTPException(status_code=400, detail="Unsupported checkout payment mode")
    total_cash_collected = invoice_amount_paid + debt_payment

    items_json = json.dumps(db_items)

    try:
        # Execute in ONE PostgreSQL transaction
        res = await db.execute(
            """
            SELECT create_sale(
                %s::uuid,
                %s::uuid,
                %s::jsonb,
                %s::numeric,
                %s::numeric,
                (SELECT method_id FROM payment_methods WHERE method_name = 'Cash'),
                %s::text,
                false
            )
            """,
            (user_id, customer_uuid, items_json, discount, invoice_amount_paid, body.notes or f"Invoice payment ({body.payment_type})")
        )
        row = await res.fetchone()
        sale_id = str(list(row.values())[0]) if row else None

        # Fetch invoice number generated by sequence
        sale_info = await db.execute("SELECT sale_number FROM sales WHERE sale_id = %s::uuid", (sale_id,))
        s_row = await sale_info.fetchone()
        if not s_row:
            raise RuntimeError("Saved invoice number was not returned")
        invoice_number = s_row["sale_number"]

        # Post old debt collection separately from invoice payment
        debt_payment_id = None
        if debt_payment > 0:
            pay_res = await db.execute(
                """
                SELECT receive_payment(
                    %s::uuid,
                    %s::uuid,
                    %s::numeric,
                    (SELECT method_id FROM payment_methods WHERE method_name = 'Cash'),
                    NULL::uuid,
                    %s::text
                )
                """,
                (user_id, customer_uuid, debt_payment, f"Applied to prior debt during bill {invoice_number}")
            )
            p_row = await pay_res.fetchone()
            debt_payment_id = str(list(p_row.values())[0]) if p_row else None

        # Record returnable containers issued on this invoice in the same transaction
        returnable_counts = {}
        for itm in db_items:
            t_id = itm["type_id"]
            if t_id in type_by_uuid and type_by_uuid[t_id].get("is_returnable_container"):
                returnable_counts[t_id] = returnable_counts.get(t_id, 0) + itm["quantity"]

        for ret_type_id, qty in returnable_counts.items():
            if qty > 0:
                await db.execute(
                    """
                    SELECT record_container_movement(
                        %s::uuid,
                        %s::uuid,
                        %s::uuid,
                        %s::integer,
                        0::integer,
                        %s::uuid,
                        %s::text
                    )
                    """,
                    (user_id, customer_uuid, ret_type_id, qty, sale_id, f"Issued on bill {invoice_number}")
                )

        if body.empty_cans_returned:
            ret_type = body.return_container_type_id
            if not ret_type:
                candidates = await db.execute(
                    "SELECT type_id FROM customer_containers WHERE customer_id = %s::uuid AND held > 0 LIMIT 2",
                    (customer_uuid,),
                )
                rows = await candidates.fetchall()
                if len(rows) != 1:
                    raise HTTPException(status_code=400, detail="Can't identify a single held can type. Leave checkout cans at zero and settle by type in Pay / Return.")
                ret_type = rows[0]["type_id"]
            await db.execute(
                "SELECT record_container_movement(%s::uuid,%s::uuid,%s::uuid,0,%s,%s::uuid,%s)",
                (user_id, customer_uuid, str(ret_type), body.empty_cans_returned, sale_id, f"Returned during bill {invoice_number}"),
            )

        # Query updated container count for customer
        can_res = await db.execute(
            "SELECT COALESCE(SUM(held), 0) AS cans FROM customer_containers WHERE customer_id = %s::uuid",
            (customer_uuid,)
        )
        c_row = await can_res.fetchone()
        final_cans = int(c_row["cans"] or 0)

        # Final balance check
        bal_res = await db.execute("SELECT balance FROM customers WHERE customer_id = %s::uuid", (customer_uuid,))
        b_row = await bal_res.fetchone()
        final_balance = float(b_row["balance"] or 0)
    except HTTPException:
        raise
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))

    response_payload = {
        "status": "success",
        "sale_id": sale_id,
        "invoice_id": sale_id,
        "invoice_number": invoice_number,
        "total": float(final_total),
        "cash_received": float(cash_received),
        "amount_paid": float(invoice_amount_paid),
        "applied_to_bill": float(invoice_amount_paid),
        "applied_to_old_debt": float(debt_payment),
        "debt_payment_id": debt_payment_id,
        "change_returned": float(cash_change),
        "previous_balance": float(current_cust_balance),
        "new_balance": final_balance,
        "new_cans_balance": final_cans,
        "total_cash_collected": float(total_cash_collected),
        "message": f"Invoice {invoice_number} created successfully."
    }

    receipt = await get_invoice_details(invoice_number, {"role": "employee"}, db)
    receipt.update({
        "cash_received": float(cash_received), "change_returned": float(cash_change),
        "applied_to_old_debt": float(debt_payment), "debt_payment_id": debt_payment_id,
        "previous_balance": float(current_cust_balance),
        "customer_balance": final_balance, "current_customer_balance": final_balance,
        "amount_paid": float(invoice_amount_paid), "applied_to_bill": float(invoice_amount_paid),
    })
    await db.execute("UPDATE sales SET receipt_snapshot = %s::jsonb WHERE sale_id = %s::uuid", (json.dumps(receipt), sale_id))
    response_payload["receipt"] = receipt

    if op_key:
        await commit_idempotency(db, op_key, response_payload)

    await db.commit()
    return response_payload


@router.get("/invoices/list")
@router.get("/sales/list")
async def list_invoices(
    q: Optional[str] = None,
    date_filter: str = "all",
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    query = """
        SELECT 
            sale_id,
            sale_number AS invoice_number,
            sale_date,
            customer_name,
            group_name,
            subtotal,
            discount,
            total,
            amount_paid,
            due,
            status,
            made_by
        FROM v_sales_list
    """
    params = []
    filters = []
    if q and q.strip():
        filters.append("(customer_name ILIKE %s OR sale_number ILIKE %s)")
        params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
    if date_filter in ("today", "yesterday"):
        filters.append("sale_date = %s")
        params.append(shop_today() - timedelta(days=int(date_filter == "yesterday")))
    elif date_filter != "all":
        raise HTTPException(status_code=400, detail="Invalid date filter")
    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += " ORDER BY sale_date DESC, sale_number DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    res = await db.execute(query, tuple(params))
    rows = await res.fetchall()
    return [
        {
            "id": str(r["sale_id"]),
            "invoice_number": r["invoice_number"],
            "date": str(r["sale_date"]),
            "customer_name": r["customer_name"],
            "total": float(r["total"] or 0),
            "amount_paid": float(r["amount_paid"] or 0),
            "due": float(r["due"] or 0),
            "status": r["status"],
            "made_by": r["made_by"]
        }
        for r in rows
    ]


@router.get("/invoices/latest")
async def get_latest_invoice_endpoint(
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    """
    Returns the latest completed sale invoice for reprint / preview.
    Does NOT create any sale.
    """
    res = await db.execute(
        """
        SELECT sale_number 
        FROM sales 
        WHERE status = 'completed'
        ORDER BY sale_date DESC, created_at DESC 
        LIMIT 1
        """
    )
    row = await res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No invoices found")
    return await get_invoice_details(row["sale_number"], current_user, db)


@router.get("/invoices/details/{invoice_number}")
async def get_invoice_details(
    invoice_number: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    role = current_user.get("role")
    clean_id = invoice_number.strip()
    inv_res = await db.execute(
        """
        SELECT 
            s.sale_id,
            s.sale_number,
            s.sale_date,
            s.created_at,
            s.receipt_snapshot,
            s.total,
            s.subtotal,
            s.discount,
            s.amount_paid,
            s.status,
            c.customer_name,
            c.phone,
            c.address,
            c.balance AS current_customer_balance,
            u.full_name AS staff_name
        FROM sales s
        JOIN customers c ON c.customer_id = s.customer_id
        LEFT JOIN app_users u ON u.user_id = s.created_by
        WHERE lower(s.sale_number) = lower(%s) OR s.sale_id::text = %s
        LIMIT 1
        """,
        (clean_id, clean_id)
    )
    inv = await inv_res.fetchone()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    items_res = await db.execute(
        """
        SELECT 
            si.sale_item_id,
            si.type_id,
            COALESCE(p.product_name, 'Drinking Water') AS product_name,
            COALESCE(pt.type_name, 'Standard') AS type_name,
            pt.sku, pt.tamil_name,
            COALESCE(pt.is_returnable_container, FALSE) AS is_returnable_container,
            u.unit_name,
            si.quantity,
            si.unit_price,
            si.line_total,
            si.returned_quantity,
            si.buying_price
        FROM sale_items si
        LEFT JOIN product_types pt ON pt.type_id = si.type_id
        LEFT JOIN products p ON p.product_id = pt.product_id
        LEFT JOIN units u ON u.unit_id = pt.unit_id
        WHERE si.sale_id = %s::uuid
        ORDER BY si.sale_item_id ASC
        """,
        (str(inv["sale_id"]),)
    )
    item_rows = await items_res.fetchall()

    tamil_names = {
        "500 ml Water": "500மிலி தண்ணீர்",
        "1 L Water": "1 லிட்டர் தண்ணீர்",
        "1.5 L Water": "1.5 லிட்டர் தண்ணீர்",
        "5 L Water": "5 லிட்டர் தண்ணீர்",
        "19 L Water (filled)": "19 லிட்டர் கேன் (நிரப்பியது)",
        "19 L Bottle (empty/new)": "19 லிட்டர் காலி கேன் (புதியது)",
        "500 ml": "500மிலி",
        "1 L": "1 லிட்டர்",
        "1.5 L": "1.5 லிட்டர்",
        "5 L": "5 லிட்டர்",
        "19 L Filled Can": "19 லிட்டர் நிரப்பப்பட்ட கேன்",
        "19 L Empty Can": "19 லிட்டர் காலி கேன்",
    }

    items = []
    for itm in item_rows:
        unit = itm["unit_name"] or ("can" if itm["is_returnable_container"] else "bottle")
        calc_subtotal = float(itm["line_total"]) if itm["line_total"] is not None else float((itm["unit_price"] or 0) * (itm["quantity"] or 1))
        t_name = itm["type_name"]
        p_name = itm["product_name"]
        disp_name = t_name if p_name in ("Drinking Water", "General", "Product") or not p_name else f"{p_name} - {t_name}"
        ta_name = itm["tamil_name"] or tamil_names.get(t_name, tamil_names.get(disp_name, disp_name))

        entry = {
            "sale_item_id": str(itm["sale_item_id"]),
            "type_id": str(itm["type_id"]) if itm["type_id"] else "",
            "name": disp_name,
            "product_name": p_name,
            "type_name": t_name,
            "variant": t_name if t_name != disp_name else "",
            "ta": ta_name,
            "sku": itm["sku"] or "",
            "unit": unit,
            "quantity": int(itm["quantity"]),
            "price": float(itm["unit_price"] or 0),
            "subtotal": calc_subtotal,
            "returned_quantity": int(itm["returned_quantity"] or 0),
        }
        if role in ("owner", "manager"):
            entry["buying_price"] = float(itm["buying_price"] or 0)
        items.append(entry)

    # Check for linked prior debt payments made at checkout
    debt_pay_res = await db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS old_debt_amt FROM payments WHERE sale_id = %s::uuid AND notes ILIKE %s AND voided_at IS NULL AND position('[VOIDED' in notes) = 0",
        (str(inv["sale_id"]), "%prior debt%")
    )
    dp_row = await debt_pay_res.fetchone()
    applied_to_old_debt = float(dp_row["old_debt_amt"]) if dp_row else 0.0

    # Check for empty cans returned during this sale
    can_mov_res = await db.execute(
        "SELECT COALESCE(SUM(returned_qty), 0) AS cans_ret FROM container_movements WHERE sale_id = %s::uuid",
        (str(inv["sale_id"]),)
    )
    cm_row = await can_mov_res.fetchone()
    cans_returned = int(cm_row["cans_ret"]) if cm_row else 0

    # Historical customer ledger balance at the time this invoice was completed
    hist_ledger = await db.execute(
        """
        SELECT running_balance 
        FROM customer_ledger 
        WHERE reference_id = %s::uuid 
        ORDER BY entry_time DESC, ledger_id DESC 
        LIMIT 1
        """,
        (str(inv["sale_id"]),)
    )
    hl_row = await hist_ledger.fetchone()
    if hl_row and hl_row["running_balance"] is not None:
        historical_balance = float(hl_row["running_balance"])
    else:
        historical_balance = max(0.0, float(inv["total"] or 0) - float(inv["amount_paid"] or 0))

    if inv["receipt_snapshot"]:
        receipt = dict(inv["receipt_snapshot"])
        current_items = {item["sale_item_id"]: item for item in items}
        receipt["items"] = [
            {**item, "returned_quantity": current_items.get(item["sale_item_id"], {}).get("returned_quantity", 0)}
            for item in receipt["items"]
        ]
        return {**receipt, "status": inv["status"]}

    return {
        "sale_id": str(inv["sale_id"]),
        "invoice_number": inv["sale_number"],
        "date": inv["created_at"].isoformat(),
        "customer_name": inv["customer_name"],
        "customer_phone": inv["phone"] or "",
        "customer_address": inv["address"] or "",
        "current_customer_balance": historical_balance,
        "customer_balance": historical_balance,
        "staff_name": inv["staff_name"] or "Cashier",
        "subtotal": float(inv["subtotal"] or inv["total"] or 0),
        "discount": float(inv["discount"] or 0),
        "total": float(inv["total"] or 0),
        "amount_paid": max(0, float(inv["amount_paid"] or 0) - applied_to_old_debt),
        "applied_to_old_debt": applied_to_old_debt,
        "balance_due": max(0.0, float(inv["total"] or 0) - float(inv["amount_paid"] or 0) + applied_to_old_debt),
        "cans_returned": cans_returned,
        "status": inv["status"],
        "items": items
    }


# ============================================================
# 3. GOODS RETURNS & INVOICE CANCELLATION
# ============================================================
@router.post("/sales/return-item")
async def return_sale_item_endpoint(
    body: ReturnItemRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Executes PostgreSQL return_sale_item stored procedure:
    - Verifies quantity doesn't exceed sold quantity.
    - Restores inventory to batch.
    - Credits customer ledger balance.
    """
    user_id = current_user.get("user_id")
    op_key = f"item_return:{user_id}:{body.operation_id}" if body.operation_id else None
    if op_key:
        cached = await check_idempotency(db, op_key, body.model_dump_json())
        if cached:
            return cached
    try:
        res = await db.execute(
            "SELECT return_sale_item(%s::uuid, %s::uuid, %s::integer, %s::text, %s::boolean)",
            (user_id, body.sale_item_id, body.quantity, body.reason, body.restock)
        )
        row = await res.fetchone()
        return_id = str(list(row.values())[0]) if row else None
        response = {
            "status": "success",
            "return_id": return_id,
            "message": f"Successfully processed return of {body.quantity} item(s)."
        }
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    if op_key:
        await commit_idempotency(db, op_key, response)
    await db.commit()
    return response


@router.post("/sales/cancel")
async def cancel_sale_endpoint(
    body: CancelSaleRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Executes PostgreSQL cancel_sale procedure:
    - Restores all batch inventory.
    - Credits full bill total to customer ledger.
    - Marks bill cancelled.
    """
    user_id = current_user.get("user_id")
    try:
        await db.execute(
            "SELECT cancel_sale(%s::uuid, %s::uuid, %s::text)",
            (user_id, body.sale_id, body.reason)
        )
        await db.commit()
        return {
            "status": "success",
            "message": "Bill cancelled successfully and stock restored."
        }
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 4. STOCK RECEIVING, ADJUSTMENTS & BATCH QUEUE
# ============================================================
@router.post("/stock/receive")
async def receive_stock_endpoint(
    body: StockReceiveRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    user_id = current_user.get("user_id")

    type_id = stock_type_id(body)

    supp_id = None
    if body.supplier_id:
        chk_s = await db.execute("SELECT supplier_id FROM suppliers WHERE supplier_id = %s::uuid", (str(body.supplier_id),))
        s_row = await chk_s.fetchone()
        if s_row:
            supp_id = str(s_row["supplier_id"])

    type_info = await db.execute("""
        SELECT type_name, default_selling_price, default_buying_price
        FROM product_types WHERE type_id = %s::uuid AND is_active FOR UPDATE
    """, (type_id,))
    t_row = await type_info.fetchone()
    if not t_row:
        raise HTTPException(status_code=404, detail="Active product not found")
    type_name = t_row["type_name"]
    def_selling = float(t_row["default_selling_price"] or 0)
    def_buying = float(t_row["default_buying_price"]) if (t_row and t_row.get("default_buying_price") is not None) else None

    selling_price = float(body.selling_price) if body.selling_price is not None else def_selling
    if body.buying_price is not None:
        buying_price = float(body.buying_price)
    elif def_buying is not None:
        buying_price = def_buying
    else:
        raise HTTPException(
            status_code=400,
            detail="Buying cost is required when no default buying cost is set."
        )
    qty = body.quantity
    if qty <= 0 or not Decimal(str(buying_price)).is_finite() or buying_price < 0 or not Decimal(str(selling_price)).is_finite() or selling_price <= 0:
        raise HTTPException(status_code=400, detail="Enter a positive stock quantity, positive selling price and valid buying cost")

    res = await db.execute(
        """
        SELECT receive_stock(
            %s::uuid,
            %s::uuid,
            %s::integer,
            %s::numeric,
            %s::numeric,
            %s::uuid,
            %s::text,
            NULL::date,
            CURRENT_DATE,
            %s::text
        )
        """,
        (user_id, type_id, qty, buying_price, selling_price, supp_id, body.invoice_no or "STOCK-REC", body.notes or "Stock received")
    )
    row = await res.fetchone()
    batch_id = str(list(row.values())[0]) if row else None

    stock_res = await db.execute("SELECT COALESCE(SUM(current_quantity), 0) AS total_stock FROM stock_batches WHERE type_id = %s::uuid", (type_id,))
    st_row = await stock_res.fetchone()
    new_total = int(st_row["total_stock"] or 0)

    await db.commit()
    return {
        "status": "success",
        "batch_id": batch_id,
        "type_id": type_id,
        "product_name": type_name,
        "added_quantity": qty,
        "new_stock": new_total,
        "message": f"Received +{qty} of {type_name}. Stock is now {new_total}."
    }


@router.post("/stock/adjust")
async def adjust_stock_endpoint(
    body: StockAdjustRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Adjusts or writes off damaged stock on a SPECIFIC batch.
    """
    user_id = current_user.get("user_id")

    type_id = stock_type_id(body)

    # If specific batch specified, use it; otherwise pick active batch
    if body.batch_id:
        batch_res = await db.execute(
            "SELECT batch_id, current_quantity FROM stock_batches WHERE batch_id = %s::uuid AND type_id = %s::uuid FOR UPDATE",
            (str(body.batch_id), type_id)
        )
    else:
        batch_res = await db.execute(
            """
            SELECT batch_id, current_quantity 
            FROM stock_batches 
            WHERE type_id = %s::uuid AND current_quantity > 0 
            ORDER BY received_date ASC, created_at ASC 
            LIMIT 1 FOR UPDATE
            """,
            (type_id,)
        )
    b_row = await batch_res.fetchone()
    if not b_row:
        raise HTTPException(status_code=400, detail="No stock batch found for this item to adjust")

    batch_id = str(b_row["batch_id"])
    current_qty = int(b_row["current_quantity"] or 0)

    if body.delta is not None:
        new_qty = current_qty + body.delta
    elif body.quantity is not None and body.quantity > 0:
        new_qty = current_qty - body.quantity
    else:
        raise HTTPException(status_code=400, detail="Enter a stock change")
    if new_qty < 0:
        raise HTTPException(status_code=400, detail="Stock change would make the batch negative")

    reason_type = body.reason_type if body.reason_type in ('adjustment', 'damaged', 'expired') else 'adjustment'
    reason = body.reason or ("Damaged goods write-off" if reason_type == 'damaged' else "Stock count correction")

    await db.execute(
        "SELECT adjust_stock(%s::uuid, %s::uuid, %s::integer, %s::text, %s::text)",
        (user_id, batch_id, new_qty, reason, reason_type)
    )

    stock_res = await db.execute("SELECT COALESCE(SUM(current_quantity), 0) AS total_stock FROM stock_batches WHERE type_id = %s::uuid", (type_id,))
    st_row = await stock_res.fetchone()
    total_stock = int(st_row["total_stock"] or 0)

    await db.commit()
    return {
        "status": "success",
        "batch_id": batch_id,
        "type_id": type_id,
        "new_batch_quantity": new_qty,
        "new_total_stock": total_stock,
        "message": f"Stock adjusted: batch now {new_qty}, total stock {total_stock}"
    }


@router.get("/stock/batches")
async def get_stock_batches(
    type_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    role = current_user.get("role")
    query = """
        SELECT 
            b.batch_id,
            b.type_id,
            pt.type_name,
            b.batch_number,
            b.current_quantity,
            b.quantity_received,
            b.selling_price,
            b.buying_price,
            b.received_date,
            b.expiry_date
        FROM stock_batches b
        JOIN product_types pt ON pt.type_id = b.type_id
        WHERE b.current_quantity > 0
    """
    params = []
    if type_id:
        query += " AND b.type_id = %s::uuid"
        params.append(type_id)

    query += " ORDER BY b.received_date ASC, b.created_at ASC"
    res = await db.execute(query, tuple(params))
    rows = await res.fetchall()

    result = []
    for r in rows:
        item = {
            "batch_id": str(r["batch_id"]),
            "type_id": str(r["type_id"]),
            "type_name": r["type_name"],
            "batch_number": r["batch_number"],
            "current_quantity": int(r["current_quantity"]),
            "quantity_received": int(r["quantity_received"]),
            "selling_price": float(r["selling_price"] or 0),
            "received_date": str(r["received_date"]),
            "expiry_date": str(r["expiry_date"]) if r["expiry_date"] else None
        }
        if role in ("owner", "manager"):
            item["buying_price"] = float(r["buying_price"] or 0)
        result.append(item)
    return result


@router.get("/stock/movements")
async def get_stock_movements(
    type_id: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    query = """
        SELECT 
            t.transaction_id,
            t.created_at,
            t.transaction_type,
            t.quantity,
            t.quantity_change,
            t.reference_type,
            t.reference_note,
            b.batch_number,
            pt.type_name,
            u.full_name AS staff_name
        FROM inventory_transactions t
        JOIN stock_batches b ON b.batch_id = t.batch_id
        JOIN product_types pt ON pt.type_id = b.type_id
        LEFT JOIN app_users u ON u.user_id = t.created_by
    """
    params = []
    if type_id:
        query += " WHERE b.type_id = %s::uuid"
        params.append(type_id)

    query += " ORDER BY t.created_at DESC LIMIT %s"
    params.append(limit)

    res = await db.execute(query, tuple(params))
    rows = await res.fetchall()
    return [
        {
            "transaction_id": str(r["transaction_id"]),
            "date": str(r["created_at"]),
            "type": r["transaction_type"],
            "quantity": int(r["quantity"]),
            "quantity_change": int(r["quantity_change"]),
            "batch_number": r["batch_number"],
            "product_name": r["type_name"],
            "note": r["reference_note"] or "",
            "staff_name": r["staff_name"] or "Staff"
        }
        for r in rows
    ]


# ============================================================
# 5. CUSTOMERS CRM & LEDGER STATEMENT
# ============================================================
@router.get("/customers")
@router.get("/customers/list")
async def list_customers(
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    show_archived: bool = False,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    query = """
        SELECT 
            c.customer_id AS id,
            c.customer_name AS name,
            c.phone,
            c.address,
            c.credit_limit,
            c.balance,
            c.is_active,
            COALESCE(cc.held, 0) AS cans
        FROM customers c
        LEFT JOIN (
            SELECT customer_id, SUM(held) AS held FROM customer_containers GROUP BY customer_id
        ) cc ON cc.customer_id = c.customer_id
    """
    where_clauses = []
    params = []

    if show_archived:
        where_clauses.append("c.is_active = FALSE")
    else:
        where_clauses.append("c.is_active = TRUE")

    if q and q.strip():
        where_clauses.append("(c.customer_name ILIKE %s OR c.phone ILIKE %s OR c.address ILIKE %s)")
        q_wild = f"%{q.strip()}%"
        params.extend([q_wild, q_wild, q_wild])

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY c.balance DESC, c.customer_name ASC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    result = await db.execute(query, tuple(params))
    rows = await result.fetchall()
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "phone": r["phone"] or "",
            "address": r["address"] or "",
            "credit_limit": float(r["credit_limit"] or 0),
            "balance": float(r["balance"] or 0),
            "cans": int(r["cans"] or 0),
            "is_active": bool(r["is_active"])
        }
        for r in rows
    ]


@router.get("/customers/details/{customer_id}")
@router.get("/customers/{customer_id}")
async def get_customer_details(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    query = """
        SELECT 
            c.customer_id AS id,
            c.customer_name AS name,
            c.phone,
            c.address,
            c.credit_limit,
            c.balance,
            c.is_active,
            COALESCE(cc.held, 0) AS cans
        FROM customers c
        LEFT JOIN (
            SELECT customer_id, SUM(held) AS held FROM customer_containers GROUP BY customer_id
        ) cc ON cc.customer_id = c.customer_id
        WHERE c.customer_id = %s::uuid
        LIMIT 1
    """
    res = await db.execute(query, (customer_id,))
    r = await res.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Customer not found")
    containers = await db.execute("""
        SELECT cc.type_id, pt.type_name AS name, pt.tamil_name AS ta, cc.held
        FROM customer_containers cc JOIN product_types pt USING (type_id)
        WHERE cc.customer_id = %s::uuid AND cc.held > 0
        ORDER BY pt.type_name, cc.type_id
    """, (customer_id,))
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "phone": r["phone"] or "",
        "address": r["address"] or "",
        "credit_limit": float(r["credit_limit"] or 0),
        "balance": float(r["balance"] or 0),
        "cans": int(r["cans"] or 0),
        "container_types": await containers.fetchall(),
        "is_active": bool(r["is_active"])
    }


@router.post("/customers/create")
async def create_customer_endpoint(
    body: CreateCustomerRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    user_id = current_user.get("user_id")
    role = current_user.get("role")

    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Customer name is required")

    credit_limit = float(body.credit_limit or 0)
    if role == "employee" and credit_limit > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a manager or the owner can set customer credit limits."
        )

    res = await db.execute(
        """
        SELECT create_customer(
            %s::uuid,
            %s::text,
            %s::text,
            %s::text,
            NULL::uuid,
            %s::numeric,
            NULL::uuid,
            %s::text
        )
        """,
        (user_id, body.name.strip(), body.phone or "", body.address or "", credit_limit, body.notes or "")
    )
    row = await res.fetchone()
    new_id = str(list(row.values())[0]) if row else None

    return {
        "status": "success",
        "customer_id": new_id,
        "id": new_id,
        "name": body.name.strip(),
        "customer": {
            "id": new_id,
            "name": body.name.strip(),
            "phone": body.phone or "",
            "balance": 0.0,
            "cans": 0,
            "credit_limit": credit_limit,
            "is_active": True
        },
        "message": f"Customer '{body.name.strip()}' created successfully"
    }


@router.post("/customers/update")
async def update_customer_endpoint(
    body: UpdateCustomerRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    cid = str(body.customer_id)
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Customer name is required")

    await db.execute(
        """
        UPDATE customers
        SET customer_name = %s,
            phone = %s,
            address = %s,
            credit_limit = %s,
            notes = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE customer_id = %s::uuid
        """,
        (
            body.name.strip(),
            body.phone.strip() if body.phone else "",
            body.address.strip() if body.address else "",
            float(body.credit_limit or 0),
            body.notes.strip() if body.notes else "",
            cid,
        )
    )
    await db.commit()
    return {
        "status": "success",
        "message": f"Customer '{body.name.strip()}' updated successfully",
        "customer": {
            "id": cid,
            "name": body.name.strip(),
            "phone": body.phone or "",
            "address": body.address or "",
            "credit_limit": float(body.credit_limit or 0),
        }
    }


@router.post("/customers/archive")
@router.post("/customers/delete")
async def archive_customer_endpoint(
    body: CustomerArchiveRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    cid = str(body.customer_id)
    if body.action == "archive":
        # Block if unsettled balance or outstanding cans
        chk_res = await db.execute(
            """
            SELECT c.balance, COALESCE(SUM(cc.held), 0) AS cans 
            FROM customers c 
            LEFT JOIN customer_containers cc ON cc.customer_id = c.customer_id 
            WHERE c.customer_id = %s::uuid 
            GROUP BY c.customer_id, c.balance
            """,
            (cid,)
        )
        row = await chk_res.fetchone()
        if row:
            bal = float(row["balance"] or 0)
            cans = int(row["cans"] or 0)
            if abs(bal) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot archive customer with unsettled balance of Rs. {bal:,.2f}. Balance must be zero."
                )
            if cans > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot archive customer with {cans} outstanding returnable can(s). Settle cans first."
                )
        await db.execute("UPDATE customers SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE customer_id = %s::uuid", (cid,))
        await db.commit()
        return {"status": "success", "message": "Customer archived successfully"}
    else:
        await db.execute("UPDATE customers SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP WHERE customer_id = %s::uuid", (cid,))
        await db.commit()
        return {"status": "success", "message": "Customer restored successfully"}


@router.get("/customers/statement/{customer_id}")
async def get_customer_statement(
    customer_id: str,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    """
    Returns the real customer account statement ledger from customer_ledger.
    """
    res = await db.execute(
        """
        SELECT 
            l.ledger_id,
            l.customer_id,
            c.customer_name,
            l.entry_time,
            l.entry_type,
            l.reference_type,
            l.reference_id,
            l.note,
            l.debit,
            l.credit,
            l.running_balance,
            u.full_name AS entered_by,
            s.sale_number
        FROM customer_ledger l
        JOIN customers c ON c.customer_id = l.customer_id
        LEFT JOIN app_users u ON u.user_id = l.created_by
        LEFT JOIN sales s ON s.sale_id = l.reference_id
        WHERE l.customer_id = %s::uuid
        ORDER BY l.entry_time DESC
        LIMIT %s
        """,
        (customer_id, limit)
    )
    rows = await res.fetchall()
    return [
        {
            "id": str(r["ledger_id"]),
            "customer_name": r["customer_name"],
            "date": str(r["entry_time"]),
            "transaction_date": str(r["entry_time"]),
            "type": r["entry_type"],
            "entry_type": r["entry_type"],
            "reference_number": r["sale_number"] or r["note"] or "",
            "reference": r["sale_number"] or r["note"] or "",
            "description": r["note"] or "",
            "debit": float(r["debit"] or 0),
            "credit": float(r["credit"] or 0),
            "running_balance": float(r["running_balance"] or 0),
            "entered_by": r["entered_by"] or "Staff"
        }
        for r in rows
    ]


# ============================================================
# 6. PAYMENTS, CORRECTIONS & CAN MOVEMENT
# ============================================================
@router.post("/payments/receive")
async def receive_payment_endpoint(
    body: CustomerTransactionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    user_id = current_user.get("user_id")
    if not body.customer_id:
        raise HTTPException(status_code=400, detail="Customer ID is required")
    if not Decimal(str(body.amount)).is_finite() or body.amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    # Idempotency check
    op_key = f"payment:{user_id}:{body.operation_id}" if body.operation_id else None
    if op_key:
        cached = await check_idempotency(db, op_key, body.model_dump_json())
        if cached:
            return cached

    customer_res = await db.execute("SELECT customer_id FROM customers WHERE customer_id = %s::uuid AND is_active FOR UPDATE", (str(body.customer_id),))
    if not await customer_res.fetchone():
        raise HTTPException(status_code=400, detail="Customer is not active")

    # Only Cash and Bank Transfer can be entered as new settlements.
    method = {"cash": "Cash", "bank": "Bank Transfer", "bank transfer": "Bank Transfer"}.get(
        (body.payment_method or "cash").strip().lower()
    )
    if method is None:
        raise HTTPException(status_code=400, detail="Choose Cash or Bank Transfer")
    m_res = await db.execute("SELECT method_id FROM payment_methods WHERE method_name = %s AND is_active", (method,))
    m_row = await m_res.fetchone()
    if not m_row:
        raise HTTPException(status_code=400, detail="Payment method is not active")
    method_id = m_row["method_id"]

    try:
        res = await db.execute(
            """
            SELECT receive_payment(
                %s::uuid,
                %s::uuid,
                %s::numeric,
                %s::uuid,
                NULL::uuid,
                %s::text
            )
            """,
            (user_id, str(body.customer_id), body.amount, method_id, body.notes or f"Payment received ({body.payment_method or 'Cash'})")
        )
        row = await res.fetchone()
        payment_id = str(list(row.values())[0]) if row else None

        bal_res = await db.execute("SELECT balance FROM customers WHERE customer_id = %s::uuid", (str(body.customer_id),))
        b_row = await bal_res.fetchone()
        new_bal = float(b_row["balance"] or 0)

        response_payload = {
            "status": "success",
            "payment_id": payment_id,
            "new_balance": new_bal,
            "message": f"Payment of Rs. {body.amount} recorded. Customer balance is now Rs. {new_bal:,.2f}"
        }
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    if op_key:
        await commit_idempotency(db, op_key, response_payload)
    await db.commit()
    return response_payload


@router.get("/payments/recent")
async def get_recent_payments(
    customer_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    query = """
        SELECT 
            p.payment_id,
            p.customer_id,
            p.sale_id,
            c.customer_name,
            p.amount,
            p.payment_date,
            p.created_at,
            p.notes,
            pm.method_name
        FROM payments p
        JOIN customers c ON c.customer_id = p.customer_id
        LEFT JOIN payment_methods pm ON pm.method_id = p.method_id
        WHERE p.voided_at IS NULL AND position('[VOIDED' in upper(COALESCE(p.notes,''))) = 0
    """
    params = []
    if customer_id and customer_id != "all":
        query += " AND p.customer_id = %s::uuid"
        params.append(customer_id)

    query += " ORDER BY p.created_at DESC LIMIT 50"
    res = await db.execute(query, tuple(params))
    rows = await res.fetchall()
    return [
        {
            "payment_id": str(r["payment_id"]),
            "customer_id": str(r["customer_id"]),
            "customer_name": r["customer_name"],
            "amount": float(r["amount"] or 0),
            "payment_date": str(r["payment_date"]),
            "created_at": str(r["created_at"]),
            "method": r["method_name"] or "Cash",
            "notes": r["notes"] or "",
            "can_correct": r["sale_id"] is None and not (r["notes"] or "").startswith("Applied to prior debt during bill")
        }
        for r in rows
    ]


@router.post("/payments/correct")
async def correct_payment_endpoint(
    body: PaymentCorrectionRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    user_id = current_user.get("user_id")
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Enter a correction reason")
    if not Decimal(str(body.new_amount)).is_finite() or body.new_amount <= 0:
        raise HTTPException(status_code=400, detail="Enter a positive amount or use Void")
    original = await lock_unvoided_payment(db, body.payment_id)
    method_id = body.method_id or original["method_id"]
    if body.payment_method:
        name = body.payment_method.strip().lower()
        aliases = {"bank": "bank transfer", "upi": "bank transfer", "check": "cheque"}
        result = await db.execute("SELECT method_id FROM payment_methods WHERE lower(method_name) = %s", (aliases.get(name, name),))
        method_row = await result.fetchone()
        if not method_row:
            raise HTTPException(status_code=400, detail="Unsupported payment method")
        method_id = method_row["method_id"]
    if Decimal(str(body.new_amount)) == original["amount"] and method_id == original["method_id"]:
        raise HTTPException(status_code=400, detail="Nothing changed")
    await reverse_account_payment(db, original, user_id, reason)
    replacement = await db.execute(
        "SELECT receive_payment(%s::uuid,%s::uuid,%s::numeric,%s::uuid,NULL::uuid,%s)",
        (user_id, original["customer_id"], body.new_amount, method_id, f"Replacement for {body.payment_id}: {reason}"),
    )
    new_id = str((await replacement.fetchone())["receive_payment"])
    balance = await db.execute("SELECT balance FROM customers WHERE customer_id = %s", (original["customer_id"],))
    new_balance = float((await balance.fetchone())["balance"])
    await db.commit()
    return {"status": "success", "payment_id": new_id, "replaced_payment_id": body.payment_id,
            "old_amount": float(original["amount"]), "new_amount": float(body.new_amount),
            "new_balance": new_balance}


async def lock_unvoided_payment(db, payment_id):
    try:
        payment_id = UUID(str(payment_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payment ID")
    res = await db.execute(
        "SELECT payment_id, customer_id, amount, method_id, sale_id, notes, voided_at FROM payments WHERE payment_id = %s FOR UPDATE",
        (payment_id,),
    )
    row = await res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Payment not found")
    if row["voided_at"] or "[VOIDED" in (row["notes"] or "").upper():
        raise HTTPException(status_code=409, detail="Payment is already reversed")
    if row["sale_id"] or (row["notes"] or "").startswith("Applied to prior debt during bill"):
        raise HTTPException(status_code=409, detail="Invoice-linked money needs the invoice reconciliation workflow")
    return row


async def reverse_account_payment(db, row, user_id, reason):
    active = await db.execute("SELECT customer_id FROM customers WHERE customer_id = %s AND is_active FOR UPDATE", (row["customer_id"],))
    if not await active.fetchone():
        raise HTTPException(status_code=409, detail="Restore the customer before reversing a payment")
    res = await db.execute(
        "SELECT post_ledger(%s::uuid,'adjustment','payment',%s::uuid,%s::numeric,0,%s,%s::uuid)",
        (row["customer_id"], row["payment_id"], row["amount"], reason, user_id),
    )
    new_balance = float((await res.fetchone())["post_ledger"])
    await db.execute("UPDATE payments SET voided_at = clock_timestamp() WHERE payment_id = %s", (row["payment_id"],))
    await db.execute("SELECT log_activity(%s::uuid,'payment_reversed',%s,'payment',%s::uuid)", (user_id, reason, row["payment_id"]))
    return new_balance


@router.post("/payments/void")
async def void_payment_endpoint(
    body: PaymentVoidRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db),
):
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Enter a void reason")
    row = await lock_unvoided_payment(db, body.payment_id)
    balance = await reverse_account_payment(db, row, current_user["user_id"], reason)
    await db.commit()
    return {"status": "success", "payment_id": body.payment_id, "voided_amount": float(row["amount"]), "new_balance": balance}


@router.post("/containers/movement")
async def container_movement_endpoint(
    body: ContainerMovementRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    """
    Records physical movement of returnable empty containers.
    """
    user_id = current_user.get("user_id")
    customer_uuid = str(body.customer_id)

    # Idempotency check
    op_key = f"container:{user_id}:{body.operation_id}" if body.operation_id else None
    if op_key:
        cached = await check_idempotency(db, op_key, body.model_dump_json())
        if cached:
            return cached

    if body.quantity <= 0 or body.action not in ("give", "return"):
        raise HTTPException(status_code=400, detail="Enter a positive can quantity and valid movement")
    if body.type_id:
        type_uuid = str(body.type_id)
    elif body.action == "return":
        type_res = await db.execute(
            "SELECT type_id FROM customer_containers WHERE customer_id = %s::uuid AND held > 0 LIMIT 2",
            (customer_uuid,),
        )
        candidates = await type_res.fetchall()
        if len(candidates) != 1:
            raise HTTPException(status_code=400, detail="No single outstanding can type found; select the returnable type explicitly")
        type_uuid = str(candidates[0]["type_id"])
    else:
        type_res = await db.execute("SELECT type_id FROM product_types WHERE is_active AND is_returnable_container LIMIT 2")
        candidates = await type_res.fetchall()
        if len(candidates) != 1:
            raise HTTPException(status_code=400, detail="Select the returnable can type explicitly")
        type_uuid = str(candidates[0]["type_id"])
    customer_res = await db.execute("SELECT customer_id FROM customers WHERE customer_id = %s::uuid AND is_active FOR UPDATE", (customer_uuid,))
    if not await customer_res.fetchone():
        raise HTTPException(status_code=400, detail="Customer is not active")
    if body.sale_id:
        sale_res = await db.execute("SELECT sale_id FROM sales WHERE sale_id = %s::uuid AND customer_id = %s::uuid AND status = 'completed'", (str(body.sale_id), customer_uuid))
        if not await sale_res.fetchone():
            raise HTTPException(status_code=400, detail="Invoice does not belong to this customer or is not completed")

    p_given = body.quantity if body.action == "give" else 0
    p_returned = body.quantity if body.action != "give" else 0
    sale_uuid = str(body.sale_id) if body.sale_id else None

    try:
        res = await db.execute(
            """
            SELECT record_container_movement(
                %s::uuid,
                %s::uuid,
                %s::uuid,
                %s::integer,
                %s::integer,
                %s::uuid,
                %s::text
            )
            """,
            (user_id, customer_uuid, type_uuid, p_given, p_returned, sale_uuid, body.notes or "Empty bottle return")
        )
        row = await res.fetchone()
        new_held = list(row.values())[0] if row else 0

        total_res = await db.execute("SELECT COALESCE(SUM(held), 0) AS total FROM customer_containers WHERE customer_id = %s::uuid", (customer_uuid,))
        total_row = await total_res.fetchone()
        response_payload = {
            "status": "success",
            "type_held": new_held,
            "held": int(total_row["total"]),
            "new_cans_balance": int(total_row["total"]),
            "message": f"Empty container movement recorded. Customer now holds {new_held} container(s)."
        }
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    if op_key:
        await commit_idempotency(db, op_key, response_payload)
    await db.commit()
    return response_payload


# ============================================================
# 7. FINANCIAL REPORTS & AUDIT METRICS (AUTHENTIC ZERO DATA)
# ============================================================
@router.get("/dashboard/today")
async def get_dashboard_today(
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    """
    Returns authentic, real-time indicators for today.
    Employees do NOT receive profit figures in the response.
    """
    role = current_user.get("role")
    day = shop_today()
    totals = await report_totals(db, day, day)
    rest = await db.execute("""
        SELECT (SELECT COALESCE(SUM(balance),0) FROM customers WHERE balance > 0) AS debt,
               (SELECT COUNT(*) FROM customers WHERE is_active) AS customers,
               (SELECT COUNT(*) FROM v_stock_by_type WHERE low_stock) AS low_stock
    """)
    row = await rest.fetchone()
    return {
        "date": day.isoformat(), "sales": totals["net_sales"], "total_sales": totals["net_sales"],
        "cash": totals["cash_collections"], "cash_inflow": totals["cash_collections"],
        "total_collections_today": totals["collections"], "debt": float(row["debt"]),
        "lowStock": row["low_stock"], "customers": row["customers"],
        **({"profit": totals["gross_profit"], "profit_today": totals["gross_profit"]} if role in ("owner", "manager") else {}),
    }


def shop_zone() -> str:
    return os.getenv("SHOP_TIMEZONE", "Asia/Colombo")


def shop_today() -> date:
    return datetime.now(ZoneInfo(shop_zone())).date()


async def report_totals(db, start_date, end_date):
    # Returns affect the date they are credited, not the original sale date.
    # Legacy note-marked voids lack a timestamp; exclude them instead of fabricating a date.
    result = await db.execute("""
        WITH sold AS (
            SELECT COALESCE(SUM(total),0) AS sales, COUNT(*) AS bills
            FROM sales WHERE sale_date BETWEEN %(start)s AND %(end)s AND status = 'completed'
        ), cost AS (
            SELECT COALESCE(SUM(si.buying_price * si.quantity),0) AS cogs
            FROM sale_items si JOIN sales s USING(sale_id)
            WHERE s.sale_date BETWEEN %(start)s AND %(end)s AND s.status = 'completed'
        ), returned AS (
            SELECT COUNT(*) AS returns_count, COALESCE(SUM(credit_amount),0) AS returns_amount,
                   COALESCE(SUM(cost_amount),0) AS restored_cost
            FROM sale_returns WHERE timezone(%(zone)s, returned_at)::date BETWEEN %(start)s AND %(end)s
        ), flow AS (
            SELECT p.amount AS amount, m.method_name FROM payments p LEFT JOIN payment_methods m USING(method_id)
            WHERE p.payment_date BETWEEN %(start)s AND %(end)s
              AND position('[VOIDED' in upper(COALESCE(p.notes,''))) = 0
            UNION ALL
            SELECT -p.amount, m.method_name FROM payments p LEFT JOIN payment_methods m USING(method_id)
            WHERE timezone(%(zone)s, p.voided_at)::date BETWEEN %(start)s AND %(end)s
        ), collected AS (
            SELECT COALESCE(SUM(amount),0) AS collections,
                   COALESCE(SUM(amount) FILTER (WHERE method_name = 'Cash'),0) AS cash_collections
            FROM flow
        ), spent AS (
            SELECT COALESCE(SUM(amount),0) AS expenses FROM expenses WHERE expense_date BETWEEN %(start)s AND %(end)s
        )
        SELECT sales - returns_amount AS net_sales, cost.cogs - restored_cost AS cogs, bills,
               returns_count, returns_amount, collections, cash_collections, expenses
        FROM sold, cost, returned, collected, spent
    """, {"start": start_date, "end": end_date, "zone": shop_zone()})
    row = await result.fetchone()
    gross = row["net_sales"] - row["cogs"]
    return {**{k: float(v) for k, v in row.items()}, "bill_count": int(row["bills"]),
            "gross_profit": float(gross), "net_profit": float(gross - row["expenses"])}


@router.get("/reports/summary")
@router.get("/reports/monthly")
async def get_report_summary(
    period: str = "this_month", from_date: Optional[date] = None, to_date: Optional[date] = None,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db),
):
    today = shop_today()
    end_date = today
    if period == "today":
        start_date = today
    elif period == "this_week":
        start_date = today - timedelta(days=today.weekday())
    elif period == "this_month":
        start_date = today.replace(day=1)
    elif period == "custom" and from_date and to_date and from_date <= to_date:
        start_date, end_date = from_date, to_date
    else:
        raise HTTPException(status_code=400, detail="Select a valid reporting period")
    totals = await report_totals(db, start_date, end_date)
    return {**totals, "period": period, "from_date": str(start_date), "to_date": str(end_date),
            "sales": totals["net_sales"], "profit": totals["gross_profit"]}
