"""Dialog for returning 19L empty bottles without buying water."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QComboBox, QSpinBox
)
from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.services.bottle_service import BottleService
from app.services.customer_service import CustomerService


class BottleReturnDialog(QDialog):
    def __init__(self, parent=None, default_customer_id=None):
        super().__init__(parent)
        self.setWindowTitle("Return Empty 19 L Bottles")
        self.resize(480, 360)
        self.setMinimumSize(440, 320)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                color: #0F172A;
            }
            QLabel {
                color: #0F172A;
                font-weight: 600;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1.5px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #0284C7;
                background-color: #FFFFFF;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #0F172A;
                selection-background-color: #0284C7;
                selection-color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(10)

        def _lbl(text: str) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet("color: #0F172A; font-weight: 600; font-size: 13px;")
            return l

        self.cmb_customer = QComboBox()
        self.lbl_held = QLabel("0 bottles")
        self.lbl_held.setStyleSheet("font-weight: bold; color: #0284C7;")

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 1000)
        self.spin_qty.setValue(1)

        self.txt_reason = QLineEdit()
        self.txt_reason.setPlaceholderText("Optional notes")

        form.addRow(_lbl("Customer*:"), self.cmb_customer)
        form.addRow(_lbl("Currently Held by Customer:"), self.lbl_held)
        form.addRow(_lbl("Empty Bottles Returned*:"), self.spin_qty)
        form.addRow(_lbl("Notes:"), self.txt_reason)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Record Return")
        self.btn_save.clicked.connect(self.save_return)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        self.load_customers(default_customer_id)
        self.cmb_customer.currentIndexChanged.connect(self.on_customer_changed)

    def load_customers(self, default_id):
        with get_db_session() as session:
            customers = session.query(Customer).filter_by(is_active=True).order_by(Customer.name.asc()).all()
            for c in customers:
                self.cmb_customer.addItem(f"{c.name} ({c.code})", c.id)

        if default_id:
            idx = self.cmb_customer.findData(default_id)
            if idx >= 0:
                self.cmb_customer.setCurrentIndex(idx)
        self.on_customer_changed()

    def on_customer_changed(self):
        cid = self.cmb_customer.currentData()
        if not cid:
            self.lbl_held.setText("0 bottles")
            return
        with get_db_session() as session:
            s = CustomerService.get_customer_financial_summary(session, cid)
            held = s["outstanding_bottles_19l"]
            self.lbl_held.setText(f"{held} bottles held")
            self.spin_qty.setMaximum(max(held, 1000))

    def save_return(self):
        cid = self.cmb_customer.currentData()
        if not cid:
            QMessageBox.warning(self, "Validation", "Please select a customer.")
            return

        qty = self.spin_qty.value()
        reason = self.txt_reason.text().strip() or None

        try:
            with get_db_session() as session:
                BottleService.return_empty_without_purchase(
                    session=session,
                    customer_id=cid,
                    quantity=qty,
                    reason=reason
                )
            QMessageBox.information(self, "Success", f"Recorded return of {qty} empty bottles. ZERO water sales created.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not record return: {str(e)}")
