"""Suppliers Management Page with Safe Removal, Archiving, and Payables."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.database.models.supplier import Supplier
from app.database.models.payment import SupplierLedgerEntry
from app.services.purchase_service import PurchaseService
from app.utilities.currency import format_currency
from app.utilities.validators import validate_name, validate_phone_number
from app.localization.translator import t


class SupplierDialog(QDialog):
    def __init__(self, parent=None, supplier_id=None):
        super().__init__(parent)
        self.setWindowTitle(t("btn_add_supplier", "Add Supplier"))
        self.setFixedSize(450, 320)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_name = QLineEdit()
        self.txt_contact = QLineEdit()
        self.txt_phone = QLineEdit()
        self.txt_email = QLineEdit()
        self.txt_addr = QLineEdit()

        form.addRow("Supplier Name*:", self.txt_name)
        form.addRow("Contact Person:", self.txt_contact)
        form.addRow("Phone Number*:", self.txt_phone)
        form.addRow("Email:", self.txt_email)
        form.addRow("Address:", self.txt_addr)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton(t("btn_cancel", "Cancel"))
        btn_cancel.setObjectName("SecondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_save = QPushButton(t("btn_save", "Save Supplier"))
        btn_save.clicked.connect(self.save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def save(self):
        name = self.txt_name.text().strip()
        raw_phone = self.txt_phone.text().strip()

        valid_name, clean_name, err_name = validate_name(name, "Supplier Name", min_len=2)
        if not valid_name:
            QMessageBox.warning(self, "Validation Error", err_name)
            self.txt_name.setFocus()
            return

        valid_phone, clean_phone, err_phone = validate_phone_number(raw_phone, required=True)
        if not valid_phone:
            QMessageBox.warning(self, "Validation Error", err_phone)
            self.txt_phone.setFocus()
            return

        with get_db_session() as session:
            sup = Supplier(
                name=clean_name,
                contact_person=self.txt_contact.text().strip() or None,
                phone=clean_phone,
                email=self.txt_email.text().strip() or None,
                address=self.txt_addr.text().strip() or None,
                is_active=True
            )
            session.add(sup)
        self.accept()


class SuppliersPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("suppliers_title", "Supplier Accounts & Payables"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("suppliers_subtitle", "Manage water distributors, packaging suppliers, and payables"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_add = QPushButton(t("btn_add_supplier", "+ Add Supplier"))
        self.btn_add.clicked.connect(self.action_add_supplier)
        top_bar.addWidget(self.btn_add)

        self.btn_refresh = QPushButton(t("btn_refresh", "Refresh"))
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_suppliers)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Filter bar
        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px;")
        f_layout = QHBoxLayout(filter_bar)
        
        self.lbl_filter = QLabel(t("status", "Status:"))
        f_layout.addWidget(self.lbl_filter)
        self.cmb_status_filter = QComboBox()
        self.cmb_status_filter.addItem(t("filter_active", "Active Suppliers Only"), "ACTIVE")
        self.cmb_status_filter.addItem(t("filter_inactive", "Archived / Inactive"), "INACTIVE")
        self.cmb_status_filter.addItem(t("filter_all", "All Suppliers"), "ALL")
        self.cmb_status_filter.currentIndexChanged.connect(self.load_suppliers)
        f_layout.addWidget(self.cmb_status_filter)
        f_layout.addStretch()
        main_layout.addWidget(filter_bar)

        # Table
        self.table_suppliers = QTableWidget()
        self.table_suppliers.setColumnCount(7)
        self.table_suppliers.setHorizontalHeaderLabels([
            "Supplier Name", "Contact Person", "Phone", "Email", "Outstanding Payable", "Status", "Actions"
        ])
        self.table_suppliers.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_suppliers.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table_suppliers.verticalHeader().setDefaultSectionSize(40)
        main_layout.addWidget(self.table_suppliers)

        self.load_suppliers()

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("suppliers_title", "Supplier Accounts & Payables"))
        self.lbl_sub.setText(t("suppliers_subtitle", "Manage water distributors, packaging suppliers, and payables"))
        self.btn_add.setText(t("btn_add_supplier", "+ Add Supplier"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
        self.lbl_filter.setText(t("status", "Status:"))
        self.table_suppliers.setHorizontalHeaderLabels([
            "Supplier Name", "Contact Person", "Phone", "Email", "Outstanding Payable", "Status", t("actions", "Actions")
        ])

    def load_suppliers(self):
        status_mode = self.cmb_status_filter.currentData() if hasattr(self, 'cmb_status_filter') else "ACTIVE"

        with get_db_session() as session:
            q = session.query(Supplier)
            if status_mode == "ACTIVE":
                q = q.filter(Supplier.is_active == True)
            elif status_mode == "INACTIVE":
                q = q.filter(Supplier.is_active == False)
            suppliers = q.order_by(Supplier.name.asc()).all()

            self.table_suppliers.setRowCount(len(suppliers))

            for row, s in enumerate(suppliers):
                self.table_suppliers.setItem(row, 0, QTableWidgetItem(s.name))
                self.table_suppliers.setItem(row, 1, QTableWidgetItem(s.contact_person or "-"))
                self.table_suppliers.setItem(row, 2, QTableWidgetItem(s.phone))
                self.table_suppliers.setItem(row, 3, QTableWidgetItem(s.email or "-"))

                last_entry = (
                    session.query(SupplierLedgerEntry)
                    .filter_by(supplier_id=s.id)
                    .order_by(SupplierLedgerEntry.id.desc())
                    .first()
                )
                bal = last_entry.running_balance_cents if last_entry else 0
                self.table_suppliers.setItem(row, 4, QTableWidgetItem(format_currency(bal)))

                # Status badge
                status_item = QTableWidgetItem(t("active", "Active") if s.is_active else t("inactive", "Archived"))
                status_item.setTextAlignment(Qt.AlignCenter)
                if not s.is_active:
                    status_item.setForeground(Qt.gray)
                self.table_suppliers.setItem(row, 5, status_item)

                # Action button (Remove or Reactivate)
                btn_widget = QWidget()
                b_layout = QHBoxLayout(btn_widget)
                b_layout.setContentsMargins(4, 2, 4, 2)
                b_layout.setSpacing(6)

                if s.is_active:
                    btn_rem = QPushButton("🗑 Remove")
                    btn_rem.setProperty("class", "ActionBtnRemove")
                    btn_rem.setToolTip("Safely archive or delete supplier")
                    btn_rem.clicked.connect(lambda _, sid=s.id, sname=s.name: self.action_remove_supplier(sid, sname))
                    b_layout.addWidget(btn_rem)
                else:
                    btn_act = QPushButton("↺ Reactivate")
                    btn_act.setProperty("class", "ActionBtnReactivate")
                    btn_act.setToolTip("Reactivate archived supplier")
                    btn_act.clicked.connect(lambda _, sid=s.id, sname=s.name: self.action_reactivate_supplier(sid, sname))
                    b_layout.addWidget(btn_act)

                self.table_suppliers.setCellWidget(row, 6, btn_widget)

    def action_add_supplier(self):
        dlg = SupplierDialog(self)
        if dlg.exec():
            self.load_suppliers()

    def action_remove_supplier(self, supplier_id: int, supplier_name: str):
        prompt = t("confirm_remove_supp", "Are you sure you want to remove supplier '{name}'?").format(name=supplier_name)
        reply = QMessageBox.question(
            self,
            t("confirm_remove_title", "Confirm Removal"),
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                res = PurchaseService.remove_supplier(supplier_id)
                msg = t("archived_msg", "Safely archived.") if res.get("action") == "archived" else t("deleted_msg", "Permanently deleted.")
                QMessageBox.information(self, "Supplier Updated", f"{res.get('message')}\n\n{msg}")
                self.load_suppliers()
            except ValueError as ve:
                QMessageBox.warning(self, t("cannot_remove", "Cannot Remove Record"), str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove supplier: {str(e)}")

    def action_reactivate_supplier(self, supplier_id: int, supplier_name: str):
        try:
            PurchaseService.reactivate_supplier(supplier_id)
            QMessageBox.information(self, "Supplier Reactivated", f"Supplier '{supplier_name}' is now active again.")
            self.load_suppliers()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reactivate supplier: {str(e)}")
