"""Accounting, Revenue, Profit & Loss, and Cashbook Service."""

from datetime import date, datetime
from typing import Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.sales import SalesInvoice, SalesInvoiceItem
from app.database.models.payment import CustomerPayment, SupplierPayment
from app.database.models.bottle import BottleDepositTransaction
from app.database.models.operations import PurchaseInvoice, Expense, ExpenseCategory
from app.config.constants import InvoiceStatus
from app.utilities.dates import today_colombo
from app.utilities.currency import format_currency


class AccountingService:
    @staticmethod
    def get_financial_summary(
        session: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate complete financial summary:
        - Net Sales Revenue = Gross Sales - Discounts (excluding refundable deposits/taxes)
        - Cost of Goods Sold (COGS) = Sum of FIFO batch costs for completed sales
        - Gross Profit = Net Sales Revenue - COGS
        - Operating Expenses = Sum of operating expenses
        - Net Operating Profit = Gross Profit - Operating Expenses
        - Credit Collections: Collections from customer credit sales (NOT counted as new sales revenue!)
        """
        inv_query = session.query(SalesInvoice).filter(SalesInvoice.status == InvoiceStatus.POSTED.value)
        if start_date:
            inv_query = inv_query.filter(func.date(SalesInvoice.invoice_date) >= start_date)
        if end_date:
            inv_query = inv_query.filter(func.date(SalesInvoice.invoice_date) <= end_date)

        invoices = inv_query.all()

        gross_sales_cents = sum(inv.subtotal_cents for inv in invoices)
        discounts_cents = sum(inv.discount_cents for inv in invoices)
        delivery_cents = sum(inv.delivery_charge_cents for inv in invoices)
        net_sales_revenue_cents = gross_sales_cents - discounts_cents + delivery_cents

        # Calculate exact FIFO COGS
        inv_ids = [inv.id for inv in invoices]
        cogs_cents = 0
        if inv_ids:
            cogs_cents = (
                session.query(func.coalesce(func.sum(SalesInvoiceItem.cogs_total_cents), 0))
                .filter(SalesInvoiceItem.invoice_id.in_(inv_ids))
                .scalar()
            ) or 0

        gross_profit_cents = net_sales_revenue_cents - cogs_cents

        # Operating expenses
        exp_query = (
            session.query(func.coalesce(func.sum(Expense.amount_cents), 0))
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .filter(ExpenseCategory.is_operating == True)
        )
        if start_date:
            exp_query = exp_query.filter(func.date(Expense.date) >= start_date)
        if end_date:
            exp_query = exp_query.filter(func.date(Expense.date) <= end_date)

        operating_expenses_cents = exp_query.scalar() or 0
        net_operating_profit_cents = gross_profit_cents - operating_expenses_cents

        # Collections from credit
        pay_query = session.query(CustomerPayment)
        if start_date:
            pay_query = pay_query.filter(func.date(CustomerPayment.payment_date) >= start_date)
        if end_date:
            pay_query = pay_query.filter(func.date(CustomerPayment.payment_date) <= end_date)
        payments = pay_query.all()
        total_payments_received_cents = sum(p.amount_cents for p in payments)

        return {
            "gross_sales_cents": gross_sales_cents,
            "discounts_cents": discounts_cents,
            "delivery_charge_cents": delivery_cents,
            "net_sales_revenue_cents": net_sales_revenue_cents,
            "net_sales_revenue_display": format_currency(net_sales_revenue_cents),
            "cogs_cents": int(cogs_cents),
            "cogs_display": format_currency(cogs_cents),
            "gross_profit_cents": gross_profit_cents,
            "gross_profit_display": format_currency(gross_profit_cents),
            "operating_expenses_cents": int(operating_expenses_cents),
            "operating_expenses_display": format_currency(operating_expenses_cents),
            "net_operating_profit_cents": net_operating_profit_cents,
            "net_operating_profit_display": format_currency(net_operating_profit_cents),
            "total_payments_received_cents": total_payments_received_cents,
            "total_payments_received_display": format_currency(total_payments_received_cents)
        }

    @staticmethod
    def get_cashbook(
        session: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Reconcile actual cash receipts and cash payments:
        Inflows:
        - Cash sales collected on invoices
        - Customer credit collections (CustomerPayments)
        - Refundable bottle deposits collected
        Outflows:
        - Supplier payments
        - Operating expenses paid in cash
        - Bottle deposits refunded
        """
        # Customer cash payments
        cust_pay_query = session.query(CustomerPayment).filter(CustomerPayment.payment_method == "CASH")
        if start_date:
            cust_pay_query = cust_pay_query.filter(func.date(CustomerPayment.payment_date) >= start_date)
        if end_date:
            cust_pay_query = cust_pay_query.filter(func.date(CustomerPayment.payment_date) <= end_date)
        cash_from_cust_payments = sum(p.amount_cents for p in cust_pay_query.all())

        # Cash from walk-in cash sales (invoices without customer_id)
        walkin_query = (
            session.query(SalesInvoice)
            .filter(SalesInvoice.customer_id.is_(None))
            .filter(SalesInvoice.payment_method == "CASH")
            .filter(SalesInvoice.status == InvoiceStatus.POSTED.value)
        )
        if start_date:
            walkin_query = walkin_query.filter(func.date(SalesInvoice.invoice_date) >= start_date)
        if end_date:
            walkin_query = walkin_query.filter(func.date(SalesInvoice.invoice_date) <= end_date)
        cash_from_walkin = sum(i.amount_paid_cents for i in walkin_query.all())

        # Deposits collected
        dep_in_query = session.query(BottleDepositTransaction).filter(BottleDepositTransaction.transaction_type == "COLLECTED")
        if start_date:
            dep_in_query = dep_in_query.filter(func.date(BottleDepositTransaction.date) >= start_date)
        if end_date:
            dep_in_query = dep_in_query.filter(func.date(BottleDepositTransaction.date) <= end_date)
        cash_from_deposits = sum(d.amount_cents for d in dep_in_query.all())

        total_inflows = cash_from_cust_payments + cash_from_walkin + cash_from_deposits

        # Outflows: Supplier payments
        sup_pay_query = session.query(SupplierPayment).filter(SupplierPayment.payment_method == "CASH")
        if start_date:
            sup_pay_query = sup_pay_query.filter(func.date(SupplierPayment.payment_date) >= start_date)
        if end_date:
            sup_pay_query = sup_pay_query.filter(func.date(SupplierPayment.payment_date) <= end_date)
        cash_to_suppliers = sum(sp.amount_cents for sp in sup_pay_query.all())

        # Outflows: Expenses
        exp_query = session.query(Expense).filter(Expense.payment_method == "CASH", Expense.is_paid == True)
        if start_date:
            exp_query = exp_query.filter(func.date(Expense.date) >= start_date)
        if end_date:
            exp_query = exp_query.filter(func.date(Expense.date) <= end_date)
        cash_for_expenses = sum(e.amount_cents for e in exp_query.all())

        # Outflows: Deposit refunds
        dep_out_query = session.query(BottleDepositTransaction).filter(BottleDepositTransaction.transaction_type == "REFUNDED")
        if start_date:
            dep_out_query = dep_out_query.filter(func.date(BottleDepositTransaction.date) >= start_date)
        if end_date:
            dep_out_query = dep_out_query.filter(func.date(BottleDepositTransaction.date) <= end_date)
        cash_for_deposit_refunds = sum(d.amount_cents for d in dep_out_query.all())

        total_outflows = cash_to_suppliers + cash_for_expenses + cash_for_deposit_refunds
        net_cash_movement = total_inflows - total_outflows

        return {
            "cash_from_customers": cash_from_cust_payments + cash_from_walkin,
            "cash_from_deposits": cash_from_deposits,
            "total_inflows": total_inflows,
            "total_inflows_display": format_currency(total_inflows),
            "cash_to_suppliers": cash_to_suppliers,
            "cash_for_expenses": cash_for_expenses,
            "cash_for_deposit_refunds": cash_for_deposit_refunds,
            "total_outflows": total_outflows,
            "total_outflows_display": format_currency(total_outflows),
            "net_cash_movement": net_cash_movement,
            "net_cash_movement_display": format_currency(net_cash_movement)
        }
