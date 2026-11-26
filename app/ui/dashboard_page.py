"""Dashboard Page displaying real database financial metrics, stock levels, and quick actions."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QScrollArea, QFrame, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.services.report_service import ReportService
from app.database.models.auth import BusinessProfile
from app.config.settings import BACKUP_DIR
from app.ui.widgets.stat_card import StatCard
from app.ui.dialogs.payment_dialog import PaymentDialog
from app.ui.dialogs.stock_adjustment_dialog import StockAdjustmentDialog
from app.ui.dialogs.refill_dialog import RefillDialog
from app.ui.dialogs.bottle_return_dialog import BottleReturnDialog
from app.ui.dialogs.expense_dialog import ExpenseDialog
from app.localization.translator import t


class DashboardPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header & Quick Actions
        top_bar = QHBoxLayout()
        header_layout = QVBoxLayout()
        self.lbl_title = QLabel(t("nav_dashboard", "Dashboard"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel("Real-time bottled water business overview and stock status")
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_layout.addWidget(self.lbl_title)
        header_layout.addWidget(self.lbl_sub)
        top_bar.addLayout(header_layout)
        top_bar.addStretch()

        # Last Backup Badge
        self.lbl_last_backup = QLabel("💾 Backup: Checking...")
        self.lbl_last_backup.setStyleSheet(
            "background-color: #F1F5F9; color: #475569; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500;"
        )
        top_bar.addWidget(self.lbl_last_backup)

        self.btn_refresh = QPushButton(t("btn_refresh", "Refresh"))
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.refresh_dashboard)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Quick Action Buttons
        actions_frame = QFrame()
        actions_frame.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 8px;")
        act_layout = QHBoxLayout(actions_frame)
        act_layout.setContentsMargins(8, 8, 8, 8)
        act_layout.setSpacing(10)

        self.btn_new_bill = QPushButton(t("btn_new_bill", "+ New Bill"))
        self.btn_new_bill.clicked.connect(lambda: self.main_window.navigate_to("sales"))
        act_layout.addWidget(self.btn_new_bill)

        self.btn_add_stock = QPushButton(t("btn_add_stock", "+ Adjust Stock"))
        self.btn_add_stock.setObjectName("SecondaryButton")
        self.btn_add_stock.clicked.connect(self.action_adjust_stock)
        act_layout.addWidget(self.btn_add_stock)

        self.btn_pay = QPushButton(t("btn_receive_payment", "Receive Payment"))
        self.btn_pay.setObjectName("SecondaryButton")
        self.btn_pay.clicked.connect(self.action_receive_payment)
        act_layout.addWidget(self.btn_pay)

        self.btn_return = QPushButton(t("btn_return_empty", "Return Empty Bottles"))
        self.btn_return.setObjectName("SecondaryButton")
        self.btn_return.clicked.connect(self.action_return_bottles)
        act_layout.addWidget(self.btn_return)

        self.btn_refill = QPushButton(t("btn_refill", "Refill 19L Bottles"))
        self.btn_refill.setStyleSheet("background-color: #0284C7; color: white;")
        self.btn_refill.clicked.connect(self.action_refill_bottles)
        act_layout.addWidget(self.btn_refill)

        self.btn_expense = QPushButton(t("btn_add_expense", "+ Add Expense"))
        self.btn_expense.setObjectName("SecondaryButton")
        self.btn_expense.clicked.connect(self.action_add_expense)
        act_layout.addWidget(self.btn_expense)

        self.btn_daily_closing = QPushButton("💵 Daily Closing")
        self.btn_daily_closing.setStyleSheet("background-color: #0F766E; color: white; font-weight: bold;")
        self.btn_daily_closing.clicked.connect(lambda: self.main_window.navigate_to("daily_closing"))
        act_layout.addWidget(self.btn_daily_closing)

        act_layout.addStretch()
        main_layout.addWidget(actions_frame)

        # Scrollable Metrics Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(16)

        # 6 Stat Cards
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)

        self.card_today_sales = StatCard("Today's Total Sales", "Rs. 0.00", accent_color="#0284C7")
        self.card_monthly_rev = StatCard("Monthly Net Revenue", "Rs. 0.00", accent_color="#0284C7")
        self.card_monthly_profit = StatCard("Monthly Net Profit", "Rs. 0.00", accent_color="#16A34A")
        self.card_cust_credit = StatCard("Customer Credit (Receivables)", "Rs. 0.00", accent_color="#DC2626")
        self.card_advances = StatCard("Customer Advances", "Rs. 0.00", accent_color="#D97706")
        self.card_inventory_val = StatCard("Total Inventory Valuation", "Rs. 0.00", accent_color="#4F46E5")

        cards_grid.addWidget(self.card_today_sales, 0, 0)
        cards_grid.addWidget(self.card_monthly_rev, 0, 1)
        cards_grid.addWidget(self.card_monthly_profit, 0, 2)
        cards_grid.addWidget(self.card_cust_credit, 1, 0)
        cards_grid.addWidget(self.card_advances, 1, 1)
        cards_grid.addWidget(self.card_inventory_val, 1, 2)
        self.content_layout.addLayout(cards_grid)

        # 19L Special Bottle State Row
        bottle_frame = QFrame()
        bottle_frame.setStyleSheet("background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 12px;")
        b_layout = QHBoxLayout(bottle_frame)

        self.lbl_b_title = QLabel(t("returnable_bottle_balance", "19 L Returnable Bottle Balance:"))
        self.lbl_b_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #1E40AF;")
        b_layout.addWidget(self.lbl_b_title)

        self.lbl_b_full = QLabel("Full Available: 0")
        self.lbl_b_full.setStyleSheet("font-weight: bold; color: #16A34A; font-size: 13px;")
        b_layout.addWidget(self.lbl_b_full)

        self.lbl_b_empty = QLabel("Empty in Warehouse: 0")
        self.lbl_b_empty.setStyleSheet("font-weight: bold; color: #D97706; font-size: 13px;")
        b_layout.addWidget(self.lbl_b_empty)

        self.lbl_b_customer = QLabel("With Customers: 0")
        self.lbl_b_customer.setStyleSheet("font-weight: bold; color: #2563EB; font-size: 13px;")
        b_layout.addWidget(self.lbl_b_customer)

        b_layout.addStretch()
        self.content_layout.addWidget(bottle_frame)

        # Stock Levels Table
        self.sec_title = QLabel("Current Product Stock & Valuation")
        self.sec_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0F172A; margin-top: 8px;")
        self.content_layout.addWidget(self.sec_title)

        self.table_stock = QTableWidget()
        self.table_stock.setColumnCount(6)
        self.table_stock.setHorizontalHeaderLabels([
            "Code", "Product Name", "Size", "Available Stock", "Min Stock", "Stock Valuation"
        ])
        self.table_stock.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_stock.setMinimumHeight(220)
        self.content_layout.addWidget(self.table_stock)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        self.refresh_dashboard()

    def retranslate_ui(self):
        """Update dashboard texts when language changes."""
        self.lbl_title.setText(t("nav_dashboard", "Dashboard"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
        self.btn_new_bill.setText(t("btn_new_bill", "+ New Bill"))
        self.btn_add_stock.setText(t("btn_add_stock", "+ Adjust Stock"))
        self.btn_pay.setText(t("btn_receive_payment", "Receive Payment"))
        self.btn_return.setText(t("btn_return_empty", "Return Empty Bottles"))
        self.btn_refill.setText(t("btn_refill", "Refill 19L Bottles"))
        self.btn_expense.setText(t("btn_add_expense", "+ Add Expense"))
        if hasattr(self, 'btn_daily_closing'):
            self.btn_daily_closing.setText(f"💵 {t('nav_daily_closing', 'Daily Closing')}")
        if hasattr(self, 'lbl_b_title'):
            self.lbl_b_title.setText(t("returnable_bottle_balance", "19 L Returnable Bottle Balance:"))
        if hasattr(self, 'card_today_sales'):
            self.card_today_sales.title_label.setText(t("today_sales", "Today's Total Sales"))
            self.card_monthly_rev.title_label.setText(t("monthly_revenue", "Monthly Net Revenue"))
            self.card_monthly_profit.title_label.setText(t("monthly_profit", "Monthly Net Profit"))
            self.card_cust_credit.title_label.setText(t("customer_credit", "Customer Credit (Receivables)"))
            self.card_advances.title_label.setText(t("customer_advances", "Customer Advances"))
            self.card_inventory_val.title_label.setText(t("inventory_valuation", "Total Inventory Valuation"))
        self.refresh_dashboard()

    def refresh_dashboard(self):
        with get_db_session() as session:
            # Check last backup
            profile = session.query(BusinessProfile).first()
            if profile and profile.last_backup_at:
                self.lbl_last_backup.setText(f"💾 Last Backup: {profile.last_backup_at.strftime('%Y-%m-%d %H:%M')}")
                self.lbl_last_backup.setStyleSheet("background-color: #DCFCE7; color: #166534; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;")
            else:
                # Check BACKUP_DIR files
                backup_files = list(BACKUP_DIR.glob("*.zip"))
                if backup_files:
                    latest = max(backup_files, key=lambda f: f.stat().st_mtime)
                    mtime = latest.stat().st_mtime
                    from datetime import datetime
                    dt_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    self.lbl_last_backup.setText(f"💾 Last Backup: {dt_str}")
                    self.lbl_last_backup.setStyleSheet("background-color: #DCFCE7; color: #166534; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;")
                else:
                    self.lbl_last_backup.setText("⚠️ No Backup Yet")
                    self.lbl_last_backup.setStyleSheet("background-color: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;")

            m = ReportService.get_dashboard_metrics(session)

            self.card_today_sales.update_value(m["today_sales_display"])
            self.card_monthly_rev.update_value(m["monthly_sales_display"])
            self.card_monthly_profit.update_value(m["monthly_net_profit_display"])
            self.card_cust_credit.update_value(m["total_customer_credit_display"])
            self.card_advances.update_value(m["total_customer_advances_display"])
            self.card_inventory_val.update_value(m["total_inventory_valuation_display"])

            self.lbl_b_full.setText(f"Full Available: {m['bottles_full_19l']} bottles")
            self.lbl_b_empty.setText(f"Empty in Warehouse: {m['bottles_empty_19l']} bottles")
            self.lbl_b_customer.setText(f"With Customers: {m['bottles_with_customers_19l']} bottles")

            # Fill stock table
            stock_list = m["stock_by_product"]
            self.table_stock.setRowCount(len(stock_list))
            for row, p in enumerate(stock_list):
                self.table_stock.setItem(row, 0, QTableWidgetItem(p["code"]))
                self.table_stock.setItem(row, 1, QTableWidgetItem(p["name"]))
                self.table_stock.setItem(row, 2, QTableWidgetItem(p["bottle_size"]))

                item_qty = QTableWidgetItem(f"{p['available_qty']} bottles")
                if p["is_low_stock"]:
                    item_qty.setForeground(Qt.red)
                    item_qty.setText(f"{p['available_qty']} bottles (LOW)")
                self.table_stock.setItem(row, 3, item_qty)

                self.table_stock.setItem(row, 4, QTableWidgetItem(f"{p['min_stock_level']} bottles"))
                self.table_stock.setItem(row, 5, QTableWidgetItem(p["valuation_display"]))

    def action_receive_payment(self):
        dlg = PaymentDialog(self)
        if dlg.exec():
            self.refresh_dashboard()

    def action_adjust_stock(self):
        dlg = StockAdjustmentDialog(self)
        if dlg.exec():
            self.refresh_dashboard()

    def action_refill_bottles(self):
        dlg = RefillDialog(self)
        if dlg.exec():
            self.refresh_dashboard()

    def action_return_bottles(self):
        dlg = BottleReturnDialog(self)
        if dlg.exec():
            self.refresh_dashboard()

    def action_add_expense(self):
        dlg = ExpenseDialog(self)
        if dlg.exec():
            self.refresh_dashboard()
