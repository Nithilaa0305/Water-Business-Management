import asyncio
import os
import sys

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
os.environ["DATABASE_URL"] = raw_test_db

from app.routers.operations import (
    create_sale_endpoint,
    get_invoice_details,
    get_customer_statement,
    CreateSaleRequest,
    SaleItem
)

async def run_tests():
    conn = await psycopg.AsyncConnection.connect(
        TEST_DB_URL,
        row_factory=dict_row
    )
    cur = conn.cursor()

    # 1. User
    await cur.execute("SELECT user_id, username, user_role FROM app_users WHERE user_role = 'owner' LIMIT 1;")
    user = await cur.fetchone()
    current_user = {"user_id": str(user["user_id"]), "role": "owner", "username": user["username"]}

    # 2. Product type & customer
    await cur.execute("SELECT type_id, type_name, default_selling_price FROM product_types WHERE is_returnable_container LIMIT 1;")
    pt = await cur.fetchone()

    await cur.execute("SELECT customer_id, customer_name, balance FROM customers LIMIT 1;")
    cust = await cur.fetchone()

    # 3. Create Sale Endpoint
    req = CreateSaleRequest(
        customer_id=str(cust["customer_id"]),
        payment_type="cash",
        cash_received=float(pt["default_selling_price"]) * 2,
        amount_paid=float(pt["default_selling_price"]) * 2,
        expected_previous_balance=float(cust["balance"]),
        apply_to_old_debt=True,
        operation_id=f"TEST-OP-{int(asyncio.get_event_loop().time() * 1000)}",
        items=[
            SaleItem(
                product_id=1,
                type_id=str(pt["type_id"]),
                name=pt["type_name"],
                price=float(pt["default_selling_price"]),
                quantity=2.0,
                subtotal=float(pt["default_selling_price"]) * 2.0
            )
        ]
    )

    sale_res = await create_sale_endpoint(body=req, current_user=current_user, db=conn)
    inv_num = sale_res["invoice_number"]
    print(f"Sale created successfully! Invoice: {inv_num}, Total: {sale_res['total']}, Cans balance: {sale_res.get('new_cans_balance')}")
    assert sale_res["total"] > 0, "Sale total must be positive"
    assert "new_cans_balance" in sale_res, "new_cans_balance must be returned"

    # 4. Get Invoice Details Endpoint
    details = await get_invoice_details(invoice_number=inv_num, current_user=current_user, db=conn)
    print(f"Fetched invoice details: {details['invoice_number']}, Customer: {details['customer_name']}, Items: {len(details['items'])}")
    assert len(details["items"]) == 1, f"Expected 1 item, got {len(details['items'])}"
    itm = details["items"][0]
    print(f"Item: name={itm['name']}, variant={itm['variant']}, unit={itm['unit']}, qty={itm['quantity']}, price={itm['price']}, subtotal={itm['subtotal']}")
    assert itm["quantity"] == 2.0, "Quantity should be 2.0"
    assert itm["unit"] is not None and itm["unit"] != "", "Unit must not be empty"
    assert itm["price"] == float(pt["default_selling_price"]), "Price must match"

    # 5. Get Customer Statement Endpoint
    stmt = await get_customer_statement(customer_id=str(cust["customer_id"]), current_user=current_user, db=conn)
    print(f"Customer statement entries count: {len(stmt)}")
    assert len(stmt) > 0, "Statement must not be empty"
    latest_entry = stmt[0]
    print(f"Latest statement entry: ref={latest_entry.get('reference_number')}, type={latest_entry.get('entry_type')}, debit={latest_entry.get('debit')}, credit={latest_entry.get('credit')}")

    await cur.close()
    await conn.close()
    print("\n>>> ALL BACKEND ROUTE & DATABASE AUDIT TESTS PASSED! <<<")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_tests())

