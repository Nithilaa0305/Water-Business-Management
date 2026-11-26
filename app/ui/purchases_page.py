"""Purchases Management Page."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)
from app.database.connection import get_db_session
from app.database.models.operations import PurchaseInvoice
from app.database.models.supplier import Supplier
from app.utilities.currency import format_currency
from app.localization.translator import t


class PurchasesPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("purchases_title", "Stock Purchases & Supplier Receiving"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("purchases_subtitle", "Record incoming bottled water inventory, batch generation, and supplier obligations"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_refresh = QPushButton(t("btn_refresh", "Refresh"))
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_purchases)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Table
        self.table_purchases = QTableWidget()
        self.table_purchases.setColumnCount(7)
        self.table_purchases.setHorizontalHeaderLabels([
            "Purchase No", "Date", "Supplier", "Total Amount", "Paid Amount", "Method", "Status"
        ])
        self.table_purchases.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table_purchases)

        self.load_purchases()

    def retranslate_ui(self):
        """Update texts when language changes."""
        self.lbl_title.setText(t("purchases_title", "Stock Purchases & Supplier Receiving"))
        self.lbl_sub.setText(t("purchases_subtitle", "Record incoming bottled water inventory, batch generation, and supplier obligations"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))

    def load_purchases(self):
        with get_db_session() as session:
            purchases = (
                session.query(PurchaseInvoice)
                .join(Supplier, Supplier.id == PurchaseInvoice.supplier_id)
                .order_by(PurchaseInvoice.purchase_date.desc(), PurchaseInvoice.id.desc())
                .all()
            )
            self.table_purchases.setRowCount(len(purchases))
            for row, p in enumerate(purchases):
                self.table_purchases.setItem(row, 0, QTableWidgetItem(p.purchase_number))
                self.table_purchases.setItem(row, 1, QTableWidgetItem(str(p.purchase_date.strftime("%Y-%m-%d"))))
                self.table_purchases.setItem(row, 2, QTableWidgetItem(p.supplier.name))
                self.table_purchases.setItem(row, 3, QTableWidgetItem(format_currency(p.total_amount_cents)))
                self.table_purchases.setItem(row, 4, QTableWidgetItem(format_currency(p.amount_paid_cents)))
                self.table_purchases.setItem(row, 5, QTableWidgetItem(p.payment_method))
                self.table_purchases.setItem(row, 6, QTableWidgetItem(p.status))
