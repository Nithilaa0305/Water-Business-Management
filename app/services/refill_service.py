"""19 L Bottle Refilling, Batch Production, and Costing Service."""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database.models.bottle import RefillBatch
from app.database.models.product import Product
from app.config.constants import BottleState, BottleMovementType, StockMovementType
from app.services.bottle_service import BottleService
from app.services.inventory_service import InventoryService
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo, today_colombo
from app.utilities.currency import to_cents


class RefillService:
    @staticmethod
    def generate_refill_batch_number(session: Session) -> str:
        """Generate unique sequential refill batch number (e.g. REFILL-20261125-001)."""
        d = today_colombo()
        date_str = d.strftime("%Y%m%d")
        prefix = f"REFILL-{date_str}-"
        last = (
            session.query(RefillBatch)
            .filter(RefillBatch.refill_batch_number.like(f"{prefix}%"))
            .order_by(RefillBatch.id.desc())
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.refill_batch_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{prefix}{seq:03d}"

    @staticmethod
    def execute_refill_batch(
        session: Session,
        empty_bottles_selected: int,
        bottles_refilled: int,
        bottles_rejected_damaged: int = 0,
        water_treatment_cost_cents: int = 0,
        cleaning_cost_cents: int = 0,
        cap_seal_cost_cents: int = 0,
        labour_cost_cents: int = 0,
        other_cost_cents: int = 0,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> RefillBatch:
        """
        Execute 19L bottle refill workflow:
        1. Validates selected bottles <= available empty stock.
        2. Validates refilled + damaged == selected.
        3. Moves empty bottles from EMPTY_AVAILABLE to FULL_AVAILABLE (refilled) and DAMAGED.
        4. Calculates unit production cost = total costs / bottles_refilled.
        5. Automatically creates an active inventory batch for product W19000.
        6. Creates ZERO sales revenue.
        """
        if empty_bottles_selected <= 0:
            raise ValueError("Empty bottles selected must be greater than zero.")
        if bottles_refilled < 0 or bottles_rejected_damaged < 0:
            raise ValueError("Refilled and damaged counts cannot be negative.")
        if (bottles_refilled + bottles_rejected_damaged) != empty_bottles_selected:
            raise ValueError(
                f"Count mismatch: Refilled ({bottles_refilled}) + Damaged ({bottles_rejected_damaged}) "
                f"must equal selected empty bottles ({empty_bottles_selected})."
            )

        # Check warehouse empty stock
        available_empty = BottleService.get_state_quantity(session, BottleState.EMPTY_AVAILABLE)
        if available_empty < empty_bottles_selected:
            raise ValueError(
                f"Cannot refill {empty_bottles_selected} bottles. "
                f"Only {available_empty} empty bottles available in warehouse."
            )

        # Calculate costs
        total_costs_cents = (
            water_treatment_cost_cents +
            cleaning_cost_cents +
            cap_seal_cost_cents +
            labour_cost_cents +
            other_cost_cents
        )
        unit_cost_cents = (total_costs_cents // bottles_refilled) if bottles_refilled > 0 else 0

        refill_num = RefillService.generate_refill_batch_number(session)

        # 1. Physical bottle movements:
        # Move empty bottles to cleaning/refill
        BottleService.move_bottles(
            session=session,
            from_state=BottleState.EMPTY_AVAILABLE,
            to_state=BottleState.IN_CLEANING_REFILL,
            quantity=empty_bottles_selected,
            movement_type=BottleMovementType.REFILL_START,
            reason=f"Batch {refill_num} started",
            user_id=user_id
        )

        # Move successfully refilled to FULL_AVAILABLE
        if bottles_refilled > 0:
            BottleService.move_bottles(
                session=session,
                from_state=BottleState.IN_CLEANING_REFILL,
                to_state=BottleState.FULL_AVAILABLE,
                quantity=bottles_refilled,
                movement_type=BottleMovementType.REFILL_FINISH,
                reason=f"Batch {refill_num} completed",
                user_id=user_id
            )

        # Move rejected/damaged to DAMAGED
        if bottles_rejected_damaged > 0:
            BottleService.move_bottles(
                session=session,
                from_state=BottleState.IN_CLEANING_REFILL,
                to_state=BottleState.DAMAGED,
                quantity=bottles_rejected_damaged,
                movement_type=BottleMovementType.REFILL_REJECT,
                reason=f"Batch {refill_num} rejected/damaged",
                user_id=user_id
            )

        # 2. Add inventory batch for 19L product (W19000)
        prod_19l = session.query(Product).filter_by(code="W19000").first()
        if not prod_19l:
            raise ValueError("19 L Product (code 'W19000') not found in database.")

        inv_batch = None
        if bottles_refilled > 0:
            inv_batch = InventoryService.add_batch(
                session=session,
                product_id=prod_19l.id,
                quantity=bottles_refilled,
                unit_cost_cents=unit_cost_cents,
                suggested_selling_price_cents=prod_19l.default_selling_price_cents,
                movement_type=StockMovementType.REFILL_IN,
                reference_type="REFILL",
                notes=f"Refilled via {refill_num}",
                user_id=user_id,
                custom_batch_number=f"BATCH-W19000-{today_colombo().strftime('%Y%m%d')}-{refill_num.split('-')[-1]}"
            )

        # 3. Create RefillBatch record
        refill_batch = RefillBatch(
            refill_batch_number=refill_num,
            date=now_colombo(),
            empty_bottles_selected=empty_bottles_selected,
            bottles_cleaned=empty_bottles_selected,
            bottles_refilled=bottles_refilled,
            bottles_rejected_damaged=bottles_rejected_damaged,
            water_treatment_cost_cents=water_treatment_cost_cents,
            cleaning_cost_cents=cleaning_cost_cents,
            cap_seal_cost_cents=cap_seal_cost_cents,
            labour_cost_cents=labour_cost_cents,
            other_cost_cents=other_cost_cents,
            total_cost_cents=total_costs_cents,
            unit_cost_cents=unit_cost_cents,
            inventory_batch_id=inv_batch.id if inv_batch else None,
            user_id=user_id,
            notes=notes
        )
        session.add(refill_batch)

        AuditService.log_action(
            session=session,
            action_type="BOTTLE_REFILL",
            entity_name="RefillBatch",
            entity_id=refill_batch.id,
            reference_no=refill_num,
            new_values={
                "refilled": bottles_refilled,
                "damaged": bottles_rejected_damaged,
                "total_cost": total_costs_cents
            },
            reason=f"Refilled {bottles_refilled} 19L bottles",
            user_id=user_id
        )
        return refill_batch
