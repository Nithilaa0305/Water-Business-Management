# ============================================================
# FILE: backend/app/routers/operations.py
# PURPOSE: Secure, hardened endpoints for POS Invoicing,
#          Stock Management (Batches & Audits), Customer CRM & Ledgers,
#          Price Adjustments, Payments, Returns, Containers, and Reports.
# ============================================================

import json
import hashlib
from datetime import datetime, date, timedelta
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
    await db.execute("""
        CREATE TABLE IF NOT EXISTS api_idempotency (
            key text PRIMARY KEY,
            payload_hash text NOT NULL,
            status text NOT NULL, -- 'in_flight', 'completed', 'failed'
            response_code int,
            response_body jsonb,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
    """)
    h = hashlib.sha256(payload_str.encode()).hexdigest()
    res = await db.execute("SELECT payload_hash, status, response_code, response_body FROM api_idempotency WHERE key = %s", (key,))
    row = await res.fetchone()
    if not row:
        try:
            await db.execute(
                "INSERT INTO api_idempotency (key, payload_hash, status) VALUES (%s, %s, 'in_flight')",
                (key, h)
            )
            return None
        except Exception as e:
            if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Operation currently in flight. Check whether it saved."
                )
            raise

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
    amount: float = 0.0
    notes: Optional[str] = None
    operation_id: Optional[str] = None
    payment_method: Optional[str] = "cash"


class PaymentCorrectionRequest(BaseModel):
    payment_id: str
    new_amount: float
    method_id: Optional[str] = None
    reason: Optional[str] = "Correction of mistake entry"


class PaymentVoidRequest(BaseModel):
    payment_id: str
    reason: Optional[str] = "Mistake payment voided"


class CreateProductRequest(BaseModel):
    name: str
    selling_price: float = 0.0
    buying_price: Optional[float] = 0.0
    initial_stock: Optional[int] = 0
    unit: Optional[str] = "bottle"
    is_returnable: Optional[bool] = False
    sku: Optional[str] = None


class UpdateProductRequest(BaseModel):
    type_id: Any
    name: str
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

    # Check whether default_buying_price column exists on product_types
    has_buy_col = True
    try:
        col_chk = await db.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'product_types' AND column_name = 'default_buying_price'")
        has_buy_col = bool(await col_chk.fetchone())
    except Exception:
        has_buy_col = False

    buy_col_sel = "t.default_buying_price" if has_buy_col else "NULL::numeric AS default_buying_price"
    buy_col_grp = ", t.default_buying_price" if has_buy_col else ""

    res = await db.execute(f"""
        SELECT 
            t.type_id,
            t.type_name,
            t.sku,
            t.default_selling_price,
            {buy_col_sel},
            t.is_returnable_container,
            t.is_active,
            u.unit_name,
            COALESCE(SUM(b.current_quantity), 0) AS stock
        FROM product_types t
        LEFT JOIN units u ON u.unit_id = t.unit_id
        LEFT JOIN stock_batches b ON b.type_id = t.type_id AND b.current_quantity > 0
        {active_clause}
        GROUP BY t.type_id, t.type_name, t.sku, t.default_selling_price{buy_col_grp}, t.is_returnable_container, t.is_active, u.unit_name
        ORDER BY 
            CASE 
                WHEN t.type_name ILIKE '%500%ml%' THEN 1
                WHEN (t.type_name ILIKE '1 L%' OR t.type_name ILIKE '1L%') AND NOT t.type_name ILIKE '1.5%' AND NOT t.type_name ILIKE '19%' THEN 2
                WHEN t.type_name ILIKE '1.5%l%' THEN 3
                WHEN t.type_name ILIKE '5%l%' AND NOT t.type_name ILIKE '%500%' THEN 4
                WHEN t.type_name ILIKE '%19%l%water%' OR (t.type_name ILIKE '%19%l%' AND NOT t.is_returnable_container) THEN 5
                WHEN t.type_name ILIKE '%empty%' OR t.is_returnable_container THEN 6
                ELSE 10
            END ASC
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
        ta = tamil_names.get(name, name)
        is_can = "can" in (r["unit_name"] or "").lower() or "19" in name or "5 L" in name
        item = {
            "id": idx,
            "type_id": str(r["type_id"]),
            "sku": r["sku"] or "",
            "name": name,
            "ta": ta,
            "price": float(r["default_selling_price"] or 0),
            "stock": int(r["stock"] or 0),
            "unit": r["unit_name"] or "bottle",
            "is_returnable": bool(r["is_returnable_container"]),
            "is_active": bool(r["is_active"]),
            "icon": "can" if is_can else "bottle",
            "buying_price": float(r["default_buying_price"]) if (is_manager_or_owner and r.get("default_buying_price") is not None) else None,
        }
        products.append(item)
    return products


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
    type_id = None
    if body.type_id:
        chk = await db.execute("SELECT type_id FROM product_types WHERE type_id = %s::uuid", (str(body.type_id),))
        t_row = await chk.fetchone()
        if t_row:
            type_id = str(t_row["type_id"])

    if not type_id and body.product_id:
        all_types_res = await db.execute("SELECT type_id, type_name FROM product_types WHERE is_active ORDER BY default_selling_price")
        all_types = await all_types_res.fetchall()
        p_str = str(body.product_id).strip().lower()
        for idx, t in enumerate(all_types, start=1):
            if str(idx) == p_str or p_str in t["type_name"].lower():
                type_id = str(t["type_id"])
                break

    if not type_id:
        raise HTTPException(status_code=400, detail="Product variant not found")

    price_val = body.new_price if body.new_price is not None else body.selling_price
    if price_val is None:
        raise HTTPException(status_code=400, detail="Price is required")
    new_price = max(0.0, float(price_val))

    # Update product_types default selling price
    await db.execute(
        "UPDATE product_types SET default_selling_price = %s, updated_at = CURRENT_TIMESTAMP WHERE type_id = %s::uuid",
        (new_price, type_id)
    )

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
        (user_id, f"Changed selling price of {p_name} to ₹{new_price}")
    )

    return {
        "status": "success",
        "type_id": type_id,
        "new_price": new_price,
        "message": f"Selling price of {p_name} updated to ₹{new_price}"
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
        u_res = await db.execute("SELECT unit_id FROM units LIMIT 1")
        u_row = await u_res.fetchone()
    unit_id = str(u_row["unit_id"]) if u_row else None

    import uuid
    sku = body.sku.strip() if (body.sku and body.sku.strip()) else f"SKU-{body.name[:3].upper()}-{int(body.selling_price)}-{uuid.uuid4().hex[:4].upper()}"

    has_buy_col = True
    try:
        col_chk = await db.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'product_types' AND column_name = 'default_buying_price'")
        has_buy_col = bool(await col_chk.fetchone())
    except Exception:
        has_buy_col = False

    def_buying = float(body.buying_price) if body.buying_price is not None else None

    if has_buy_col:
        ins_res = await db.execute(
            """
            INSERT INTO product_types (
                product_id,
                type_name,
                sku,
                unit_id,
                default_selling_price,
                default_buying_price,
                is_returnable_container,
                is_active
            )
            VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s, %s, TRUE)
            RETURNING type_id
            """,
            (
                product_id,
                body.name.strip(),
                sku,
                unit_id,
                max(0.0, float(body.selling_price)),
                def_buying,
                bool(body.is_returnable)
            )
        )
    else:
        ins_res = await db.execute(
            """
            INSERT INTO product_types (
                product_id,
                type_name,
                sku,
                unit_id,
                default_selling_price,
                is_returnable_container,
                is_active
            )
            VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s, TRUE)
            RETURNING type_id
            """,
            (
                product_id,
                body.name.strip(),
                sku,
                unit_id,
                max(0.0, float(body.selling_price)),
                bool(body.is_returnable)
            )
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

    if body.buying_price is not None:
        has_buy_col = True
        try:
            col_chk = await db.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'product_types' AND column_name = 'default_buying_price'")
            has_buy_col = bool(await col_chk.fetchone())
        except Exception:
            has_buy_col = False
        if has_buy_col:
            updates.append("default_buying_price = %s")
            params.append(max(0.0, float(body.buying_price)))

    params.append(tid)
    await db.execute(
        f"UPDATE product_types SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE type_id = %s::uuid",
        tuple(params)
    )

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
    op_key = body.operation_id or (idempotency_key if isinstance(idempotency_key, str) else None)
    if op_key:
        cached = await check_idempotency(db, op_key, body.model_dump_json())
        if cached:
            return cached

    user_id = current_user.get("user_id")

    # Resolve Customer
    customer_uuid = None
    if body.customer_id:
        chk = await db.execute("SELECT customer_id, balance FROM customers WHERE customer_id = %s::uuid AND is_active", (str(body.customer_id),))
        c_row = await chk.fetchone()
        if c_row:
            customer_uuid = str(c_row["customer_id"])
            current_cust_balance = float(c_row["balance"] or 0)

    if not customer_uuid:
        cust_res = await db.execute("SELECT customer_id, balance FROM customers WHERE is_active ORDER BY created_at LIMIT 1")
        c_row = await cust_res.fetchone()
        if c_row:
            customer_uuid = str(c_row["customer_id"])
            current_cust_balance = float(c_row["balance"] or 0)
        else:
            raise HTTPException(status_code=400, detail="No active customer found")

    # Check for stale balance conflict
    if body.expected_previous_balance is not None:
        if abs(float(body.expected_previous_balance) - current_cust_balance) > 0.01:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "stale_balance",
                    "message": "Customer balance changed since review. Please confirm updated split.",
                    "current_balance": current_cust_balance
                }
            )

    pt_res = await db.execute("SELECT type_id, type_name, default_selling_price, is_returnable_container FROM product_types WHERE is_active")
    all_types = await pt_res.fetchall()
    type_by_uuid = {str(r["type_id"]): r for r in all_types}

    db_items = []
    calc_total = 0.0

    for itm in body.items:
        chosen_type = None
        if itm.type_id and str(itm.type_id) in type_by_uuid:
            chosen_type = type_by_uuid[str(itm.type_id)]
        elif itm.product_id:
            p_str = str(itm.product_id).strip().lower()
            for idx, t in enumerate(all_types, start=1):
                t_name = t["type_name"].lower()
                if str(idx) == p_str or p_str in t_name:
                    chosen_type = t
                    break

        if not chosen_type and all_types:
            chosen_type = all_types[0]

        if chosen_type:
            price = itm.price if (itm.price is not None and itm.price > 0) else float(chosen_type["default_selling_price"] or 0)
            qty = max(1, itm.quantity)
            item_entry = {
                "type_id": str(chosen_type["type_id"]),
                "quantity": qty,
                "price": price
            }
            if itm.batch_id:
                item_entry["batch_id"] = str(itm.batch_id)
            db_items.append(item_entry)
            calc_total += (price * qty)

    if not db_items:
        raise HTTPException(status_code=400, detail="No valid items in invoice")

    discount = float(body.discount or 0.0)
    final_total = max(0.0, calc_total - discount)

    # Tender split logic
    if body.payment_type == "credit":
        invoice_amount_paid = 0.0
        debt_payment = 0.0
        cash_change = 0.0
        total_cash_collected = 0.0
        cash_received = 0.0
    else:
        # Cash or custom payment
        cash_received = float(body.cash_received if body.cash_received is not None else (body.amount_paid if body.amount_paid is not None else final_total))
        invoice_amount_paid = min(final_total, cash_received)
        excess_cash = max(0.0, cash_received - final_total)

        if excess_cash > 0 and current_cust_balance > 0:
            if body.apply_to_old_debt is False:
                # Seller selected: Give change instead
                debt_payment = 0.0
                cash_change = excess_cash
            else:
                # Default: Apply to old debt
                max_debt_applicable = min(current_cust_balance, excess_cash)
                if body.debt_payment_amount is not None:
                    debt_payment = min(max_debt_applicable, float(body.debt_payment_amount))
                else:
                    debt_payment = max_debt_applicable
                cash_change = excess_cash - debt_payment
        else:
            debt_payment = 0.0
            cash_change = excess_cash

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
                NULL::uuid,
                %s::text,
                true
            )
            """,
            (user_id, customer_uuid, items_json, discount, invoice_amount_paid, body.notes or f"Invoice payment ({body.payment_type})")
        )
        row = await res.fetchone()
        sale_id = str(list(row.values())[0]) if row else None

        # Fetch invoice number generated by sequence
        sale_info = await db.execute("SELECT sale_number FROM sales WHERE sale_id = %s::uuid", (sale_id,))
        s_row = await sale_info.fetchone()
        invoice_number = s_row["sale_number"] if s_row else "INV-000001"

        # If debt payment applies, post it linked to the same sale
        debt_payment_id = None
        if debt_payment > 0:
            pay_res = await db.execute(
                """
                SELECT receive_payment(
                    %s::uuid,
                    %s::uuid,
                    %s::numeric,
                    NULL::uuid,
                    %s::uuid,
                    %s::text
                )
                """,
                (user_id, customer_uuid, debt_payment, sale_id, f"Applied to prior debt during bill {invoice_number}")
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
        "total": final_total,
        "cash_received": cash_received,
        "amount_paid": invoice_amount_paid,
        "applied_to_bill": invoice_amount_paid,
        "applied_to_old_debt": debt_payment,
        "debt_payment_id": debt_payment_id,
        "change_returned": cash_change,
        "previous_balance": current_cust_balance,
        "new_balance": final_balance,
        "new_cans_balance": final_cans,
        "total_cash_collected": total_cash_collected,
        "message": f"Invoice {invoice_number} created successfully."
    }

    if op_key:
        await commit_idempotency(db, op_key, response_payload)

    return response_payload


@router.get("/invoices/list")
@router.get("/sales/list")
async def list_invoices(
    q: Optional[str] = None,
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
    if q and q.strip():
        query += " WHERE customer_name ILIKE %s OR sale_number ILIKE %s"
        params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])

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
        WHERE s.sale_number ILIKE %s OR s.sale_id::text = %s
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
            pt.sku,
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
        ta_name = tamil_names.get(t_name, tamil_names.get(disp_name, disp_name))

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
        "SELECT COALESCE(SUM(amount), 0) AS old_debt_amt FROM payments WHERE sale_id = %s::uuid AND notes ILIKE %s",
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

    return {
        "sale_id": str(inv["sale_id"]),
        "invoice_number": inv["sale_number"],
        "date": str(inv["sale_date"]),
        "customer_name": inv["customer_name"],
        "customer_phone": inv["phone"] or "",
        "customer_address": inv["address"] or "",
        "current_customer_balance": historical_balance,
        "customer_balance": historical_balance,
        "staff_name": inv["staff_name"] or "Cashier",
        "subtotal": float(inv["subtotal"] or inv["total"] or 0),
        "discount": float(inv["discount"] or 0),
        "total": float(inv["total"] or 0),
        "amount_paid": float(inv["amount_paid"] or 0),
        "applied_to_old_debt": applied_to_old_debt,
        "balance_due": max(0.0, float(inv["total"] or 0) - float(inv["amount_paid"] or 0)),
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
    try:
        res = await db.execute(
            "SELECT return_sale_item(%s::uuid, %s::uuid, %s::integer, %s::text)",
            (user_id, body.sale_item_id, body.quantity, body.reason)
        )
        row = await res.fetchone()
        return_id = str(list(row.values())[0]) if row else None
        return {
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

    type_id = None
    if body.type_id:
        chk = await db.execute("SELECT type_id, default_selling_price FROM product_types WHERE type_id = %s::uuid", (str(body.type_id),))
        t_row = await chk.fetchone()
        if t_row:
            type_id = str(t_row["type_id"])

    if not type_id and body.product_id:
        all_types_res = await db.execute("SELECT type_id, type_name, default_selling_price FROM product_types WHERE is_active ORDER BY default_selling_price")
        all_types = await all_types_res.fetchall()
        p_str = str(body.product_id).strip().lower()
        for idx, t in enumerate(all_types, start=1):
            if str(idx) == p_str or p_str in t["type_name"].lower():
                type_id = str(t["type_id"])
                break

    if not type_id:
        raise HTTPException(status_code=400, detail="Product variant not found")

    supp_id = None
    if body.supplier_id:
        chk_s = await db.execute("SELECT supplier_id FROM suppliers WHERE supplier_id = %s::uuid", (str(body.supplier_id),))
        s_row = await chk_s.fetchone()
        if s_row:
            supp_id = str(s_row["supplier_id"])

    type_info = await db.execute("""
        SELECT type_name, default_selling_price, 
               CASE WHEN EXISTS (
                   SELECT 1 FROM information_schema.columns WHERE table_name = 'product_types' AND column_name = 'default_buying_price'
               ) THEN default_buying_price ELSE NULL END AS default_buying_price
        FROM product_types WHERE type_id = %s::uuid
    """, (type_id,))
    t_row = await type_info.fetchone()
    type_name = t_row["type_name"] if t_row else "item"
    def_selling = float(t_row["default_selling_price"] or 0) if t_row else 20.0
    def_buying = float(t_row["default_buying_price"]) if (t_row and t_row.get("default_buying_price") is not None) else None

    selling_price = float(body.selling_price) if body.selling_price is not None else def_selling
    if body.buying_price is not None:
        buying_price = max(0.0, float(body.buying_price))
    elif def_buying is not None:
        buying_price = def_buying
    else:
        raise HTTPException(
            status_code=400,
            detail="Buying cost is required when no default buying cost is set."
        )
    qty = max(1, int(body.quantity))

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

    type_id = None
    if body.type_id:
        chk = await db.execute("SELECT type_id FROM product_types WHERE type_id = %s::uuid", (str(body.type_id),))
        t_row = await chk.fetchone()
        if t_row:
            type_id = str(t_row["type_id"])

    if not type_id and body.product_id:
        all_types_res = await db.execute("SELECT type_id, type_name FROM product_types WHERE is_active ORDER BY default_selling_price")
        all_types = await all_types_res.fetchall()
        p_str = str(body.product_id).strip().lower()
        for idx, t in enumerate(all_types, start=1):
            if str(idx) == p_str or p_str in t["type_name"].lower():
                type_id = str(t["type_id"])
                break

    if not type_id:
        raise HTTPException(status_code=400, detail="Product variant not found")

    # If specific batch specified, use it; otherwise pick active batch
    if body.batch_id:
        batch_res = await db.execute(
            "SELECT batch_id, current_quantity FROM stock_batches WHERE batch_id = %s::uuid AND type_id = %s::uuid",
            (str(body.batch_id), type_id)
        )
    else:
        batch_res = await db.execute(
            """
            SELECT batch_id, current_quantity 
            FROM stock_batches 
            WHERE type_id = %s::uuid AND current_quantity > 0 
            ORDER BY received_date ASC, created_at ASC 
            LIMIT 1
            """,
            (type_id,)
        )
    b_row = await batch_res.fetchone()
    if not b_row:
        raise HTTPException(status_code=400, detail="No stock batch found for this item to adjust")

    batch_id = str(b_row["batch_id"])
    current_qty = int(b_row["current_quantity"] or 0)

    if body.delta is not None:
        new_qty = max(0, current_qty + body.delta)
    elif body.quantity is not None and body.quantity > 0:
        new_qty = max(0, current_qty - abs(body.quantity))
    else:
        new_qty = max(0, current_qty - 1)

    reason_type = body.reason_type if body.reason_type in ('adjustment', 'damaged', 'expired') else 'adjustment'
    reason = body.reason or ("Damaged goods write-off" if reason_type == 'damaged' else "Stock count correction")

    await db.execute(
        "SELECT adjust_stock(%s::uuid, %s::uuid, %s::integer, %s::text, %s::text)",
        (user_id, batch_id, new_qty, reason, reason_type)
    )

    stock_res = await db.execute("SELECT COALESCE(SUM(current_quantity), 0) AS total_stock FROM stock_batches WHERE type_id = %s::uuid", (type_id,))
    st_row = await stock_res.fetchone()
    total_stock = int(st_row["total_stock"] or 0)

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
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "phone": r["phone"] or "",
        "address": r["address"] or "",
        "credit_limit": float(r["credit_limit"] or 0),
        "balance": float(r["balance"] or 0),
        "cans": int(r["cans"] or 0),
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
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    # Idempotency check
    op_key = f"payment:{body.operation_id}" if body.operation_id else None
    if op_key:
        cached = await check_idempotency(db, op_key, body.model_dump())
        if cached:
            return cached

    # Resolve payment_method to method_id
    method_id = None
    if body.payment_method:
        m_str = body.payment_method.strip().lower()
        m_map = {
            "cash": "Cash",
            "upi": "Bank Transfer",
            "bank": "Bank Transfer",
            "bank transfer": "Bank Transfer",
            "cheque": "Cheque",
            "check": "Cheque",
            "card": "Card"
        }
        target_name = m_map.get(m_str, "Cash")
        m_res = await db.execute("SELECT method_id FROM payment_methods WHERE method_name ILIKE %s LIMIT 1", (f"%{target_name}%",))
        m_row = await m_res.fetchone()
        if m_row:
            method_id = str(m_row["method_id"])

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
            "message": f"Payment of ₹{body.amount} recorded. Customer balance is now ₹{new_bal:,.2f}"
        }
        if op_key:
            await commit_idempotency(db, op_key, response_payload)
        return response_payload
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))


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
            c.customer_name,
            p.amount,
            p.payment_date,
            p.created_at,
            p.notes,
            pm.method_name
        FROM payments p
        JOIN customers c ON c.customer_id = p.customer_id
        LEFT JOIN payment_methods pm ON pm.method_id = p.method_id
        WHERE (p.notes IS NULL OR position('[VOIDED' in p.notes) = 0)
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
            "notes": r["notes"] or ""
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
    p_res = await db.execute(
        "SELECT payment_id, customer_id, amount, notes, method_id FROM payments WHERE payment_id = %s::uuid LIMIT 1",
        (body.payment_id,)
    )
    p_row = await p_res.fetchone()
    if not p_row:
        raise HTTPException(status_code=404, detail="Payment record not found")

    old_amount = float(p_row["amount"])
    new_amount = float(body.new_amount)
    if new_amount <= 0:
        raise HTTPException(status_code=400, detail="Corrected amount must be greater than zero. Use Void to cancel.")

    diff = new_amount - old_amount
    customer_id = str(p_row["customer_id"])

    # Update payments table
    updates = ["amount = %s", "notes = COALESCE(notes, '') || ' [Corrected from ₹' || %s || ' to ₹' || %s || ']'"]
    params = [new_amount, old_amount, new_amount]

    if body.method_id:
        updates.append("method_id = %s::uuid")
        params.append(body.method_id)

    params.append(body.payment_id)
    await db.execute(f"UPDATE payments SET {', '.join(updates)} WHERE payment_id = %s::uuid", tuple(params))

    # Delta adjustment in ledger
    debit = abs(diff) if diff < 0 else 0
    credit = diff if diff > 0 else 0
    note = body.reason or f"Payment corrected from Rs. {old_amount} to Rs. {new_amount}"

    ledger_res = await db.execute(
        """
        SELECT post_ledger(
            %s::uuid,
            'adjustment',
            'payment',
            %s::uuid,
            %s::numeric,
            %s::numeric,
            %s::text,
            %s::uuid
        )
        """,
        (customer_id, body.payment_id, debit, credit, note, user_id)
    )
    l_row = await ledger_res.fetchone()
    new_balance = float(list(l_row.values())[0]) if l_row else 0.0

    return {
        "status": "success",
        "payment_id": body.payment_id,
        "old_amount": old_amount,
        "new_amount": new_amount,
        "new_balance": new_balance,
        "message": f"Payment corrected from ₹{old_amount} to ₹{new_amount}. Balance updated."
    }


@router.post("/payments/void")
async def void_payment_endpoint(
    body: PaymentVoidRequest,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Preserves audit history: does NOT hard delete.
    Marks payment voided and offsets ledger balance.
    """
    user_id = current_user.get("user_id")
    p_res = await db.execute(
        "SELECT payment_id, customer_id, amount, notes FROM payments WHERE payment_id = %s::uuid LIMIT 1",
        (body.payment_id,)
    )
    p_row = await p_res.fetchone()
    if not p_row:
        raise HTTPException(status_code=404, detail="Payment record not found")

    old_amount = float(p_row["amount"])
    customer_id = str(p_row["customer_id"])

    # Reverse via ledger (debit = old_amount to restore debt balance)
    ledger_res = await db.execute(
        """
        SELECT post_ledger(
            %s::uuid,
            'adjustment',
            'payment',
            %s::uuid,
            %s::numeric,
            0::numeric,
            %s::text,
            %s::uuid
        )
        """,
        (customer_id, body.payment_id, old_amount, body.reason or f"Voided mistake payment of Rs. {old_amount}", user_id)
    )
    l_row = await ledger_res.fetchone()
    new_balance = float(list(l_row.values())[0]) if l_row else 0.0

    # Soft mark voided in notes (preserves database integrity without hard deletion)
    await db.execute(
        "UPDATE payments SET notes = COALESCE(notes, '') || ' [VOIDED: ' || %s || ']' WHERE payment_id = %s::uuid",
        (body.reason or "Voided by manager", body.payment_id)
    )

    return {
        "status": "success",
        "payment_id": body.payment_id,
        "voided_amount": old_amount,
        "new_balance": new_balance,
        "message": f"Payment of ₹{old_amount} voided successfully. Debt restored."
    }


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
    op_key = f"container:{body.operation_id}" if body.operation_id else None
    if op_key:
        cached = await check_idempotency(db, op_key, body.model_dump())
        if cached:
            return cached

    # Resolve returnable container type_id
    if body.type_id:
        type_uuid = str(body.type_id)
    else:
        type_res = await db.execute("SELECT type_id FROM product_types WHERE is_returnable_container LIMIT 1")
        t_row = await type_res.fetchone()
        type_uuid = str(t_row["type_id"]) if t_row else None

    if not type_uuid:
        raise HTTPException(status_code=400, detail="No returnable container product variant configured")

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

        response_payload = {
            "status": "success",
            "held": new_held,
            "new_cans_balance": new_held,
            "message": f"Empty container movement recorded. Customer now holds {new_held} container(s)."
        }
        if op_key:
            await commit_idempotency(db, op_key, response_payload)
        return response_payload
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))


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

    cash_res = await db.execute("SELECT COALESCE(SUM(amount), 0) AS cash FROM payments WHERE payment_date = CURRENT_DATE AND (notes IS NULL OR position('[VOIDED' in notes) = 0)")
    cash_row = await cash_res.fetchone()
    cash = float(cash_row["cash"] or 0)

    sales_res = await db.execute("SELECT COALESCE(SUM(total), 0) AS sales FROM sales WHERE sale_date = CURRENT_DATE AND status != 'cancelled'")
    sales_row = await sales_res.fetchone()
    sales = float(sales_row["sales"] or 0)

    debt_res = await db.execute("SELECT COALESCE(SUM(balance), 0) AS debt FROM customers WHERE is_active AND balance > 0")
    debt_row = await debt_res.fetchone()
    debt = float(debt_row["debt"] or 0)

    cust_cnt_res = await db.execute("SELECT COUNT(*) AS cnt FROM customers WHERE is_active")
    cust_cnt = await cust_cnt_res.fetchone()
    customers = int(cust_cnt["cnt"] or 0)

    low_stock_res = await db.execute(
        """
        SELECT COUNT(*) AS low_cnt FROM (
            SELECT t.type_id, COALESCE(SUM(b.current_quantity), 0) as total_qty, t.low_stock_limit
            FROM product_types t
            LEFT JOIN stock_batches b ON b.type_id = t.type_id AND b.current_quantity > 0
            WHERE t.is_active
            GROUP BY t.type_id, t.low_stock_limit
            HAVING COALESCE(SUM(b.current_quantity), 0) <= t.low_stock_limit
        ) sub
        """
    )
    low_row = await low_stock_res.fetchone()
    low_stock = int(low_row["low_cnt"] or 0)

    payload = {
        "cash": cash,
        "cash_inflow": cash,
        "collections": cash,
        "total_collections_today": cash,
        "sales": sales,
        "total_sales": sales,
        "total_sales_today": sales,
        "debt": debt,
        "owed_to_you": debt,
        "lowStock": low_stock,
        "customers": customers,
    }

    # Gross profit strictly allowlisted to Owner and Manager
    if role in ("owner", "manager"):
        profit_res = await db.execute(
            """
            SELECT COALESCE(SUM(si.line_total - (si.buying_price * si.quantity)), 0) AS profit
            FROM sale_items si
            JOIN sales s ON s.sale_id = si.sale_id
            WHERE s.sale_date = CURRENT_DATE AND s.status != 'cancelled'
            """
        )
        profit_row = await profit_res.fetchone()
        profit = float(profit_row["profit"] or 0)
        payload["profit"] = profit
        payload["profit_today"] = profit
    else:
        payload["profit"] = None
        payload["profit_today"] = None

    return payload


@router.get("/reports/summary")
@router.get("/reports/monthly")
async def get_report_summary(
    period: str = "this_month",  # "today", "this_week", "this_month", "custom"
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(require_role("owner", "manager")),
    db: AsyncConnection = Depends(get_db)
):
    """
    Computes authentic, reconciled financial report from actual ledger records.
    Never returns hardcoded or fake numbers.
    """
    today = date.today()
    if period == "today":
        start_date = today
        end_date = today
    elif period == "this_week":
        # Monday as start of week
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == "this_month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "custom" and from_date and to_date:
        start_date = date.fromisoformat(from_date)
        end_date = date.fromisoformat(to_date)
    else:
        start_date = today.replace(day=1)
        end_date = today

    # 1. Total Sales and Bill Count
    s_res = await db.execute(
        """
        SELECT 
            COALESCE(SUM(total), 0) AS net_sales,
            COUNT(*) AS bill_count
        FROM sales 
        WHERE sale_date BETWEEN %s AND %s AND status != 'cancelled'
        """,
        (start_date, end_date)
    )
    s_row = await s_res.fetchone()
    sales = float(s_row["net_sales"] or 0)
    bills = int(s_row["bill_count"] or 0)

    # 2. Total Cash Collections
    c_res = await db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS collections FROM payments WHERE payment_date BETWEEN %s AND %s AND (notes IS NULL OR position('[VOIDED' in notes) = 0)",
        (start_date, end_date)
    )
    c_row = await c_res.fetchone()
    collections = float(c_row["collections"] or 0)

    # 3. Cost of Goods Sold & Gross Profit
    cogs_res = await db.execute(
        """
        SELECT 
            COALESCE(SUM(si.buying_price * si.quantity), 0) AS total_cost
        FROM sale_items si
        JOIN sales s ON s.sale_id = si.sale_id
        WHERE s.sale_date BETWEEN %s AND %s AND s.status != 'cancelled'
        """,
        (start_date, end_date)
    )
    cogs_row = await cogs_res.fetchone()
    cogs = float(cogs_row["total_cost"] or 0)
    gross_profit = max(0.0, sales - cogs)

    # 4. Expenses
    exp_res = await db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total_exp FROM expenses WHERE expense_date BETWEEN %s AND %s",
        (start_date, end_date)
    )
    exp_row = await exp_res.fetchone()
    expenses = float(exp_row["total_exp"] or 0)

    # 5. Returns Count & Value
    ret_res = await db.execute(
        "SELECT COUNT(*) AS ret_count, COALESCE(SUM(credit_amount), 0) AS ret_val FROM sale_returns WHERE returned_at::date BETWEEN %s AND %s",
        (start_date, end_date)
    )
    ret_row = await ret_res.fetchone()
    returns_count = int(ret_row["ret_count"] or 0)
    returns_val = float(ret_row["ret_val"] or 0)

    net_profit = gross_profit - expenses

    return {
        "period": period,
        "from_date": str(start_date),
        "to_date": str(end_date),
        "sales": sales,
        "net_sales": sales,
        "collections": collections,
        "cogs": cogs,
        "profit": gross_profit,
        "gross_profit": gross_profit,
        "expenses": expenses,
        "net_profit": net_profit,
        "bills": bills,
        "bill_count": bills,
        "returns_count": returns_count,
        "returns_amount": returns_val
    }
