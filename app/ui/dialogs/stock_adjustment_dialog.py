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
        self.setFixedSize(480, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

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

        form.addRow("Inventory Batch*:", self.cmb_batch)
        form.addRow("Available in Batch:", self.lbl_avail)
        form.addRow("Adjustment Type*:", self.cmb_type)
        form.addRow("Quantity (Bottles)*:", self.spin_qty)
        form.addRow("Mandatory Reason*:", self.txt_reason)
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
