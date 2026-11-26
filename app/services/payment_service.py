"""Payment processing service for Customers and Suppliers."""

from typing import Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.customer import Customer
from app.database.models.payment import CustomerPayment, CustomerLedgerEntry
from app.services.credit_service import CreditService
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo
from app.utilities.currency import format_currency


class PaymentService:
    @staticmethod
    def generate_payment_number(session: Session, prefix: str = "RCP-") -> str:
        """Generate unique receipt / payment number."""
        date_str = now_colombo().strftime("%Y%m")
        pfx = f"{prefix}{date_str}-"
        last = (
            session.query(CustomerPayment)
            .filter(CustomerPayment.payment_number.like(f"{pfx}%"))
            .order_by(CustomerPayment.id.desc())
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.payment_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{pfx}{seq:04d}"

    @staticmethod
    def record_customer_payment(
        session: Session,
        customer_id: int,
        amount_cents: int,
        payment_method: str = "CASH",
        reference_no: Optional[str] = None,
        notes: Optional[str] = None,
        specific_invoice_allocations: Optional[Dict[int, int]] = None,
        user_id: Optional[int] = None
    ) -> CustomerPayment:
        """
        Record a customer payment.
        Allocates to unpaid invoices (oldest first or manual).
        If customer overpays, remaining amount becomes an advance (credit to customer).
        Updates customer ledger atomically.
        """
        if amount_cents <= 0:
            raise ValueError("Payment amount must be greater than zero.")

        customer = session.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            raise ValueError(f"Customer #{customer_id} not found.")

        pay_num = PaymentService.generate_payment_number(session, prefix="RCP-")

        # Create payment record
        payment = CustomerPayment(
            payment_number=pay_num,
            customer_id=customer_id,
            payment_date=now_colombo(),
            amount_cents=amount_cents,
            payment_method=payment_method,
            reference_no=reference_no,
            unallocated_amount_cents=0,  # Will be updated below
            notes=notes,
            user_id=user_id
        )
        session.add(payment)
        session.flush()

        # Allocate against invoices
        allocated_cents, advance_cents = CreditService.allocate_payment_to_invoices(
            session=session,
            payment_id=payment.id,
            customer_id=customer_id,
            total_payment_cents=amount_cents,
            specific_invoice_allocations=specific_invoice_allocations
        )
        payment.unallocated_amount_cents = advance_cents

        # Update Customer Ledger
        last_entry = (
            session.query(CustomerLedgerEntry)
            .filter_by(customer_id=customer_id)
            .order_by(CustomerLedgerEntry.date.desc(), CustomerLedgerEntry.id.desc())
            .first()
        )
        prev_balance = last_entry.running_balance_cents if last_entry else 0
        new_balance = prev_balance - amount_cents

        ledger_entry = CustomerLedgerEntry(
            customer_id=customer_id,
            date=now_colombo(),
            transaction_type="PAYMENT",
            reference_no=payment.payment_number,
            debit_cents=0,
            credit_cents=amount_cents,
            running_balance_cents=new_balance,
            user_id=user_id,
            notes=f"Payment via {payment_method}" + (f" (Advance: {format_currency(advance_cents)})" if advance_cents > 0 else "")
        )
        session.add(ledger_entry)
        session.flush()

        AuditService.log_action(
            session=session,
            action_type="PAYMENT_RECEIVE",
            entity_name="CustomerPayment",
            entity_id=payment.id,
            reference_no=payment.payment_number,
            new_values={"amount": amount_cents, "method": payment_method, "advance": advance_cents},
            reason="Customer payment received",
            user_id=user_id
        )
        return payment
