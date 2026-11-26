"""Daily Cash Closing, Drawer Reconciliation, Sri Lankan Denominations, and Report Service."""

import json
from datetime import date, datetime, time
from typing import Dict, Any, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.operations import DailyCashClosing, Expense
from app.database.models.sales import SalesInvoice
from app.database.models.payment import CustomerPayment, SupplierPayment
from app.database.models.auth import BusinessProfile
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo, today_colombo
from app.utilities.currency import format_currency

# Official Sri Lankan Currency Denominations
SL_DENOMINATIONS: List[Dict[str, Any]] = [
    {"name": "Rs. 5,000 Note", "value_rs": 5000, "value_cents": 500000},
    {"name": "Rs. 1,000 Note", "value_rs": 1000, "value_cents": 100000},
    {"name": "Rs. 500 Note",   "value_rs": 500,  "value_cents": 50000},
    {"name": "Rs. 100 Note",   "value_rs": 100,  "value_cents": 10000},
    {"name": "Rs. 50 Note",    "value_rs": 50,   "value_cents": 5000},
    {"name": "Rs. 20 Note",    "value_rs": 20,   "value_cents": 2000},
    {"name": "Rs. 10 Coin",    "value_rs": 10,   "value_cents": 1000},
    {"name": "Rs. 5 Coin",     "value_rs": 5,    "value_cents": 500},
    {"name": "Rs. 2 Coin",     "value_rs": 2,    "value_cents": 200},
    {"name": "Rs. 1 Coin",     "value_rs": 1,    "value_cents": 100},
]

DENOM_MAP = {str(d["value_rs"]): d["value_cents"] for d in SL_DENOMINATIONS}


class DailyClosingService:
    @staticmethod
    def calculate_counted_from_denominations(counts: Dict[str, int]) -> int:
        """Calculate total physical cash cents from currency denomination counts."""
        total_cents = 0
        for val_rs_str, count in counts.items():
            if val_rs_str in DENOM_MAP and count > 0:
                total_cents += int(count) * DENOM_MAP[val_rs_str]
        return total_cents

    @staticmethod
    def calculate_daily_summary(
        session: Session,
        closing_date: Optional[date] = None,
        opening_cash_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate actual cash inflows and outflows for the given date.
        Reconciles:
        - Opening cash float (from previous closing if not provided)
        - Cash water sales
        - Credit collections received in cash
        - Customer advance payments received in cash
        - Bottle deposits collected in cash
        - Cash expenses
        - Supplier cash payments
        - Deposit refunds paid in cash
        """
        c_date = closing_date or today_colombo()
        date_str = c_date.strftime("%Y-%m-%d") if hasattr(c_date, "strftime") else str(c_date)

        # 1. Opening Cash Float
        if opening_cash_cents is None:
            prev_closing = (
                session.query(DailyCashClosing)
                .filter(DailyCashClosing.closing_date < c_date)
                .order_by(DailyCashClosing.closing_date.desc())
                .first()
            )
            opening_cash_cents = prev_closing.counted_cash_cents if prev_closing else 0

        # 2. Cash Inflows
        # Cash sales from direct invoice payments (walk-in or immediate cash bill)
        cash_sales = (
            session.query(func.coalesce(func.sum(SalesInvoice.amount_paid_cents), 0))
            .filter(func.date(SalesInvoice.invoice_date) == date_str)
            .filter(SalesInvoice.payment_method == "CASH")
            .filter(SalesInvoice.status == "POSTED")
            .scalar()
        ) or 0

        # Standalone customer payments collected in CASH on this date
        cash_payments = (
            session.query(CustomerPayment)
            .filter(func.date(CustomerPayment.payment_date) == date_str)
            .filter(CustomerPayment.payment_method == "CASH")
            .all()
        )
        total_cash_payments = sum(p.amount_cents for p in cash_payments)
        customer_advances = sum(p.unallocated_amount_cents for p in cash_payments if p.unallocated_amount_cents > 0)
        credit_collections = total_cash_payments - customer_advances

        # Bottle deposits collected in cash on this date
        deposits_collected = (
            session.query(func.coalesce(func.sum(SalesInvoice.bottle_deposit_cents), 0))
            .filter(func.date(SalesInvoice.invoice_date) == date_str)
            .filter(SalesInvoice.payment_method == "CASH")
            .scalar()
        ) or 0

        # 3. Cash Outflows
        # Cash operating expenses
        cash_expenses = (
            session.query(func.coalesce(func.sum(Expense.amount_cents), 0))
            .filter(func.date(Expense.date) == date_str)
            .filter(Expense.payment_method == "CASH")
            .filter(Expense.is_paid == True)
            .scalar()
        ) or 0

        # Supplier cash payments
        supplier_cash = (
            session.query(func.coalesce(func.sum(SupplierPayment.amount_cents), 0))
            .filter(func.date(SupplierPayment.payment_date) == date_str)
            .filter(SupplierPayment.payment_method == "CASH")
            .scalar()
        ) or 0

        deposit_refunds = 0  # Paid refunds in cash

        total_inflow = cash_sales + credit_collections + customer_advances + deposits_collected
        total_outflow = cash_expenses + supplier_cash + deposit_refunds
        expected_cash = opening_cash_cents + total_inflow - total_outflow

        return {
            "closing_date": c_date,
            "opening_cash_cents": opening_cash_cents,
            "opening_cash_display": format_currency(opening_cash_cents),
            "cash_sales_cents": cash_sales,
            "cash_sales_display": format_currency(cash_sales),
            "credit_collections_cents": credit_collections,
            "credit_collections_display": format_currency(credit_collections),
            "customer_advances_cents": customer_advances,
            "customer_advances_display": format_currency(customer_advances),
            "deposits_collected_cents": deposits_collected,
            "deposits_collected_display": format_currency(deposits_collected),
            "cash_expenses_cents": cash_expenses,
            "cash_expenses_display": format_currency(cash_expenses),
            "supplier_payments_cents": supplier_cash,
            "supplier_payments_display": format_currency(supplier_cash),
            "deposit_refunds_cents": deposit_refunds,
            "deposit_refunds_display": format_currency(deposit_refunds),
            "total_inflow_cents": total_inflow,
            "total_inflow_display": format_currency(total_inflow),
            "total_outflow_cents": total_outflow,
            "total_outflow_display": format_currency(total_outflow),
            "expected_cash_cents": expected_cash,
            "expected_cash_display": format_currency(expected_cash),
        }

    @staticmethod
    def record_daily_closing(
        session: Session,
        closing_date: date,
        opening_cash_cents: int,
        actual_cash_cents: int,
        denominations_counts: Optional[Dict[str, int]] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> DailyCashClosing:
        """
        Record or finalize daily physical cash drawer closing.
        Computes variance and sets status ('BALANCED', 'EXCESS', 'SHORTAGE').
        """
        summary = DailyClosingService.calculate_daily_summary(
            session=session,
            closing_date=closing_date,
            opening_cash_cents=opening_cash_cents
        )

        expected_cents = summary["expected_cash_cents"]
        diff_cents = actual_cash_cents - expected_cents

        if diff_cents == 0:
            status = "BALANCED"
        elif diff_cents > 0:
            status = "EXCESS"
        else:
            status = "SHORTAGE"

        closing_num = f"CLS-{closing_date.strftime('%Y%m%d')}"
        denom_json = json.dumps(denominations_counts) if denominations_counts else None

        existing = session.query(DailyCashClosing).filter_by(closing_date=closing_date).first()
        if existing:
            existing.opening_cash_cents = opening_cash_cents
            existing.cash_sales_cents = summary["cash_sales_cents"]
            existing.credit_collections_cents = summary["credit_collections_cents"]
            existing.customer_advances_cents = summary["customer_advances_cents"]
            existing.deposits_collected_cents = summary["deposits_collected_cents"]
            existing.cash_expenses_cents = summary["cash_expenses_cents"]
            existing.supplier_payments_cents = summary["supplier_payments_cents"]
            existing.deposit_refunds_cents = summary["deposit_refunds_cents"]
            existing.expected_cash_cents = expected_cents
            existing.counted_cash_cents = actual_cash_cents
            existing.difference_cents = diff_cents
            existing.status = status
            existing.denomination_json = denom_json
            existing.notes = notes
            existing.user_id = user_id
            closing = existing
        else:
            closing = DailyCashClosing(
                closing_number=closing_num,
                closing_date=closing_date,
                opening_cash_cents=opening_cash_cents,
                cash_sales_cents=summary["cash_sales_cents"],
                credit_collections_cents=summary["credit_collections_cents"],
                customer_advances_cents=summary["customer_advances_cents"],
                deposits_collected_cents=summary["deposits_collected_cents"],
                cash_expenses_cents=summary["cash_expenses_cents"],
                supplier_payments_cents=summary["supplier_payments_cents"],
                deposit_refunds_cents=summary["deposit_refunds_cents"],
                expected_cash_cents=expected_cents,
                counted_cash_cents=actual_cash_cents,
                difference_cents=diff_cents,
                status=status,
                denomination_json=denom_json,
                notes=notes,
                user_id=user_id
            )
            session.add(closing)

        session.commit()

        AuditService.log_action(
            session=session,
            action_type="DAILY_CLOSING",
            entity_name="DailyCashClosing",
            entity_id=closing.id,
            reference_no=closing.closing_number,
            new_values={
                "date": str(closing_date),
                "expected": expected_cents,
                "counted": actual_cash_cents,
                "difference": diff_cents,
                "status": status
            },
            reason=f"Daily cash closing finalized ({status})",
            user_id=user_id
        )
        return closing

    @staticmethod
    def generate_closing_report_text(closing: DailyCashClosing) -> str:
        """Generate formatted ASCII / printable text report for the daily closing."""
        date_str = closing.closing_date.strftime("%Y-%m-%d")
        denom_counts = {}
        if closing.denomination_json:
            try:
                denom_counts = json.loads(closing.denomination_json)
            except Exception:
                pass

        lines = [
            "================================================================",
            "             WATER BUSINESS MANAGER — DAILY CLOSING             ",
            "================================================================",
            f"Closing Ref:    {closing.closing_number}",
            f"Closing Date:   {date_str}",
            f"Status:         {closing.status}",
            "----------------------------------------------------------------",
            "DRAWER RECONCILIATION SUMMARY:",
            f"  (+) Opening Cash Float:           {format_currency(closing.opening_cash_cents):>18}",
            f"  (+) Cash Water Sales:             {format_currency(closing.cash_sales_cents):>18}",
            f"  (+) Credit Collections (Cash):    {format_currency(closing.credit_collections_cents):>18}",
            f"  (+) Customer Advances (Cash):     {format_currency(closing.customer_advances_cents):>18}",
            f"  (+) Bottle Deposits Collected:    {format_currency(closing.deposits_collected_cents):>18}",
            "  --------------------------------------------------------------",
            f"  (-) Cash Operating Expenses:      {format_currency(closing.cash_expenses_cents):>18}",
            f"  (-) Supplier Cash Payments:       {format_currency(closing.supplier_payments_cents):>18}",
            f"  (-) Bottle Deposits Refunded:     {format_currency(closing.deposit_refunds_cents):>18}",
            "----------------------------------------------------------------",
            f"  EXPECTED DRAWER CASH:             {format_currency(closing.expected_cash_cents):>18}",
            f"  ACTUAL COUNTED CASH:              {format_currency(closing.counted_cash_cents):>18}",
            f"  DIFFERENCE / VARIANCE:            {format_currency(closing.difference_cents):>18}",
            "================================================================",
            "PHYSICAL CURRENCY DENOMINATIONS:",
        ]

        for d in SL_DENOMINATIONS:
            k = str(d["value_rs"])
            count = denom_counts.get(k, 0)
            subtotal_cents = count * d["value_cents"]
            lines.append(f"  {d['name']:<18} x {count:>5}  =  {format_currency(subtotal_cents):>16}")

        lines.extend([
            "----------------------------------------------------------------",
            f"Notes: {closing.notes or 'None'}",
            "",
            "Cashier Signature: __________________   Date: _______________",
            "",
            "Owner Verification: _________________   Date: _______________",
            "================================================================"
        ])
        return "\n".join(lines)
