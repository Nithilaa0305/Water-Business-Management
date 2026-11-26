"""Customer management, customer pricing rules, and balance calculations."""

from typing import List, Optional, Dict, Any
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.database.models.customer import Customer, CustomerCategory, DeliveryRoute, CustomerPrice
from app.database.models.sales import SalesInvoice, SalesInvoiceItem
from app.database.models.payment import CustomerLedgerEntry
from app.database.models.bottle import CustomerBottleLedger, BottleDeposit
from app.database.models.product import Product
from app.database.connection import get_db_session
from app.services.audit_service import AuditService
from app.utilities.currency import format_currency


class CustomerService:
    @staticmethod
    def generate_customer_code(session: Session) -> str:
        """Generate next customer code (e.g. CUST-001)."""
        count = session.query(func.count(Customer.id)).scalar() or 0
        return f"CUST-{(count + 1):03d}"

    @staticmethod
    def create_customer(
        session: Session,
        name: str,
        phone: str,
        business_name: Optional[str] = None,
        code: Optional[str] = None,
        alt_phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        area: Optional[str] = None,
        delivery_route_id: Optional[int] = None,
        category_id: Optional[int] = None,
        credit_limit_cents: int = 5000000,
        credit_period_days: int = 30,
        opening_balance_cents: int = 0,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Customer:
        """Create a new customer and initialize their financial ledger if opening balance > 0."""
        cust_code = code or CustomerService.generate_customer_code(session)
        customer = Customer(
            code=cust_code,
            name=name,
            business_name=business_name,
            phone=phone,
            alt_phone=alt_phone,
            email=email,
            address=address,
            area=area,
            delivery_route_id=delivery_route_id,
            category_id=category_id,
            credit_limit_cents=credit_limit_cents,
            credit_period_days=credit_period_days,
            opening_balance_cents=opening_balance_cents,
            notes=notes,
            is_active=True
        )
        session.add(customer)
        session.flush()

        # If opening balance exists, record opening ledger entry
        if opening_balance_cents != 0:
            is_debit = opening_balance_cents > 0
            entry = CustomerLedgerEntry(
                customer_id=customer.id,
                transaction_type="OPENING_BALANCE",
                reference_no=f"OPEN-{customer.code}",
                debit_cents=opening_balance_cents if is_debit else 0,
                credit_cents=abs(opening_balance_cents) if not is_debit else 0,
                running_balance_cents=opening_balance_cents,
                user_id=user_id,
                notes="Initial customer opening balance"
            )
            session.add(entry)

        AuditService.log_action(
            session=session,
            action_type="CUSTOMER_CREATE",
            entity_name="Customer",
            entity_id=customer.id,
            reference_no=customer.code,
            new_values={"name": name, "phone": phone, "opening_balance": opening_balance_cents},
            user_id=user_id
        )
        return customer

    @staticmethod
    def search_customers(session: Session, query_str: str) -> List[Customer]:
        """Search customers by name, phone, code, area, or business name."""
        if not query_str or not query_str.strip():
            return session.query(Customer).filter_by(is_active=True).order_by(Customer.name.asc()).limit(50).all()

        q = f"%{query_str.strip()}%"
        return (
            session.query(Customer)
            .filter(Customer.is_active == True)
            .filter(
                or_(
                    Customer.name.ilike(q),
                    Customer.phone.ilike(q),
                    Customer.code.ilike(q),
                    Customer.business_name.ilike(q),
                    Customer.area.ilike(q)
                )
            )
            .order_by(Customer.name.asc())
            .limit(50)
            .all()
        )

    @staticmethod
    def get_suggested_price(
        session: Session,
        customer_id: Optional[int],
        product_id: int,
        packaging_unit_id: Optional[int] = None
    ) -> int:
        """
        Price suggestion priority:
        1. Explicit customer-specific price agreement (CustomerPrice).
        2. Last sale price charged to this customer for this product.
        3. Default product selling price (scaled by packaging unit factor).
        """
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            return 0

        # Step 1: Explicit agreement
        if customer_id:
            agreement = (
                session.query(CustomerPrice)
                .filter_by(customer_id=customer_id, product_id=product_id)
                .order_by(CustomerPrice.id.desc())
                .first()
            )
            if agreement:
                return agreement.agreed_price_cents

            # Step 2: Last sale price
            last_item = (
                session.query(SalesInvoiceItem)
                .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id)
                .filter(SalesInvoice.customer_id == customer_id)
                .filter(SalesInvoice.status == "POSTED")
                .filter(SalesInvoiceItem.product_id == product_id)
                .order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.id.desc())
                .first()
            )
            if last_item:
                return last_item.unit_price_cents

        # Step 3: Default product price
        return product.default_selling_price_cents

    @staticmethod
    def set_customer_agreed_price(
        session: Session,
        customer_id: int,
        product_id: int,
        price_cents: int,
        packaging_unit_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> CustomerPrice:
        """Save or update explicit customer pricing agreement."""
        existing = (
            session.query(CustomerPrice)
            .filter_by(customer_id=customer_id, product_id=product_id)
            .first()
        )
        if existing:
            existing.agreed_price_cents = price_cents
            existing.notes = notes
            session.flush()
            return existing
        else:
            cp = CustomerPrice(
                customer_id=customer_id,
                product_id=product_id,
                packaging_unit_id=packaging_unit_id,
                agreed_price_cents=price_cents,
                notes=notes
            )
            session.add(cp)
            session.flush()
            return cp

    @staticmethod
    def delete_customer_agreed_price(session: Session, customer_id: int, product_id: int) -> bool:
        """Delete explicit customer agreed price so customer reverts to standard selling price."""
        existing = (
            session.query(CustomerPrice)
            .filter_by(customer_id=customer_id, product_id=product_id)
            .first()
        )
        if existing:
            session.delete(existing)
            session.flush()
            return True
        return False

    @staticmethod
    def get_all_customer_prices(session: Session, customer_id: int) -> List[Dict[str, Any]]:
        """
        Return list of all active products with their default price and 
        any custom agreed price for the specified customer.
        """
        products = session.query(Product).filter_by(is_active=True).order_by(Product.code.asc()).all()
        result = []
        for p in products:
            cp = (
                session.query(CustomerPrice)
                .filter_by(customer_id=customer_id, product_id=p.id)
                .first()
            )
            result.append({
                "product_id": p.id,
                "product_code": p.code,
                "product_name": p.name,
                "bottle_size": p.bottle_size,
                "default_price_cents": p.default_selling_price_cents,
                "agreed_price_cents": cp.agreed_price_cents if cp else None,
                "has_custom_price": cp is not None,
                "notes": cp.notes if cp else ""
            })
        return result

    @staticmethod
    def save_customer_prices(session: Session, customer_id: int, prices_data: List[Dict[str, Any]]) -> None:
        """
        Batch save or update agreed prices for a customer.
        Each item in prices_data: {product_id, agreed_price_cents, has_custom_price, notes}
        """
        for item in prices_data:
            pid = item["product_id"]
            if item.get("has_custom_price") and item.get("agreed_price_cents") is not None:
                CustomerService.set_customer_agreed_price(
                    session=session,
                    customer_id=customer_id,
                    product_id=pid,
                    price_cents=item["agreed_price_cents"],
                    notes=item.get("notes")
                )
            else:
                CustomerService.delete_customer_agreed_price(
                    session=session,
                    customer_id=customer_id,
                    product_id=pid
                )

    @staticmethod
    def get_customer_financial_summary(session: Session, customer_id: int) -> Dict[str, Any]:
        """
        Calculate auditable customer financial and bottle balances:
        - Outstanding debt (from posted invoices minus payments)
        - Available advances (unallocated payments)
        - Current bottle obligation
        - Total refundable deposit liability
        """
        # Running financial balance from customer ledger
        last_entry = (
            session.query(CustomerLedgerEntry)
            .filter_by(customer_id=customer_id)
            .order_by(CustomerLedgerEntry.id.desc())
            .first()
        )
        running_bal = last_entry.running_balance_cents if last_entry else 0

        # Outstanding 19L bottles
        last_bottle_entry = (
            session.query(CustomerBottleLedger)
            .filter_by(customer_id=customer_id)
            .order_by(CustomerBottleLedger.id.desc())
            .first()
        )
        bottle_bal = last_bottle_entry.running_bottle_balance if last_bottle_entry else 0

        # Refundable deposit balance
        deposit_bal = (
            session.query(func.coalesce(func.sum(BottleDeposit.balance_deposit_cents), 0))
            .filter_by(customer_id=customer_id, status="ACTIVE")
            .scalar()
        )

        # Clear terminology for user
        if running_bal > 0:
            status_text = f"Customer owes you {format_currency(running_bal)}"
        elif running_bal < 0:
            status_text = f"You owe customer {format_currency(abs(running_bal))} (Advance)"
        else:
            status_text = "Account settled (Rs. 0.00)"

        return {
            "running_balance_cents": running_bal,
            "current_balance_cents": running_bal,
            "running_balance_display": format_currency(running_bal),
            "is_debt": running_bal > 0,
            "is_advance": running_bal < 0,
            "advance_cents": abs(running_bal) if running_bal < 0 else 0,
            "status_text": status_text,
            "outstanding_bottles_19l": bottle_bal,
            "deposit_balance_cents": int(deposit_bal),
            "deposit_balance_display": format_currency(deposit_bal)
        }

    @staticmethod
    def remove_customer(
        session: Any = None,
        customer_id: Optional[int] = None,
        reason: str = "",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Safely remove or deactivate a customer:
        Safety checks:
        1. If customer has outstanding unpaid credit balance (debt > 0), raise error preventing deletion.
        2. If customer holds 19L returnable bottles (bottles > 0), raise error preventing deletion.
        3. If customer has historical transactions (posted invoices, payments, or ledger entries):
           Deactivates customer (is_active = False) to protect accounting integrity and audit history.
        4. If customer has no transactions at all, allows permanent deletion from the database.
        Returns: {"action": "DEACTIVATED" or "DELETED", "message": "..."}
        """
        if isinstance(session, int) and customer_id is None:
            customer_id = session
            session = None

        if session is None:
            with get_db_session() as s:
                return CustomerService.remove_customer(session=s, customer_id=customer_id, reason=reason, user_id=user_id)

        from app.database.models.payment import CustomerPayment
        customer = session.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            raise ValueError(f"Customer #{customer_id} not found.")

        # Safety Check 1: Financial Balance
        summary = CustomerService.get_customer_financial_summary(session, customer_id)
        if summary["running_balance_cents"] > 0:
            raise ValueError(
                f"Cannot remove customer '{customer.name}'. "
                f"Customer still owes you {summary['running_balance_display']}. "
                f"The outstanding financial account must be settled before removal."
            )

        # Safety Check 2: 19 L Reusable Bottles
        if summary["outstanding_bottles_19l"] > 0:
            raise ValueError(
                f"Cannot remove customer '{customer.name}'. "
                f"Customer still holds {summary['outstanding_bottles_19l']} returnable 19 L bottles. "
                f"All empty containers must be returned or accounted for before removal."
            )

        # Safety Check 3: Historical Transactions Check
        has_invoices = session.query(SalesInvoice).filter_by(customer_id=customer_id).count() > 0
        has_payments = session.query(CustomerPayment).filter_by(customer_id=customer_id).count() > 0
        has_ledger = session.query(CustomerLedgerEntry).filter(
            CustomerLedgerEntry.customer_id == customer_id,
            CustomerLedgerEntry.transaction_type != "OPENING_BALANCE"
        ).count() > 0

        if has_invoices or has_payments or has_ledger:
            # Safe Deactivation / Archiving
            customer.is_active = False
            AuditService.log_action(
                session=session,
                action_type="CUSTOMER_DEACTIVATE",
                entity_name="Customer",
                entity_id=customer.id,
                reference_no=customer.code,
                reason=reason or "Deactivated customer with past transaction history",
                user_id=user_id
            )
            return {
                "action": "DEACTIVATED",
                "message": (
                    f"Customer '{customer.name}' has historical sales and payment records.\n\n"
                    f"To preserve your financial and tax history, this customer has been Deactivated (Archived).\n"
                    f"They will no longer appear in New Bill or active customer lists."
                )
            }
        else:
            # Permanent Deletion (safe because 0 invoices, 0 payments, 0 debt, 0 bottles)
            session.query(CustomerLedgerEntry).filter_by(customer_id=customer_id).delete()
            session.query(CustomerBottleLedger).filter_by(customer_id=customer_id).delete()
            session.query(CustomerPrice).filter_by(customer_id=customer_id).delete()
            cust_name = customer.name
            session.delete(customer)

            AuditService.log_action(
                session=session,
                action_type="CUSTOMER_DELETE",
                entity_name="Customer",
                entity_id=customer_id,
                reason=reason or "Permanently deleted customer with zero history",
                user_id=user_id
            )
            return {
                "action": "DELETED",
                "message": f"Customer '{cust_name}' had no sales history and has been permanently removed."
            }

    @staticmethod
    def reactivate_customer(
        session: Any = None,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Customer:
        """Reactivate an archived customer."""
        if isinstance(session, int) and customer_id is None:
            customer_id = session
            session = None

        if session is None:
            with get_db_session() as s:
                return CustomerService.reactivate_customer(session=s, customer_id=customer_id, user_id=user_id)

        customer = session.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            raise ValueError(f"Customer #{customer_id} not found.")
        customer.is_active = True
        AuditService.log_action(
            session=session,
            action_type="CUSTOMER_REACTIVATE",
            entity_name="Customer",
            entity_id=customer.id,
            reference_no=customer.code,
            reason="Customer reactivated",
            user_id=user_id
        )
        return customer
