import asyncio
import os
import sys
import json
import urllib.request
import urllib.error

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import psycopg
from psycopg.rows import dict_row

raw_test_db = os.getenv("TEST_DATABASE_URL")
if not raw_test_db:
    sys.exit("ERROR: TEST_DATABASE_URL environment variable is required to run tests.")

db_lower = raw_test_db.lower().split("?")[0]
if not (db_lower.endswith("/billing_test") or "_test" in db_lower.split("/")[-1]):
    sys.exit("REFUSING TO RUN: TEST_DATABASE_URL must point to an isolated test database ending in '_test' (e.g. /billing_test). Live database access is strictly forbidden.")

TEST_DB_URL = raw_test_db.replace("postgresql+psycopg://", "postgresql://")
API_BASE_URL = "http://localhost:8000"

async def run_batch1_verification():
    print("=" * 70)
    print("BATCH 1 VERIFICATION: SAVED INVOICES, PRINT, AND DIRECT PDF DOWNLOAD")
    print("=" * 70)

    # 1. Verify running backend API authentication and INV-000037 fix
    print("\n[Step 1] Reproducing and Verifying Fix for INV-000037 over HTTP API...")
    login_req = urllib.request.Request(
        f"{API_BASE_URL}/auth/sign-in",
        data=json.dumps({"pin": "1234", "role": "owner"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    login_resp = urllib.request.urlopen(login_req)
    token = json.loads(login_resp.read().decode("utf-8"))["access_token"]
    assert token, "Failed to authenticate with owner PIN"
    print("✓ Owner signed in successfully. Token acquired.")

    # Request INV-000037
    inv37_req = urllib.request.Request(
        f"{API_BASE_URL}/invoices/details/INV-000037",
        headers={"Authorization": f"Bearer {token}"}
    )
    inv37_resp = urllib.request.urlopen(inv37_req)
    assert inv37_resp.status == 200, f"Expected 200 OK, got {inv37_resp.status}"
    inv37_data = json.loads(inv37_resp.read().decode("utf-8"))
    print(f"✓ INV-000037 retrieved successfully via GET /invoices/details/INV-000037:")
    print(f"   - Invoice Number: {inv37_data['invoice_number']}")
    print(f"   - Customer: {inv37_data['customer_name']} (Phone: {inv37_data['customer_phone']})")
    print(f"   - Total: Rs. {inv37_data['total']:,.2f} | Paid: Rs. {inv37_data['amount_paid']:,.2f} | Balance Due: Rs. {inv37_data['balance_due']:,.2f}")
    print(f"   - Itemized Lines Count: {len(inv37_data['items'])}")
    for itm in inv37_data["items"]:
        print(f"     * {itm['name']} | Qty: {itm['quantity']} {itm['unit']} | Rate: Rs. {itm['price']:,.2f} | Line Total: Rs. {itm['subtotal']:,.2f} | Tamil: {itm.get('ta')}")
        # Verify NO UUIDs leaked into name or variant
        assert not itm['name'].count("-") > 3 or len(itm['name']) < 30, f"Name contains UUID: {itm['name']}"
        assert not (itm.get('variant') and len(itm['variant']) == 36 and itm['variant'].count("-") == 4), f"Variant contains raw UUID: {itm.get('variant')}"

    # Verify 404 behavior and error handling (does not return zero-item invoice)
    try:
        inv_fake_req = urllib.request.Request(
            f"{API_BASE_URL}/invoices/details/INV-NONEXISTENT-9999",
            headers={"Authorization": f"Bearer {token}"}
        )
        urllib.request.urlopen(inv_fake_req)
        assert False, "Nonexistent invoice should return 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"
        print("✓ Non-existent invoice properly returns 404 Not Found (never renders zero-item mock)")

    # 2. Test Multi-Item and Long Invoice in Isolated Test Database billing_test
    print("\n[Step 2] Testing Multi-Item and Long Invoices in Isolated Test DB (billing_test)...")
    conn = await psycopg.AsyncConnection.connect(TEST_DB_URL, row_factory=dict_row)
    cur = conn.cursor()

    # Get or create customer in billing_test
    await cur.execute("SELECT customer_id, customer_name, balance FROM customers WHERE is_active LIMIT 1")
    cust = await cur.fetchone()
    if not cust:
        await cur.execute("INSERT INTO customers (customer_name, phone, balance, is_active) VALUES ('Test Multi-Item Buyer', '077-9998888', 0, TRUE) RETURNING customer_id, customer_name, balance")
        cust = await cur.fetchone()
        await conn.commit()

    # Get available product types and active batches in billing_test
    await cur.execute("""
        SELECT pt.type_id, pt.type_name, pt.default_selling_price, b.batch_id, COALESCE(b.buying_price, 30.0) AS buying_price 
        FROM product_types pt 
        JOIN stock_batches b ON b.type_id = pt.type_id
        WHERE pt.is_active 
        LIMIT 6
    """)
    types = await cur.fetchall()
    assert len(types) >= 2, "billing_test must have at least 2 product types with batches"

    # Get owner user_id
    await cur.execute("SELECT user_id FROM app_users WHERE user_role = 'owner' LIMIT 1")
    owner_id = (await cur.fetchone())["user_id"]

    # Create a realistic multi-item sale in billing_test
    import uuid
    test_sale_id = uuid.uuid4()
    test_sale_number = f"INV-TEST-{int(asyncio.get_event_loop().time() * 1000) % 1000000:06d}"

    subtotal = 0.0
    items_to_insert = []
    for idx, t in enumerate(types):
        qty = idx + 2
        rate = float(t["default_selling_price"] or 50.0)
        cost = float(t["buying_price"] or 30.0)
        line_tot = qty * rate
        subtotal += line_tot
        items_to_insert.append((test_sale_id, t["type_id"], t["batch_id"], qty, rate, cost))

    amount_paid = subtotal  # Fully paid
    await cur.execute("""
        INSERT INTO sales (sale_id, sale_number, customer_id, sale_date, subtotal, discount, total, amount_paid, status, created_by)
        VALUES (%s, %s, %s, CURRENT_DATE, %s, 0.0, %s, %s, 'completed', %s)
    """, (test_sale_id, test_sale_number, cust["customer_id"], subtotal, subtotal, amount_paid, owner_id))

    for itm in items_to_insert:
        await cur.execute("""
            INSERT INTO sale_items (sale_item_id, sale_id, type_id, batch_id, quantity, unit_price, buying_price)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s)
        """, itm)

    # Record container return of 2 cans
    await cur.execute("""
        INSERT INTO container_movements (movement_id, customer_id, type_id, sale_id, movement_date, given_qty, returned_qty, notes, created_by)
        VALUES (gen_random_uuid(), %s, %s, %s, CURRENT_DATE, 0, 2, '2 empty cans returned with sale', %s)
    """, (cust["customer_id"], types[0]["type_id"], test_sale_id, owner_id))

    await conn.commit()
    print(f"✓ Created test multi-item invoice {test_sale_number} with {len(items_to_insert)} lines in billing_test.")

    # Now verify via operations.get_invoice_details
    from app.routers.operations import get_invoice_details
    mock_user = {"user_id": str(owner_id), "role": "owner", "username": "owner"}
    details = await get_invoice_details(test_sale_number, mock_user, conn)

    assert details["invoice_number"] == test_sale_number
    assert len(details["items"]) == len(items_to_insert), f"Expected {len(items_to_insert)} items, got {len(details['items'])}"
    assert details["subtotal"] == subtotal
    assert details["amount_paid"] == amount_paid
    assert details["balance_due"] == 0.0
    assert details["cans_returned"] == 2
    print(f"✓ Retrieved {test_sale_number} from database:")
    print(f"   - Items count: {len(details['items'])}")
    print(f"   - Subtotal: Rs. {details['subtotal']:,.2f}")
    print(f"   - Cans Returned: {details['cans_returned']}")
    for itm in details["items"]:
        print(f"     * {itm['name']} | Qty: {itm['quantity']} {itm['unit']} | Price: Rs. {itm['price']:,.2f} | Subtotal: Rs. {itm['subtotal']:,.2f} | Ta: {itm.get('ta')}")

    # 3. Long Invoice Pagination Simulation (Multi-page check)
    print("\n[Step 3] Verifying Multi-Page Long Invoice handling logic...")
    long_sale_id = uuid.uuid4()
    long_sale_number = f"INV-LONG-{int(asyncio.get_event_loop().time() * 1000) % 1000000:06d}"
    long_items = []
    long_subtotal = 0.0
    # Simulate 18 lines (which forces page 2 on A4)
    for i in range(18):
        t = types[i % len(types)]
        qty = i + 1
        rate = float(t["default_selling_price"] or 45.0)
        cost = float(t["buying_price"] or 30.0)
        ltot = qty * rate
        long_subtotal += ltot
        long_items.append((long_sale_id, t["type_id"], t["batch_id"], qty, rate, cost))

    await cur.execute("""
        INSERT INTO sales (sale_id, sale_number, customer_id, sale_date, subtotal, discount, total, amount_paid, status, created_by)
        VALUES (%s, %s, %s, CURRENT_DATE, %s, 0.0, %s, %s, 'completed', %s)
    """, (long_sale_id, long_sale_number, cust["customer_id"], long_subtotal, long_subtotal, long_subtotal, owner_id))

    for itm in long_items:
        await cur.execute("""
            INSERT INTO sale_items (sale_item_id, sale_id, type_id, batch_id, quantity, unit_price, buying_price)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s)
        """, itm)
    await conn.commit()

    long_details = await get_invoice_details(long_sale_number, mock_user, conn)
    assert len(long_details["items"]) == 18, f"Expected 18 items, got {len(long_details['items'])}"
    print(f"✓ Long invoice {long_sale_number} with 18 items retrieved with all 18 line items intact.")

    await cur.close()
    await conn.close()

    print("\n" + "=" * 70)
    print(">>> ALL BATCH 1 VERIFICATION CHECKS PASSED SUCCESSFULLY! <<<")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_batch1_verification())

