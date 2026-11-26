"""Dialog to execute 19 L bottle cleaning and refill batch."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QSpinBox, QDoubleSpinBox
)
from app.database.connection import get_db_session
from app.config.constants import BottleState
from app.services.bottle_service import BottleService
from app.services.refill_service import RefillService
from app.utilities.currency import to_cents


class RefillDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Refill 19 L Bottles")
        self.setFixedSize(500, 440)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.lbl_empty_avail = QLabel("0 bottles")
        self.lbl_empty_avail.setStyleSheet("font-weight: bold; color: #0284C7;")

        self.spin_selected = QSpinBox()
        self.spin_selected.setRange(1, 5000)
        self.spin_selected.setValue(30)
        self.spin_selected.valueChanged.connect(self.on_counts_changed)

        self.spin_refilled = QSpinBox()
        self.spin_refilled.setRange(0, 5000)
        self.spin_refilled.setValue(30)
        self.spin_refilled.valueChanged.connect(self.on_counts_changed)

        self.spin_damaged = QSpinBox()
        self.spin_damaged.setRange(0, 500)
        self.spin_damaged.setValue(0)
        self.spin_damaged.valueChanged.connect(self.on_counts_changed)

        # Direct Production Costs
        self.spin_water = QDoubleSpinBox()
        self.spin_water.setRange(0, 500000)
        self.spin_water.setPrefix("Rs. ")
        self.spin_water.setValue(1500.00)

        self.spin_caps = QDoubleSpinBox()
        self.spin_caps.setRange(0, 500000)
        self.spin_caps.setPrefix("Rs. ")
        self.spin_caps.setValue(600.00)

        self.spin_labour = QDoubleSpinBox()
        self.spin_labour.setRange(0, 500000)
        self.spin_labour.setPrefix("Rs. ")
        self.spin_labour.setValue(900.00)

        self.lbl_unit_cost = QLabel("Rs. 100.00 / bottle")
        self.lbl_unit_cost.setStyleSheet("font-weight: bold; color: #16A34A;")

        self.txt_notes = QLineEdit()

        form.addRow("Available Empty in Warehouse:", self.lbl_empty_avail)
        form.addRow("Empty Bottles Selected*:", self.spin_selected)
        form.addRow("Successfully Refilled*:", self.spin_refilled)
        form.addRow("Damaged / Rejected*:", self.spin_damaged)
        form.addRow("Water Treatment Cost:", self.spin_water)
        form.addRow("Caps & Seals Cost:", self.spin_caps)
        form.addRow("Direct Labour Cost:", self.spin_labour)
        form.addRow("Calculated Unit Cost:", self.lbl_unit_cost)
        form.addRow("Notes:", self.txt_notes)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Execute Refill")
        self.btn_save.clicked.connect(self.save_refill)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        self.refresh_available_empty()

    def refresh_available_empty(self):
        with get_db_session() as session:
            avail = BottleService.get_state_quantity(session, BottleState.EMPTY_AVAILABLE)
            self.lbl_empty_avail.setText(f"{avail} bottles available")
            self.spin_selected.setMaximum(max(avail, 1))

    def on_counts_changed(self):
        refilled = self.spin_refilled.value()
        total_costs = self.spin_water.value() + self.spin_caps.value() + self.spin_labour.value()
        if refilled > 0:
            unit_cost = total_costs / refilled
            self.lbl_unit_cost.setText(f"Rs. {unit_cost:.2f} / bottle")
        else:
            self.lbl_unit_cost.setText("Rs. 0.00 / bottle")

    def save_refill(self):
        selected = self.spin_selected.value()
        refilled = self.spin_refilled.value()
        damaged = self.spin_damaged.value()

        if (refilled + damaged) != selected:
            QMessageBox.warning(
                self, "Count Mismatch",
                f"Refilled ({refilled}) + Damaged ({damaged}) must equal Selected ({selected})."
            )
            return

        try:
            with get_db_session() as session:
                RefillService.execute_refill_batch(
                    session=session,
                    empty_bottles_selected=selected,
                    bottles_refilled=refilled,
                    bottles_rejected_damaged=damaged,
                    water_treatment_cost_cents=to_cents(self.spin_water.value()),
                    cap_seal_cost_cents=to_cents(self.spin_caps.value()),
                    labour_cost_cents=to_cents(self.spin_labour.value()),
                    notes=self.txt_notes.text().strip() or None
                )
            QMessageBox.information(self, "Success", f"Refill batch complete! {refilled} full bottles added to inventory.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not execute refill: {str(e)}")
