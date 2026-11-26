"""Dialog to pre-configure and manage customer-specific agreed product prices."""

from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QCheckBox, QFrame, QMessageBox, QWidget
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.services.customer_service import CustomerService
from app.utilities.currency import to_cents, from_cents, format_currency
from app.localization.translator import t


class CustomerPriceDialog(QDialog):
    def __init__(self, parent=None, customer_id: int = None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.customer_name = ""
        self.customer_code = ""
        self.price_rows: List[Dict[str, Any]] = []

        self.setWindowTitle(t("customer_prices_title", "Customer Agreed Selling Prices"))
        self.setMinimumSize(880, 520)
        self.resize(920, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                color: #0F172A;
            }
            QLabel {
                color: #0F172A;
            }
            QTableWidget {
                background-color: #FFFFFF;
                color: #0F172A;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #0F172A;
                font-weight: 600;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header Info Banner
        header_frame = QFrame()
        header_frame.setStyleSheet(
            "background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 12px;"
        )
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(6, 6, 6, 6)
        h_layout.setSpacing(4)

        self.lbl_customer_title = QLabel("Customer: Loading...")
        self.lbl_customer_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #166534;")
        h_layout.addWidget(self.lbl_customer_title)

        lbl_desc = QLabel(
            "Pre-configure custom selling prices for this customer. "
            "Both single bottle rates and full case/pack equivalents (Case of 24 & Case of 12) are shown. "
            "When billing this customer, these custom rates will automatically be populated."
        )
        lbl_desc.setStyleSheet("color: #15803D; font-size: 12px;")
        lbl_desc.setWordWrap(True)
        h_layout.addWidget(lbl_desc)

        main_layout.addWidget(header_frame)

        # Products Table
        self.table_prices = QTableWidget()
        self.table_prices.setColumnCount(6)
        self.table_prices.setHorizontalHeaderLabels([
            "Product", "Standard Price", "Custom?", "Agreed Bottle Price", "Equivalent Case / Pack Rates", "Notes / Reference"
        ])
        self.table_prices.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_prices.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_prices.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_prices.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_prices.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table_prices.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_prices.verticalHeader().setDefaultSectionSize(44)
        main_layout.addWidget(self.table_prices)

        # Buttons Bar
        btn_bar = QHBoxLayout()
        self.btn_reset_all = QPushButton("Reset All to Standard")
        self.btn_reset_all.setObjectName("SecondaryButton")
        self.btn_reset_all.setToolTip("Clear all custom prices for this customer")
        self.btn_reset_all.clicked.connect(self.action_reset_all)
        btn_bar.addWidget(self.btn_reset_all)

        btn_bar.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("💾 Save Agreed Prices")
        self.btn_save.clicked.connect(self.action_save_prices)
        btn_bar.addWidget(self.btn_save)

        main_layout.addLayout(btn_bar)

        self.load_customer_data()

    def load_customer_data(self):
        if not self.customer_id:
            return

        with get_db_session() as session:
            cust = session.query(Customer).filter_by(id=self.customer_id).first()
            if cust:
                self.customer_name = cust.name
                self.customer_code = cust.code
                phone_str = f" | Phone: {cust.phone}" if cust.phone else ""
                area_str = f" | Area: {cust.area}" if cust.area else ""
                self.lbl_customer_title.setText(f"👤 [{cust.code}] {cust.name}{phone_str}{area_str}")

            self.price_rows = CustomerService.get_all_customer_prices(session, self.customer_id)

        self.populate_table()

    def populate_table(self):
        self.table_prices.setRowCount(len(self.price_rows))

        for row, item in enumerate(self.price_rows):
            # Column 0: Product Info
            display_name = f"[{item['product_code']}] {item['product_name']} ({item['bottle_size']})"
            prod_item = QTableWidgetItem(display_name)
            prod_item.setFlags(prod_item.flags() & ~Qt.ItemIsEditable)
            self.table_prices.setItem(row, 0, prod_item)

            # Column 1: Standard Default Price
            std_price_str = format_currency(item["default_price_cents"])
            std_item = QTableWidgetItem(std_price_str)
            std_item.setTextAlignment(Qt.AlignCenter)
            std_item.setFlags(std_item.flags() & ~Qt.ItemIsEditable)
            self.table_prices.setItem(row, 1, std_item)

            # Column 2: Checkbox "Use Custom Price"
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(item["has_custom_price"])
            chk_layout.addWidget(chk)
            self.table_prices.setCellWidget(row, 2, chk_widget)

            # Column 3: Agreed Price SpinBox
            spin_price = QDoubleSpinBox()
            spin_price.setRange(0.01, 1000000.00)
            spin_price.setPrefix("Rs. ")
            spin_price.setDecimals(2)
            spin_price.setMinimumWidth(120)

            # Pre-fill custom price if available, else standard price
            if item["has_custom_price"] and item["agreed_price_cents"] is not None:
                spin_price.setValue(float(from_cents(item["agreed_price_cents"])))
            else:
                spin_price.setValue(float(from_cents(item["default_price_cents"])))

            spin_price.setEnabled(chk.isChecked())
            chk.toggled.connect(lambda checked, sp=spin_price: sp.setEnabled(checked))

            spin_frame = QWidget()
            sp_layout = QHBoxLayout(spin_frame)
            sp_layout.setContentsMargins(4, 2, 4, 2)
            sp_layout.addWidget(spin_price)
            self.table_prices.setCellWidget(row, 3, spin_frame)

            # Column 4: Equivalent Case & Pack Rates Label
            lbl_equiv = QLabel()
            lbl_equiv.setStyleSheet("font-size: 11px; color: #0284C7; font-weight: 500;")
            
            def make_equiv_updater(lbl, p_code):
                def update_text(val):
                    c = to_cents(val)
                    if "19000" in p_code or "19L" in p_code:
                        lbl.setText(f"Refill rate: {format_currency(c)} (No packaging case)")
                    else:
                        c24 = c * 24
                        c12 = c * 12
                        lbl.setText(f"Case of 24: {format_currency(c24)} | Case of 12: {format_currency(c12)}")
                return update_text

            fn_update = make_equiv_updater(lbl_equiv, item["product_code"])
            spin_price.valueChanged.connect(fn_update)
            fn_update(spin_price.value())
            self.table_prices.setCellWidget(row, 4, lbl_equiv)

            # Column 5: Notes
            txt_notes = QLineEdit()
            txt_notes.setPlaceholderText("e.g. Contract rate, Wholesale discount")
            txt_notes.setText(item.get("notes") or "")
            self.table_prices.setCellWidget(row, 5, txt_notes)

            # Store references in widget property for saving
            chk_widget.setProperty("chk", chk)
            spin_frame.setProperty("spin", spin_price)
            txt_notes.setProperty("product_id", item["product_id"])

    def action_reset_all(self):
        reply = QMessageBox.question(
            self,
            "Reset All Agreed Prices",
            f"Are you sure you want to reset all custom prices for {self.customer_name} to standard prices?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for row in range(self.table_prices.rowCount()):
                chk_w = self.table_prices.cellWidget(row, 2)
                chk = chk_w.property("chk") if chk_w else None
                if chk:
                    chk.setChecked(False)
                txt_notes = self.table_prices.cellWidget(row, 5)
                if txt_notes:
                    txt_notes.setText("")

    def action_save_prices(self):
        prices_to_save = []
        for row in range(self.table_prices.rowCount()):
            item = self.price_rows[row]
            pid = item["product_id"]

            chk_w = self.table_prices.cellWidget(row, 2)
            chk = chk_w.property("chk") if chk_w else None
            is_custom = chk.isChecked() if chk else False

            spin_w = self.table_prices.cellWidget(row, 3)
            spin = spin_w.property("spin") if spin_w else None
            price_val = spin.value() if spin else 0.0

            txt_notes = self.table_prices.cellWidget(row, 5)
            notes_val = txt_notes.text().strip() if txt_notes else ""

            prices_to_save.append({
                "product_id": pid,
                "has_custom_price": is_custom,
                "agreed_price_cents": to_cents(price_val) if is_custom else None,
                "notes": notes_val if is_custom else ""
            })

        try:
            with get_db_session() as session:
                CustomerService.save_customer_prices(session, self.customer_id, prices_to_save)

            QMessageBox.information(
                self,
                "Agreed Prices Saved",
                f"Custom selling prices for '{self.customer_name}' have been saved successfully!\n\n"
                "When you create bills for this customer, these custom rates will automatically be used."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save agreed prices: {str(e)}")
