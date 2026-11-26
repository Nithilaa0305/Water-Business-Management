"""Reporting Service aggregating business metrics across sales, stock, bottles, credit and finance."""

from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.models.sales import SalesInvoice, SalesInvoiceItem
from app.database.models.product import Product
from app.database.models.inventory import InventoryBatch
from app.database.models.customer import Customer
from app.database.models.payment import CustomerLedgerEntry
from app.database.models.bottle import CustomerBottleLedger, BottleInventory
from app.config.constants import InvoiceStatus, BottleState
from app.services.accounting_service import AccountingService
from app.services.bottle_service import BottleService
from app.services.credit_service import CreditService
from app.utilities.currency import format_currency


class ReportService:
    @staticmethod
    def get_dashboard_metrics(session: Session, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Aggregate all dashboard summary cards in a single efficient query pass."""
        today = target_date or date.today()

        # 1. Today's invoices
        today_invoices = (
            session.query(SalesInvoice)
            .filter(func.date(SalesInvoice.invoice_date) == today)
            .filter(SalesInvoice.status == InvoiceStatus.POSTED.value)
            .all()
        )
        today_sales_cents = sum(i.total_amount_cents for i in today_invoices)
        today_cash_sales_cents = sum(i.amount_paid_cents for i in today_invoices if i.payment_method == "CASH" or i.amount_paid_cents > 0)
        today_credit_sales_cents = max(0, today_sales_cents - today_cash_sales_cents)

        # 2. Month-to-date financial summary
        month_start = today.replace(day=1)
        monthly_fin = AccountingService.get_financial_summary(session, start_date=month_start, end_date=today)

        # 3. Total outstanding customer credit (sum of positive customer ledger balances)
        subq_cust = (
            session.query(
                CustomerLedgerEntry.customer_id,
                func.max(CustomerLedgerEntry.id).label("max_id")
            )
            .group_by(CustomerLedgerEntry.customer_id)
            .subquery()
        )
        latest_cust_entries = (
            session.query(CustomerLedgerEntry)
            .join(subq_cust, CustomerLedgerEntry.id == subq_cust.c.max_id)
            .all()
        )
        total_customer_credit_cents = sum(e.running_balance_cents for e in latest_cust_entries if e.running_balance_cents > 0)
        total_customer_advances_cents = sum(abs(e.running_balance_cents) for e in latest_cust_entries if e.running_balance_cents < 0)

        # 4. Bottle counts
        bottle_counts = BottleService.get_all_state_counts(session)

        # 5. Product stock quantities
        products = session.query(Product).filter_by(is_active=True).all()
        stock_by_product = []
        low_stock_count = 0
        total_inventory_valuation_cents = 0

        for p in products:
            avail = (
                session.query(func.coalesce(func.sum(InventoryBatch.remaining_qty), 0))
                .filter(InventoryBatch.product_id == p.id, InventoryBatch.status == "ACTIVE")
                .scalar()
            ) or 0

            val = (
                session.query(func.coalesce(func.sum(InventoryBatch.remaining_qty * InventoryBatch.unit_cost_cents), 0))
                .filter(InventoryBatch.product_id == p.id, InventoryBatch.status == "ACTIVE")
                .scalar()
            ) or 0

            total_inventory_valuation_cents += val
            is_low = avail < p.min_stock_level
            if is_low:
                low_stock_count += 1

            stock_by_product.append({
                "code": p.code,
                "name": p.name,
                "bottle_size": p.bottle_size,
                "available_qty": int(avail),
                "min_stock_level": p.min_stock_level,
                "is_low_stock": is_low,
                "valuation_cents": int(val),
                "valuation_display": format_currency(val)
            })

        return {
            "today_sales_cents": today_sales_cents,
            "today_sales_display": format_currency(today_sales_cents),
            "today_cash_sales_cents": today_cash_sales_cents,
            "today_credit_sales_cents": today_credit_sales_cents,
            "monthly_sales_display": monthly_fin["net_sales_revenue_display"],
            "monthly_cogs_display": monthly_fin["cogs_display"],
            "monthly_gross_profit_display": monthly_fin["gross_profit_display"],
            "monthly_net_profit_display": monthly_fin["net_operating_profit_display"],
            "total_customer_credit_display": format_currency(total_customer_credit_cents),
            "total_customer_advances_display": format_currency(total_customer_advances_cents),
            "total_inventory_valuation_display": format_currency(total_inventory_valuation_cents),
            "low_stock_count": low_stock_count,
            "bottles_full_19l": bottle_counts.get(BottleState.FULL_AVAILABLE.value, 0),
            "bottles_empty_19l": bottle_counts.get(BottleState.EMPTY_AVAILABLE.value, 0),
            "bottles_with_customers_19l": bottle_counts.get(BottleState.HELD_BY_CUSTOMERS.value, 0),
            "stock_by_product": stock_by_product
        }

    @staticmethod
    def get_product_sales_report(session: Session, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get product-wise sales breakdown with revenue and gross profit."""
        query = (
            session.query(
                Product.code,
                Product.name,
                func.sum(SalesInvoiceItem.base_quantity).label("total_qty"),
                func.sum(SalesInvoiceItem.line_total_cents).label("total_revenue"),
                func.sum(SalesInvoiceItem.cogs_total_cents).label("total_cogs")
            )
            .join(Product, Product.id == SalesInvoiceItem.product_id)
            .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id)
            .filter(SalesInvoice.status == InvoiceStatus.POSTED.value)
        )
        if start_date:
            query = query.filter(func.date(SalesInvoice.invoice_date) >= start_date)
        if end_date:
            query = query.filter(func.date(SalesInvoice.invoice_date) <= end_date)

        results = query.group_by(Product.id).order_by(func.sum(SalesInvoiceItem.line_total_cents).desc()).all()

        report = []
        for r in results:
            rev = r.total_revenue or 0
            cogs = r.total_cogs or 0
            profit = rev - cogs
            margin_pct = (profit / rev * 100) if rev > 0 else 0
            report.append({
                "code": r.code,
                "name": r.name,
                "quantity_sold": int(r.total_qty or 0),
                "revenue_display": format_currency(rev),
                "cogs_display": format_currency(cogs),
                "gross_profit_display": format_currency(profit),
                "margin_pct": f"{margin_pct:.1f}%"
            })
        return report
