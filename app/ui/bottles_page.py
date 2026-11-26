"""Special 19 L Returnable Bottle Management Page."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.database.models.bottle import CustomerBottleLedger
from app.config.constants import BottleState
from app.services.bottle_service import BottleService
from app.ui.widgets.stat_card import StatCard
from app.ui.dialogs.refill_dialog import RefillDialog
from app.ui.dialogs.bottle_return_dialog import BottleReturnDialog
from app.localization.translator import t


class BottlesPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header & Actions
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("bottles_title", "19 L Returnable Bottle Management"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("bottles_subtitle", "Separate tracking of water product vs reusable container, refill workflow, and reconciliation"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_return = QPushButton(t("btn_return_empty", "Return Empty Bottles"))
        self.btn_return.setObjectName("SecondaryButton")
        self.btn_return.clicked.connect(self.action_return_empty)
        top_bar.addWidget(self.btn_return)

        self.btn_refill = QPushButton(t("btn_refill", "Refill 19L Bottles"))
        self.btn_refill.setStyleSheet("background-color: #0284C7; color: white;")
        self.btn_refill.clicked.connect(self.action_refill)
        top_bar.addWidget(self.btn_refill)

        self.btn_refresh = QPushButton(t("btn_refresh", "Refresh"))
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_bottle_data)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # 4 Core Bottle State Stat Cards
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)

        self.card_full = StatCard("1. Full Bottles Available", "0", subtitle="Ready for sale/delivery", accent_color="#16A34A")
        self.card_empty = StatCard("2. Empty in Warehouse", "0", subtitle="Awaiting cleaning & refill", accent_color="#D97706")
        self.card_customer = StatCard("3. Held by Customers", "0", subtitle="Customer bottle obligations", accent_color="#2563EB")
        self.card_damaged = StatCard("4. Damaged / Rejected", "0", subtitle="Awaiting inspection", accent_color="#DC2626")

        cards_grid.addWidget(self.card_full, 0, 0)
        cards_grid.addWidget(self.card_empty, 0, 1)
        cards_grid.addWidget(self.card_customer, 0, 2)
        cards_grid.addWidget(self.card_damaged, 0, 3)
        main_layout.addLayout(cards_grid)

        # Reconciliation Banner
        self.banner_recon = QFrame()
        self.banner_recon.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 10px;")
        b_layout = QHBoxLayout(self.banner_recon)
        self.lbl_recon_text = QLabel("Physical Bottle Audit: Checking reconciliation...")
        self.lbl_recon_text.setStyleSheet("font-weight: bold; color: #166534;")
        b_layout.addWidget(self.lbl_recon_text)
        b_layout.addStretch()
        main_layout.addWidget(self.banner_recon)

        # Customer Bottle Obligations & FIFO Aging Table
        lbl_tbl = QLabel("Customer Outstanding 19 L Bottle Obligations & Aging (FIFO):")
        lbl_tbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #0F172A; margin-top: 8px;")
        main_layout.addWidget(lbl_tbl)

        self.table_customers = QTableWidget()
        self.table_customers.setColumnCount(9)
        self.table_customers.setHorizontalHeaderLabels([
            "Customer Code", "Customer Name", "Phone", "Total Held", "0-7 Days", "8-30 Days", "31-60 Days", ">60 Days Overdue", "Actions"
        ])
        self.table_customers.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table_customers)

        self.load_bottle_data()

    def load_bottle_data(self):
        with get_db_session() as session:
            counts = BottleService.get_all_state_counts(session)
            self.card_full.update_value(f"{counts[BottleState.FULL_AVAILABLE.value]} bottles")
            self.card_empty.update_value(f"{counts[BottleState.EMPTY_AVAILABLE.value]} bottles")
            self.card_customer.update_value(f"{counts[BottleState.HELD_BY_CUSTOMERS.value]} bottles")
            self.card_damaged.update_value(f"{counts[BottleState.DAMAGED.value]} bottles")

            # Reconciliation check
            recon = BottleService.reconcile_bottles(session)
            if recon["is_reconciled"]:
                self.banner_recon.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 10px;")
                self.lbl_recon_text.setText(
                    f"✓ Physical Container Reconciliation Balanced: {recon['active_total']} total active containers. Discrepancy: 0."
                )
            else:
                self.banner_recon.setStyleSheet("background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 10px;")
                self.lbl_recon_text.setText(
                    f"⚠ Container Discrepancy Detected! Warehouse customer count differs from customer ledgers by {recon['discrepancy']} bottles."
                )

            # Customer bottle aging report using FIFO policy
            aging_data = BottleService.get_customer_bottle_aging(session)
            self.table_customers.setRowCount(len(aging_data))

            for row, d in enumerate(aging_data):
                self.table_customers.setItem(row, 0, QTableWidgetItem(d["customer_code"]))
                self.table_customers.setItem(row, 1, QTableWidgetItem(d["customer_name"]))
                self.table_customers.setItem(row, 2, QTableWidgetItem(d["customer_phone"]))

                bal_item = QTableWidgetItem(f"{d['total_held']} bottles")
                bal_item.setForeground(Qt.blue)
                bal_item.setTextAlignment(Qt.AlignCenter)
                self.table_customers.setItem(row, 3, bal_item)

                d0_7_item = QTableWidgetItem(str(d["d0_7"]))
                d0_7_item.setTextAlignment(Qt.AlignCenter)
                self.table_customers.setItem(row, 4, d0_7_item)

                d8_30_item = QTableWidgetItem(str(d["d8_30"]))
                d8_30_item.setTextAlignment(Qt.AlignCenter)
                self.table_customers.setItem(row, 5, d8_30_item)

                d31_60_item = QTableWidgetItem(str(d["d31_60"]))
                d31_60_item.setTextAlignment(Qt.AlignCenter)
                if d["d31_60"] > 0:
                    d31_60_item.setForeground(Qt.darkYellow)
                self.table_customers.setItem(row, 6, d31_60_item)

                over60_item = QTableWidgetItem(str(d["over_60"]))
                over60_item.setTextAlignment(Qt.AlignCenter)
                if d["over_60"] > 0:
                    over60_item.setForeground(Qt.red)
                self.table_customers.setItem(row, 7, over60_item)

                btn_ret = QPushButton("Return Bottles")
                btn_ret.setObjectName("SecondaryButton")
                cid = d["customer_id"]
                btn_ret.clicked.connect(lambda _, c_id=cid: self.return_for_customer(c_id))
                self.table_customers.setCellWidget(row, 8, btn_ret)

    def action_return_empty(self):
        dlg = BottleReturnDialog(self)
        if dlg.exec():
            self.load_bottle_data()

    def return_for_customer(self, customer_id):
        dlg = BottleReturnDialog(self, default_customer_id=customer_id)
        if dlg.exec():
            self.load_bottle_data()

    def action_refill(self):
        dlg = RefillDialog(self)
        if dlg.exec():
            self.load_bottle_data()

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("bottles_title", "19 L Returnable Bottle Management"))
        self.lbl_sub.setText(t("bottles_subtitle", "Separate tracking of water product vs reusable container, refill workflow, and reconciliation"))
        self.btn_return.setText(t("btn_return_empty", "Return Empty Bottles"))
        self.btn_refill.setText(t("btn_refill", "Refill 19L Bottles"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
        if hasattr(self, 'card_full'):
            self.card_full.title_label.setText(t("card_full_bottles", "1. Full Bottles Available"))
            self.card_empty.title_label.setText(t("card_empty_bottles", "2. Empty in Warehouse"))
            self.card_customer.title_label.setText(t("card_cust_bottles", "3. Held by Customers"))
            self.card_damaged.title_label.setText(t("card_damaged_bottles", "4. Damaged / Rejected"))
        if hasattr(self, 'table_customers'):
            self.table_customers.setHorizontalHeaderLabels([
                "Customer Code",
                "Customer Name",
                t("phone", "Phone"),
                t("bottles_held", "Total Held"),
                t("bottle_aging_0_7", "0-7 Days"),
                t("bottle_aging_8_30", "8-30 Days"),
                t("bottle_aging_31_60", "31-60 Days"),
                t("bottle_aging_60_plus", ">60 Days Overdue"),
                t("actions", "Actions")
            ])
        self.load_bottle_data()
