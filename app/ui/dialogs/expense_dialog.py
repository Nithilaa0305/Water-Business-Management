"""Dialog to record expense."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QComboBox, QDoubleSpinBox
)
from app.database.connection import get_db_session
from app.database.models.operations import ExpenseCategory
from app.services.expense_service import ExpenseService
from app.utilities.currency import to_cents


class ExpenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record Business Expense")
        self.setFixedSize(450, 350)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_category = QComboBox()
        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Detailed description of expense")

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 10000000.00)
        self.spin_amount.setPrefix("Rs. ")
        self.spin_amount.setValue(500.00)

        self.cmb_method = QComboBox()
        self.cmb_method.addItems(["CASH", "BANK_TRANSFER", "CARD", "CHEQUE"])

        self.txt_payee = QLineEdit()
        self.txt_ref = QLineEdit()

        form.addRow("Expense Category*:", self.cmb_category)
        form.addRow("Description*:", self.txt_desc)
        form.addRow("Amount*:", self.spin_amount)
        form.addRow("Payment Method:", self.cmb_method)
        form.addRow("Payee / Supplier:", self.txt_payee)
        form.addRow("Reference / Receipt #:", self.txt_ref)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Expense")
        self.btn_save.clicked.connect(self.save_expense)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        self.load_categories()

    def load_categories(self):
        with get_db_session() as session:
            cats = session.query(ExpenseCategory).order_by(ExpenseCategory.name.asc()).all()
            for c in cats:
                self.cmb_category.addItem(c.name, c.id)

    def save_expense(self):
        desc = self.txt_desc.text().strip()
        if not desc:
            QMessageBox.warning(self, "Validation", "Description is required.")
            return

        cat_id = self.cmb_category.currentData()
        amt_cents = to_cents(self.spin_amount.value())

        try:
            with get_db_session() as session:
                ExpenseService.record_expense(
                    session=session,
                    category_id=cat_id,
                    description=desc,
                    amount_cents=amt_cents,
                    payment_method=self.cmb_method.currentText(),
                    payee=self.txt_payee.text().strip() or None,
                    reference_no=self.txt_ref.text().strip() or None
                )
            QMessageBox.information(self, "Success", "Expense recorded successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not record expense: {str(e)}")
