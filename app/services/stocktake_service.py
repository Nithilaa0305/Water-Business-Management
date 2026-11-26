"""Physical Stock Verification (Stocktake) Service."""

from datetime import date
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.inventory import StocktakeAudit, StocktakeItem, InventoryBatch
from app.database.models.product import Product
from app.database.models.bottle import BottleInventory
from app.config.constants import BottleState, StockMovementType
from app.services.inventory_service import InventoryService
from app.services.bottle_service import BottleService
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo, today_colombo
from app.utilities.currency import format_currency


class StocktakeService:
    @staticmethod
    def generate_audit_number(session: Session, prefix: str = "STK-") -> str:
        """Generate unique sequential stocktake audit number."""
        date_str = now_colombo().strftime("%Y%m%d")
        pfx = f"{prefix}{date_str}-"
        last = (
            session.query(StocktakeAudit)
            .filter(StocktakeAudit.audit_number.like(f"{pfx}%"))
            .order_by(StocktakeAudit.id.desc())
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.audit_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{pfx}{seq:03d}"

    @staticmethod
    def get_system_snapshot(session: Session) -> Dict[str, Any]:
        """
        Get live system snapshot for stocktake verification:
        - Product stock counts across 5 bottle sizes
        - 19 L container quantities across 7 physical states
        """
        products = session.query(Product).filter_by(is_active=True).order_by(Product.code.asc()).all()
        prod_data = []
        for p in products:
            system_qty = InventoryService.get_available_stock(session, p.id)
            # Find latest batch unit cost
            latest_batch = (
                session.query(InventoryBatch)
                .filter_by(product_id=p.id, status="ACTIVE")
                .order_by(InventoryBatch.id.desc())
                .first()
            )
            cost_cents = latest_batch.unit_cost_cents if latest_batch else 0
            prod_data.append({
                "product_id": p.id,
                "code": p.code,
                "name": p.name,
                "bottle_size": p.bottle_size,
                "recorded_qty": system_qty,
                "unit_cost_cents": cost_cents,
                "unit_cost_display": format_currency(cost_cents),
                "is_returnable": p.is_returnable,
            })

        bottle_states = BottleService.get_all_state_counts(session)
        return {
            "products": prod_data,
            "bottle_states": bottle_states,
        }

    @staticmethod
    def create_stocktake_audit(
        session: Session,
        counts_data: List[Dict[str, Any]],
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
        auto_apply_adjustments: bool = False
    ) -> StocktakeAudit:
        """
        Record a physical stocktake verification session.
        counts_data: list of dicts with:
          - product_id: int
          - counted_qty: int
          - batch_id: Optional[int]
          - reason: Optional[str]
        """
        audit_num = StocktakeService.generate_audit_number(session)
        audit = StocktakeAudit(
            audit_number=audit_num,
            audit_date=now_colombo(),
            status="DRAFT",
            notes=notes,
            user_id=user_id
        )
        session.add(audit)
        session.flush()

        for item_data in counts_data:
            p_id = item_data["product_id"]
            counted = int(item_data["counted_qty"])
            recorded = InventoryService.get_available_stock(session, p_id)
            diff = counted - recorded

            # Find active batch for costing
            batch = None
            if item_data.get("batch_id"):
                batch = session.query(InventoryBatch).filter_by(id=item_data["batch_id"]).first()
            if not batch:
                batch = (
                    session.query(InventoryBatch)
                    .filter_by(product_id=p_id, status="ACTIVE")
                    .order_by(InventoryBatch.id.desc())
                    .first()
                )

            cost_cents = batch.unit_cost_cents if batch else 0
            variance_val_cents = diff * cost_cents

            stk_item = StocktakeItem(
                audit_id=audit.id,
                product_id=p_id,
                batch_id=batch.id if batch else None,
                recorded_qty=recorded,
                counted_qty=counted,
                difference_qty=diff,
                unit_cost_cents=cost_cents,
                variance_value_cents=variance_val_cents,
                reason=item_data.get("reason"),
                is_adjusted=False
            )
            session.add(stk_item)

        session.flush()

        if auto_apply_adjustments:
            StocktakeService.apply_adjustments(session, audit.id, user_id=user_id)

        AuditService.log_action(
            session=session,
            action_type="STOCKTAKE_CREATE",
            entity_name="StocktakeAudit",
            entity_id=audit.id,
            reference_no=audit.audit_number,
            new_values={"items_count": len(counts_data), "status": audit.status},
            reason=notes or "Stocktake audit performed",
            user_id=user_id
        )
        return audit

    @staticmethod
    def apply_adjustments(
        session: Session,
        audit_id: int,
        user_id: Optional[int] = None
    ) -> StocktakeAudit:
        """
        Authorize and apply inventory adjustments based on stocktake discrepancies.
        Updates InventoryBatch records and logs StockMovement and Audit entries.
        """
        audit = session.query(StocktakeAudit).filter_by(id=audit_id).first()
        if not audit:
            raise ValueError(f"Stocktake audit #{audit_id} not found.")

        if audit.status == "COMPLETED":
            raise ValueError("Adjustments for this audit have already been posted.")

        for item in audit.items:
            if item.is_adjusted or item.difference_qty == 0:
                item.is_adjusted = True
                continue

            diff = item.difference_qty
            product = item.product
            batch = item.batch

            if diff < 0:
                # Physical count is less than system -> Shortage
                shortage = abs(diff)
                if batch and batch.remaining_qty >= shortage:
                    InventoryService.adjust_stock(
                        session=session,
                        batch_id=batch.id,
                        adjustment_type="CORRECTION_OUT",
                        quantity=shortage,
                        reason=f"Stocktake {audit.audit_number} variance: shortage",
                        user_id=user_id
                    )
                else:
                    # Allocate shortage across active batches FIFO
                    active_batches = (
                        session.query(InventoryBatch)
                        .filter_by(product_id=product.id, status="ACTIVE")
                        .order_by(InventoryBatch.received_date.asc(), InventoryBatch.id.asc())
                        .all()
                    )
                    rem_shortage = shortage
                    for b in active_batches:
                        if rem_shortage <= 0:
                            break
                        deduct = min(rem_shortage, b.remaining_qty)
                        if deduct > 0:
                            InventoryService.adjust_stock(
                                session=session,
                                batch_id=b.id,
                                adjustment_type="CORRECTION_OUT",
                                quantity=deduct,
                                reason=f"Stocktake {audit.audit_number} variance: shortage",
                                user_id=user_id
                            )
                            rem_shortage -= deduct

            elif diff > 0:
                # Physical count is greater than system -> Surplus
                surplus = diff
                if batch:
                    InventoryService.adjust_stock(
                        session=session,
                        batch_id=batch.id,
                        adjustment_type="CORRECTION_IN",
                        quantity=surplus,
                        reason=f"Stocktake {audit.audit_number} variance: surplus found",
                        user_id=user_id
                    )
                else:
                    # Create new batch for surplus
                    InventoryService.add_batch(
                        session=session,
                        product_id=product.id,
                        quantity=surplus,
                        unit_cost_cents=item.unit_cost_cents,
                        movement_type=StockMovementType.ADJUSTMENT_IN,
                        notes=f"Stocktake {audit.audit_number} surplus inventory batch",
                        user_id=user_id
                    )

            item.is_adjusted = True

        audit.status = "COMPLETED"
        session.commit()

        AuditService.log_action(
            session=session,
            action_type="STOCKTAKE_ADJUST",
            entity_name="StocktakeAudit",
            entity_id=audit.id,
            reference_no=audit.audit_number,
            reason="Authorized stocktake adjustments posted",
            user_id=user_id
        )
        return audit

    @staticmethod
    def adjust_19l_container_state(
        session: Session,
        state: BottleState,
        counted_qty: int,
        reason: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Direct physical reconciliation for 19L bottle states.
        Adjusts state container count to match physical count.
        """
        inv = session.query(BottleInventory).filter_by(state=state.value).first()
        if not inv:
            inv = BottleInventory(state=state.value, quantity=0)
            session.add(inv)

        old_qty = inv.quantity
        diff = counted_qty - old_qty
        inv.quantity = counted_qty
        session.commit()

        AuditService.log_action(
            session=session,
            action_type="BOTTLE_STATE_AUDIT",
            entity_name="BottleInventory",
            entity_id=inv.id,
            reference_no=state.value,
            old_values={"quantity": old_qty},
            new_values={"quantity": counted_qty, "difference": diff},
            reason=reason or f"Physical stocktake count for {state.value}",
            user_id=user_id
        )
        return {
            "state": state.value,
            "old_qty": old_qty,
            "new_qty": counted_qty,
            "difference": diff,
        }
