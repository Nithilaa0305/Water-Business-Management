"""First-In, First-Out (FIFO) Costing and Batch Allocation Service."""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database.models.inventory import InventoryBatch
from app.database.models.product import Product
from app.utilities.currency import format_currency


class FIFOService:
    @staticmethod
    def get_active_batches(session: Session, product_id: int) -> List[InventoryBatch]:
        """Fetch active batches for a product sorted strictly by oldest received date then ID (FIFO order)."""
        return (
            session.query(InventoryBatch)
            .filter(InventoryBatch.product_id == product_id)
            .filter(InventoryBatch.status == "ACTIVE")
            .filter(InventoryBatch.remaining_qty > 0)
            .order_by(InventoryBatch.received_date.asc(), InventoryBatch.id.asc())
            .all()
        )

    @staticmethod
    def preview_fifo_allocation(
        session: Session,
        product_id: int,
        required_base_qty: int,
        selling_price_cents: int,
        specific_batch_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Simulate FIFO allocation without mutating database state.
        Returns total cost of goods sold, batch breakdown, and below-cost warnings.
        """
        if required_base_qty <= 0:
            return {"allocations": [], "total_cogs_cents": 0, "sufficient": True, "below_cost": False}

        if specific_batch_id:
            batches = (
                session.query(InventoryBatch)
                .filter(InventoryBatch.id == specific_batch_id)
                .filter(InventoryBatch.status == "ACTIVE")
                .filter(InventoryBatch.remaining_qty > 0)
                .all()
            )
        else:
            batches = FIFOService.get_active_batches(session, product_id)

        available_qty = sum(b.remaining_qty for b in batches)
        if available_qty < required_base_qty:
            prod = session.query(Product).filter_by(id=product_id).first()
            prod_name = prod.name if prod else f"Product #{product_id}"
            return {
                "sufficient": False,
                "available_qty": available_qty,
                "required_qty": required_base_qty,
                "error_message": f"Only {available_qty} bottles available of {prod_name}. Cannot fulfill {required_base_qty} bottles."
            }

        needed = required_base_qty
        allocations = []
        total_cogs_cents = 0
        below_cost_detected = False

        for batch in batches:
            if needed <= 0:
                break
            take_qty = min(needed, batch.remaining_qty)
            cost_cents = batch.unit_cost_cents
            line_cogs = take_qty * cost_cents
            total_cogs_cents += line_cogs

            if selling_price_cents < cost_cents:
                below_cost_detected = True

            allocations.append({
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "quantity": take_qty,
                "unit_cost_cents": cost_cents,
                "unit_cost_display": format_currency(cost_cents),
                "total_cogs_cents": line_cogs,
                "below_cost": selling_price_cents < cost_cents
            })
            needed -= take_qty

        return {
            "sufficient": True,
            "allocations": allocations,
            "total_cogs_cents": total_cogs_cents,
            "below_cost": below_cost_detected
        }

    @staticmethod
    def execute_fifo_allocation(
        session: Session,
        product_id: int,
        required_base_qty: int,
        selling_price_cents: int,
        specific_batch_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Deduct quantities from oldest batches in FIFO order.
        Updates batch remaining_qty and status atomically.
        """
        preview = FIFOService.preview_fifo_allocation(
            session=session,
            product_id=product_id,
            required_base_qty=required_base_qty,
            selling_price_cents=selling_price_cents,
            specific_batch_id=specific_batch_id
        )

        if not preview.get("sufficient", False):
            raise ValueError(preview.get("error_message", "Insufficient stock."))

        committed_allocations = []
        for alloc in preview["allocations"]:
            batch = session.query(InventoryBatch).filter_by(id=alloc["batch_id"]).first()
            take_qty = alloc["quantity"]
            batch.remaining_qty -= take_qty
            if batch.remaining_qty == 0:
                batch.status = "EXHAUSTED"

            committed_allocations.append({
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "quantity": take_qty,
                "unit_cost_cents": alloc["unit_cost_cents"],
                "unit_price_cents": selling_price_cents
            })

        return committed_allocations
