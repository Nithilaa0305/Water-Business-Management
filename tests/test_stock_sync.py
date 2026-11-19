import os
import sys
import json
import uuid
import urllib.request
import urllib.error
import psycopg

raw_test_db = os.getenv("TEST_DATABASE_URL")
if not raw_test_db:
    sys.exit("ERROR: TEST_DATABASE_URL environment variable is required to run tests.")

db_lower = raw_test_db.lower().split("?")[0]
if not (db_lower.endswith("/billing_test") or "_test" in db_lower.split("/")[-1]):
    sys.exit("REFUSING TO RUN: TEST_DATABASE_URL must point to an isolated test database ending in '_test' (e.g. /billing_test). Live database access is strictly forbidden.")

DB_URL = raw_test_db.replace("postgresql+psycopg://", "postgresql://")
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")

def http_req(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            return status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"detail": content}
        return e.code, parsed

def get_auth_token():
    status, body = http_req("/auth/sign-in", "POST", {"pin": "1234", "role": "owner"})
    assert status == 200, f"Auth failed: {status} {body}"
    return body["access_token"]

def get_pg_batches(type_id):
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT batch_number, current_quantity, buying_price, selling_price FROM stock_batches WHERE type_id = %s::uuid AND current_quantity > 0 ORDER BY received_date, created_at",
                (type_id,)
            )
            return cur.fetchall()

def run_tests():
    token = get_auth_token()
    
    print("=== TEST 1: CREATE TEST SKU WITH 20 UNITS ACROSS TWO BATCHES ===")
    unique_suffix = uuid.uuid4().hex[:6]
    sku_code = f"SKU-SYNC-{unique_suffix.upper()}"
    prod_name = f"Test Sync Water {unique_suffix}"
    
    status, create_res = http_req(
        "/products/create",
        "POST",
        {
            "name": prod_name,
            "sku": sku_code,
            "unit": "can",
            "selling_price": 90.0,
            "buying_price": 50.0,
            "initial_stock": 0,
            "is_returnable": False
        },
        token=token
    )
    assert status == 200, f"Create product failed: {status} {create_res}"
    type_id = create_res["type_id"]
    print(f"Created SKU '{prod_name}' with type_id={type_id}")
    
    status, rec1 = http_req(
        "/stock/receive",
        "POST",
        {
            "type_id": type_id,
            "quantity": 12,
            "buying_price": 50.0,
            "selling_price": 90.0,
            "invoice_no": f"BATCH1-{unique_suffix}"
        },
        token=token
    )
    assert status == 200, f"Receive batch 1 failed: {status} {rec1}"
    
    status, rec2 = http_req(
        "/stock/receive",
        "POST",
        {
            "type_id": type_id,
            "quantity": 8,
            "buying_price": 52.0,
            "selling_price": 90.0,
            "invoice_no": f"BATCH2-{unique_suffix}"
        },
        token=token
    )
    assert status == 200, f"Receive batch 2 failed: {status} {rec2}"
    
    status, products = http_req("/products/list", "GET", token=token)
    assert status == 200
    sku_prod = next((p for p in products if p["type_id"] == type_id), None)
    assert sku_prod is not None, "Product not in /products/list"
    assert sku_prod["stock"] == 20, f"Expected 20, got {sku_prod['stock']}"
    
    batches = get_pg_batches(type_id)
    assert len(batches) == 2, f"Expected 2 batches, found {len(batches)}"
    total_pg_stock = sum(b[1] for b in batches)
    assert total_pg_stock == 20, f"Expected 20 in DB, found {total_pg_stock}"
    print(f"PASS: Stock & Invoice Items both show 20 sellable units across two batches: {batches}")
    
    print("\n=== TEST 2: EXECUTE SALE OF 3 UNITS (CONFIRM BOTH SHOW 17) ===")
    status, custs = http_req("/customers/list", "GET", token=token)
    assert status == 200
    cust = custs[0]
    
    status, sale_res = http_req(
        "/sales/create",
        "POST",
        {
            "customer_id": cust["id"],
            "operation_id": f"OP-TEST-SALE-{unique_suffix}",
            "items": [{"type_id": type_id, "quantity": 3, "price": 90.0}],
            "payment_type": "cash",
            "cash_received": 270.0,
            "amount_paid": 270.0
        },
        token=token
    )
    assert status == 200, f"Sale failed: {status} {sale_res}"
    
    status, products = http_req("/products/list", "GET", token=token)
    sku_prod = next(p for p in products if p["type_id"] == type_id)
    assert sku_prod["stock"] == 17, f"Expected 17, got {sku_prod['stock']}"
    batches = get_pg_batches(type_id)
    total_pg_stock = sum(b[1] for b in batches)
    assert total_pg_stock == 17, f"Expected 17 in DB, found {total_pg_stock}"
    print(f"PASS: Both screens show 17 units immediately. DB batches: {batches}")
    
    print("\n=== TEST 3: RECEIVE 5 UNITS INTO STOCK (CONFIRM BOTH SHOW 22) ===")
    status, rec3 = http_req(
        "/stock/receive",
        "POST",
        {
            "type_id": type_id,
            "quantity": 5,
            "buying_price": 50.0,
            "selling_price": 90.0,
            "invoice_no": f"BATCH3-{unique_suffix}"
        },
        token=token
    )
    assert status == 200, f"Receive failed: {status} {rec3}"
    
    status, products = http_req("/products/list", "GET", token=token)
    sku_prod = next(p for p in products if p["type_id"] == type_id)
    assert sku_prod["stock"] == 22, f"Expected 22, got {sku_prod['stock']}"
    batches = get_pg_batches(type_id)
    total_pg_stock = sum(b[1] for b in batches)
    assert total_pg_stock == 22, f"Expected 22 in DB, found {total_pg_stock}"
    print(f"PASS: Both screens show 22 units immediately. DB batches: {batches}")
    
    print("\n=== TEST 4: ATTEMPT OVERSELL BEYOND 22 (SERVER REJECTS, COUNTS UNCHANGED) ===")
    status, oversell_res = http_req(
        "/sales/create",
        "POST",
        {
            "customer_id": cust["id"],
            "operation_id": f"OP-TEST-OVERSELL-{unique_suffix}",
            "items": [{"type_id": type_id, "quantity": 25, "price": 90.0}],
            "payment_type": "cash",
            "cash_received": 2250.0,
            "amount_paid": 2250.0
        },
        token=token
    )
    assert status == 400, f"Expected 400 rejection, got {status}: {oversell_res}"
    print(f"PASS: Oversell correctly rejected with 400: {oversell_res}")
    
    status, products = http_req("/products/list", "GET", token=token)
    sku_prod = next(p for p in products if p["type_id"] == type_id)
    assert sku_prod["stock"] == 22, f"Expected 22 unchanged, got {sku_prod['stock']}"
    batches = get_pg_batches(type_id)
    total_pg_stock = sum(b[1] for b in batches)
    assert total_pg_stock == 22, f"Expected 22 unchanged in DB, found {total_pg_stock}"
    print(f"PASS: Count remains exactly 22 on both screens after rejected oversell.")
    
    print("\n=== TEST 5: VERIFY 19 L FILLED WATER AND 19 L EMPTY CANS REMAIN COMPLETELY SEPARATE ===")
    filled_prod = next((p for p in products if "19" in p["name"] and ("filled" in p["name"].lower() or not p["is_returnable"] or "water" in p["name"].lower())), None)
    empty_prod = next((p for p in products if ("empty" in p["name"].lower() or "can" in p["name"].lower() or "bottle" in p["name"].lower()) and p["type_id"] != filled_prod["type_id"]), None)
    
    assert filled_prod is not None, "Could not find filled 19L product"
    assert empty_prod is not None, "Could not find empty can product"
    
    print(f"Filled Water: '{filled_prod['name']}' (type_id={filled_prod['type_id']}, stock={filled_prod['stock']})")
    print(f"Empty Can:    '{empty_prod['name']}' (type_id={empty_prod['type_id']}, stock={empty_prod['stock']})")
    
    if empty_prod["stock"] < 10:
        status, rec_empty = http_req(
            "/stock/receive",
            "POST",
            {
                "type_id": empty_prod["type_id"],
                "quantity": 10,
                "buying_price": 50.0,
                "selling_price": empty_prod["price"] or 150.0,
                "invoice_no": f"CAN-REC-{unique_suffix}"
            },
            token=token
        )
        assert status == 200
        status, products = http_req("/products/list", "GET", token=token)
        empty_prod = next(p for p in products if p["type_id"] == empty_prod["type_id"])
    
    initial_filled_stock = filled_prod["stock"]
    initial_empty_stock = empty_prod["stock"]
    
    status, sale_filled_res = http_req(
        "/sales/create",
        "POST",
        {
            "customer_id": cust["id"],
            "operation_id": f"OP-TEST-FILLED-{unique_suffix}",
            "items": [{"type_id": filled_prod["type_id"], "quantity": 2, "price": filled_prod["price"]}],
            "payment_type": "cash",
            "cash_received": 2 * filled_prod["price"],
            "amount_paid": 2 * filled_prod["price"]
        },
        token=token
    )
    assert status == 200, f"Sale filled water failed: {status} {sale_filled_res}"
    
    status, products_after_filled_sale = http_req("/products/list", "GET", token=token)
    new_filled = next(p for p in products_after_filled_sale if p["type_id"] == filled_prod["type_id"])
    new_empty = next(p for p in products_after_filled_sale if p["type_id"] == empty_prod["type_id"])
    
    assert new_filled["stock"] == initial_filled_stock - 2, f"Filled stock should decrease by 2 ({initial_filled_stock} -> {new_filled['stock']})"
    assert new_empty["stock"] == initial_empty_stock, f"Empty can stock MUST NOT CHANGE on filled water sale! ({initial_empty_stock} vs {new_empty['stock']})"
    print(f"PASS: Selling 2 filled cans decremented filled stock ({initial_filled_stock} -> {new_filled['stock']}) while empty can stock stayed untouched ({initial_empty_stock}).")
    
    status, adj_res = http_req(
        "/stock/adjust",
        "POST",
        {
            "type_id": empty_prod["type_id"],
            "quantity": 2,
            "reason": "Damaged container write-off",
            "reason_type": "damaged"
        },
        token=token
    )
    assert status == 200, f"Adjust empty can failed: {status} {adj_res}"
    
    status, products_after_empty_adj = http_req("/products/list", "GET", token=token)
    final_filled = next(p for p in products_after_empty_adj if p["type_id"] == filled_prod["type_id"])
    final_empty = next(p for p in products_after_empty_adj if p["type_id"] == empty_prod["type_id"])
    
    assert final_empty["stock"] == initial_empty_stock - 2, f"Empty can stock should decrease by 2 ({initial_empty_stock} -> {final_empty['stock']})"
    assert final_filled["stock"] == new_filled["stock"], f"Filled stock MUST NOT CHANGE on empty can adjustment! ({new_filled['stock']} vs {final_filled['stock']})"
    print(f"PASS: Adjusting empty can stock decremented empty stock ({initial_empty_stock} -> {final_empty['stock']}) while filled water stock stayed untouched ({final_filled['stock']}).")
    
    print("\n>>> ALL 5 REQUIRED STOCK SYNC VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_tests()
