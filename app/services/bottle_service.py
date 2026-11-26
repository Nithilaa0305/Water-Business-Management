"""Special 19 L Returnable Bottle Management: physical states, customer ledger, and reconciliation."""

from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.bottle import BottleInventory, BottleMovement, CustomerBottleLedger
from app.database.models.customer import Customer
from app.config.constants import BottleState, BottleMovementType
from app.utilities.dates import now_colombo, today_colombo
from app.services.audit_service import AuditService


class BottleService:
    @staticmethod
    def get_state_quantity(session: Session, state: BottleState) -> int:
        """Get snapshot bottle count for a given physical state."""
        b = session.query(BottleInventory).filter_by(state=state.value).first()
        return b.quantity if b else 0

    @staticmethod
    def get_all_state_counts(session: Session) -> Dict[str, int]:
        """Get counts across all 7 bottle states."""
        records = session.query(BottleInventory).all()
        counts = {s.value: 0 for s in BottleState}
        for r in records:
            counts[r.state] = r.quantity
        return counts

    @staticmethod
    def move_bottles(
        session: Session,
        from_state: Optional[BottleState],
        to_state: Optional[BottleState],
        quantity: int,
        movement_type: BottleMovementType,
        customer_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        reason: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> BottleMovement:
        """
        Record physical movement between bottle states and update inventory counts.
        Prevents negative stock in warehouse states.
        """
        if quantity <= 0:
            raise ValueError("Bottle movement quantity must be greater than zero.")

        # Deduct from source state
        if from_state is not None:
            source = session.query(BottleInventory).filter_by(state=from_state.value).first()
            if not source:
                source = BottleInventory(state=from_state.value, quantity=0)
                session.add(source)
            if source.quantity < quantity and from_state != BottleState.HELD_BY_CUSTOMERS:
                raise ValueError(
                    f"Insufficient bottles in {from_state.value}. "
                    f"Available: {source.quantity}, requested: {quantity}."
                )
            source.quantity -= quantity

        # Add to destination state
        if to_state is not None:
            dest = session.query(BottleInventory).filter_by(state=to_state.value).first()
            if not dest:
                dest = BottleInventory(state=to_state.value, quantity=0)
                session.add(dest)
            dest.quantity += quantity

        # Record auditable physical movement
        movement = BottleMovement(
            date=now_colombo(),
            movement_type=movement_type.value,
            quantity=quantity,
            from_state=from_state.value if from_state else None,
            to_state=to_state.value if to_state else None,
            customer_id=customer_id,
            invoice_id=invoice_id,
            reason=reason,
            user_id=user_id
        )
        session.add(movement)
        return movement

    @staticmethod
    def record_customer_bottle_movement(
        session: Session,
        customer_id: int,
        movement_type: str,
        full_issued: int = 0,
        empty_returned: int = 0,
        invoice_id: Optional[int] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> CustomerBottleLedger:
        """
        Record customer bottle obligation ledger entry.
        Running bottle balance = previous_balance + full_issued - empty_returned.
        """
        last_entry = (
            session.query(CustomerBottleLedger)
            .filter_by(customer_id=customer_id)
            .order_by(CustomerBottleLedger.id.desc())
            .first()
        )
        prev_balance = last_entry.running_bottle_balance if last_entry else 0
        new_balance = prev_balance + full_issued - empty_returned

        if new_balance < 0:
            raise ValueError(
                f"Customer currently holds {prev_balance} bottles. "
                f"Cannot accept return of {empty_returned} bottles (would cause negative balance)."
            )

        entry = CustomerBottleLedger(
            customer_id=customer_id,
            date=now_colombo(),
            movement_type=movement_type,
            full_issued=full_issued,
            empty_returned=empty_returned,
            running_bottle_balance=new_balance,
            invoice_id=invoice_id,
            user_id=user_id,
            notes=notes
        )
        session.add(entry)
        session.flush()
        return entry

    @staticmethod
    def return_empty_without_purchase(
        session: Session,
        customer_id: int,
        quantity: int,
        reason: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> CustomerBottleLedger:
        """
        Customer returns empty bottles without buying water.
        Decreases customer bottle obligation, increases warehouse EMPTY_AVAILABLE.
        Generates ZERO water sales revenue.
        """
        if quantity <= 0:
            raise ValueError("Return quantity must be greater than zero.")

        # 1. Update customer bottle ledger
        ledger_entry = BottleService.record_customer_bottle_movement(
            session=session,
            customer_id=customer_id,
            movement_type="RETURN_EMPTY_ONLY",
            full_issued=0,
            empty_returned=quantity,
            notes=reason or "Empty bottle return without water purchase",
            user_id=user_id
        )

        # 2. Move bottles: HELD_BY_CUSTOMERS -> EMPTY_AVAILABLE
        BottleService.move_bottles(
            session=session,
            from_state=BottleState.HELD_BY_CUSTOMERS,
            to_state=BottleState.EMPTY_AVAILABLE,
            quantity=quantity,
            movement_type=BottleMovementType.RETURN_EMPTY,
            customer_id=customer_id,
            reason=reason or "Empty bottle return without purchase",
            user_id=user_id
        )

        AuditService.log_action(
            session=session,
            action_type="BOTTLE_RETURN",
            entity_name="CustomerBottleLedger",
            entity_id=ledger_entry.id,
            new_values={"qty": quantity, "new_cust_balance": ledger_entry.running_bottle_balance},
            reason="Customer returned empty bottles",
            user_id=user_id
        )
        return ledger_entry

    @staticmethod
    def reconcile_bottles(session: Session) -> Dict[str, Any]:
        """
        Physical bottle reconciliation across all active and retired states.
        Formula:
        Total Company Containers = FULL + EMPTY + IN_CLEANING + HELD_BY_CUSTOMERS + DAMAGED.
        Retired Containers = LOST_WRITTEN_OFF + PERMANENTLY_SOLD.
        """
        counts = BottleService.get_all_state_counts(session)
        
        active_total = (
            counts[BottleState.FULL_AVAILABLE.value] +
            counts[BottleState.EMPTY_AVAILABLE.value] +
            counts[BottleState.IN_CLEANING_REFILL.value] +
            counts[BottleState.HELD_BY_CUSTOMERS.value] +
            counts[BottleState.DAMAGED.value]
        )
        retired_total = (
            counts[BottleState.LOST_WRITTEN_OFF.value] +
            counts[BottleState.PERMANENTLY_SOLD.value]
        )
        total_tracked = active_total + retired_total

        # Sum of individual customer balances from customer bottle ledger
        subquery = (
            session.query(
                CustomerBottleLedger.customer_id,
                func.max(CustomerBottleLedger.id).label("max_id")
            )
            .group_by(CustomerBottleLedger.customer_id)
            .subquery()
        )
        customer_sum = (
            session.query(func.coalesce(func.sum(CustomerBottleLedger.running_bottle_balance), 0))
            .join(subquery, CustomerBottleLedger.id == subquery.c.max_id)
            .scalar()
        ) or 0

        discrepancy = counts[BottleState.HELD_BY_CUSTOMERS.value] - customer_sum

        return {
            "counts": counts,
            "active_total": active_total,
            "retired_total": retired_total,
            "total_tracked": total_tracked,
            "customer_ledger_sum": int(customer_sum),
            "discrepancy": discrepancy,
            "is_reconciled": discrepancy == 0
        }

    @staticmethod
    def get_customer_bottle_aging(
        session: Session,
        customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculate 19L customer bottle aging report using FIFO allocation policy.
        Empty bottle returns offset the oldest delivered bottles first.
        Unreturned bottles are aged based on delivery date into:
        - 0-7 days (normal turnaround)
        - 8-30 days (due for return)
        - 31-60 days (overdue)
        - >60 days (severely overdue / deposit at risk)
        """
        today = today_colombo()

        # Query customers with active bottle ledger entries
        cust_query = session.query(Customer).filter_by(is_active=True)
        if customer_id:
            cust_query = cust_query.filter(Customer.id == customer_id)
        customers = cust_query.order_by(Customer.name.asc()).all()

        results = []
        for cust in customers:
            entries = (
                session.query(CustomerBottleLedger)
                .filter_by(customer_id=cust.id)
                .order_by(CustomerBottleLedger.date.asc(), CustomerBottleLedger.id.asc())
                .all()
            )
            if not entries:
                continue

            # Latest running balance
            latest_balance = entries[-1].running_bottle_balance
            if latest_balance <= 0:
                continue

            # Total returns to consume FIFO
            total_returns = sum(e.empty_returned for e in entries)

            # Queue of delivery events
            deliveries = [
                {"date": e.date.date() if hasattr(e.date, "date") else e.date, "qty": e.full_issued}
                for e in entries if e.full_issued > 0
            ]

            # FIFO offset of returns against oldest deliveries
            unreturned_batches = []
            rem_returns = total_returns
            for d in deliveries:
                d_qty = d["qty"]
                if rem_returns >= d_qty:
                    rem_returns -= d_qty
                else:
                    unreturned = d_qty - rem_returns
                    rem_returns = 0
                    unreturned_batches.append({"date": d["date"], "qty": unreturned})

            # Age unreturned bottles
            d0_7 = 0
            d8_30 = 0
            d31_60 = 0
            over_60 = 0

            for b in unreturned_batches:
                age_days = (today - b["date"]).days
                b_qty = b["qty"]
                if age_days <= 7:
                    d0_7 += b_qty
                elif age_days <= 30:
                    d8_30 += b_qty
                elif age_days <= 60:
                    d31_60 += b_qty
                else:
                    over_60 += b_qty

            results.append({
                "customer_id": cust.id,
                "customer_code": cust.code,
                "customer_name": cust.name,
                "customer_phone": cust.phone,
                "total_held": latest_balance,
                "d0_7": d0_7,
                "d8_30": d8_30,
                "d31_60": d31_60,
                "over_60": over_60,
            })

        return results

