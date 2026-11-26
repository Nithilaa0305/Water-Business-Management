"""Customer credit, payment allocation, advances, and aging reports."""

from datetime import date, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.customer import Customer
from app.database.models.sales import SalesInvoice
from app.database.models.payment import CustomerPayment, CustomerPaymentAllocation, CustomerLedgerEntry
from app.utilities.dates import today_colombo, now_colombo
from app.utilities.currency import format_currency


class CreditService:
    @staticmethod
    def get_unpaid_invoices(session: Session, customer_id: int) -> List[SalesInvoice]:
        """Fetch all posted unpaid or partially paid invoices for a customer, oldest first."""
        return (
            session.query(SalesInvoice)
            .filter(SalesInvoice.customer_id == customer_id)
            .filter(SalesInvoice.status == "POSTED")
            .filter(SalesInvoice.amount_paid_cents < SalesInvoice.total_amount_cents)
            .order_by(SalesInvoice.invoice_date.asc(), SalesInvoice.id.asc())
            .all()
        )

    @staticmethod
    def allocate_payment_to_invoices(
        session: Session,
        payment_id: int,
        customer_id: int,
        total_payment_cents: int,
        specific_invoice_allocations: Optional[Dict[int, int]] = None
    ) -> Tuple[int, int]:
        """
        Allocate payment amount against customer's invoices.
        If specific_invoice_allocations is provided: allocates specified amounts to those invoices.
        Otherwise: automatically allocates to the oldest unpaid invoices first.
        Any leftover payment amount is returned as customer advance.
        Returns: (total_allocated_cents, advance_cents)
        """
        remaining_payment = total_payment_cents
        total_allocated = 0

        if specific_invoice_allocations:
            # Manual allocation
            for inv_id, alloc_amount in specific_invoice_allocations.items():
                if remaining_payment <= 0:
                    break
                invoice = session.query(SalesInvoice).filter_by(id=inv_id, customer_id=customer_id).first()
                if not invoice:
                    continue
                due = invoice.total_amount_cents - invoice.amount_paid_cents
                actual_alloc = min(remaining_payment, alloc_amount, due)
                if actual_alloc > 0:
                    invoice.amount_paid_cents += actual_alloc
                    alloc = CustomerPaymentAllocation(
                        payment_id=payment_id,
                        invoice_id=invoice.id,
                        allocated_amount_cents=actual_alloc
                    )
                    session.add(alloc)
                    remaining_payment -= actual_alloc
                    total_allocated += actual_alloc
        else:
            # Automatic oldest-first allocation
            unpaid_invoices = CreditService.get_unpaid_invoices(session, customer_id)
            for inv in unpaid_invoices:
                if remaining_payment <= 0:
                    break
                due = inv.total_amount_cents - inv.amount_paid_cents
                alloc_amount = min(remaining_payment, due)
                inv.amount_paid_cents += alloc_amount
                alloc = CustomerPaymentAllocation(
                    payment_id=payment_id,
                    invoice_id=inv.id,
                    allocated_amount_cents=alloc_amount
                )
                session.add(alloc)
                remaining_payment -= alloc_amount
                total_allocated += alloc_amount

        advance_cents = max(0, remaining_payment)
        return total_allocated, advance_cents

    @staticmethod
    def get_customer_aging(session: Session, customer_id: int) -> Dict[str, Any]:
        """
        Calculate credit aging brackets:
        - Current (not yet due)
        - 1-30 days overdue
        - 31-60 days overdue
        - 61-90 days overdue
        - >90 days overdue
        """
        today = today_colombo()
        invoices = CreditService.get_unpaid_invoices(session, customer_id)
        
        current_cents = 0
        d1_30_cents = 0
        d31_60_cents = 0
        d61_90_cents = 0
        over90_cents = 0

        for inv in invoices:
            due = inv.total_amount_cents - inv.amount_paid_cents
            due_date = inv.due_date or inv.invoice_date.date()
            days_overdue = (today - due_date).days

            if days_overdue <= 0:
                current_cents += due
            elif days_overdue <= 30:
                d1_30_cents += due
            elif days_overdue <= 60:
                d31_60_cents += due
            elif days_overdue <= 90:
                d61_90_cents += due
            else:
                over90_cents += due

        total_due = current_cents + d1_30_cents + d31_60_cents + d61_90_cents + over90_cents

        return {
            "customer_id": customer_id,
            "current_cents": current_cents,
            "d1_30_cents": d1_30_cents,
            "d31_60_cents": d31_60_cents,
            "d61_90_cents": d61_90_cents,
            "over90_cents": over90_cents,
            "total_overdue_cents": d1_30_cents + d31_60_cents + d61_90_cents + over90_cents,
            "total_due_cents": total_due,
            "total_due_display": format_currency(total_due)
        }
