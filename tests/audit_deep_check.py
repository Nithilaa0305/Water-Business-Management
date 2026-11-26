"""Deep isolated audit checks for financial, inventory, bottle and accounting integrity."""

import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from app.database.connection import get_session_factory, Base
from app.database.migrations.migration_manager import seed_default_data
from app.services.inventory_service import InventoryService
from app.services.sales_service import SalesService
from app.services.customer_service import CustomerService
from app.services.payment_service import PaymentService
from app.services.bottle_service import BottleService
from app.services.accounting_service import AccountingService
from app.database.models.product import Product


def test_deep_financial_and_inventory_audit():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
        test_db = Path(tf.name)

    try:
        engine = create_engine(f'sqlite:///{test_db.as_posix()}')
        Base.metadata.create_all(bind=engine)
        seed_default_data(engine)
        SessionFactory = get_session_factory(engine)

        with SessionFactory() as session:
            p500 = session.query(Product).filter_by(code='W0500').first()
            p19l = session.query(Product).filter_by(code='W19000').first()

            # 1. Multi-batch FIFO allocation with cost verification
            b1 = InventoryService.add_batch(session, p500.id, quantity=30, unit_cost_cents=3000)
            b2 = InventoryService.add_batch(session, p500.id, quantity=50, unit_cost_cents=3500)

            cust = CustomerService.create_customer(session, name='Deep Audit Customer', phone='0770001122')

            # Purchase 40 bottles @ Rs. 60
            inv = SalesService.create_invoice(
                session=session,
                items_data=[{'product_id': p500.id, 'quantity': 40, 'unit_price_cents': 6000}],
                customer_id=cust.id,
                payment_method='CREDIT',
                amount_paid_cents=0
            )

            # COGS = 30 * 3000 + 10 * 3500 = 90,000 + 35,000 = 125,000 cents (Rs. 1,250.00)
            assert inv.items[0].cogs_total_cents == 125000
            assert b1.remaining_qty == 0
            assert b2.remaining_qty == 40

            # 2. Revenue Isolation & Advance Payment
            fin_before = AccountingService.get_financial_summary(session)
            assert fin_before['net_sales_revenue_cents'] == 240000
            assert fin_before['cogs_cents'] == 125000
            assert fin_before['gross_profit_cents'] == 115000

            # Customer pays Rs. 3,000 against Rs. 2,400 invoice (Rs. 600 advance)
            pay = PaymentService.record_customer_payment(session, cust.id, amount_cents=300000, payment_method='CASH')
            assert pay.unallocated_amount_cents == 60000

            fin_after = AccountingService.get_financial_summary(session)
            # Revenue MUST remain exactly Rs. 2,400
            assert fin_after['net_sales_revenue_cents'] == 240000

            # 3. Bottle Reconciliation
            reconcile = BottleService.reconcile_bottles(session)
            assert reconcile['discrepancy'] == 0
            assert reconcile['is_reconciled'] is True

    finally:
        if test_db.exists():
            try:
                test_db.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    test_deep_financial_and_inventory_audit()
    print("ALL DEEP AUDIT CHECKS PASSED SUCCESSFULLY!")
