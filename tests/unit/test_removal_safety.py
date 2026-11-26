"""Comprehensive tests for record removal safety, deactivation/reactivation, and backup management."""

import pytest
from datetime import date
from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.database.models.supplier import Supplier
from app.database.models.product import Product
from app.database.models.operations import Expense, ExpenseCategory, PurchaseInvoice
from app.database.models.sales import SalesInvoice
from app.database.models.payment import CustomerLedgerEntry, SupplierLedgerEntry
from app.database.models.bottle import CustomerBottleLedger
from app.database.models.inventory import InventoryBatch
from app.services.customer_service import CustomerService
from app.services.inventory_service import InventoryService
from app.services.purchase_service import PurchaseService
from app.services.expense_service import ExpenseService
from app.services.backup_service import BackupService


def test_customer_removal_blocked_by_debt():
    """Ensure customer with outstanding debt cannot be removed."""
    with get_db_session() as session:
        cust = Customer(code="CUST-DEBT-01", name="Indebted Customer", phone="0771112222", is_active=True)
        session.add(cust)
        session.flush()

        ledger = CustomerLedgerEntry(
            customer_id=cust.id,
            transaction_type="INVOICE",
            debit_cents=500000,
            credit_cents=0,
            running_balance_cents=500000
        )
        session.add(ledger)
        session.flush()
        cid = cust.id

    with pytest.raises(ValueError, match="owes you|settled before removal"):
        CustomerService.remove_customer(cid)


def test_customer_removal_blocked_by_bottles():
    """Ensure customer holding 19L bottles cannot be removed."""
    with get_db_session() as session:
        cust = Customer(code="CUST-BOT-01", name="Bottle Holding Customer", phone="0773334444", is_active=True)
        session.add(cust)
        session.flush()

        b_ledger = CustomerBottleLedger(
            customer_id=cust.id,
            movement_type="DELIVERY",
            full_issued=5,
            empty_returned=0,
            running_bottle_balance=5
        )
        session.add(b_ledger)
        session.flush()
        cid = cust.id

    with pytest.raises(ValueError, match="returnable 19 L bottles|All empty containers"):
        CustomerService.remove_customer(cid)


def test_customer_safe_archiving_with_history():
    """Ensure customer with zero debt/bottles but past history is safely archived (is_active=False)."""
    with get_db_session() as session:
        cust = Customer(code="CUST-HIST-01", name="Settled Customer", phone="0775556666", is_active=True)
        session.add(cust)
        session.flush()

        inv = SalesInvoice(
            invoice_number="INV-SAFE-001",
            customer_id=cust.id,
            subtotal_cents=100000,
            total_amount_cents=100000,
            amount_paid_cents=100000
        )
        session.add(inv)

        ledger = CustomerLedgerEntry(
            customer_id=cust.id,
            transaction_type="PAYMENT",
            debit_cents=0,
            credit_cents=100000,
            running_balance_cents=0
        )
        session.add(ledger)
        session.flush()
        cid = cust.id

    result = CustomerService.remove_customer(cid)
    assert result["action"] in ("DEACTIVATED", "archived", "deactivated")

    with get_db_session() as session:
        c = session.get(Customer, cid)
        assert c is not None
        assert c.is_active is False

    # Test reactivation
    CustomerService.reactivate_customer(cid)
    with get_db_session() as session:
        c = session.get(Customer, cid)
        assert c.is_active is True


def test_unused_customer_permanent_deletion():
    """Ensure unused customer with no ledger/bottle/invoice records is permanently deleted."""
    with get_db_session() as session:
        cust = Customer(code="CUST-DEL-01", name="Unused Customer", phone="0779998888", is_active=True)
        session.add(cust)
        session.flush()
        cid = cust.id

    result = CustomerService.remove_customer(cid)
    assert result["action"] in ("DELETED", "deleted")

    with get_db_session() as session:
        c = session.get(Customer, cid)
        assert c is None


def test_supplier_removal_safety():
    """Ensure supplier with payable is blocked; unused is deleted; historical is archived."""
    with get_db_session() as session:
        sup_debt = Supplier(name="Owed Supplier", phone="0112223333", is_active=True)
        session.add(sup_debt)
        session.flush()

        s_ledger = SupplierLedgerEntry(
            supplier_id=sup_debt.id,
            transaction_type="PURCHASE",
            debit_cents=0,
            credit_cents=300000,
            running_balance_cents=300000
        )
        session.add(s_ledger)
        session.flush()
        sid_debt = sup_debt.id

    # 1. Blocked by payable
    with pytest.raises(ValueError, match="still owe|Balance must be settled"):
        PurchaseService.remove_supplier(sid_debt)

    # 2. Historical supplier with settled purchases -> archived
    with get_db_session() as session:
        sup_settled = Supplier(name="Settled Supplier", phone="0114445555", is_active=True)
        session.add(sup_settled)
        session.flush()

        p_inv = PurchaseInvoice(
            purchase_number="PO-001",
            supplier_id=sup_settled.id,
            total_amount_cents=100000,
            amount_paid_cents=100000
        )
        session.add(p_inv)
        session.flush()
        sid_settled = sup_settled.id

    res_archive = PurchaseService.remove_supplier(sid_settled)
    assert res_archive["action"] in ("DEACTIVATED", "archived", "deactivated")

    # Reactivate
    PurchaseService.reactivate_supplier(sid_settled)
    with get_db_session() as session:
        s = session.get(Supplier, sid_settled)
        assert s.is_active is True

    # 3. Unused supplier -> permanently deleted
    with get_db_session() as session:
        sup_unused = Supplier(name="Unused Supplier", phone="0119999999", is_active=True)
        session.add(sup_unused)
        session.flush()
        sid_unused = sup_unused.id

    res_del = PurchaseService.remove_supplier(sid_unused)
    assert res_del["action"] in ("DELETED", "deleted")
    with get_db_session() as session:
        assert session.get(Supplier, sid_unused) is None


def test_product_removal_safety():
    """Ensure product with stock is blocked; unused is deleted; historical is archived."""
    with get_db_session() as session:
        p_stock = Product(code="W_TEST_1", name="Stocked Water", bottle_size="500 ml", uom="Bottle", default_selling_price_cents=5000, is_active=True)
        session.add(p_stock)
        session.flush()

        batch = InventoryBatch(
            batch_number="B-TEST-001",
            product_id=p_stock.id,
            received_date=date.today(),
            original_qty=100,
            remaining_qty=50,
            unit_cost_cents=3000
        )
        session.add(batch)
        session.flush()
        pid_stock = p_stock.id

    # 1. Blocked by remaining stock
    with pytest.raises(ValueError, match="bottles in stock|sold or written off"):
        InventoryService.remove_product(pid_stock)

    # 2. Historical product with 0 stock but batches -> archived
    with get_db_session() as session:
        p_hist = Product(code="W_TEST_2", name="Historical Water", bottle_size="1 L", uom="Bottle", default_selling_price_cents=5000, is_active=True)
        session.add(p_hist)
        session.flush()

        batch2 = InventoryBatch(
            batch_number="B-TEST-002",
            product_id=p_hist.id,
            received_date=date.today(),
            original_qty=100,
            remaining_qty=0,
            unit_cost_cents=3000
        )
        session.add(batch2)
        session.flush()
        pid_hist = p_hist.id

    res_arch = InventoryService.remove_product(pid_hist)
    assert res_arch["action"] in ("DEACTIVATED", "archived", "deactivated")

    # Reactivate
    InventoryService.reactivate_product(pid_hist)
    with get_db_session() as session:
        p = session.get(Product, pid_hist)
        assert p.is_active is True

    # 3. Unused product -> permanently deleted
    with get_db_session() as session:
        p_unused = Product(code="W_TEST_3", name="Unused Water", bottle_size="1.5 L", uom="Bottle", default_selling_price_cents=5000, is_active=True)
        session.add(p_unused)
        session.flush()
        pid_unused = p_unused.id

    res_del = InventoryService.remove_product(pid_unused)
    assert res_del["action"] in ("DELETED", "deleted")
    with get_db_session() as session:
        assert session.get(Product, pid_unused) is None


def test_expense_deletion():
    """Ensure recorded expense can be deleted."""
    with get_db_session() as session:
        cat = session.query(ExpenseCategory).first()
        if not cat:
            cat = ExpenseCategory(name="Utilities")
            session.add(cat)
            session.flush()

        exp = Expense(
            category_id=cat.id,
            amount_cents=150000,
            description="Test Power Bill",
            payment_method="CASH"
        )
        session.add(exp)
        session.flush()
        eid = exp.id

    ExpenseService.delete_expense(eid)
    with get_db_session() as session:
        assert session.get(Expense, eid) is None


def test_backup_service_creation_and_listing():
    """Ensure BackupService creates backups in configured location and lists them."""
    backup_dir = BackupService.get_configured_backup_dir()
    assert backup_dir.exists()

    dest = BackupService.create_backup()
    assert dest.exists()
    assert dest.suffix == ".db"

    backups = BackupService.list_backups()
    assert len(backups) >= 1
    filenames = [b["filename"] for b in backups]
    assert dest.name in filenames
