"""Inventory management service: batch handling, movements, and stock calculations."""

from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.product import Product, PackagingUnit, ProductPriceHistory
from app.database.models.inventory import InventoryBatch, StockMovement, StockAdjustment
from app.config.constants import StockMovementType
from app.utilities.dates import today_colombo, now_colombo
from app.utilities.currency import to_cents
from app.services.audit_service import AuditService
from app.database.connection import get_db_session


class InventoryService:
    @staticmethod
    def generate_batch_number(session: Session, product_code: str, custom_date: Optional[date] = None) -> str:
        """Generate a unique sequential batch number (e.g. BATCH-W0500-20261125-001)."""
        d = custom_date or today_colombo()
        date_str = d.strftime("%Y%m%d")
        prefix = f"BATCH-{product_code}-{date_str}-"
        
        last_batch = (
            session.query(InventoryBatch)
            .filter(InventoryBatch.batch_number.like(f"{prefix}%"))
            .order_by(InventoryBatch.id.desc())
            .first()
        )
        seq = 1
        if last_batch:
            try:
                seq = int(last_batch.batch_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{prefix}{seq:03d}"

    @staticmethod
    def get_available_stock(session: Session, product_id: int) -> int:
        """Get total base units available for a product across active batches."""
        total = (
            session.query(func.coalesce(func.sum(InventoryBatch.remaining_qty), 0))
            .filter(InventoryBatch.product_id == product_id)
            .filter(InventoryBatch.status == "ACTIVE")
            .filter(InventoryBatch.remaining_qty > 0)
            .scalar()
        )
        return int(total)

    @staticmethod
    def get_stock_by_packaging_unit(session: Session, product_id: int, packaging_unit_id: Optional[int] = None) -> Dict[str, Any]:
        """Get available stock formatted by base bottles and full cases."""
        base_stock = InventoryService.get_available_stock(session, product_id)
        factor = 1
        unit_name = "Bottles"
        if packaging_unit_id:
            unit = session.query(PackagingUnit).filter_by(id=packaging_unit_id).first()
            if unit:
                factor = unit.factor
                unit_name = unit.name
        
        full_units = base_stock // factor
        loose_bottles = base_stock % factor
        return {
            "base_bottles": base_stock,
            "packaging_qty": full_units,
            "loose_bottles": loose_bottles,
            "unit_name": unit_name,
            "factor": factor
        }

    @staticmethod
    def add_batch(
        session: Session,
        product_id: int,
        quantity: int,
        unit_cost_cents: int,
        received_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
        mfg_date: Optional[date] = None,
        supplier_id: Optional[int] = None,
        production_batch_id: Optional[int] = None,
        suggested_selling_price_cents: Optional[int] = None,
        movement_type: StockMovementType = StockMovementType.PURCHASE,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
        custom_batch_number: Optional[str] = None
    ) -> InventoryBatch:
        """Create a new inventory batch and corresponding stock movement."""
        if quantity <= 0:
            raise ValueError("Batch quantity must be greater than zero.")
        
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        rec_date = received_date or today_colombo()
        batch_num = custom_batch_number or InventoryService.generate_batch_number(session, product.code, rec_date)

        # Ensure batch number uniqueness
        existing = session.query(InventoryBatch).filter_by(batch_number=batch_num).first()
        if existing:
            batch_num = f"{batch_num}-R{int(now_colombo().timestamp()) % 1000}"

        batch = InventoryBatch(
            batch_number=batch_num,
            product_id=product_id,
            supplier_id=supplier_id,
            production_batch_id=production_batch_id,
            received_date=rec_date,
            mfg_date=mfg_date,
            expiry_date=expiry_date,
            original_qty=quantity,
            remaining_qty=quantity,
            unit_cost_cents=unit_cost_cents,
            suggested_selling_price_cents=suggested_selling_price_cents or product.default_selling_price_cents,
            status="ACTIVE",
            notes=notes,
            created_by_user_id=user_id
        )
        session.add(batch)
        session.flush()

        # Record movement
        movement = StockMovement(
            date=now_colombo(),
            product_id=product_id,
            batch_id=batch.id,
            movement_type=movement_type.value,
            quantity=quantity,
            unit_cost_cents=unit_cost_cents,
            reference_type=reference_type,
            reference_id=reference_id,
            reason=f"Batch {batch_num} received",
            user_id=user_id
        )
        session.add(movement)

        AuditService.log_action(
            session=session,
            action_type="STOCK_ADD",
            entity_name="InventoryBatch",
            entity_id=batch.id,
            reference_no=batch.batch_number,
            new_values={"qty": quantity, "cost_cents": unit_cost_cents, "product": product.name},
            user_id=user_id,
            reason=f"Added {quantity} bottles to stock"
        )
        return batch

    @staticmethod
    def adjust_stock(
        session: Session,
        batch_id: int,
        adjustment_type: str,  # 'DAMAGE', 'EXPIRED', 'LOST', 'CORRECTION_IN', 'CORRECTION_OUT'
        quantity: int,
        reason: str,
        user_id: Optional[int] = None
    ) -> StockAdjustment:
        """Adjust stock in a specific batch with mandatory reason."""
        if quantity <= 0:
            raise ValueError("Adjustment quantity must be greater than zero.")
        if not reason or not reason.strip():
            raise ValueError("A clear reason is required for any stock adjustment.")

        batch = session.query(InventoryBatch).filter_by(id=batch_id).first()
        if not batch:
            raise ValueError(f"Batch ID {batch_id} not found.")

        old_remaining = batch.remaining_qty

        if adjustment_type in ("DAMAGE", "EXPIRED", "LOST", "CORRECTION_OUT"):
            if batch.remaining_qty < quantity:
                raise ValueError(
                    f"Cannot reduce {quantity} bottles from Batch {batch.batch_number}. "
                    f"Only {batch.remaining_qty} bottles available."
                )
            batch.remaining_qty -= quantity
            if batch.remaining_qty == 0:
                batch.status = "EXHAUSTED"
            movement_qty = -quantity
            movement_type = StockMovementType.DAMAGE if adjustment_type == "DAMAGE" else StockMovementType.ADJUSTMENT_OUT
        elif adjustment_type == "CORRECTION_IN":
            batch.remaining_qty += quantity
            batch.status = "ACTIVE"
            movement_qty = quantity
            movement_type = StockMovementType.ADJUSTMENT_IN
        else:
            raise ValueError(f"Unknown adjustment type: {adjustment_type}")

        # Record adjustment
        adj = StockAdjustment(
            date=now_colombo(),
            product_id=batch.product_id,
            batch_id=batch.id,
            adjustment_type=adjustment_type,
            quantity=quantity,
            reason=reason,
            user_id=user_id
        )
        session.add(adj)
        session.flush()

        # Record stock movement
        m = StockMovement(
            date=now_colombo(),
            product_id=batch.product_id,
            batch_id=batch.id,
            movement_type=movement_type.value,
            quantity=movement_qty,
            unit_cost_cents=batch.unit_cost_cents,
            reference_type="ADJUSTMENT",
            reference_id=adj.id,
            reason=reason,
            user_id=user_id
        )
        session.add(m)

        AuditService.log_action(
            session=session,
            action_type="STOCK_ADJUSTMENT",
            entity_name="InventoryBatch",
            entity_id=batch.id,
            reference_no=batch.batch_number,
            old_values={"remaining_qty": old_remaining},
            new_values={"remaining_qty": batch.remaining_qty, "adjustment_type": adjustment_type},
            reason=reason,
            user_id=user_id
        )
        return adj

    @staticmethod
    def remove_product(
        session: Any = None,
        product_id: Optional[int] = None,
        reason: str = "",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Safely remove or deactivate a product:
        - If product has remaining stock, block deletion.
        - If product has historical batches/sales, deactivate (is_active = False).
        - If unused, permanently delete.
        """
        if isinstance(session, int) and product_id is None:
            product_id = session
            session = None

        if session is None:
            with get_db_session() as s:
                return InventoryService.remove_product(session=s, product_id=product_id, reason=reason, user_id=user_id)

        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            raise ValueError(f"Product #{product_id} not found.")

        avail_stock = InventoryService.get_available_stock(session, product_id)
        if avail_stock > 0:
            raise ValueError(
                f"Cannot remove product '{product.name}'. "
                f"There are currently {avail_stock} bottles in stock. "
                f"Remaining stock must be sold or written off before removal."
            )

        has_batches = session.query(InventoryBatch).filter_by(product_id=product_id).count() > 0
        if has_batches:
            product.is_active = False
            AuditService.log_action(
                session=session,
                action_type="PRODUCT_DEACTIVATE",
                entity_name="Product",
                entity_id=product.id,
                reference_no=product.code,
                reason=reason or "Deactivated product with past batches",
                user_id=user_id
            )
            return {
                "action": "DEACTIVATED",
                "message": f"Product '{product.name}' has historical sales/batch records. It has been deactivated and hidden from new bills."
            }
        else:
            p_name = product.name
            session.delete(product)
            AuditService.log_action(
                session=session,
                action_type="PRODUCT_DELETE",
                entity_name="Product",
                entity_id=product_id,
                reason=reason or "Permanently deleted unused product",
                user_id=user_id
            )
            return {
                "action": "DELETED",
                "message": f"Product '{p_name}' had no stock history and has been permanently removed."
            }

    @staticmethod
    def reactivate_product(
        session: Any = None,
        product_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Product:
        """Reactivate an archived product."""
        if isinstance(session, int) and product_id is None:
            product_id = session
            session = None

        if session is None:
            with get_db_session() as s:
                return InventoryService.reactivate_product(session=s, product_id=product_id, user_id=user_id)

        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            raise ValueError(f"Product #{product_id} not found.")
        product.is_active = True
        AuditService.log_action(
            session=session,
            action_type="PRODUCT_REACTIVATE",
            entity_name="Product",
            entity_id=product.id,
            reference_no=product.code,
            reason="Product reactivated",
            user_id=user_id
        )
        return product
