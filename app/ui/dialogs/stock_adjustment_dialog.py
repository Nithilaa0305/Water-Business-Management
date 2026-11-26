"""Dialog for manual stock adjustment with mandatory reason."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QComboBox, QSpinBox
)
from app.database.connection import get_db_session
from app.database.models.inventory import InventoryBatch
from app.database.models.product import Product
from app.services.inventory_service import InventoryService


class StockAdjustmentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adjust Batch Stock")
        self.resize(500, 420)
        self.setMinimumSize(460, 380)
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

        self.cmb_batch = QComboBox()
        self.lbl_avail = QLabel("-")
        self.lbl_avail.setStyleSheet("font-weight: bold; color: #0284C7;")

        self.cmb_type = QComboBox()
        self.cmb_type.addItem("Damage (Breakage / Leaking)", "DAMAGE")
        self.cmb_type.addItem("Expired Bottles", "EXPIRED")
        self.cmb_type.addItem("Lost / Missing Containers", "LOST")
        self.cmb_type.addItem("Stock Count Reduction (Correction Out)", "CORRECTION_OUT")
        self.cmb_type.addItem("Stock Count Addition (Correction In)", "CORRECTION_IN")

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 10000)
        self.spin_qty.setValue(1)

        self.txt_reason = QLineEdit()
        self.txt_reason.setPlaceholderText("Mandatory reason for audit trail")

        form.addRow(_lbl("Inventory Batch*:"), self.cmb_batch)
        form.addRow(_lbl("Available in Batch:"), self.lbl_avail)
        form.addRow(_lbl("Adjustment Type*:"), self.cmb_type)
        form.addRow(_lbl("Quantity (Bottles)*:"), self.spin_qty)
        form.addRow(_lbl("Mandatory Reason*:"), self.txt_reason)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Apply Adjustment")
        self.btn_save.clicked.connect(self.save_adjustment)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        self.load_batches()
        self.cmb_batch.currentIndexChanged.connect(self.on_batch_changed)

    def load_batches(self):
        with get_db_session() as session:
            batches = (
                session.query(InventoryBatch)
                .join(Product, Product.id == InventoryBatch.product_id)
                .filter(InventoryBatch.status == "ACTIVE")
                .filter(InventoryBatch.remaining_qty > 0)
                .order_by(InventoryBatch.id.desc())
                .all()
            )
            for b in batches:
                self.cmb_batch.addItem(f"{b.product.name} - {b.batch_number} ({b.remaining_qty} avail)", b.id)
        self.on_batch_changed()

    def on_batch_changed(self):
        bid = self.cmb_batch.currentData()
        if not bid:
            self.lbl_avail.setText("-")
            return
        with get_db_session() as session:
            b = session.query(InventoryBatch).filter_by(id=bid).first()
            if b:
                self.lbl_avail.setText(f"{b.remaining_qty} bottles remaining")

    def save_adjustment(self):
        bid = self.cmb_batch.currentData()
        reason = self.txt_reason.text().strip()
        if not bid or not reason:
            QMessageBox.warning(self, "Validation", "Please select a batch and enter a mandatory reason.")
            return

        adj_type = self.cmb_type.currentData()
        qty = self.spin_qty.value()

        try:
            with get_db_session() as session:
                InventoryService.adjust_stock(
                    session=session,
                    batch_id=bid,
                    adjustment_type=adj_type,
                    quantity=qty,
                    reason=reason
                )
            QMessageBox.information(self, "Success", f"Stock adjustment of {qty} bottles recorded.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not adjust stock: {str(e)}")
