"""Expense management service."""

from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.connection import get_db_session
from app.database.models.operations import Expense, ExpenseCategory
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo, today_colombo
from app.utilities.currency import to_cents


class ExpenseService:
    @staticmethod
    def record_expense(
        session: Session,
        category_id: int,
        description: str,
        amount_cents: int,
        payment_method: str = "CASH",
        payee: Optional[str] = None,
        reference_no: Optional[str] = None,
        is_paid: bool = True,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Expense:
        """Record business expense."""
        if amount_cents <= 0:
            raise ValueError("Expense amount must be greater than zero.")
        if not description or not description.strip():
            raise ValueError("Description is required.")

        category = session.query(ExpenseCategory).filter_by(id=category_id).first()
        if not category:
            raise ValueError(f"Category #{category_id} not found.")

        expense = Expense(
            date=now_colombo(),
            category_id=category_id,
            description=description.strip(),
            amount_cents=amount_cents,
            payment_method=payment_method,
            payee=payee,
            reference_no=reference_no,
            is_paid=is_paid,
            notes=notes,
            user_id=user_id
        )
        session.add(expense)
        session.flush()

        AuditService.log_action(
            session=session,
            action_type="EXPENSE_ADD",
            entity_name="Expense",
            entity_id=expense.id,
            new_values={"category": category.name, "amount": amount_cents, "desc": description},
            user_id=user_id
        )
        return expense

    @staticmethod
    def delete_expense(
        session: Any = None,
        expense_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> bool:
        """Delete an expense record with audit logging."""
        if isinstance(session, int) and expense_id is None:
            expense_id = session
            session = None

        if session is None:
            with get_db_session() as s:
                return ExpenseService.delete_expense(session=s, expense_id=expense_id, user_id=user_id)

        expense = session.query(Expense).filter_by(id=expense_id).first()
        if not expense:
            raise ValueError(f"Expense #{expense_id} not found.")

        exp_desc = expense.description
        exp_amt = expense.amount_cents
        session.delete(expense)

        AuditService.log_action(
            session=session,
            action_type="EXPENSE_DELETE",
            entity_name="Expense",
            entity_id=expense_id,
            old_values={"description": exp_desc, "amount": exp_amt},
            reason="Deleted expense record",
            user_id=user_id
        )
        return True
