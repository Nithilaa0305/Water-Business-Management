"""Dialog to receive customer payment."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QComboBox, QDoubleSpinBox
)
from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.services.payment_service import PaymentService
from app.services.customer_service import CustomerService
from app.utilities.currency import to_cents, format_currency


class PaymentDialog(QDialog):
    def __init__(self, parent=None, default_customer_id=None):
        super().__init__(parent)
        self.setWindowTitle("Receive Customer Payment")
        self.resize(480, 420)
        self.setMinimumSize(440, 380)
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
            QLineEdit, QComboBox, QDoubleSpinBox {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1.5px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
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
        self.lbl_balance = QLabel("-")
        self.lbl_balance.setStyleSheet("font-weight: bold; color: #0284C7;")

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 10000000.00)
        self.spin_amount.setPrefix("Rs. ")
        self.spin_amount.setValue(1000.00)

        self.cmb_method = QComboBox()
        self.cmb_method.addItems(["CASH", "BANK_TRANSFER", "CHEQUE", "CARD"])

        self.txt_ref = QLineEdit()
        self.txt_ref.setPlaceholderText("Cheque / Bank transaction number")

        self.txt_notes = QLineEdit()

        form.addRow(_lbl("Customer*:"), self.cmb_customer)
        form.addRow(_lbl("Current Balance:"), self.lbl_balance)
        form.addRow(_lbl("Payment Amount*:"), self.spin_amount)
        form.addRow(_lbl("Payment Method:"), self.cmb_method)
        form.addRow(_lbl("Reference No:"), self.txt_ref)
        form.addRow(_lbl("Notes:"), self.txt_notes)
        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Payment")
        self.btn_save.clicked.connect(self.save_payment)
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
            self.lbl_balance.setText("-")
            return
        with get_db_session() as session:
            s = CustomerService.get_customer_financial_summary(session, cid)
            self.lbl_balance.setText(s["status_text"])

    def save_payment(self):
        cid = self.cmb_customer.currentData()
        if not cid:
            QMessageBox.warning(self, "Validation", "Please select a customer.")
            return

        amt_cents = to_cents(self.spin_amount.value())
        if amt_cents <= 0:
            QMessageBox.warning(self, "Validation", "Payment amount must be greater than zero.")
            return

        method = self.cmb_method.currentText()
        ref = self.txt_ref.text().strip() or None
        notes = self.txt_notes.text().strip() or None

        try:
            with get_db_session() as session:
                PaymentService.record_customer_payment(
                    session=session,
                    customer_id=cid,
                    amount_cents=amt_cents,
                    payment_method=method,
                    reference_no=ref,
                    notes=notes
                )
            QMessageBox.information(self, "Success", f"Payment of {format_currency(amt_cents)} recorded successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not record payment: {str(e)}")
