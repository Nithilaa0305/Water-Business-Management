"""Refundable Bottle Deposit Liability Management."""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database.models.bottle import BottleDeposit, BottleDepositTransaction
from app.database.models.customer import Customer
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo


class DepositService:
    @staticmethod
    def generate_deposit_number(session: Session) -> str:
        """Generate unique deposit number (e.g. DEP-202611-0001)."""
        date_str = now_colombo().strftime("%Y%m")
        prefix = f"DEP-{date_str}-"
        last = (
            session.query(BottleDeposit)
            .filter(BottleDeposit.deposit_number.like(f"{prefix}%"))
            .order_by(BottleDeposit.id.desc())
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.deposit_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def collect_deposit(
        session: Session,
        customer_id: int,
        bottle_count: int,
        deposit_per_bottle_cents: int,
        invoice_id: Optional[int] = None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> BottleDeposit:
        """
        Record collection of refundable bottle deposits.
        Deposits are treated strictly as customer liabilities, NEVER as sales revenue.
        """
        if bottle_count <= 0 or deposit_per_bottle_cents <= 0:
            raise ValueError("Bottle count and deposit per bottle must be greater than zero.")

        total_cents = bottle_count * deposit_per_bottle_cents
        dep_num = DepositService.generate_deposit_number(session)

        deposit = BottleDeposit(
            deposit_number=dep_num,
            customer_id=customer_id,
            invoice_id=invoice_id,
            bottle_count=bottle_count,
            deposit_per_bottle_cents=deposit_per_bottle_cents,
            total_deposit_cents=total_cents,
            refunded_deposit_cents=0,
            balance_deposit_cents=total_cents,
            status="ACTIVE",
            date=now_colombo(),
            user_id=user_id
        )
        session.add(deposit)
        session.flush()

        # Record transaction
        tx = BottleDepositTransaction(
            deposit_id=deposit.id,
            customer_id=customer_id,
            transaction_type="COLLECTED",
            amount_cents=total_cents,
            bottle_count=bottle_count,
            date=now_colombo(),
            user_id=user_id,
            notes=notes or "Deposit collected upon bottle issue"
        )
        session.add(tx)

        AuditService.log_action(
            session=session,
            action_type="DEPOSIT_COLLECT",
            entity_name="BottleDeposit",
            entity_id=deposit.id,
            reference_no=dep_num,
            new_values={"bottles": bottle_count, "amount": total_cents},
            user_id=user_id
        )
        return deposit

    @staticmethod
    def refund_deposit(
        session: Session,
        deposit_id: int,
        refund_bottles: int,
        user_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> BottleDepositTransaction:
        """
        Refund customer bottle deposit.
        Reduces deposit liability and records cash outflow. Does NOT affect sales revenue.
        """
        deposit = session.query(BottleDeposit).filter_by(id=deposit_id).first()
        if not deposit:
            raise ValueError(f"Deposit #{deposit_id} not found.")

        remaining_bottles = deposit.bottle_count - (deposit.refunded_deposit_cents // deposit.deposit_per_bottle_cents)
        if refund_bottles <= 0 or refund_bottles > remaining_bottles:
            raise ValueError(
                f"Cannot refund {refund_bottles} bottles. "
                f"Maximum refundable: {remaining_bottles} bottles."
            )

        refund_amount_cents = refund_bottles * deposit.deposit_per_bottle_cents
        deposit.refunded_deposit_cents += refund_amount_cents
        deposit.balance_deposit_cents -= refund_amount_cents
        if deposit.balance_deposit_cents == 0:
            deposit.status = "REFUNDED"

        tx = BottleDepositTransaction(
            deposit_id=deposit.id,
            customer_id=deposit.customer_id,
            transaction_type="REFUNDED",
            amount_cents=refund_amount_cents,
            bottle_count=refund_bottles,
            date=now_colombo(),
            user_id=user_id,
            notes=notes or f"Refunded deposit for {refund_bottles} bottles"
        )
        session.add(tx)

        AuditService.log_action(
            session=session,
            action_type="DEPOSIT_REFUND",
            entity_name="BottleDeposit",
            entity_id=deposit.id,
            reference_no=deposit.deposit_number,
            new_values={"refund_bottles": refund_bottles, "refund_amount": refund_amount_cents},
            user_id=user_id
        )
        return tx
