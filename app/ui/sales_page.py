"""Fast Billing & Sales Invoicing Screen."""

from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QSpinBox, QDoubleSpinBox, QFrame, QMessageBox, QDateEdit, QCompleter, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.database.models.product import Product, PackagingUnit
from app.database.models.sales import SalesInvoice
from app.services.customer_service import CustomerService
from app.services.inventory_service import InventoryService
from app.services.sales_service import SalesService
from app.services.credit_service import CreditService
from app.ui.dialogs.invoice_preview_dialog import InvoicePreviewDialog
from app.ui.dialogs.customer_dialog import CustomerDialog
from app.utilities.currency import to_cents, from_cents, format_currency
from app.localization.translator import t


class SalesPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.invoice_items: List[Dict[str, Any]] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header
        top_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("sales_title", "New Bill / Sales Management"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("sales_subtitle", "Fast keyboard-friendly invoicing, customer price suggestion, and 19L bottle tracking"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_layout.addLayout(header_text)
        top_layout.addStretch()

        self.btn_new_cust = QPushButton(t("btn_add_customer", "+ Add Customer"))
        self.btn_new_cust.setObjectName("SecondaryButton")
        self.btn_new_cust.clicked.connect(self.action_new_customer)
        top_layout.addWidget(self.btn_new_cust)
        main_layout.addLayout(top_layout)

        # Customer selection bar
        cust_bar = QFrame()
        cust_bar.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px;")
        cust_vlayout = QVBoxLayout(cust_bar)
        cust_vlayout.setContentsMargins(10, 8, 10, 8)
        cust_vlayout.setSpacing(8)

        # Row 1: Selection & Fast Action Buttons
        cust_row1 = QHBoxLayout()
        cust_row1.setSpacing(10)

        self.lbl_select_cust = QLabel(t("select_customer", "Customer:"))
        self.lbl_select_cust.setStyleSheet("font-weight: 600; font-size: 13px; color: #334155;")
        cust_row1.addWidget(self.lbl_select_cust)

        self.cmb_customer = QComboBox()
        self.cmb_customer.setEditable(True)
        self.cmb_customer.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_customer.setMinimumWidth(320)
        if self.cmb_customer.lineEdit():
            self.cmb_customer.lineEdit().setPlaceholderText("Search by ID (e.g. CUST-001) or Name...")
        self.cmb_customer.currentIndexChanged.connect(self.on_customer_selected)
        if self.cmb_customer.completer():
            self.cmb_customer.completer().setFilterMode(Qt.MatchContains)
            self.cmb_customer.completer().setCaseSensitivity(Qt.CaseInsensitive)
            self.cmb_customer.completer().setCompletionMode(QCompleter.PopupCompletion)
        cust_row1.addWidget(self.cmb_customer, 3)

        self.btn_walkin = QPushButton(t("walkin_customer", "🚶 Walk-in Cash"))
        self.btn_walkin.setObjectName("SecondaryButton")
        self.btn_walkin.setToolTip("Quickly select Anonymous Walk-in Cash Customer")
        self.btn_walkin.clicked.connect(self.select_walkin_customer)
        cust_row1.addWidget(self.btn_walkin)

        self.btn_cust_prices = QPushButton(t("btn_prices", "💲 Pre-Set Prices"))
        self.btn_cust_prices.setObjectName("SecondaryButton")
        self.btn_cust_prices.setToolTip("View or pre-configure agreed product selling prices for this customer")
        self.btn_cust_prices.clicked.connect(self.open_selected_customer_prices)
        cust_row1.addWidget(self.btn_cust_prices)

        self.btn_repeat_order = QPushButton(t("btn_repeat_order", "🔁 Repeat Last Order"))
        self.btn_repeat_order.setObjectName("SecondaryButton")
        self.btn_repeat_order.setToolTip("1-Click repeat order from this customer's previous bill, revalidating stock & prices")
        self.btn_repeat_order.clicked.connect(self.action_repeat_last_order)
        cust_row1.addWidget(self.btn_repeat_order)

        cust_row1.addStretch()
        cust_vlayout.addLayout(cust_row1)

        # Row 2: Customer Live Status Badges (Financial balance & 19L bottles)
        cust_row2 = QHBoxLayout()
        cust_row2.setSpacing(12)

        self.lbl_cust_financial = QLabel("Account Settled")
        self.lbl_cust_financial.setWordWrap(True)
        self.lbl_cust_financial.setStyleSheet("background-color: #F0FDF4; color: #166534; font-weight: bold; font-size: 12px; padding: 5px 12px; border-radius: 6px; border: 1px solid #BBF7D0;")
        cust_row2.addWidget(self.lbl_cust_financial)

        self.lbl_cust_bottles = QLabel("19L Bottles: 0")
        self.lbl_cust_bottles.setWordWrap(True)
        self.lbl_cust_bottles.setStyleSheet("background-color: #EFF6FF; color: #1E40AF; font-weight: bold; font-size: 12px; padding: 5px 12px; border-radius: 6px; border: 1px solid #BFDBFE;")
        cust_row2.addWidget(self.lbl_cust_bottles)

        cust_row2.addStretch()
        cust_vlayout.addLayout(cust_row2)

        main_layout.addWidget(cust_bar)

        # Item Entry Row
        item_bar = QFrame()
        item_bar.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px;")
        item_layout = QHBoxLayout(item_bar)
        item_layout.setContentsMargins(6, 6, 6, 6)
        item_layout.setSpacing(10)

        # Product combo
        item_layout.addWidget(QLabel("Product:"))
        self.cmb_product = QComboBox()
        self.cmb_product.setMinimumWidth(220)
        self.cmb_product.currentIndexChanged.connect(self.on_product_selected)
        item_layout.addWidget(self.cmb_product)

        # Packaging unit combo
        item_layout.addWidget(QLabel("Unit:"))
        self.cmb_unit = QComboBox()
        self.cmb_unit.currentIndexChanged.connect(self.on_unit_selected)
        item_layout.addWidget(self.cmb_unit)

        # Qty
        item_layout.addWidget(QLabel("Qty:"))
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 10000)
        self.spin_qty.setValue(10)
        item_layout.addWidget(self.spin_qty)

        # Unit price
        item_layout.addWidget(QLabel("Price (Rs.):"))
        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0.01, 1000000.00)
        self.spin_price.setValue(60.00)
        item_layout.addWidget(self.spin_price)

        self.lbl_price_type = QLabel("Standard Price")
        self.lbl_price_type.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; background: #F1F5F9;")
        item_layout.addWidget(self.lbl_price_type)

        # Available stock label
        self.lbl_stock_avail = QLabel("Stock: -")
        self.lbl_stock_avail.setStyleSheet("color: #64748B; font-size: 12px;")
        item_layout.addWidget(self.lbl_stock_avail)

        self.btn_add_item = QPushButton(t("add_item", "+ Add Item"))
        self.btn_add_item.clicked.connect(self.add_item_to_invoice)
        item_layout.addWidget(self.btn_add_item)

        main_layout.addWidget(item_bar)

        # Invoice items table
        self.table_items = QTableWidget()
        self.table_items.setColumnCount(7)
        self.table_items.setHorizontalHeaderLabels([
            "Product", "Packaging Unit", "Qty", "Unit Price", "Line Total", "19L Bottle", "Action"
        ])
        self.table_items.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_items.verticalHeader().setDefaultSectionSize(40)
        main_layout.addWidget(self.table_items)

        # Price update on bill checkbox bar
        opt_bar = QHBoxLayout()
        self.chk_save_agreed_prices = QCheckBox(t("save_as_agreed_prices", "Update customer's agreed prices with the unit prices on this bill"))
        self.chk_save_agreed_prices.setToolTip("If checked, any custom unit prices entered on this bill will be saved as this customer's pre-configured agreed prices for future bills.")
        self.chk_save_agreed_prices.setStyleSheet("color: #0369A1; font-weight: 600; font-size: 12px; padding: 2px;")
        opt_bar.addWidget(self.chk_save_agreed_prices)
        opt_bar.addStretch()
        main_layout.addLayout(opt_bar)

        # Footer calculation & payment controls
        footer_layout = QHBoxLayout()

        # Left: 19L bottle exchange controls
        bottle_box = QFrame()
        bottle_box.setStyleSheet("background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 12px;")
        b_box_layout = QVBoxLayout(bottle_box)

        lbl_b_title = QLabel("19 L Returnable Bottles on this Bill:")
        lbl_b_title.setStyleSheet("font-weight: bold; color: #1E40AF;")
        b_box_layout.addWidget(lbl_b_title)

        row_ret = QHBoxLayout()
        row_ret.addWidget(QLabel("Empty 19L Bottles Returned:"))
        self.spin_19l_returned = QSpinBox()
        self.spin_19l_returned.setRange(0, 1000)
        self.spin_19l_returned.setValue(0)
        row_ret.addWidget(self.spin_19l_returned)
        b_box_layout.addLayout(row_ret)

        footer_layout.addWidget(bottle_box)
        footer_layout.addStretch()

        # Right: Totals and Payment
        totals_box = QFrame()
        totals_box.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        tot_layout = QVBoxLayout(totals_box)
        tot_layout.setSpacing(8)

        # Subtotal
        self.lbl_subtotal = QLabel("Subtotal: Rs. 0.00")
        self.lbl_subtotal.setStyleSheet("font-size: 14px; font-weight: 500;")
        tot_layout.addWidget(self.lbl_subtotal)

        # Invoice discount
        disc_row = QHBoxLayout()
        disc_row.addWidget(QLabel("Discount (Rs.):"))
        self.spin_inv_discount = QDoubleSpinBox()
        self.spin_inv_discount.setRange(0, 1000000)
        self.spin_inv_discount.valueChanged.connect(self.recalculate_totals)
        disc_row.addWidget(self.spin_inv_discount)
        tot_layout.addLayout(disc_row)

        # Total
        self.lbl_total = QLabel("Total: Rs. 0.00")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: bold; color: #0284C7;")
        tot_layout.addWidget(self.lbl_total)

        # Payment method
        pay_row = QHBoxLayout()
        pay_row.addWidget(QLabel("Method:"))
        self.cmb_pay_method = QComboBox()
        self.cmb_pay_method.addItems(["CASH", "CREDIT", "BANK_TRANSFER", "CHEQUE", "MIXED"])
        self.cmb_pay_method.currentIndexChanged.connect(self.on_payment_method_changed)
        pay_row.addWidget(self.cmb_pay_method)

        pay_row.addWidget(QLabel("Paid (Rs.):"))
        self.spin_amount_paid = QDoubleSpinBox()
        self.spin_amount_paid.setRange(0, 10000000)
        self.spin_amount_paid.setValue(0.00)
        self.spin_amount_paid.valueChanged.connect(self.update_allocation_breakdown)
        pay_row.addWidget(self.spin_amount_paid)
        tot_layout.addLayout(pay_row)

        # Payment Allocation Mode and Breakdown
        alloc_row = QHBoxLayout()
        alloc_row.addWidget(QLabel("Allocation:"))
        self.cmb_alloc_mode = QComboBox()
        self.cmb_alloc_mode.addItem("Current Invoice", "CURRENT_INVOICE")
        self.cmb_alloc_mode.addItem("Oldest Outstanding Debt", "OLDEST_INVOICES")
        self.cmb_alloc_mode.addItem("Customer Advance", "ADVANCE")
        self.cmb_alloc_mode.currentIndexChanged.connect(self.update_allocation_breakdown)
        alloc_row.addWidget(self.cmb_alloc_mode)
        tot_layout.addLayout(alloc_row)

        self.lbl_alloc_breakdown = QLabel("")
        self.lbl_alloc_breakdown.setWordWrap(True)
        self.lbl_alloc_breakdown.setStyleSheet("color: #475569; font-size: 11px; padding-top: 2px;")
        tot_layout.addWidget(self.lbl_alloc_breakdown)

        footer_layout.addWidget(totals_box)
        main_layout.addLayout(footer_layout)

        # Action Buttons
        btn_bar = QHBoxLayout()
        self.btn_clear = QPushButton("Clear Bill")
        self.btn_clear.setObjectName("SecondaryButton")
        self.btn_clear.clicked.connect(self.clear_invoice)
        btn_bar.addWidget(self.btn_clear)

        btn_bar.addStretch()

        self.btn_save = QPushButton("Save Bill")
        self.btn_save.clicked.connect(lambda: self.save_invoice(print_after=False))
        btn_bar.addWidget(self.btn_save)

        self.btn_save_print = QPushButton("Save & Print Invoice")
        self.btn_save_print.setStyleSheet("background-color: #16A34A; color: white;")
        self.btn_save_print.clicked.connect(lambda: self.save_invoice(print_after=True))
        btn_bar.addWidget(self.btn_save_print)

        main_layout.addLayout(btn_bar)

        self.load_customers()
        self.load_products()
        self.load_units()

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("sales_title", "New Bill / Sales Management"))
        self.lbl_sub.setText(t("sales_subtitle", "Fast keyboard-friendly invoicing, customer price suggestion, and 19L bottle tracking"))
        self.btn_new_cust.setText(t("btn_add_customer", "+ Add Customer"))
        self.btn_add_item.setText(t("add_item", "+ Add Item"))
        self.btn_clear.setText(t("btn_clear", "Clear Bill"))
        self.btn_save.setText(t("btn_save_bill", "Save Bill"))
        self.btn_save_print.setText(t("btn_save_print", "Save & Print Invoice"))
        if hasattr(self, 'lbl_select_cust'):
            self.lbl_select_cust.setText(t("select_customer", "Customer:"))
        if hasattr(self, 'btn_walkin'):
            self.btn_walkin.setText(t("walkin_customer", "🚶 Walk-in Cash"))
        if hasattr(self, 'btn_cust_prices'):
            self.btn_cust_prices.setText(t("btn_prices", "💲 Pre-Set Prices"))
        if hasattr(self, 'btn_repeat_order'):
            self.btn_repeat_order.setText(t("btn_repeat_order", "🔁 Repeat Last Order"))
        if hasattr(self, 'chk_save_agreed_prices'):
            self.chk_save_agreed_prices.setText(t("save_as_agreed_prices", "Update customer's agreed prices with the unit prices on this bill"))
        if hasattr(self, 'table_items'):
            self.table_items.setHorizontalHeaderLabels([
                t("col_product", "Product"),
                t("col_unit", "Packaging Unit"),
                t("col_qty", "Qty"),
                t("col_price", "Unit Price"),
                t("col_line_total", "Line Total"),
                t("col_bottle_action", "19L Bottle"),
                t("col_action", "Action")
            ])
        if hasattr(self, 'cmb_alloc_mode'):
            curr_mode = self.cmb_alloc_mode.currentData()
            self.cmb_alloc_mode.blockSignals(True)
            self.cmb_alloc_mode.clear()
            self.cmb_alloc_mode.addItem(t("alloc_current", "Current Invoice"), "CURRENT_INVOICE")
            self.cmb_alloc_mode.addItem(t("alloc_oldest", "Oldest Outstanding Debt"), "OLDEST_INVOICES")
            self.cmb_alloc_mode.addItem(t("alloc_advance", "Customer Advance"), "ADVANCE")
            idx = self.cmb_alloc_mode.findData(curr_mode)
            if idx >= 0:
                self.cmb_alloc_mode.setCurrentIndex(idx)
            self.cmb_alloc_mode.blockSignals(False)
        self.load_customers()

    def load_customers(self):
        curr_id = self.cmb_customer.currentData() if hasattr(self, 'cmb_customer') else None
        self.cmb_customer.blockSignals(True)
        self.cmb_customer.clear()
        self.cmb_customer.addItem(f"{t('walkin_customer', '🚶 Walk-in Cash')} (Anonymous)", None)
        with get_db_session() as session:
            customers = session.query(Customer).filter_by(is_active=True).order_by(Customer.code.asc()).all()
            for c in customers:
                display_label = f"[{c.code}] {c.name}" + (f" ({c.phone})" if c.phone else "")
                self.cmb_customer.addItem(display_label, c.id)

        if self.cmb_customer.completer():
            self.cmb_customer.completer().setFilterMode(Qt.MatchContains)
            self.cmb_customer.completer().setCaseSensitivity(Qt.CaseInsensitive)
            self.cmb_customer.completer().setCompletionMode(QCompleter.PopupCompletion)

        # Restore previous selection or default to 0 (Walk-in)
        target_idx = 0
        if curr_id:
            found = self.cmb_customer.findData(curr_id)
            if found >= 0:
                target_idx = found
        self.cmb_customer.setCurrentIndex(target_idx)
        self.cmb_customer.blockSignals(False)
        self.on_customer_selected()

    def select_walkin_customer(self):
        self.cmb_customer.setCurrentIndex(0)
        self.on_customer_selected()

    def load_products(self):
        self.cmb_product.clear()
        with get_db_session() as session:
            products = session.query(Product).filter_by(is_active=True).order_by(Product.code.asc()).all()
            for p in products:
                self.cmb_product.addItem(f"{p.name} ({p.code})", p.id)

    def load_units(self):
        self.cmb_unit.clear()
        with get_db_session() as session:
            units = session.query(PackagingUnit).order_by(PackagingUnit.factor.asc()).all()
            for u in units:
                self.cmb_unit.addItem(u.name, u.id)

    def on_customer_selected(self):
        cid = self.cmb_customer.currentData()
        if not cid:
            # Check if user typed a search term without clicking popup
            text = self.cmb_customer.currentText().strip().lower()
            if text and not text.startswith("walk-in") and not text.startswith("🚶"):
                for i in range(1, self.cmb_customer.count()):
                    item_text = self.cmb_customer.itemText(i).lower()
                    if text in item_text:
                        cid = self.cmb_customer.itemData(i)
                        self.cmb_customer.blockSignals(True)
                        self.cmb_customer.setCurrentIndex(i)
                        self.cmb_customer.blockSignals(False)
                        break

        if not cid:
            self.lbl_cust_financial.setText("Walk-in Cash Customer (No Credit)")
            self.lbl_cust_bottles.setText("19L Bottles: 0")
            self.update_suggested_price()
            return

        with get_db_session() as session:
            s = CustomerService.get_customer_financial_summary(session, cid)
            self.lbl_cust_financial.setText(s["status_text"])
            self.lbl_cust_bottles.setText(f"19L Bottles Held: {s['outstanding_bottles_19l']}")

            # If there are already items on the bill and customer has agreed prices,
            # update the item prices and line totals
            if self.invoice_items:
                for item in self.invoice_items:
                    sugg_cents = CustomerService.get_suggested_price(
                        session, cid, item["product_id"], item.get("packaging_unit_id")
                    )
                    factor = item.get("factor", 1)
                    item["unit_price_cents"] = sugg_cents * factor
                    item["line_total_cents"] = item["quantity"] * item["unit_price_cents"]
                self.refresh_items_table()
                self.recalculate_totals()

        self.update_suggested_price()

    def on_product_selected(self):
        self.update_suggested_price()
        self.update_available_stock()

    def on_unit_selected(self):
        self.update_suggested_price()

    def update_available_stock(self):
        pid = self.cmb_product.currentData()
        if not pid:
            self.lbl_stock_avail.setText("Stock: -")
            return
        with get_db_session() as session:
            avail = InventoryService.get_available_stock(session, pid)
            self.lbl_stock_avail.setText(f"Available Stock: {avail} bottles")

    def update_suggested_price(self):
        pid = self.cmb_product.currentData()
        cid = self.cmb_customer.currentData()
        uid = self.cmb_unit.currentData()
        if not pid:
            if hasattr(self, 'lbl_price_type'):
                self.lbl_price_type.setText("-")
            return

        with get_db_session() as session:
            from app.database.models.customer import CustomerPrice
            agreement = None
            if cid:
                agreement = (
                    session.query(CustomerPrice)
                    .filter_by(customer_id=cid, product_id=pid)
                    .first()
                )

            price_cents = CustomerService.get_suggested_price(session, cid, pid, uid)
            factor = 1
            if uid:
                u = session.query(PackagingUnit).filter_by(id=uid).first()
                if u:
                    factor = u.factor

            final_unit_price = price_cents * factor
            self.spin_price.setValue(float(from_cents(final_unit_price)))

            if hasattr(self, 'lbl_price_type'):
                if agreement:
                    self.lbl_price_type.setText("🏷 Agreed Price (Pre-Set)")
                    self.lbl_price_type.setStyleSheet(
                        "color: #15803D; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; background: #DCFCE7;"
                    )
                elif cid:
                    self.lbl_price_type.setText("🏷 Customer Rate")
                    self.lbl_price_type.setStyleSheet(
                        "color: #0369A1; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; background: #E0F2FE;"
                    )
                else:
                    self.lbl_price_type.setText("🏷 Standard Price")
                    self.lbl_price_type.setStyleSheet(
                        "color: #64748B; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; background: #F1F5F9;"
                    )

    def on_payment_method_changed(self):
        method = self.cmb_pay_method.currentText()
        if method == "CASH":
            # Default paid amount to total
            self.spin_amount_paid.setValue(self.calculate_net_total())
        elif method == "CREDIT":
            self.spin_amount_paid.setValue(0.00)

    def add_item_to_invoice(self):
        pid = self.cmb_product.currentData()
        if not pid:
            return

        qty = self.spin_qty.value()
        price_cents = to_cents(self.spin_price.value())
        uid = self.cmb_unit.currentData()

        with get_db_session() as session:
            prod = session.query(Product).filter_by(id=pid).first()
            unit = session.query(PackagingUnit).filter_by(id=uid).first() if uid else None

            factor = unit.factor if unit else 1
            base_qty = qty * factor
            avail = InventoryService.get_available_stock(session, pid)

            # Check if stock is sufficient
            already_in_cart = sum(i["base_qty"] for i in self.invoice_items if i["product_id"] == pid)
            if (base_qty + already_in_cart) > avail:
                QMessageBox.warning(
                    self, "Insufficient Stock",
                    f"Only {avail} bottles available of {prod.name}. Reduce quantity or add stock."
                )
                return

            line_total = qty * price_cents
            self.invoice_items.append({
                "product_id": pid,
                "product_name": prod.name,
                "is_returnable": prod.is_returnable,
                "packaging_unit_id": uid,
                "unit_name": unit.name if unit else prod.uom,
                "factor": factor,
                "quantity": qty,
                "base_qty": base_qty,
                "unit_price_cents": price_cents,
                "line_total_cents": line_total
            })

        self.refresh_items_table()
        self.recalculate_totals()

    def refresh_items_table(self):
        self.table_items.setRowCount(len(self.invoice_items))
        for row, item in enumerate(self.invoice_items):
            self.table_items.setItem(row, 0, QTableWidgetItem(item["product_name"]))
            self.table_items.setItem(row, 1, QTableWidgetItem(item["unit_name"]))

            # Editable Qty SpinBox in table
            spin_qty = QSpinBox()
            spin_qty.setRange(1, 10000)
            spin_qty.setValue(item["quantity"])
            spin_qty.valueChanged.connect(lambda val, r=row: self.on_table_item_qty_changed(r, val))
            q_frame = QWidget()
            q_layout = QHBoxLayout(q_frame)
            q_layout.setContentsMargins(4, 2, 4, 2)
            q_layout.addWidget(spin_qty)
            self.table_items.setCellWidget(row, 2, q_frame)

            # Editable Unit Price SpinBox in table (allows on-the-fly price edits!)
            spin_price = QDoubleSpinBox()
            spin_price.setRange(0.01, 1000000.00)
            spin_price.setDecimals(2)
            spin_price.setPrefix("Rs. ")
            spin_price.setValue(float(from_cents(item["unit_price_cents"])))
            spin_price.valueChanged.connect(lambda val, r=row: self.on_table_item_price_changed(r, val))
            p_frame = QWidget()
            p_layout = QHBoxLayout(p_frame)
            p_layout.setContentsMargins(4, 2, 4, 2)
            p_layout.addWidget(spin_price)
            self.table_items.setCellWidget(row, 3, p_frame)

            tot_item = QTableWidgetItem(format_currency(item["line_total_cents"]))
            tot_item.setTextAlignment(Qt.AlignCenter)
            self.table_items.setItem(row, 4, tot_item)

            self.table_items.setItem(row, 5, QTableWidgetItem("Yes" if item["is_returnable"] else "-"))

            btn_remove = QPushButton("✕ Remove")
            btn_remove.setProperty("class", "ActionBtnRemove")
            btn_remove.setToolTip("Remove this item from invoice")
            btn_remove.clicked.connect(lambda _, r=row: self.remove_item(r))

            btn_frame = QWidget()
            b_layout = QHBoxLayout(btn_frame)
            b_layout.setContentsMargins(4, 2, 4, 2)
            b_layout.addWidget(btn_remove)
            self.table_items.setCellWidget(row, 6, btn_frame)

    def on_table_item_qty_changed(self, row: int, new_qty: int):
        if 0 <= row < len(self.invoice_items):
            item = self.invoice_items[row]
            item["quantity"] = new_qty
            factor = item.get("factor", 1)
            item["base_qty"] = new_qty * factor
            item["line_total_cents"] = new_qty * item["unit_price_cents"]
            tot_item = self.table_items.item(row, 4)
            if tot_item:
                tot_item.setText(format_currency(item["line_total_cents"]))
            self.recalculate_totals()

    def on_table_item_price_changed(self, row: int, new_price_float: float):
        if 0 <= row < len(self.invoice_items):
            item = self.invoice_items[row]
            price_cents = to_cents(new_price_float)
            item["unit_price_cents"] = price_cents
            item["line_total_cents"] = item["quantity"] * price_cents
            tot_item = self.table_items.item(row, 4)
            if tot_item:
                tot_item.setText(format_currency(item["line_total_cents"]))
            self.recalculate_totals()

    def open_selected_customer_prices(self):
        cid = self.cmb_customer.currentData()
        if not cid:
            QMessageBox.information(
                self, "Select Customer", 
                "Please select an identified customer from the dropdown to view or configure their agreed prices."
            )
            return
        from app.ui.dialogs.customer_price_dialog import CustomerPriceDialog
        dlg = CustomerPriceDialog(self, customer_id=cid)
        if dlg.exec():
            self.update_suggested_price()
            if self.invoice_items:
                with get_db_session() as session:
                    for item in self.invoice_items:
                        sugg_cents = CustomerService.get_suggested_price(
                            session, cid, item["product_id"], item.get("packaging_unit_id")
                        )
                        factor = item.get("factor", 1)
                        item["unit_price_cents"] = sugg_cents * factor
                        item["line_total_cents"] = item["quantity"] * item["unit_price_cents"]
                self.refresh_items_table()
                self.recalculate_totals()

    def remove_item(self, row_idx):
        if 0 <= row_idx < len(self.invoice_items):
            self.invoice_items.pop(row_idx)
            self.refresh_items_table()
            self.recalculate_totals()

    def calculate_net_total(self) -> float:
        subtotal_cents = sum(i["line_total_cents"] for i in self.invoice_items)
        disc_cents = to_cents(self.spin_inv_discount.value())
        net_cents = max(0, subtotal_cents - disc_cents)
        return float(from_cents(net_cents))

    def recalculate_totals(self):
        subtotal_cents = sum(i["line_total_cents"] for i in self.invoice_items)
        disc_cents = to_cents(self.spin_inv_discount.value())
        net_cents = max(0, subtotal_cents - disc_cents)

        self.lbl_subtotal.setText(f"Subtotal: {format_currency(subtotal_cents)}")
        self.lbl_total.setText(f"Total: {format_currency(net_cents)}")

        if self.cmb_pay_method.currentText() == "CASH":
            self.spin_amount_paid.setValue(float(from_cents(net_cents)))

        self.update_allocation_breakdown()

    def update_allocation_breakdown(self):
        """Display real-time payment allocation breakdown."""
        cid = self.cmb_customer.currentData() if hasattr(self, 'cmb_customer') else None
        if not hasattr(self, 'lbl_alloc_breakdown'):
            return

        if not cid:
            self.lbl_alloc_breakdown.setText("Walk-in customer: Settled immediately.")
            return

        with get_db_session() as session:
            s = CustomerService.get_customer_financial_summary(session, cid)
            prev_balance_cents = s["current_balance_cents"]

        net_cents = to_cents(self.calculate_net_total())
        paid_cents = to_cents(self.spin_amount_paid.value())
        mode = self.cmb_alloc_mode.currentData() if hasattr(self, 'cmb_alloc_mode') else "CURRENT_INVOICE"

        if mode == "CURRENT_INVOICE":
            alloc_curr = min(paid_cents, net_cents)
            rem_bill = net_cents - alloc_curr
            new_total_debt = prev_balance_cents + rem_bill
            self.lbl_alloc_breakdown.setText(
                f"Prev Debt: {format_currency(prev_balance_cents)} | "
                f"Paid on Bill: {format_currency(alloc_curr)} | "
                f"Remaining Debt: {format_currency(new_total_debt)}"
            )
        elif mode == "OLDEST_INVOICES":
            alloc_prev = min(paid_cents, prev_balance_cents)
            rem_pay = max(0, paid_cents - alloc_prev)
            alloc_curr = min(rem_pay, net_cents)
            rem_bill = net_cents - alloc_curr
            new_total_debt = prev_balance_cents - alloc_prev + rem_bill
            self.lbl_alloc_breakdown.setText(
                f"Paid Old Debt: {format_currency(alloc_prev)} | "
                f"Paid on Bill: {format_currency(alloc_curr)} | "
                f"Remaining Debt: {format_currency(new_total_debt)}"
            )
        else:
            new_total_debt = prev_balance_cents + net_cents - paid_cents
            self.lbl_alloc_breakdown.setText(
                f"Recorded as Advance | Net Debt After: {format_currency(new_total_debt)}"
            )

    def action_repeat_last_order(self):
        """1-Click duplicate customer's previous invoice, revalidating current stock and prices."""
        cid = self.cmb_customer.currentData()
        if not cid:
            QMessageBox.information(self, "Select Customer", "Please select an identified customer to repeat their previous order.")
            return

        with get_db_session() as session:
            last_inv = (
                session.query(SalesInvoice)
                .filter_by(customer_id=cid, status="POSTED")
                .order_by(SalesInvoice.id.desc())
                .first()
            )
            if not last_inv:
                QMessageBox.information(self, "No History", "No previous invoices found for this customer.")
                return

            repeat_data = SalesService.prepare_repeat_order(session, last_inv.id)

        # Clear existing items and fill with repeated order
        self.invoice_items.clear()
        for it in repeat_data["items"]:
            self.invoice_items.append({
                "product_id": it["product_id"],
                "product_name": it["product_name"],
                "product_code": it["product_code"],
                "bottle_size": it["bottle_size"],
                "packaging_unit_id": it["packaging_unit_id"],
                "packaging_unit_name": it["packaging_unit_name"],
                "factor": it["unit_factor"],
                "quantity": it["quantity"],
                "base_qty": it["quantity"] * it["unit_factor"],
                "unit_price_cents": it["unit_price_cents"],
                "line_total_cents": it["quantity"] * it["unit_price_cents"],
                "is_returnable": (it["bottle_size"] == "19 L" or "19" in it["product_name"]),
            })

        self.refresh_items_table()
        self.spin_inv_discount.setValue(float(from_cents(repeat_data["discount_cents"])))
        self.recalculate_totals()

        if repeat_data["warnings"]:
            warn_msg = "\n".join(repeat_data["warnings"])
            QMessageBox.warning(self, "Revalidation Warnings", f"Order duplicated from {repeat_data['previous_invoice_number']}:\n\n{warn_msg}")
        else:
            QMessageBox.information(
                self, "Order Repeated",
                f"Successfully duplicated items from invoice #{repeat_data['previous_invoice_number']}. Stock & current prices revalidated!"
            )

    def clear_invoice(self):
        self.invoice_items.clear()
        self.refresh_items_table()
        self.spin_inv_discount.setValue(0.00)
        self.spin_amount_paid.setValue(0.00)
        self.spin_19l_returned.setValue(0)
        self.recalculate_totals()

    def save_invoice(self, print_after=False):
        if not self.invoice_items:
            QMessageBox.warning(self, "Validation", "Please add at least one product to the invoice.")
            return

        cid = self.cmb_customer.currentData()
        method = self.cmb_pay_method.currentText()
        paid_cents = to_cents(self.spin_amount_paid.value())
        disc_cents = to_cents(self.spin_inv_discount.value())
        empty_ret = self.spin_19l_returned.value()
        alloc_mode = self.cmb_alloc_mode.currentData() if hasattr(self, 'cmb_alloc_mode') else "CURRENT_INVOICE"

        # Prevent double click by disabling buttons
        self.btn_save.setEnabled(False)
        self.btn_save_print.setEnabled(False)

        try:
            with get_db_session() as session:
                items_data = [
                    {
                        "product_id": i["product_id"],
                        "quantity": i["quantity"],
                        "unit_price_cents": i["unit_price_cents"],
                        "packaging_unit_id": i["packaging_unit_id"]
                    }
                    for i in self.invoice_items
                ]
                inv = SalesService.create_invoice(
                    session=session,
                    items_data=items_data,
                    customer_id=cid,
                    payment_method=method,
                    amount_paid_cents=paid_cents,
                    discount_cents=disc_cents,
                    empty_19l_returned=empty_ret,
                    payment_allocation_mode=alloc_mode
                )
                saved_id = inv.id
                saved_num = inv.invoice_number

                # If requested, update customer's pre-configured agreed prices with prices on this bill
                if cid and hasattr(self, 'chk_save_agreed_prices') and self.chk_save_agreed_prices.isChecked():
                    for item in self.invoice_items:
                        CustomerService.set_customer_agreed_price(
                            session=session,
                            customer_id=cid,
                            product_id=item["product_id"],
                            price_cents=item["unit_price_cents"],
                            packaging_unit_id=item.get("packaging_unit_id"),
                            notes=f"Updated from bill #{saved_num}"
                        )

            if hasattr(self, 'chk_save_agreed_prices'):
                self.chk_save_agreed_prices.setChecked(False)

            QMessageBox.information(self, "Success", f"Invoice #{saved_num} created successfully!")
            self.clear_invoice()
            self.on_customer_selected()

            if print_after:
                preview = InvoicePreviewDialog(saved_id, self)
                preview.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save invoice: {str(e)}")
        finally:
            self.btn_save.setEnabled(True)
            self.btn_save_print.setEnabled(True)

    def action_new_customer(self):
        dlg = CustomerDialog(self)
        if dlg.exec():
            self.load_customers()
