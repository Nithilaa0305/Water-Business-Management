"""Customer Database, Removal with Safety, and Statements Page."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.services.customer_service import CustomerService
from app.ui.dialogs.customer_dialog import CustomerDialog
from app.ui.dialogs.payment_dialog import PaymentDialog
from app.ui.dialogs.customer_price_dialog import CustomerPriceDialog
from app.localization.translator import t


class CustomersPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("nav_customers", "Customer Accounts & Balances"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel("Manage customer profiles, credit limits, 19L bottle obligations, and safe archiving")
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_add = QPushButton("+ Add Customer")
        self.btn_add.clicked.connect(self.action_add_customer)
        top_bar.addWidget(self.btn_add)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_customers)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Search & Filter Bar
        search_bar = QFrame()
        search_bar.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px;")
        s_layout = QHBoxLayout(search_bar)
        
        self.lbl_search = QLabel("Search:")
        s_layout.addWidget(self.lbl_search)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search by name, phone, code, or area...")
        self.txt_search.textChanged.connect(self.load_customers)
        s_layout.addWidget(self.txt_search)

        s_layout.addWidget(QLabel("Status:"))
        self.cmb_status_filter = QComboBox()
        self.cmb_status_filter.addItem("Active Customers Only", "ACTIVE")
        self.cmb_status_filter.addItem("Archived / Inactive Customers", "INACTIVE")
        self.cmb_status_filter.addItem("All Customers", "ALL")
        self.cmb_status_filter.currentIndexChanged.connect(self.load_customers)
        s_layout.addWidget(self.cmb_status_filter)

        main_layout.addWidget(search_bar)

        # Customers Table
        self.table_customers = QTableWidget()
        self.table_customers.setColumnCount(8)
        self.table_customers.setHorizontalHeaderLabels([
            "Code", "Customer Name", "Phone", "Area", "Financial Balance", "19L Bottles", "Status", "Actions"
        ])
        self.table_customers.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_customers.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table_customers.verticalHeader().setDefaultSectionSize(40)
        main_layout.addWidget(self.table_customers)

        self.load_customers()

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("customers_title", "Customer Accounts & Balances"))
        self.lbl_sub.setText(t("customers_subtitle", "Manage customer profiles, credit limits, 19L bottle obligations, and safe archiving"))
        self.lbl_search.setText(t("search", "Search:"))
        self.btn_add.setText(t("btn_add_customer", "+ Add Customer"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
        self.load_customers()

    def load_customers(self):
        query_str = self.txt_search.text().strip()
        status_mode = self.cmb_status_filter.currentData() if hasattr(self, 'cmb_status_filter') else "ACTIVE"

        with get_db_session() as session:
            q = session.query(Customer)
            if status_mode == "ACTIVE":
                q = q.filter(Customer.is_active == True)
            elif status_mode == "INACTIVE":
                q = q.filter(Customer.is_active == False)

            if query_str:
                pattern = f"%{query_str}%"
                from sqlalchemy import or_
                q = q.filter(
                    or_(
                        Customer.name.ilike(pattern),
                        Customer.phone.ilike(pattern),
                        Customer.code.ilike(pattern),
                        Customer.business_name.ilike(pattern),
                        Customer.area.ilike(pattern)
                    )
                )

            customers = q.order_by(Customer.name.asc()).limit(100).all()
            self.table_customers.setRowCount(len(customers))

            for row, c in enumerate(customers):
                self.table_customers.setItem(row, 0, QTableWidgetItem(c.code))
                self.table_customers.setItem(row, 1, QTableWidgetItem(c.name))
                self.table_customers.setItem(row, 2, QTableWidgetItem(c.phone))
                self.table_customers.setItem(row, 3, QTableWidgetItem(c.area or "-"))

                summary = CustomerService.get_customer_financial_summary(session, c.id)
                bal_item = QTableWidgetItem(summary["status_text"])
                if summary["is_debt"]:
                    bal_item.setForeground(Qt.red)
                elif summary["is_advance"]:
                    bal_item.setForeground(Qt.darkGreen)
                self.table_customers.setItem(row, 4, bal_item)

                bot_item = QTableWidgetItem(f"{summary['outstanding_bottles_19l']} bottles")
                self.table_customers.setItem(row, 5, bot_item)

                status_item = QTableWidgetItem("Active" if c.is_active else "Archived")
                status_item.setForeground(Qt.darkGreen if c.is_active else Qt.gray)
                self.table_customers.setItem(row, 6, status_item)

                btn_frame = QWidget()
                btn_box = QHBoxLayout(btn_frame)
                btn_box.setContentsMargins(4, 2, 4, 2)
                btn_box.setSpacing(6)

                if c.is_active:
                    btn_pay = QPushButton("💳 Pay")
                    btn_pay.setProperty("class", "ActionBtnPay")
                    btn_pay.setToolTip("Record payment from customer")
                    btn_pay.clicked.connect(lambda _, cid=c.id: self.receive_payment(cid))
                    btn_box.addWidget(btn_pay)

                    btn_price = QPushButton("💲 Prices")
                    btn_price.setProperty("class", "ActionBtnPrice")
                    btn_price.setToolTip("Set or edit agreed product selling prices for this customer")
                    btn_price.clicked.connect(lambda _, cid=c.id: self.manage_customer_prices(cid))
                    btn_box.addWidget(btn_price)

                    btn_edit = QPushButton("✏ Edit")
                    btn_edit.setProperty("class", "ActionBtnEdit")
                    btn_edit.setToolTip("Edit customer profile and credit limit")
                    btn_edit.clicked.connect(lambda _, cid=c.id: self.edit_customer(cid))
                    btn_box.addWidget(btn_edit)

                    btn_remove = QPushButton("🗑 Remove")
                    btn_remove.setProperty("class", "ActionBtnRemove")
                    btn_remove.setToolTip("Safely archive or delete customer")
                    btn_remove.clicked.connect(lambda _, cid=c.id, name=c.name: self.action_remove_customer(cid, name))
                    btn_box.addWidget(btn_remove)
                else:
                    btn_reactivate = QPushButton("↺ Reactivate")
                    btn_reactivate.setProperty("class", "ActionBtnReactivate")
                    btn_reactivate.setToolTip("Reactivate archived customer")
                    btn_reactivate.clicked.connect(lambda _, cid=c.id, name=c.name: self.action_reactivate_customer(cid, name))
                    btn_box.addWidget(btn_reactivate)

                    btn_edit = QPushButton("✏ Edit")
                    btn_edit.setProperty("class", "ActionBtnEdit")
                    btn_edit.setToolTip("Edit customer profile")
                    btn_edit.clicked.connect(lambda _, cid=c.id: self.edit_customer(cid))
                    btn_box.addWidget(btn_edit)

                self.table_customers.setCellWidget(row, 7, btn_frame)

    def action_add_customer(self):
        dlg = CustomerDialog(self)
        if dlg.exec():
            self.load_customers()

    def edit_customer(self, cid):
        dlg = CustomerDialog(self, customer_id=cid)
        if dlg.exec():
            self.load_customers()

    def manage_customer_prices(self, cid):
        dlg = CustomerPriceDialog(self, customer_id=cid)
        dlg.exec()

    def receive_payment(self, cid):
        dlg = PaymentDialog(self, default_customer_id=cid)
        if dlg.exec():
            self.load_customers()

    def action_remove_customer(self, cid: int, name: str):
        reply = QMessageBox.question(
            self,
            "Confirm Customer Removal",
            f"Are you sure you want to remove customer '{name}'?\n\n"
            "Safety Protection Policy:\n"
            "• If the customer owes money or holds bottles, removal is blocked.\n"
            "• If the customer has past sales/payment history, they will be safely Archived to protect your accounts.\n"
            "• If they have zero history, they will be permanently deleted.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                with get_db_session() as session:
                    res = CustomerService.remove_customer(session, cid, reason="User requested removal from Customers page")
                QMessageBox.information(self, "Customer Removed", res["message"])
                self.load_customers()
            except ValueError as ve:
                QMessageBox.warning(self, "Safety Check Blocked Removal", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove customer: {str(e)}")

    def action_reactivate_customer(self, cid: int, name: str):
        try:
            with get_db_session() as session:
                CustomerService.reactivate_customer(session, cid)
            QMessageBox.information(self, "Customer Reactivated", f"Customer '{name}' is now active and available for new sales.")
            self.load_customers()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reactivate customer: {str(e)}")
