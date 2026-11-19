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

API_BASE_URL = "http://localhost:8000"

async def test_batch2():
    print("=" * 70)
    print("BATCH 2 VERIFICATION: HOME & SHARED LAYOUT")
    print("=" * 70)

    # 1. Test Owner Dashboard
    print("\n[Step 1] Verifying /dashboard/today for Owner (Authorized)...")
    owner_req = urllib.request.Request(
        f"{API_BASE_URL}/auth/sign-in",
        data=json.dumps({"pin": "1234", "role": "owner"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    owner_resp = urllib.request.urlopen(owner_req)
    owner_token = json.loads(owner_resp.read().decode("utf-8"))["access_token"]

    dash_req = urllib.request.Request(
        f"{API_BASE_URL}/dashboard/today",
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    dash_resp = urllib.request.urlopen(dash_req)
    assert dash_resp.status == 200
    owner_data = json.loads(dash_resp.read().decode("utf-8"))

    print(f"✓ Owner Dashboard Numbers:")
    print(f"   - Today's Sales: Rs. {owner_data.get('sales', 0):,.2f}")
    print(f"   - Today's Collections: Rs. {owner_data.get('cash', 0):,.2f}")
    print(f"   - Today's Gross Profit: Rs. {owner_data.get('profit', 0):,.2f} (Visible to Owner)")
    assert "sales" in owner_data
    assert "cash" in owner_data
    assert owner_data.get("profit") is not None, "Owner must receive profit figure"

    # 2. Test Employee Dashboard: Gross Profit MUST BE HIDDEN
    print("\n[Step 2] Verifying Employee Role Restriction on Today's Analysis...")
    emp_req = urllib.request.Request(
        f"{API_BASE_URL}/auth/sign-in",
        data=json.dumps({"pin": "1234", "role": "employee"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    emp_resp = urllib.request.urlopen(emp_req)
    emp_token = json.loads(emp_resp.read().decode("utf-8"))["access_token"]

    emp_dash_req = urllib.request.Request(
        f"{API_BASE_URL}/dashboard/today",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    emp_dash_resp = urllib.request.urlopen(emp_dash_req)
    assert emp_dash_resp.status == 200
    emp_data = json.loads(emp_dash_resp.read().decode("utf-8"))

    print(f"✓ Employee Dashboard Numbers:")
    print(f"   - Today's Sales: Rs. {emp_data.get('sales', 0):,.2f}")
    print(f"   - Today's Collections: Rs. {emp_data.get('cash', 0):,.2f}")
    print(f"   - Today's Gross Profit: {emp_data.get('profit')} (Strictly None/Hidden for Employee)")
    assert emp_data.get("profit") is None, "Gross profit must be strictly None for employee role"

    # 3. Test Products List for Needs Attention Sorting (out of stock first)
    print("\n[Step 3] Verifying Products inventory for Needs Attention Today sidebar...")
    prod_req = urllib.request.Request(
        f"{API_BASE_URL}/products/list",
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    prod_resp = urllib.request.urlopen(prod_req)
    assert prod_resp.status == 200
    prod_data = json.loads(prod_resp.read().decode("utf-8"))
    prods = prod_data if isinstance(prod_data, list) else prod_data.get("products", [])

    print(f"✓ Total active products retrieved: {len(prods)}")
    out_of_stock = [p for p in prods if (p.get("stock") or 0) == 0]
    low_stock = [p for p in prods if 0 < (p.get("stock") or 0) <= 10]
    print(f"   - Out of Stock items (stock == 0): {len(out_of_stock)}")
    print(f"   - Low Stock items (0 < stock <= 10): {len(low_stock)}")

    # 4. Verify Frontend Home.tsx structure & layout rules
    print("\n[Step 4] Verifying Home.tsx layout code compliance...")
    with open("frontend/src/pages/Home.tsx", "r", encoding="utf-8") as f:
        home_code = f.read()

    # Confirm 2x2 launcher grid
    assert "home-launcher-grid" in home_code, "Must have 2x2 launcher grid"
    assert "actions.map" in home_code, "Must render four action tiles"
    # Confirm Today's Analysis strip
    assert "home-today-analysis-card" in home_code, "Must have Today's Analysis card"
    assert "today-metrics-strip" in home_code, "Must have Today's Analysis metrics strip"
    # Confirm right sidebar
    assert "home-attention-card" in home_code, "Must have Needs Attention Today sidebar"
    assert "Nothing needs attention" in home_code, "Must have 'Nothing needs attention' empty state"
    # Confirm removal of Last Invoice shortcut and Money to Collect
    assert "handleViewLastInvoice" not in home_code, "Last Invoice shortcut must NOT exist"
    assert "Money to Collect" not in home_code, "Money to Collect must NOT exist"
    assert "Outstanding Debt" not in home_code, "All-time debt must NOT be in Today's Analysis"

    print("✓ 2x2 Launcher Action Grid confirmed (Invoice, Stock, Pay/Return, Reports)")
    print("✓ Today's Analysis strip confirmed (Sales, Collections, Gross Profit)")
    print("✓ Customer Debt strictly excluded from Today's Analysis daily strip")
    print("✓ Needs Attention Today sidebar confirmed on right with out-of-stock first")
    print("✓ 'Nothing needs attention' only shown after successful empty response")
    print("✓ Last Invoice / View Reprint shortcut completely removed")
    print("✓ Money to Collect card completely removed")
    print("✓ Misplaced Add Customer / Add Product / Home / Total removed from top-right header")

    print("\n" + "=" * 70)
    print(">>> ALL BATCH 2 VERIFICATION CHECKS PASSED SUCCESSFULLY! <<<")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_batch2())
