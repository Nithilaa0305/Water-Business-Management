import asyncio
import sys
import psycopg
from psycopg.rows import dict_row
import urllib.request
import json
import uuid

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

raw_test_db = os.getenv("TEST_DATABASE_URL")
if not raw_test_db:
    sys.exit("ERROR: TEST_DATABASE_URL environment variable is required to run tests.")

db_lower = raw_test_db.lower().split("?")[0]
if not (db_lower.endswith("/billing_test") or "_test" in db_lower.split("/")[-1]):
    sys.exit("REFUSING TO RUN: TEST_DATABASE_URL must point to an isolated test database ending in '_test' (e.g. /billing_test). Live database access is strictly forbidden.")

DB_URL = raw_test_db.replace("postgresql+psycopg://", "postgresql://")
API_BASE = "http://localhost:8000"

def api_call(path, method="GET", body=None, token=None):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"detail": err_body}

async def test_batch3():
    print("=== STARTING BATCH 3 VERIFICATION TESTS ===")
    
    conn = await psycopg.AsyncConnection.connect(DB_URL, row_factory=dict_row, autocommit=True)
    await conn.execute("UPDATE app_users SET pin_hash = crypt('1234', gen_salt('bf', 6)) WHERE user_role = 'employee'")
    await conn.commit()
    await conn.close()
    
    # 1. Sign in as Owner to get token
    status, auth_data = api_call("/auth/sign-in", "POST", {"pin": "1234", "role": "owner"})
    assert status == 200, f"Owner signin failed: {auth_data}"
    owner_token = auth_data["access_token"]
    print("✓ Owner signed in successfully")

    # 2. Test list_products for Owner (should include buying_price)
    status, prods = api_call("/products/list", "GET", token=owner_token)
    assert status == 200, f"List products failed: {prods}"
    assert isinstance(prods, list), "Products response should be a list"
    assert len(prods) > 0, "Should have active products"
    for p in prods:
        assert "buying_price" in p, "Owner product response should contain buying_price key"
        assert p["is_active"] is True, f"Active list must contain only active products, got {p}"
    print(f"✓ Owner list_products returned {len(prods)} active products with buying_price field")

    # 3. Test list_products for Employee (buying_price must be None / hidden)
    # Sign in as Employee (pin 1234)
    status, emp_auth = api_call("/auth/sign-in", "POST", {"pin": "1234", "role": "employee"})
    assert status == 200, f"Employee signin failed: {emp_auth}"
    emp_token = emp_auth["access_token"]
    
    status, emp_prods = api_call("/products/list", "GET", token=emp_token)
    assert status == 200, f"Employee list products failed: {emp_prods}"
    for p in emp_prods:
        assert p["buying_price"] is None, f"Employee must NOT see buying_price! Got: {p['buying_price']}"
    print("✓ Employee list_products correctly hides buying_price (all None)")

    # 4. Test show_archived filter on products
    status, arch_prods = api_call("/products/list?show_archived=true", "GET", token=owner_token)
    assert status == 200, f"Archived products failed: {arch_prods}"
    for p in arch_prods:
        assert p["is_active"] is False, f"Archived list must contain ONLY inactive products! Found active: {p}"
    print(f"✓ show_archived=true on products returns strictly archived products (found {len(arch_prods)})")

    # 5. Create a test product with default_buying_price
    test_pname = f"Batch3 Mineral Water {uuid.uuid4().hex[:6]}"
    status, create_res = api_call("/products/create", "POST", {
        "name": test_pname,
        "selling_price": 80.0,
        "buying_price": 50.0,
        "unit": "bottle",
        "is_returnable": False
    }, token=owner_token)
    assert status == 200, f"Product create failed: {create_res}"
    type_id = create_res["type_id"]
    print(f"✓ Created test product '{test_pname}' with default buying cost Rs. 50.0, selling Rs. 80.0")

    # Verify default buying cost persisted in database
    conn = await psycopg.AsyncConnection.connect(DB_URL, row_factory=dict_row, autocommit=True)
    cur = await conn.execute("SELECT type_name, default_selling_price, default_buying_price FROM product_types WHERE type_id = %s::uuid", (type_id,))
    pt_row = await cur.fetchone()
    assert pt_row is not None, "Product type not found in DB"
    assert float(pt_row["default_buying_price"]) == 50.0, f"Expected 50.0, got {pt_row['default_buying_price']}"
    print("✓ DB verified: default_buying_price is 50.0")

    # 6. Receive stock with an overridden buying_price (e.g. 55.0)
    status, rec_res = api_call("/stock/receive", "POST", {
        "type_id": type_id,
        "quantity": 25,
        "buying_price": 55.0,
        "selling_price": 80.0,
    }, token=owner_token)
    assert status == 200, f"Stock receive failed: {rec_res}"
    batch_id = rec_res.get("batch_id")
    print(f"✓ Stock received: 25 units at overridden buying price Rs. 55.0 (batch {batch_id})")

    # Verify the batch was recorded at 55.0, while the product default remains 50.0!
    cur = await conn.execute("SELECT buying_price, selling_price, current_quantity FROM stock_batches WHERE type_id = %s::uuid AND current_quantity > 0 ORDER BY created_at DESC LIMIT 1", (type_id,))
    b_row = await cur.fetchone()
    assert b_row is not None, "Batch row not found"
    assert float(b_row["buying_price"]) == 55.0, f"Batch buying price should be 55.0, got {b_row['buying_price']}"

    cur = await conn.execute("SELECT default_buying_price FROM product_types WHERE type_id = %s::uuid", (type_id,))
    pt_row = await cur.fetchone()
    assert float(pt_row["default_buying_price"]) == 50.0, f"Product default must NOT change on batch override! Got {pt_row['default_buying_price']}"
    print("✓ Product default buying cost remained Rs. 50.0 while batch received at Rs. 55.0")

    # 7. Update product's default buying cost to 60.0 via /products/update
    status, up_res = api_call("/products/update", "POST", {
        "type_id": type_id,
        "name": test_pname,
        "selling_price": 85.0,
        "buying_price": 60.0
    }, token=owner_token)
    assert status == 200, f"Product update failed: {up_res}"

    # Verify existing batch buying price was NOT modified!
    cur = await conn.execute("SELECT buying_price FROM stock_batches WHERE type_id = %s::uuid", (type_id,))
    b_row = await cur.fetchone()
    assert float(b_row["buying_price"]) == 55.0, f"Past batch buying price was corrupted! Expected 55.0, got {b_row['buying_price']}"

    cur = await conn.execute("SELECT default_buying_price, default_selling_price FROM product_types WHERE type_id = %s::uuid", (type_id,))
    pt_row = await cur.fetchone()
    assert float(pt_row["default_buying_price"]) == 60.0, f"Product default should be 60.0, got {pt_row['default_buying_price']}"
    print("✓ Updating product default cost to Rs. 60.0 did NOT touch existing batch cost (stayed Rs. 55.0)")

    # 8. Test product with NO default buying price: receive stock without buying_price must fail with HTTP 400
    test_nobuy = f"No Cost Product {uuid.uuid4().hex[:6]}"
    status, nobuy_res = api_call("/products/create", "POST", {
        "name": test_nobuy,
        "selling_price": 40.0,
        "buying_price": None,
        "unit": "bottle"
    }, token=owner_token)
    nobuy_tid = nobuy_res["type_id"]

    # Clear default_buying_price to NULL in DB
    await conn.execute("UPDATE product_types SET default_buying_price = NULL WHERE type_id = %s::uuid", (nobuy_tid,))
    
    # Try receiving stock without specifying buying_price
    status, err_rec = api_call("/stock/receive", "POST", {
        "type_id": nobuy_tid,
        "quantity": 10
    }, token=owner_token)
    assert status == 400, f"Should reject stock receive when no buying price is provided and no default exists! Got status {status}: {err_rec}"
    assert "Buying cost is required" in err_rec.get("detail", ""), f"Unexpected error detail: {err_rec}"
    print("✓ Successfully rejected stock receive without buying cost when no default is configured (no silent 0 or 60% mock)")

    # 9. Test Customers: Active vs Archived filtering
    status, act_custs = api_call("/customers/list?show_archived=false", "GET", token=owner_token)
    assert status == 200
    for c in act_custs:
        assert c["is_active"] is True, f"Active customer list must contain only active records! Got: {c}"
    print(f"✓ Active customer list returned {len(act_custs)} active customers (all is_active=True)")

    status, arch_custs = api_call("/customers/list?show_archived=true", "GET", token=owner_token)
    assert status == 200
    for c in arch_custs:
        assert c["is_active"] is False, f"Archived customer list must contain only archived records! Got: {c}"
    print(f"✓ Archived customer list returned {len(arch_custs)} archived customers (all is_active=False)")

    # 10. Test Customer Archive and Restore
    # Create clean test customer with 0 balance
    cname = f"Test Cust {uuid.uuid4().hex[:6]}"
    cres = await conn.execute("INSERT INTO customers (customer_name, phone, balance, credit_limit, is_active) VALUES (%s, '0779999999', 0, 1000, TRUE) RETURNING customer_id", (cname,))
    crow = await cres.fetchone()
    cid = str(crow["customer_id"])
    await conn.commit()

    # Archive customer
    status, arch_res = api_call("/customers/archive", "POST", {"customer_id": cid, "action": "archive"}, token=owner_token)
    assert status == 200, f"Customer archive failed: {arch_res}"

    # Verify is_active = False in DB and appears in show_archived=True
    await conn.commit()
    cur = await conn.execute("SELECT is_active FROM customers WHERE customer_id = %s::uuid", (cid,))
    chk = await cur.fetchone()
    assert chk["is_active"] is False, "Customer should be archived in DB"

    status, arch_list = api_call("/customers/list?show_archived=true", "GET", token=owner_token)
    assert any(str(c["id"]) == cid for c in arch_list), "Archived customer should appear in archived list"

    # Restore customer
    status, rest_res = api_call("/customers/archive", "POST", {"customer_id": cid, "action": "restore"}, token=owner_token)
    assert status == 200, f"Customer restore failed: {rest_res}"

    status, act_list = api_call("/customers/list?show_archived=false", "GET", token=owner_token)
    assert any(str(c["id"]) == cid for c in act_list), "Restored customer should appear in active list"

    await conn.commit()
    cur = await conn.execute("SELECT is_active FROM customers WHERE customer_id = %s::uuid", (cid,))
    chk = await cur.fetchone()
    assert chk["is_active"] is True, "Customer should be restored in DB"
    print("✓ Customer archive and restore cycle verified end-to-end")

    # 11. Test Customer Archive blocking when debt exists
    await conn.execute("UPDATE customers SET balance = 500.0 WHERE customer_id = %s::uuid", (cid,))
    await conn.commit()
    status, block_res = api_call("/customers/archive", "POST", {"customer_id": cid, "action": "archive"}, token=owner_token)
    assert status == 400, "Should block archiving customer with unsettled balance"
    assert "Rs. 500.00" in block_res.get("detail", ""), f"Error message should use 'Rs.', got: {block_res}"
    print("✓ Blocked archiving customer with unsettled balance and verified 'Rs.' currency format in error")

    # Cleanup test customer
    await conn.execute("DELETE FROM customers WHERE customer_id = %s::uuid", (cid,))
    await conn.commit()
    await conn.close()

    print("\n=== ALL BATCH 3 VERIFICATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(test_batch3())

