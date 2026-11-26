"""Supplier Management, Purchases, Supplier Credit, and Inventory Receiving."""

from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.supplier import Supplier
from app.database.models.operations import PurchaseInvoice, PurchaseInvoiceItem
from app.database.models.payment import SupplierPayment, SupplierPaymentAllocation, SupplierLedgerEntry
from app.database.models.product import Product, PackagingUnit
from app.config.constants import StockMovementType
from app.services.inventory_service import InventoryService
from app.services.audit_service import AuditService
from app.database.connection import get_db_session
from app.utilities.dates import now_colombo, today_colombo
from app.utilities.currency import format_currency


class PurchaseService:
    @staticmethod
    def generate_purchase_number(session: Session, prefix: str = "PUR-") -> str:
        """Generate unique purchase order/invoice number."""
        date_str = now_colombo().strftime("%Y%m")
        pfx = f"{prefix}{date_str}-"
        last = (
            session.query(PurchaseInvoice)
            .filter(PurchaseInvoice.purchase_number.like(f"{pfx}%"))
            .order_by(PurchaseInvoice.id.desc())
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.purchase_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{pfx}{seq:04d}"

    @staticmethod
    def create_purchase(
        session: Session,
        supplier_id: int,
        items_data: List[Dict[str, Any]],
        supplier_invoice_no: Optional[str] = None,
        payment_method: str = "CREDIT",
        amount_paid_cents: int = 0,
        due_date: Optional[date] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> PurchaseInvoice:
        """
        Record inventory purchase from a supplier:
        - Creates PurchaseInvoice and items.
        - Automatically creates new InventoryBatches for each product received.
        - Updates supplier debt in SupplierLedger.
        - Records payment if cash/partial payment made.
        """
        if not items_data:
            raise ValueError("Purchase must have at least one product item.")

        supplier = session.query(Supplier).filter_by(id=supplier_id).first()
        if not supplier:
            raise ValueError(f"Supplier #{supplier_id} not found.")

        pur_num = PurchaseService.generate_purchase_number(session)

        purchase = PurchaseInvoice(
            purchase_number=pur_num,
            supplier_invoice_no=supplier_invoice_no,
            supplier_id=supplier_id,
            purchase_date=now_colombo(),
            total_amount_cents=0,
            amount_paid_cents=amount_paid_cents,
            payment_method=payment_method,
            status="POSTED",
            due_date=due_date,
            notes=notes,
            user_id=user_id
        )
        session.add(purchase)
        session.flush()

        total_amount_cents = 0

        for item_in in items_data:
            product_id = item_in["product_id"]
            qty = int(item_in["quantity"])
            unit_cost_cents = int(item_in["unit_cost_cents"])
            packaging_unit_id = item_in.get("packaging_unit_id")
            mfg_date = item_in.get("mfg_date")
            expiry_date = item_in.get("expiry_date")

            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ValueError(f"Product #{product_id} not found.")

            factor = 1
            if packaging_unit_id:
                pkg = session.query(PackagingUnit).filter_by(id=packaging_unit_id).first()
                if pkg:
                    factor = pkg.factor

            base_qty = qty * factor
            line_cost = qty * unit_cost_cents
            base_unit_cost = unit_cost_cents // factor
            total_amount_cents += line_cost

            # Automatically create inventory batch
            batch = InventoryService.add_batch(
                session=session,
                product_id=product_id,
                quantity=base_qty,
                unit_cost_cents=base_unit_cost,
                received_date=today_colombo(),
                mfg_date=mfg_date,
                expiry_date=expiry_date,
                supplier_id=supplier_id,
                suggested_selling_price_cents=product.default_selling_price_cents,
                movement_type=StockMovementType.PURCHASE,
                reference_type="PURCHASE",
                reference_id=purchase.id,
                notes=f"Purchased from {supplier.name} ({pur_num})",
                user_id=user_id
            )

            pur_item = PurchaseInvoiceItem(
                purchase_id=purchase.id,
                product_id=product_id,
                packaging_unit_id=packaging_unit_id,
                unit_factor=factor,
                quantity=qty,
                base_quantity=base_qty,
                unit_cost_cents=unit_cost_cents,
                total_cost_cents=line_cost,
                batch_number=batch.batch_number,
                expiry_date=expiry_date
            )
            session.add(pur_item)

        purchase.total_amount_cents = total_amount_cents

        # Update Supplier Ledger (credit increases our debt to supplier)
        last_entry = (
            session.query(SupplierLedgerEntry)
            .filter_by(supplier_id=supplier_id)
            .order_by(SupplierLedgerEntry.date.desc(), SupplierLedgerEntry.id.desc())
            .first()
        )
        prev_balance = last_entry.running_balance_cents if last_entry else 0
        new_balance = prev_balance + total_amount_cents

        ledger_entry = SupplierLedgerEntry(
            supplier_id=supplier_id,
            date=now_colombo(),
            transaction_type="PURCHASE",
            reference_no=purchase.purchase_number,
            debit_cents=0,
            credit_cents=total_amount_cents,
            running_balance_cents=new_balance,
            user_id=user_id,
            notes=f"Purchase {purchase.purchase_number}" + (f" (Sup Inv: {supplier_invoice_no})" if supplier_invoice_no else "")
        )
        session.add(ledger_entry)

        # Record payment if amount_paid_cents > 0
        if amount_paid_cents > 0:
            PurchaseService.record_supplier_payment(
                session=session,
                supplier_id=supplier_id,
                amount_cents=amount_paid_cents,
                payment_method=payment_method,
                reference_no=purchase.purchase_number,
                purchase_id=purchase.id,
                user_id=user_id
            )

        AuditService.log_action(
            session=session,
            action_type="PURCHASE_RECEIVE",
            entity_name="PurchaseInvoice",
            entity_id=purchase.id,
            reference_no=purchase.purchase_number,
            new_values={"total": total_amount_cents, "supplier": supplier.name},
            user_id=user_id
        )
        return purchase

    @staticmethod
    def record_supplier_payment(
        session: Session,
        supplier_id: int,
        amount_cents: int,
        payment_method: str = "CASH",
        reference_no: Optional[str] = None,
        purchase_id: Optional[int] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> SupplierPayment:
        """Record payment to supplier and update supplier ledger."""
        if amount_cents <= 0:
            raise ValueError("Payment amount must be greater than zero.")

        date_str = now_colombo().strftime("%Y%m")
        pay_num = f"SPAY-{date_str}-{int(now_colombo().timestamp()) % 10000:04d}"

        payment = SupplierPayment(
            payment_number=pay_num,
            supplier_id=supplier_id,
            payment_date=now_colombo(),
            amount_cents=amount_cents,
            payment_method=payment_method,
            reference_no=reference_no,
            notes=notes,
            user_id=user_id
        )
        session.add(payment)
        session.flush()

        if purchase_id:
            alloc = SupplierPaymentAllocation(
                payment_id=payment.id,
                purchase_invoice_id=purchase_id,
                allocated_amount_cents=amount_cents
            )
            session.add(alloc)

        last_entry = (
            session.query(SupplierLedgerEntry)
            .filter_by(supplier_id=supplier_id)
            .order_by(SupplierLedgerEntry.date.desc(), SupplierLedgerEntry.id.desc())
            .first()
        )
        prev_balance = last_entry.running_balance_cents if last_entry else 0
        new_balance = prev_balance - amount_cents

        entry = SupplierLedgerEntry(
            supplier_id=supplier_id,
            date=now_colombo(),
            transaction_type="PAYMENT",
            reference_no=pay_num,
            debit_cents=amount_cents,
            credit_cents=0,
            running_balance_cents=new_balance,
            user_id=user_id,
            notes=notes or f"Paid to supplier via {payment_method}"
        )
        session.add(entry)
        return payment

    @staticmethod
    def remove_supplier(
        session: Any = None,
        supplier_id: Optional[int] = None,
        reason: str = "",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Safely remove or deactivate a supplier:
        - If money is owed to supplier, block deletion.
        - If purchase history exists, deactivate.
        - If unused, permanently delete.
        """
        if isinstance(session, int) and supplier_id is None:
            supplier_id = session
            session = None

        if session is None:
            with get_db_session() as s:
                return PurchaseService.remove_supplier(session=s, supplier_id=supplier_id, reason=reason, user_id=user_id)

        supplier = session.query(Supplier).filter_by(id=supplier_id).first()
        if not supplier:
            raise ValueError(f"Supplier #{supplier_id} not found.")

        last_entry = (
            session.query(SupplierLedgerEntry)
            .filter_by(supplier_id=supplier_id)
            .order_by(SupplierLedgerEntry.id.desc())
            .first()
        )
        bal = last_entry.running_balance_cents if last_entry else 0
        if bal > 0:
            raise ValueError(f"Cannot remove supplier '{supplier.name}'. You still owe {format_currency(bal)}. Balance must be settled first.")

        has_purchases = session.query(PurchaseInvoice).filter_by(supplier_id=supplier_id).count() > 0
        if has_purchases:
            supplier.is_active = False
            AuditService.log_action(
                session=session,
                action_type="SUPPLIER_DEACTIVATE",
                entity_name="Supplier",
                entity_id=supplier.id,
                reference_no=supplier.name,
                reason=reason or "Deactivated supplier with purchase history",
                user_id=user_id
            )
            return {
                "action": "DEACTIVATED",
                "message": f"Supplier '{supplier.name}' has purchase history. It has been deactivated."
            }
        else:
            s_name = supplier.name
            session.delete(supplier)
            AuditService.log_action(
                session=session,
                action_type="SUPPLIER_DELETE",
                entity_name="Supplier",
                entity_id=supplier_id,
                reason=reason or "Permanently deleted unused supplier",
                user_id=user_id
            )
            return {
                "action": "DELETED",
                "message": f"Supplier '{s_name}' had no purchase history and has been permanently removed."
            }

    @staticmethod
    def reactivate_supplier(
        session: Any = None,
        supplier_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Supplier:
        """Reactivate an archived supplier."""
        if isinstance(session, int) and supplier_id is None:
            supplier_id = session
            session = None

        if session is None:
            with get_db_session() as s:
                return PurchaseService.reactivate_supplier(session=s, supplier_id=supplier_id, user_id=user_id)

        supplier = session.query(Supplier).filter_by(id=supplier_id).first()
        if not supplier:
            raise ValueError(f"Supplier #{supplier_id} not found.")
        supplier.is_active = True
        AuditService.log_action(
            session=session,
            action_type="SUPPLIER_REACTIVATE",
            entity_name="Supplier",
            entity_id=supplier.id,
            reference_no=supplier.name,
            reason="Supplier reactivated",
            user_id=user_id
        )
        return supplier
