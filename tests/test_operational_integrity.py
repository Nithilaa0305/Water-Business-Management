"""Run from repository root with an explicit disposable TEST_DATABASE_URL.

This suite applies the installation SQL itself and refuses an initialized database.
It drives the in-process FastAPI app (not an independently configured server).
"""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from uuid import uuid4
from urllib.parse import urlparse

import psycopg
from fastapi.testclient import TestClient

url = os.environ.get("TEST_DATABASE_URL", "")
parsed = urlparse(url)
if parsed.scheme != "postgresql" or parsed.hostname not in ("127.0.0.1", "::1", "localhost") or not parsed.path.endswith("_test") or parsed.query:
    raise SystemExit("An explicitly configured loopback disposable *_test database is required (no URL query parameters).")
os.environ["DATABASE_URL"] = url
os.environ["SECRET_KEY"] = uuid4().hex + uuid4().hex
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import app


def main():
    root = Path(__file__).resolve().parents[1]
    with psycopg.connect(url, autocommit=True) as conn:
        if conn.execute("SELECT to_regclass('public.customers')").fetchone()[0]:
            raise SystemExit("Use a new, empty disposable database.")
        for line in (root / "install.sql").read_text().splitlines():
            if line.startswith("\\i "):
                conn.execute((root / line[3:]).read_text())
        assert conn.execute("SELECT COUNT(*) FROM app_users").fetchone()[0] == 0
        conn.execute((root / "setup/seed_catalog.sql").read_text())
        assert conn.execute("""SELECT count(*) FROM product_types
            WHERE default_selling_price = 0 AND default_buying_price IS NULL""").fetchone()[0] == 6
        assert conn.execute("SELECT COUNT(*) FROM stock_batches").fetchone()[0] == 0
        owner_pin, employee_pin = "93015412", "90315016"
        owner = conn.execute("SELECT create_user('Integrity Owner','integrity-owner',%s,'owner')", (owner_pin,)).fetchone()[0]
        conn.execute("SELECT create_user('Integrity Employee','integrity-employee',%s,'employee',%s)", (employee_pin, owner))
        with TestClient(app) as api:
            def auth(username, pin):
                res = api.post("/auth/sign-in", json={"username": username, "pin": pin})
                assert res.status_code == 200, res.text
                return {"Authorization": f"Bearer {res.json()['access_token']}"}

            headers = auth("integrity-owner", owner_pin)
            employee_headers = auth("integrity-employee", employee_pin)

            def post(path, expected=200, **body):
                res = api.post(path, json=body, headers=headers)
                assert res.status_code == expected, (path, res.status_code, res.text)
                return res.json()

            def get(path, auth_headers=headers):
                res = api.get(path, headers=auth_headers)
                assert res.status_code == 200, (path, res.text)
                return res.json()

            customer = post("/customers/create", name="Integrity customer")["customer_id"]
            product = post("/products/create", name="Integrity filled", tamil_name="தண்ணீர்", unit="can",
                           selling_price=1700, buying_price=1782, is_returnable=True)["type_id"]
            post("/stock/receive", type_id=product, quantity=4)
            assert next(p for p in get("/products/list") if p["type_id"] == product)["buying_price"] == 1782

            conn.execute("SELECT post_ledger(%s,'adjustment','test',gen_random_uuid(),500,0,'Opening fixture',%s)", (customer, owner))
            checkout = dict(operation_id="checkout-fixture", customer_id=customer, expected_previous_balance=500,
                            cash_received=2000, items=[{"type_id":product,"quantity":1,"price":1700}])
            with ThreadPoolExecutor(max_workers=2) as parallel:
                a, b = (parallel.submit(post, "/sales/create", **checkout) for _ in range(2))
                sale = a.result()
                assert b.result() == sale
            assert post("/sales/create", **checkout) == sale
            assert sale["amount_paid"] == 1700 and sale["applied_to_old_debt"] == 300 and sale["new_balance"] == 200
            assert sale["new_cans_balance"] == 1 and sale["change_returned"] == 0
            assert conn.execute("SELECT amount_paid FROM sales WHERE sale_id=%s", (sale["sale_id"],)).fetchone()[0] == 1700
            assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
            post("/sales/create", 400, **{**checkout, "operation_id": "unknown", "customer_id": str(uuid4())})
            assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
            assert next(p for p in get("/products/list") if p["type_id"] == product)["stock"] == 3
            post("/sales/create", 409, **{**checkout, "operation_id": "stale-balance"})
            post("/sales/create", 409, **{**checkout, "expected_previous_balance": 200, "operation_id": "stale-price",
                 "items": [{"type_id": product, "quantity": 1, "price": 50}]})
            post("/stock/receive", 400, product_id="1", quantity=1, buying_price=55)
            assert get("/dashboard/today")["profit"] == -82
            post("/stock/receive", type_id=product, quantity=1, buying_price=1800)
            assert conn.execute("SELECT buying_price FROM sale_items").fetchone()[0] == 1782
            summary = get("/reports/summary?period=today")
            assert (summary["gross_profit"], summary["net_sales"], summary["cash_collections"]) == (-82, 1700, 2000)
            assert "profit" not in get("/dashboard/today", employee_headers)
            assert api.get("/reports/summary", headers=employee_headers).status_code == 403

            post("/products/update", type_id=product, name="Renamed product", tamil_name="கேன்")
            history = get(f"/invoices/details/{sale['invoice_number']}")
            assert history["items"][0]["ta"] == "தண்ணீர்" and history["cash_received"] == 2000
            assert history["amount_paid"] == 1700 and history["customer_balance"] == 200
            assert "buying_price" not in get(f"/invoices/details/{sale['invoice_number']}", employee_headers)["items"][0]

            payment_body = dict(customer_id=customer, amount=50, operation_id="payment-fixture", payment_method="cash")
            payment = post("/payments/receive", **payment_body)
            assert payment == post("/payments/receive", **payment_body) and payment["new_balance"] == 150
            post("/payments/receive", 409, **{**payment_body, "amount": 60})
            cans = dict(customer_id=customer, quantity=1, operation_id="can-fixture", action="return")
            assert post("/containers/movement", **cans)["held"] == 0
            assert post("/containers/movement", **cans)["held"] == 0
            corrected = post("/payments/correct", payment_id=payment["payment_id"], new_amount=60, payment_method="bank", reason="Fixture correction")
            assert corrected["new_balance"] == 140
            assert conn.execute("SELECT method_name FROM payment_methods JOIN payments USING (method_id) WHERE payment_id=%s", (corrected["payment_id"],)).fetchone()[0] == "Bank Transfer"
            assert post("/payments/void", payment_id=corrected["payment_id"], reason="Fixture void")["new_balance"] == 200
            post("/payments/void", 409, payment_id=corrected["payment_id"], reason="Repeated attempt")
            assert get(f"/customers/details/{customer}")["balance"] == 200

            sale2 = post("/sales/create", customer_id=customer, discount=200, cash_received=1500, empty_cans_returned=1,
                         items=[{"type_id": product, "quantity": 1}])
            assert sale2["new_cans_balance"] == 0 and sale2["receipt"]["cans_returned"] == 1
            post("/sales/cancel", 400, sale_id=sale2["sale_id"], reason="Cannot silently cancel paid invoice")
            item_id = sale2["receipt"]["items"][0]["sale_item_id"]
            return_body = dict(sale_item_id=item_id, quantity=1, reason="Damaged fixture", restock=False, operation_id="return-fixture")
            returned = post("/sales/return-item", **return_body)
            assert returned == post("/sales/return-item", **return_body)
            assert conn.execute("SELECT credit_amount,cost_amount FROM sale_returns WHERE return_id=%s", (returned["return_id"],)).fetchone() == (1500, 0)
            assert next(p for p in get("/products/list") if p["type_id"] == product)["stock"] == 3
            post("/payments/receive", 400, customer_id=customer, amount=10, payment_method="cheque")
            assert get("/reports/summary?period=today")["collections"] == 3500

            other = post("/customers/create", name="Change fixture")["customer_id"]
            conn.execute("SELECT post_ledger(%s,'adjustment','test',gen_random_uuid(),100,0,'Opening fixture',%s)", (other, owner))
            change = post("/sales/create", **{**checkout, "operation_id": "change-fixture", "customer_id": other, "expected_previous_balance": 100})
            assert (change["amount_paid"], change["applied_to_old_debt"], change["change_returned"], change["new_balance"]) == (1700, 100, 200, 0)
            second_type = next(p for p in get("/products/list") if p["sku"] == "SKU-19L")["type_id"]
            empty_type = next(p for p in get("/products/list") if p["sku"] == "SKU-19L-EMPTY")["type_id"]
            post("/containers/movement", customer_id=other, action="give", quantity=2, type_id=second_type)
            assert len(get(f"/customers/details/{other}")["container_types"]) == 2
            post("/containers/movement", 400, customer_id=other, action="return", quantity=1)
            post("/containers/movement", 400, customer_id=other, action="return", quantity=1, type_id=empty_type)
            can_return = post("/containers/movement", customer_id=other, action="return", quantity=1, type_id=second_type)
            assert (can_return["type_held"], can_return["held"]) == (1, 2)
            assert next(p for p in get("/products/list") if p["type_id"] == empty_type)["stock"] == 0

            case = post("/products/create", name="500 ml Fixture Case", sku="CASE-FIXTURE", unit="case",
                        selling_price=25, buying_price=18)["type_id"]
            post("/stock/receive", type_id=case, quantity=12)
            unpaid = post("/sales/create", customer_id=other, payment_type="credit", items=[{"type_id":case,"quantity":1}])
            assert unpaid["new_balance"] == 25 and unpaid["amount_paid"] == 0
            post("/sales/cancel", sale_id=unpaid["sale_id"], reason="Unpaid fixture")
            post("/sales/cancel", 400, sale_id=unpaid["sale_id"], reason="Already cancelled")
            assert get(f"/customers/details/{other}")["balance"] == 0
            assert next(p for p in get("/products/list") if p["type_id"] == case)["stock"] == 12
            post("/stock/adjust", type_id=case, delta=5, reason="Receive correction")
            post("/stock/adjust", 400, type_id=case, delta=-999, reason="Invalid change")
            assert next(p for p in get("/products/list") if p["type_id"] == case)["stock"] == 17
            assert api.post("/auth/sign-out", headers=employee_headers).status_code == 200
            assert api.get("/products/list", headers=employee_headers).status_code == 401
            assert api.get("/health").json()["app"] == "wholesale-billing"
        print("PASS: clean schema, stock, exact checkout tender, history, replay, invalid customer, role guards, corrections, returns, can movements and signed reports")


if __name__ == "__main__":
    main()
