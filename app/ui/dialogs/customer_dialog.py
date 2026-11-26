"""Dialog to create or edit customer."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QComboBox, QDoubleSpinBox, QSpinBox
)
from app.database.connection import get_db_session
from app.database.models.customer import Customer, CustomerCategory, DeliveryRoute
from app.services.customer_service import CustomerService
from app.utilities.currency import to_cents, from_cents
from app.utilities.validators import validate_name, validate_phone_number


class CustomerDialog(QDialog):
    def __init__(self, parent=None, customer_id=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.setWindowTitle("Edit Customer" if customer_id else "Add New Customer")
        self.setFixedSize(480, 440)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_name = QLineEdit()
        self.txt_biz = QLineEdit()
        self.txt_phone = QLineEdit()
        self.txt_alt_phone = QLineEdit()
        self.txt_area = QLineEdit()
        self.cmb_category = QComboBox()
        self.cmb_route = QComboBox()

        self.spin_credit_limit = QDoubleSpinBox()
        self.spin_credit_limit.setRange(0, 100000000)
        self.spin_credit_limit.setPrefix("Rs. ")
        self.spin_credit_limit.setValue(50000.00)

        self.spin_credit_period = QSpinBox()
        self.spin_credit_period.setRange(0, 365)
        self.spin_credit_period.setSuffix(" days")
        self.spin_credit_period.setValue(30)

        self.spin_opening_balance = QDoubleSpinBox()
        self.spin_opening_balance.setRange(-10000000, 10000000)
        self.spin_opening_balance.setPrefix("Rs. ")
        self.spin_opening_balance.setValue(0.00)
        if customer_id:
            self.spin_opening_balance.setEnabled(False)  # Opening balance locked once created

        form.addRow("Customer Name*:", self.txt_name)
        form.addRow("Business Name:", self.txt_biz)
        form.addRow("Phone Number*:", self.txt_phone)
        form.addRow("Alt Phone:", self.txt_alt_phone)
        form.addRow("Area / City:", self.txt_area)
        form.addRow("Customer Category:", self.cmb_category)
        form.addRow("Delivery Route:", self.cmb_route)
        form.addRow("Credit Limit:", self.spin_credit_limit)
        form.addRow("Credit Period:", self.spin_credit_period)
        form.addRow("Opening Balance:", self.spin_opening_balance)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        if customer_id:
            self.btn_prices = QPushButton("💲 Agreed Prices...")
            self.btn_prices.setProperty("class", "ActionBtnPrice")
            self.btn_prices.setToolTip("Pre-configure custom selling prices for this customer")
            self.btn_prices.clicked.connect(self.open_prices_dialog)
            btn_layout.addWidget(self.btn_prices)

        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Customer")
        self.btn_save.clicked.connect(self.save_customer)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        self.load_reference_data()
        if customer_id:
            self.load_customer_data(customer_id)

    def load_reference_data(self):
        with get_db_session() as session:
            cats = session.query(CustomerCategory).all()
            for c in cats:
                self.cmb_category.addItem(c.name, c.id)

            routes = session.query(DeliveryRoute).all()
            self.cmb_route.addItem("None", None)
            for r in routes:
                self.cmb_route.addItem(r.name, r.id)

    def load_customer_data(self, cid):
        with get_db_session() as session:
            c = session.query(Customer).filter_by(id=cid).first()
            if c:
                self.txt_name.setText(c.name)
                self.txt_biz.setText(c.business_name or "")
                self.txt_phone.setText(c.phone)
                self.txt_alt_phone.setText(c.alt_phone or "")
                self.txt_area.setText(c.area or "")
                self.spin_credit_limit.setValue(float(from_cents(c.credit_limit_cents)))
                self.spin_credit_period.setValue(c.credit_period_days)
                self.spin_opening_balance.setValue(float(from_cents(c.opening_balance_cents)))

    def save_customer(self):
        name = self.txt_name.text().strip()
        raw_phone = self.txt_phone.text().strip()
        raw_alt_phone = self.txt_alt_phone.text().strip()

        # Strict Field Validation
        valid_name, clean_name, err_name = validate_name(name, "Customer Name", min_len=2)
        if not valid_name:
            QMessageBox.warning(self, "Validation Error", err_name)
            self.txt_name.setFocus()
            return

        valid_phone, clean_phone, err_phone = validate_phone_number(raw_phone, required=True)
        if not valid_phone:
            QMessageBox.warning(self, "Validation Error", err_phone)
            self.txt_phone.setFocus()
            return

        clean_alt = None
        if raw_alt_phone:
            valid_alt, clean_alt, err_alt = validate_phone_number(raw_alt_phone, required=False)
            if not valid_alt:
                QMessageBox.warning(self, "Validation Error", f"Alt Phone Error: {err_alt}")
                self.txt_alt_phone.setFocus()
                return

        try:
            with get_db_session() as session:
                if self.customer_id:
                    c = session.query(Customer).filter_by(id=self.customer_id).first()
                    c.name = clean_name
                    c.business_name = self.txt_biz.text().strip() or None
                    c.phone = clean_phone
                    c.alt_phone = clean_alt
                    c.area = self.txt_area.text().strip() or None
                    c.category_id = self.cmb_category.currentData()
                    c.delivery_route_id = self.cmb_route.currentData()
                    c.credit_limit_cents = to_cents(self.spin_credit_limit.value())
                    c.credit_period_days = self.spin_credit_period.value()
                else:
                    CustomerService.create_customer(
                        session=session,
                        name=clean_name,
                        phone=clean_phone,
                        business_name=self.txt_biz.text().strip() or None,
                        alt_phone=clean_alt,
                        area=self.txt_area.text().strip() or None,
                        category_id=self.cmb_category.currentData(),
                        delivery_route_id=self.cmb_route.currentData(),
                        credit_limit_cents=to_cents(self.spin_credit_limit.value()),
                        credit_period_days=self.spin_credit_period.value(),
                        opening_balance_cents=to_cents(self.spin_opening_balance.value())
                    )
            QMessageBox.information(self, "Success", "Customer saved successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save customer: {str(e)}")

    def open_prices_dialog(self):
        if self.customer_id:
            from app.ui.dialogs.customer_price_dialog import CustomerPriceDialog
            dlg = CustomerPriceDialog(self, customer_id=self.customer_id)
            dlg.exec()
