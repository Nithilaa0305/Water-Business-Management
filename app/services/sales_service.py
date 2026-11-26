"""Sales Billing, Invoice Processing, Credit Sales, Returns and Cancellations."""

from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database.models.sales import (
    SalesInvoice, SalesInvoiceItem, SaleBatchAllocation, SalesReturn, SalesReturnItem, CreditNote
)
from app.database.models.customer import Customer
from app.database.models.product import Product, PackagingUnit
from app.database.models.payment import CustomerLedgerEntry, CustomerPayment
from app.database.models.inventory import StockMovement, InventoryBatch
from app.config.constants import (
    StockMovementType, BottleState, BottleMovementType, InvoiceStatus
)
from app.services.fifo_service import FIFOService
from app.services.bottle_service import BottleService
from app.services.credit_service import CreditService
from app.services.payment_service import PaymentService
from app.services.pricing_service import PricingService
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo, today_colombo
from app.utilities.currency import format_currency


class SalesService:
    @staticmethod
    def generate_invoice_number(session: Session, prefix: str = "INV-") -> str:
        """Generate unique sequential invoice number (e.g. INV-202611-0001)."""
        date_str = now_colombo().strftime("%Y%m")
        pfx = f"{prefix}{date_str}-"
        last = (
            session.query(SalesInvoice)
            .filter(SalesInvoice.invoice_number.like(f"{pfx}%"))
            .order_by(SalesInvoice.id.desc())
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.invoice_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{pfx}{seq:04d}"

    @staticmethod
    def create_invoice(
        session: Session,
        items_data: List[Dict[str, Any]],
        customer_id: Optional[int] = None,
        payment_method: str = "CASH",
        amount_paid_cents: int = 0,
        discount_cents: int = 0,
        delivery_charge_cents: int = 0,
        tax_cents: int = 0,
        due_date: Optional[date] = None,
        notes: Optional[str] = None,
        empty_19l_returned: int = 0,
        bottle_deposit_cents: int = 0,
        payment_allocation_mode: str = "CURRENT_INVOICE",
        user_id: Optional[int] = None
    ) -> SalesInvoice:
        """
        Create and post a complete sales invoice.
        Executes atomically:
        - FIFO batch allocations and COGS calculation.
        - Physical stock movements.
        - 19L bottle state updates and customer bottle ledger.
        - Customer credit and payment allocation.
        - Customer ledger entry.
        - Append-only audit record.
        """
        if not items_data:
            raise ValueError("An invoice must contain at least one item.")

        customer = None
        if customer_id:
            customer = session.query(Customer).filter_by(id=customer_id).first()
            if not customer:
                raise ValueError(f"Customer #{customer_id} not found.")

        # If credit sale or bottle obligations exist, customer is mandatory
        is_credit = payment_method == "CREDIT" or amount_paid_cents < 0
        has_bottle_obligations = empty_19l_returned > 0
        for item in items_data:
            prod = session.query(Product).filter_by(id=item["product_id"]).first()
            if prod and prod.is_returnable:
                has_bottle_obligations = True
                break

        if (is_credit or has_bottle_obligations) and not customer:
            raise ValueError("An identified customer is required for credit sales and returnable bottle transactions.")

        inv_num = SalesService.generate_invoice_number(session)

        invoice = SalesInvoice(
            invoice_number=inv_num,
            invoice_date=now_colombo(),
            customer_id=customer_id,
            status=InvoiceStatus.POSTED.value,
            subtotal_cents=0,
            discount_cents=discount_cents,
            delivery_charge_cents=delivery_charge_cents,
            tax_cents=tax_cents,
            total_amount_cents=0,
            amount_paid_cents=min(amount_paid_cents, 0),  # Will be updated with actual payment
            payment_method=payment_method,
            due_date=due_date,
            notes=notes,
            prepared_by_user_id=user_id,
            bottles_delivered_19l=0,
            bottles_returned_19l=empty_19l_returned,
            bottle_deposit_cents=bottle_deposit_cents
        )
        session.add(invoice)
        session.flush()

        subtotal_cents = 0
        total_cogs_cents = 0
        total_19l_delivered = 0

        # Process each item
        for item_in in items_data:
            product_id = item_in["product_id"]
            qty = int(item_in["quantity"])
            unit_price_cents = int(item_in["unit_price_cents"])
            line_disc_cents = int(item_in.get("line_discount_cents", 0))
            packaging_unit_id = item_in.get("packaging_unit_id")
            specific_batch_id = item_in.get("specific_batch_id")

            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ValueError(f"Product #{product_id} not found.")

            factor = 1
            if packaging_unit_id:
                pkg = session.query(PackagingUnit).filter_by(id=packaging_unit_id).first()
                if pkg:
                    factor = pkg.factor

            base_qty = qty * factor
            line_total = (qty * unit_price_cents) - line_disc_cents

            # Allocate from FIFO batches
            allocations = FIFOService.execute_fifo_allocation(
                session=session,
                product_id=product_id,
                required_base_qty=base_qty,
                selling_price_cents=unit_price_cents // factor,
                specific_batch_id=specific_batch_id
            )

            line_cogs = sum(a["quantity"] * a["unit_cost_cents"] for a in allocations)
            total_cogs_cents += line_cogs
            subtotal_cents += line_total

            if product.is_returnable:
                total_19l_delivered += base_qty

            inv_item = SalesInvoiceItem(
                invoice_id=invoice.id,
                product_id=product_id,
                packaging_unit_id=packaging_unit_id,
                unit_factor=factor,
                quantity=qty,
                base_quantity=base_qty,
                unit_price_cents=unit_price_cents,
                line_discount_cents=line_disc_cents,
                line_total_cents=line_total,
                cogs_total_cents=line_cogs
            )
            session.add(inv_item)
            session.flush()

            # Record batch allocations and stock movements
            for alloc in allocations:
                batch_alloc = SaleBatchAllocation(
                    invoice_item_id=inv_item.id,
                    batch_id=alloc["batch_id"],
                    base_quantity=alloc["quantity"],
                    unit_cost_cents=alloc["unit_cost_cents"],
                    unit_price_cents=alloc["unit_price_cents"]
                )
                session.add(batch_alloc)
                session.flush()

                stock_mov = StockMovement(
                    date=now_colombo(),
                    product_id=product_id,
                    batch_id=alloc["batch_id"],
                    movement_type=StockMovementType.SALE.value,
                    quantity=-alloc["quantity"],
                    unit_cost_cents=alloc["unit_cost_cents"],
                    reference_type="INVOICE",
                    reference_id=invoice.id,
                    reason=f"Sold via {invoice.invoice_number}",
                    user_id=user_id
                )
                session.add(stock_mov)

        invoice.subtotal_cents = subtotal_cents
        net_total = subtotal_cents - discount_cents + delivery_charge_cents + tax_cents
        invoice.total_amount_cents = net_total
        invoice.bottles_delivered_19l = total_19l_delivered

        # Handle 19L bottle physical states and customer bottle obligation
        if total_19l_delivered > 0 or empty_19l_returned > 0:
            # Move delivered full bottles: FULL_AVAILABLE -> HELD_BY_CUSTOMERS
            if total_19l_delivered > 0:
                BottleService.move_bottles(
                    session=session,
                    from_state=BottleState.FULL_AVAILABLE,
                    to_state=BottleState.HELD_BY_CUSTOMERS,
                    quantity=total_19l_delivered,
                    movement_type=BottleMovementType.DELIVERY_FULL,
                    customer_id=customer_id,
                    invoice_id=invoice.id,
                    reason=f"Delivered on invoice {inv_num}",
                    user_id=user_id
                )

            # Move returned empty bottles: HELD_BY_CUSTOMERS -> EMPTY_AVAILABLE
            if empty_19l_returned > 0:
                BottleService.move_bottles(
                    session=session,
                    from_state=BottleState.HELD_BY_CUSTOMERS,
                    to_state=BottleState.EMPTY_AVAILABLE,
                    quantity=empty_19l_returned,
                    movement_type=BottleMovementType.RETURN_EMPTY,
                    customer_id=customer_id,
                    invoice_id=invoice.id,
                    reason=f"Returned on invoice {inv_num}",
                    user_id=user_id
                )

            # Update customer bottle ledger
            BottleService.record_customer_bottle_movement(
                session=session,
                customer_id=customer_id,
                movement_type="INVOICE_EXCHANGE" if (total_19l_delivered and empty_19l_returned) else ("DELIVERY" if total_19l_delivered else "RETURN"),
                full_issued=total_19l_delivered,
                empty_returned=empty_19l_returned,
                invoice_id=invoice.id,
                notes=f"Invoice {inv_num}: Issued {total_19l_delivered}, Returned {empty_19l_returned}",
                user_id=user_id
            )

        # Handle payments and Customer Financial Ledger
        if customer:
            # Check credit limit policy
            last_entry = (
                session.query(CustomerLedgerEntry)
                .filter_by(customer_id=customer_id)
                .order_by(CustomerLedgerEntry.date.desc(), CustomerLedgerEntry.id.desc())
                .first()
            )
            prev_balance = last_entry.running_balance_cents if last_entry else 0
            
            # Post invoice debit to customer ledger
            balance_after_invoice = prev_balance + net_total
            inv_ledger = CustomerLedgerEntry(
                customer_id=customer_id,
                date=now_colombo(),
                transaction_type="INVOICE",
                reference_no=invoice.invoice_number,
                debit_cents=net_total,
                credit_cents=0,
                running_balance_cents=balance_after_invoice,
                user_id=user_id,
                notes=f"Invoice {invoice.invoice_number}"
            )
            session.add(inv_ledger)
            session.flush()

            # Record customer payment if amount_paid_cents > 0
            allocated_to_current = 0
            allocated_to_previous = 0
            available_advance = 0

            if amount_paid_cents > 0:
                if payment_allocation_mode == "CURRENT_INVOICE":
                    # Allocate directly to current invoice first
                    alloc_curr = min(amount_paid_cents, net_total)
                    specific_alloc = {invoice.id: alloc_curr}
                    rem_pay = amount_paid_cents - alloc_curr
                    payment = PaymentService.record_customer_payment(
                        session=session,
                        customer_id=customer_id,
                        amount_cents=amount_paid_cents,
                        payment_method=payment_method,
                        reference_no=invoice.invoice_number,
                        notes=f"Payment for invoice {invoice.invoice_number}",
                        specific_invoice_allocations=specific_alloc,
                        user_id=user_id
                    )
                    allocated_to_current = alloc_curr
                    available_advance = payment.unallocated_amount_cents
                    allocated_to_previous = amount_paid_cents - allocated_to_current - available_advance
                elif payment_allocation_mode == "OLDEST_INVOICES":
                    # Oldest unpaid invoices first, then current
                    payment = PaymentService.record_customer_payment(
                        session=session,
                        customer_id=customer_id,
                        amount_cents=amount_paid_cents,
                        payment_method=payment_method,
                        reference_no=invoice.invoice_number,
                        notes=f"Payment allocated to debt from {invoice.invoice_number}",
                        specific_invoice_allocations=None,
                        user_id=user_id
                    )
                    allocated_to_current = invoice.amount_paid_cents
                    available_advance = payment.unallocated_amount_cents
                    allocated_to_previous = amount_paid_cents - allocated_to_current - available_advance
                elif payment_allocation_mode == "ADVANCE":
                    # Retain full payment as customer advance
                    payment = CustomerPayment(
                        payment_number=PaymentService.generate_payment_number(session, prefix="RCP-"),
                        customer_id=customer_id,
                        payment_date=now_colombo(),
                        amount_cents=amount_paid_cents,
                        payment_method=payment_method,
                        reference_no=invoice.invoice_number,
                        unallocated_amount_cents=amount_paid_cents,
                        notes=f"Customer advance on invoice {invoice.invoice_number}",
                        user_id=user_id
                    )
                    session.add(payment)
                    session.flush()
                    # Ledger entry for advance
                    end_bal = balance_after_invoice - amount_paid_cents
                    adv_ledger = CustomerLedgerEntry(
                        customer_id=customer_id,
                        date=now_colombo(),
                        transaction_type="ADVANCE",
                        reference_no=payment.payment_number,
                        debit_cents=0,
                        credit_cents=amount_paid_cents,
                        running_balance_cents=end_bal,
                        user_id=user_id,
                        notes=f"Customer Advance payment via {payment_method}"
                    )
                    session.add(adv_ledger)
                    available_advance = amount_paid_cents
                else:
                    # Default fallback
                    payment = PaymentService.record_customer_payment(
                        session=session,
                        customer_id=customer_id,
                        amount_cents=amount_paid_cents,
                        payment_method=payment_method,
                        reference_no=invoice.invoice_number,
                        notes=f"Payment for invoice {invoice.invoice_number}",
                        specific_invoice_allocations={invoice.id: amount_paid_cents},
                        user_id=user_id
                    )
                    allocated_to_current = min(amount_paid_cents, net_total)
                    available_advance = payment.unallocated_amount_cents

                session.flush()

            # End ledger balance
            latest_ledger = (
                session.query(CustomerLedgerEntry)
                .filter_by(customer_id=customer_id)
                .order_by(CustomerLedgerEntry.date.desc(), CustomerLedgerEntry.id.desc())
                .first()
            )
            final_debt = latest_ledger.running_balance_cents if latest_ledger else 0

            # Attach explicit payment allocation breakdown
            invoice.payment_breakdown = {
                "previous_balance_cents": prev_balance,
                "current_invoice_total_cents": net_total,
                "payment_received_cents": amount_paid_cents,
                "allocated_to_current_cents": allocated_to_current,
                "allocated_to_previous_cents": allocated_to_previous,
                "remaining_customer_debt_cents": final_debt,
                "available_advance_cents": available_advance,
            }
        else:
            # Anonymous walk-in cash customer
            invoice.amount_paid_cents = net_total
            invoice.payment_breakdown = {
                "previous_balance_cents": 0,
                "current_invoice_total_cents": net_total,
                "payment_received_cents": net_total,
                "allocated_to_current_cents": net_total,
                "allocated_to_previous_cents": 0,
                "remaining_customer_debt_cents": 0,
                "available_advance_cents": 0,
            }

        AuditService.log_action(
            session=session,
            action_type="INVOICE_CREATE",
            entity_name="SalesInvoice",
            entity_id=invoice.id,
            reference_no=invoice.invoice_number,
            new_values={
                "total": net_total,
                "paid": invoice.amount_paid_cents,
                "cogs": total_cogs_cents,
                "gross_profit": net_total - total_cogs_cents
            },
            reason="Created sales invoice",
            user_id=user_id
        )
        session.flush()
        return invoice

    @staticmethod
    def cancel_invoice(session: Session, invoice_id: int, reason: str, user_id: Optional[int] = None) -> SalesInvoice:
        """
        Cancel a completed sales invoice.
        Reverses:
        - Restores inventory to batches.
        - Reverses bottle movements if 19L containers involved.
        - Adjusts customer financial ledger and bottle ledger.
        """
        if not reason or not reason.strip():
            raise ValueError("A clear reason is required to cancel an invoice.")

        invoice = session.query(SalesInvoice).filter_by(id=invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice #{invoice_id} not found.")
        if invoice.status == InvoiceStatus.CANCELLED.value:
            raise ValueError("This invoice has already been cancelled.")

        invoice.status = InvoiceStatus.CANCELLED.value
        invoice.cancellation_reason = reason
        invoice.cancelled_at = now_colombo()

        # 1. Reverse stock allocations back into batches
        allocations = (
            session.query(SaleBatchAllocation)
            .join(SalesInvoiceItem, SalesInvoiceItem.id == SaleBatchAllocation.invoice_item_id)
            .filter(SalesInvoiceItem.invoice_id == invoice.id)
            .all()
        )
        for alloc in allocations:
            batch = session.query(InventoryBatch).filter_by(id=alloc.batch_id).first()
            if batch:
                batch.remaining_qty += alloc.base_quantity
                batch.status = "ACTIVE"

                stock_mov = StockMovement(
                    date=now_colombo(),
                    product_id=batch.product_id,
                    batch_id=batch.id,
                    movement_type=StockMovementType.SALES_RETURN.value,
                    quantity=alloc.base_quantity,
                    unit_cost_cents=alloc.unit_cost_cents,
                    reference_type="INVOICE_CANCEL",
                    reference_id=invoice.id,
                    reason=f"Cancelled invoice {invoice.invoice_number}: {reason}",
                    user_id=user_id
                )
                session.add(stock_mov)

        # 2. Reverse 19L bottle movements
        if invoice.bottles_delivered_19l > 0:
            BottleService.move_bottles(
                session=session,
                from_state=BottleState.HELD_BY_CUSTOMERS,
                to_state=BottleState.FULL_AVAILABLE,
                quantity=invoice.bottles_delivered_19l,
                movement_type=BottleMovementType.RETURN_FULL,
                customer_id=invoice.customer_id,
                invoice_id=invoice.id,
                reason=f"Invoice {invoice.invoice_number} cancelled",
                user_id=user_id
            )
        if invoice.bottles_returned_19l > 0:
            BottleService.move_bottles(
                session=session,
                from_state=BottleState.EMPTY_AVAILABLE,
                to_state=BottleState.HELD_BY_CUSTOMERS,
                quantity=invoice.bottles_returned_19l,
                movement_type=BottleMovementType.DELIVERY_FULL,
                customer_id=invoice.customer_id,
                invoice_id=invoice.id,
                reason=f"Invoice {invoice.invoice_number} cancelled reversal",
                user_id=user_id
            )

        if invoice.customer_id and (invoice.bottles_delivered_19l > 0 or invoice.bottles_returned_19l > 0):
            BottleService.record_customer_bottle_movement(
                session=session,
                customer_id=invoice.customer_id,
                movement_type="INVOICE_CANCEL",
                full_issued=invoice.bottles_returned_19l,  # Reverse direction
                empty_returned=invoice.bottles_delivered_19l,
                invoice_id=invoice.id,
                notes=f"Reversed invoice {invoice.invoice_number} cancellation",
                user_id=user_id
            )

        # 3. Reverse customer financial ledger
        if invoice.customer_id:
            last_entry = (
                session.query(CustomerLedgerEntry)
                .filter_by(customer_id=invoice.customer_id)
                .order_by(CustomerLedgerEntry.date.desc(), CustomerLedgerEntry.id.desc())
                .first()
            )
            prev_balance = last_entry.running_balance_cents if last_entry else 0
            new_balance = prev_balance - invoice.total_amount_cents

            ledger_entry = CustomerLedgerEntry(
                customer_id=invoice.customer_id,
                date=now_colombo(),
                transaction_type="INVOICE_CANCEL",
                reference_no=invoice.invoice_number,
                debit_cents=0,
                credit_cents=invoice.total_amount_cents,
                running_balance_cents=new_balance,
                user_id=user_id,
                notes=f"Cancellation of {invoice.invoice_number}: {reason}"
            )
            session.add(ledger_entry)

        AuditService.log_action(
            session=session,
            action_type="INVOICE_CANCEL",
            entity_name="SalesInvoice",
            entity_id=invoice.id,
            reference_no=invoice.invoice_number,
            reason=reason,
            user_id=user_id
        )
        session.flush()
        return invoice

    @staticmethod
    def prepare_repeat_order(session: Session, invoice_id: int) -> Dict[str, Any]:
        """
        1-Click repeat order from a previous invoice.
        Re-validates available batch stock and current customer pricing.
        Flags any price changes or stock shortages before billing.
        """
        invoice = session.query(SalesInvoice).filter_by(id=invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice #{invoice_id} not found.")

        items = []
        warnings = []
        for it in invoice.items:
            prod = it.product
            # Check current available stock
            avail_stock = FIFOService.get_available_stock(session, prod.id)
            needed_base = it.quantity * (it.unit_factor or 1)
            if avail_stock < needed_base:
                warnings.append(
                    f"Stock Warning: '{prod.name}' needs {needed_base} bottles, but only {avail_stock} available in stock."
                )

            # Check current effective customer price
            pricing = PricingService.get_effective_customer_price(
                session, invoice.customer_id, prod.id, it.packaging_unit_id
            )
            curr_unit_price = pricing["price_cents"]
            if curr_unit_price != it.unit_price_cents:
                warnings.append(
                    f"Price Update: '{prod.name}' price changed from {format_currency(it.unit_price_cents)} to {format_currency(curr_unit_price)}."
                )

            pkg_name = it.packaging_unit.name if it.packaging_unit else "Bottle"
            items.append({
                "product_id": prod.id,
                "product_code": prod.code,
                "product_name": prod.name,
                "bottle_size": prod.bottle_size,
                "packaging_unit_id": it.packaging_unit_id,
                "packaging_unit_name": pkg_name,
                "unit_factor": it.unit_factor or 1,
                "quantity": it.quantity,
                "unit_price_cents": curr_unit_price,
                "old_unit_price_cents": it.unit_price_cents,
                "line_discount_cents": 0,
                "available_stock": avail_stock,
            })

        return {
            "previous_invoice_number": invoice.invoice_number,
            "customer_id": invoice.customer_id,
            "customer_name": invoice.customer.name if invoice.customer else "Walk-in Customer",
            "items": items,
            "warnings": warnings,
            "discount_cents": invoice.discount_cents,
            "delivery_charge_cents": invoice.delivery_charge_cents,
        }

