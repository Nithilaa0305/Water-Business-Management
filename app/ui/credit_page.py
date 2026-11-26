"""Credit & Payments Management Page: Aging Reports and Collections."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.database.models.payment import CustomerPayment
from app.services.credit_service import CreditService
from app.services.customer_service import CustomerService
from app.ui.widgets.stat_card import StatCard
from app.ui.dialogs.payment_dialog import PaymentDialog
from app.utilities.currency import format_currency
from app.localization.translator import t


class CreditPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("credit_title", "Customer Credit & Aging Management"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("credit_subtitle", "Accounts receivable, payment allocations, credit aging, and overdue debt tracking"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_pay = QPushButton(t("btn_receive_payment", "+ Receive Payment"))
        self.btn_pay.clicked.connect(self.action_receive_payment)
        top_bar.addWidget(self.btn_pay)

        self.btn_refresh = QPushButton(t("btn_refresh", "Refresh"))
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_credit_data)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Aging Summary Cards
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)

        self.card_current = StatCard("Current (Not Due)", "Rs. 0.00", accent_color="#16A34A")
        self.card_d1_30 = StatCard("1–30 Days Overdue", "Rs. 0.00", accent_color="#D97706")
        self.card_d31_60 = StatCard("31–60 Days Overdue", "Rs. 0.00", accent_color="#EA580C")
        self.card_over60 = StatCard(">60 Days Overdue", "Rs. 0.00", accent_color="#DC2626")

        cards_grid.addWidget(self.card_current, 0, 0)
        cards_grid.addWidget(self.card_d1_30, 0, 1)
        cards_grid.addWidget(self.card_d31_60, 0, 2)
        cards_grid.addWidget(self.card_over60, 0, 3)
        main_layout.addLayout(cards_grid)

        # Outstanding Debt Table
        lbl_tbl = QLabel("Outstanding Customer Credit Balances:")
        lbl_tbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #0F172A; margin-top: 8px;")
        main_layout.addWidget(lbl_tbl)

        self.table_credit = QTableWidget()
        self.table_credit.setColumnCount(6)
        self.table_credit.setHorizontalHeaderLabels([
            "Customer Code", "Customer Name", "Total Debt", "Current Due", "Overdue Amount", "Action"
        ])
        self.table_credit.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table_credit)

        self.load_credit_data()

    def load_credit_data(self):
        with get_db_session() as session:
            customers = session.query(Customer).filter_by(is_active=True).all()

            tot_current = 0
            tot_d1_30 = 0
            tot_d31_60 = 0
            tot_over60 = 0

            debtor_list = []
            for c in customers:
                aging = CreditService.get_customer_aging(session, c.id)
                summary = CustomerService.get_customer_financial_summary(session, c.id)

                if summary["running_balance_cents"] > 0:
                    debtor_list.append((c, summary["running_balance_cents"], aging))
                    tot_current += aging["current_cents"]
                    tot_d1_30 += aging["d1_30_cents"]
                    tot_d31_60 += aging["d31_60_cents"]
                    tot_over60 += aging["d61_90_cents"] + aging["over90_cents"]

            self.card_current.update_value(format_currency(tot_current))
            self.card_d1_30.update_value(format_currency(tot_d1_30))
            self.card_d31_60.update_value(format_currency(tot_d31_60))
            self.card_over60.update_value(format_currency(tot_over60))

            # Populate table
            self.table_credit.setRowCount(len(debtor_list))
            for row, (c, debt, aging) in enumerate(debtor_list):
                self.table_credit.setItem(row, 0, QTableWidgetItem(c.code))
                self.table_credit.setItem(row, 1, QTableWidgetItem(c.name))

                debt_item = QTableWidgetItem(format_currency(debt))
                debt_item.setForeground(Qt.red)
                self.table_credit.setItem(row, 2, debt_item)

                self.table_credit.setItem(row, 3, QTableWidgetItem(format_currency(aging["current_cents"])))

                over_item = QTableWidgetItem(format_currency(aging["total_overdue_cents"]))
                if aging["total_overdue_cents"] > 0:
                    over_item.setForeground(Qt.red)
                self.table_credit.setItem(row, 4, over_item)

                btn_pay = QPushButton("Receive Payment")
                btn_pay.clicked.connect(lambda _, cid=c.id: self.receive_for_customer(cid))
                self.table_credit.setCellWidget(row, 5, btn_pay)

    def action_receive_payment(self):
        dlg = PaymentDialog(self)
        if dlg.exec():
            self.load_credit_data()

    def receive_for_customer(self, cid):
        dlg = PaymentDialog(self, default_customer_id=cid)
        if dlg.exec():
            self.load_credit_data()

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("credit_title", "Customer Credit & Aging Management"))
        self.lbl_sub.setText(t("credit_subtitle", "Accounts receivable, payment allocations, credit aging, and overdue debt tracking"))
        self.btn_pay.setText(t("btn_receive_payment", "+ Receive Payment"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
        self.load_credit_data()
