"""Comprehensive Reports Page: Sales, Stock, Bottles, Financials and Excel Export."""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit, QMessageBox, QFileDialog
)
from PySide6.QtCore import QDate, Qt
from app.database.connection import get_db_session
from app.services.report_service import ReportService
from app.services.accounting_service import AccountingService
from app.services.import_export_service import ExportService
from app.utilities.currency import format_currency
from app.localization.translator import t


class ReportsPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("reports_title", "Business Reports & Financial Analytics"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("reports_subtitle", "Reconciled financial statements, product performance, and Excel data export"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_export = QPushButton(t("btn_export_excel", "Export Products to Excel"))
        self.btn_export.setObjectName("SecondaryButton")
        self.btn_export.clicked.connect(self.action_export_excel)
        top_bar.addWidget(self.btn_export)

        self.btn_templates = QPushButton("Download Excel Templates")
        self.btn_templates.setObjectName("SecondaryButton")
        self.btn_templates.clicked.connect(self.action_download_templates)
        top_bar.addWidget(self.btn_templates)

        self.btn_refresh = QPushButton(t("btn_refresh", "Refresh"))
        self.btn_refresh.clicked.connect(self.load_all_reports)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Tabs for different report categories
        self.tabs = QTabWidget()

        # Tab 1: Product-wise Sales & Profit
        self.tab_sales = QWidget()
        s_layout = QVBoxLayout(self.tab_sales)
        self.table_sales = QTableWidget()
        self.table_sales.setColumnCount(6)
        self.table_sales.setHorizontalHeaderLabels([
            "Code", "Product Name", "Bottles Sold", "Revenue (Rs.)", "Cost of Goods Sold (Rs.)", "Gross Profit (Rs.)"
        ])
        self.table_sales.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        s_layout.addWidget(self.table_sales)
        self.tabs.addTab(self.tab_sales, "Product Sales & Profit")

        # Tab 2: Profit & Loss Statement
        self.tab_pl = QWidget()
        pl_layout = QVBoxLayout(self.tab_pl)
        self.table_pl = QTableWidget()
        self.table_pl.setColumnCount(2)
        self.table_pl.setHorizontalHeaderLabels(["Financial Metric", "Amount (Rs.)"])
        self.table_pl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        pl_layout.addWidget(self.table_pl)
        self.tabs.addTab(self.tab_pl, "Profit & Loss Statement")

        # Tab 3: Cashbook Reconciliation
        self.tab_cash = QWidget()
        c_layout = QVBoxLayout(self.tab_cash)
        self.table_cash = QTableWidget()
        self.table_cash.setColumnCount(2)
        self.table_cash.setHorizontalHeaderLabels(["Cash Flow Item", "Amount (Rs.)"])
        self.table_cash.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        c_layout.addWidget(self.table_cash)
        self.tabs.addTab(self.tab_cash, "Cashbook")

        main_layout.addWidget(self.tabs)

        self.load_all_reports()

    def load_all_reports(self):
        with get_db_session() as session:
            # 1. Product Sales
            sales = ReportService.get_product_sales_report(session)
            self.table_sales.setRowCount(len(sales))
            for row, s in enumerate(sales):
                self.table_sales.setItem(row, 0, QTableWidgetItem(s["code"]))
                self.table_sales.setItem(row, 1, QTableWidgetItem(s["name"]))
                self.table_sales.setItem(row, 2, QTableWidgetItem(f"{s['quantity_sold']} bottles"))
                self.table_sales.setItem(row, 3, QTableWidgetItem(s["revenue_display"]))
                self.table_sales.setItem(row, 4, QTableWidgetItem(s["cogs_display"]))
                self.table_sales.setItem(row, 5, QTableWidgetItem(s["gross_profit_display"]))

            # 2. P&L Statement
            fin = AccountingService.get_financial_summary(session)
            pl_rows = [
                ("Gross Sales Revenue", format_currency(fin["gross_sales_cents"])),
                ("Less: Discounts Given", "-" + format_currency(fin["discounts_cents"])),
                ("Add: Delivery Charges", "+" + format_currency(fin["delivery_charge_cents"])),
                ("= Net Sales Revenue", fin["net_sales_revenue_display"]),
                ("Less: Cost of Goods Sold (FIFO Batch Costs)", "-" + fin["cogs_display"]),
                ("= Gross Profit", fin["gross_profit_display"]),
                ("Less: Operating Expenses", "-" + fin["operating_expenses_display"]),
                ("= Net Operating Profit", fin["net_operating_profit_display"]),
                ("Credit Collections Received (Not Revenue)", fin["total_payments_received_display"])
            ]
            self.table_pl.setRowCount(len(pl_rows))
            for row, (label, val) in enumerate(pl_rows):
                item_lbl = QTableWidgetItem(label)
                item_val = QTableWidgetItem(val)
                if label.startswith("="):
                    font = item_lbl.font()
                    font.setBold(True)
                    item_lbl.setFont(font)
                    item_val.setFont(font)
                    item_val.setForeground(Qt.blue)
                self.table_pl.setItem(row, 0, item_lbl)
                self.table_pl.setItem(row, 1, item_val)

            # 3. Cashbook
            cb = AccountingService.get_cashbook(session)
            cb_rows = [
                ("Cash Inflow: Customer Payments & Walk-in Sales", format_currency(cb["cash_from_customers"])),
                ("Cash Inflow: Refundable Bottle Deposits Received", format_currency(cb["cash_from_deposits"])),
                ("= Total Cash Inflows", cb["total_inflows_display"]),
                ("Cash Outflow: Paid to Suppliers", "-" + format_currency(cb["cash_to_suppliers"])),
                ("Cash Outflow: Operating Expenses Paid in Cash", "-" + format_currency(cb["cash_for_expenses"])),
                ("Cash Outflow: Bottle Deposits Refunded to Customers", "-" + format_currency(cb["cash_for_deposit_refunds"])),
                ("= Total Cash Outflows", "-" + cb["total_outflows_display"]),
                ("= Net Cash Movement", cb["net_cash_movement_display"])
            ]
            self.table_cash.setRowCount(len(cb_rows))
            for row, (label, val) in enumerate(cb_rows):
                item_lbl = QTableWidgetItem(label)
                item_val = QTableWidgetItem(val)
                if label.startswith("="):
                    font = item_lbl.font()
                    font.setBold(True)
                    item_lbl.setFont(font)
                    item_val.setFont(font)
                    item_val.setForeground(Qt.darkGreen)
                self.table_cash.setItem(row, 0, item_lbl)
                self.table_cash.setItem(row, 1, item_val)

    def action_export_excel(self):
        try:
            with get_db_session() as session:
                target = ExportService.export_products_to_excel(session)
            QMessageBox.information(self, "Export Successful", f"Products exported to Excel:\n{target}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

    def action_download_templates(self):
        try:
            templates = ExportService.generate_import_templates()
            paths = "\n".join(str(p) for p in templates.values())
            QMessageBox.information(self, "Templates Generated", f"Import templates saved to:\n{paths}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate templates: {str(e)}")

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("reports_title", "Business Reports & Financial Analytics"))
        self.lbl_sub.setText(t("reports_subtitle", "Reconciled financial statements, product performance, and Excel data export"))
        self.btn_export.setText(t("btn_export_excel", "Export Products to Excel"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
