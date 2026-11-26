"""Stock Management Page: Product inventory, Batch-wise FIFO stock, Safe Removal, and Adjustments."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox, QFrame, QTabWidget
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.database.models.product import Product
from app.database.models.inventory import InventoryBatch
from app.services.inventory_service import InventoryService
from app.ui.dialogs.stock_adjustment_dialog import StockAdjustmentDialog
from app.utilities.currency import format_currency
from app.localization.translator import t


class StockPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("nav_stock", "Stock & FIFO Inventory Management"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel("Traceable batch-based stock, remaining quantities, unit costs, and product management")
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_adjust = QPushButton("+ Adjust Stock")
        self.btn_adjust.clicked.connect(self.action_adjust_stock)
        top_bar.addWidget(self.btn_adjust)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_stock_data)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Tabs: Batches vs Products
        self.tabs = QTabWidget()

        # Tab 1: FIFO Batches
        tab_batches = QWidget()
        b_layout = QVBoxLayout(tab_batches)
        b_layout.setContentsMargins(0, 10, 0, 0)

        # Filter bar
        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px; color: #0F172A;")
        f_layout = QHBoxLayout(filter_bar)
        lbl_filter_prod = QLabel("Filter by Product:")
        lbl_filter_prod.setStyleSheet("color: #0F172A; font-weight: 600;")
        f_layout.addWidget(lbl_filter_prod)
        self.cmb_filter_product = QComboBox()
        self.cmb_filter_product.addItem("All Products", None)
        self.cmb_filter_product.currentIndexChanged.connect(self.load_batches_data)
        f_layout.addWidget(self.cmb_filter_product)
        f_layout.addStretch()
        b_layout.addWidget(filter_bar)

        self.table_batches = QTableWidget()
        self.table_batches.setColumnCount(8)
        self.table_batches.setHorizontalHeaderLabels([
            "Batch Number", "Product", "Received Date", "Original Qty", "Remaining Qty", "Unit Cost", "Total Value", "Status"
        ])
        self.table_batches.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        b_layout.addWidget(self.table_batches)
        self.tabs.addTab(tab_batches, "FIFO Inventory Batches")

        # Tab 2: Products Master & Removal
        tab_prods = QWidget()
        p_layout = QVBoxLayout(tab_prods)
        p_layout.setContentsMargins(0, 10, 0, 0)

        self.table_products = QTableWidget()
        self.table_products.setColumnCount(8)
        self.table_products.setHorizontalHeaderLabels([
            "Code", "Product Name", "Bottle Size", "Selling Price", "Available Stock", "Min Level", "Status", "Actions"
        ])
        self.table_products.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_products.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table_products.verticalHeader().setDefaultSectionSize(40)
        p_layout.addWidget(self.table_products)
        self.tabs.addTab(tab_prods, "Products Master List")

        main_layout.addWidget(self.tabs)

        self.load_products_filter()
        self.load_stock_data()

    def retranslate_ui(self):
        self.lbl_title.setText(t("stock_title", "Stock & FIFO Inventory Management"))
        self.lbl_sub.setText(t("stock_subtitle", "Traceable batch-based stock, remaining quantities, unit costs, and product management"))
        self.btn_adjust.setText(t("btn_add_stock", "+ Adjust Stock"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
        self.tabs.setTabText(0, t("tab_fifo_batches", "FIFO Inventory Batches"))
        self.tabs.setTabText(1, t("tab_products_master", "Products Master List"))
        self.load_stock_data()

    def load_products_filter(self):
        self.cmb_filter_product.clear()
        self.cmb_filter_product.addItem("All Products", None)
        with get_db_session() as session:
            products = session.query(Product).order_by(Product.code.asc()).all()
            for p in products:
                self.cmb_filter_product.addItem(f"{p.name} ({p.code})", p.id)

    def load_stock_data(self):
        self.load_batches_data()
        self.load_products_data()

    def load_batches_data(self):
        pid = self.cmb_filter_product.currentData()
        with get_db_session() as session:
            query = (
                session.query(InventoryBatch)
                .join(Product, Product.id == InventoryBatch.product_id)
                .order_by(InventoryBatch.received_date.desc(), InventoryBatch.id.desc())
            )
            if pid:
                query = query.filter(InventoryBatch.product_id == pid)

            batches = query.all()
            self.table_batches.setRowCount(len(batches))

            for row, b in enumerate(batches):
                self.table_batches.setItem(row, 0, QTableWidgetItem(b.batch_number))
                self.table_batches.setItem(row, 1, QTableWidgetItem(b.product.name))
                self.table_batches.setItem(row, 2, QTableWidgetItem(str(b.received_date)))
                self.table_batches.setItem(row, 3, QTableWidgetItem(f"{b.original_qty} bottles"))

                rem_item = QTableWidgetItem(f"{b.remaining_qty} bottles")
                if b.remaining_qty == 0:
                    rem_item.setForeground(Qt.gray)
                self.table_batches.setItem(row, 4, rem_item)

                self.table_batches.setItem(row, 5, QTableWidgetItem(format_currency(b.unit_cost_cents)))
                val = b.remaining_qty * b.unit_cost_cents
                self.table_batches.setItem(row, 6, QTableWidgetItem(format_currency(val)))

                status_item = QTableWidgetItem(b.status)
                if b.status == "ACTIVE":
                    status_item.setForeground(Qt.darkGreen)
                elif b.status == "EXHAUSTED":
                    status_item.setForeground(Qt.gray)
                self.table_batches.setItem(row, 7, status_item)

    def load_products_data(self):
        with get_db_session() as session:
            products = session.query(Product).order_by(Product.code.asc()).all()
            self.table_products.setRowCount(len(products))

            for row, p in enumerate(products):
                self.table_products.setItem(row, 0, QTableWidgetItem(p.code))
                self.table_products.setItem(row, 1, QTableWidgetItem(p.name))
                self.table_products.setItem(row, 2, QTableWidgetItem(p.bottle_size))
                self.table_products.setItem(row, 3, QTableWidgetItem(format_currency(p.default_selling_price_cents)))

                avail = InventoryService.get_available_stock(session, p.id)
                avail_item = QTableWidgetItem(f"{avail} bottles")
                if avail < p.min_stock_level:
                    avail_item.setForeground(Qt.red)
                self.table_products.setItem(row, 4, avail_item)

                self.table_products.setItem(row, 5, QTableWidgetItem(f"{p.min_stock_level} bottles"))

                status_item = QTableWidgetItem("Active" if p.is_active else "Archived")
                status_item.setForeground(Qt.darkGreen if p.is_active else Qt.gray)
                self.table_products.setItem(row, 6, status_item)

                btn_frame = QWidget()
                btn_box = QHBoxLayout(btn_frame)
                btn_box.setContentsMargins(4, 2, 4, 2)
                btn_box.setSpacing(6)

                if p.is_active:
                    btn_rem = QPushButton("🗑 Remove")
                    btn_rem.setProperty("class", "ActionBtnRemove")
                    btn_rem.setToolTip("Safely archive or delete product")
                    btn_rem.clicked.connect(lambda _, pid=p.id, name=p.name: self.action_remove_product(pid, name))
                    btn_box.addWidget(btn_rem)
                else:
                    btn_react = QPushButton("↺ Reactivate")
                    btn_react.setProperty("class", "ActionBtnReactivate")
                    btn_react.setToolTip("Reactivate archived product")
                    btn_react.clicked.connect(lambda _, pid=p.id, name=p.name: self.action_reactivate_product(pid, name))
                    btn_box.addWidget(btn_react)

                self.table_products.setCellWidget(row, 7, btn_frame)

    def action_adjust_stock(self):
        dlg = StockAdjustmentDialog(self)
        if dlg.exec():
            self.load_stock_data()

    def action_remove_product(self, pid: int, name: str):
        reply = QMessageBox.question(
            self,
            "Confirm Product Removal",
            f"Are you sure you want to remove product '{name}'?\n\n"
            "Safety Protection Policy:\n"
            "• If this product has active stock, removal is blocked.\n"
            "• If it has past batches or sales, it will be safely Archived to protect historical invoices.\n"
            "• If completely unused, it will be permanently deleted.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                with get_db_session() as session:
                    res = InventoryService.remove_product(session, pid, reason="User requested removal from Stock page")
                QMessageBox.information(self, "Product Removed", res["message"])
                self.load_stock_data()
                self.load_products_filter()
            except ValueError as ve:
                QMessageBox.warning(self, "Safety Check Blocked Removal", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove product: {str(e)}")

    def action_reactivate_product(self, pid: int, name: str):
        try:
            with get_db_session() as session:
                InventoryService.reactivate_product(session, pid)
            QMessageBox.information(self, "Product Reactivated", f"Product '{name}' is now active and available for new bills.")
            self.load_stock_data()
            self.load_products_filter()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reactivate product: {str(e)}")
