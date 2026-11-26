"""Expenses Recording, Safe Deletion, and Categorization Page."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.database.models.operations import Expense, ExpenseCategory
from app.services.expense_service import ExpenseService
from app.ui.dialogs.expense_dialog import ExpenseDialog
from app.utilities.currency import format_currency
from app.localization.translator import t


class ExpensesPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("expenses_title", "Operating Expenses Management"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("expenses_subtitle", "Record electricity, fuel, water treatment, salaries, vehicle repairs, and rent"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_add = QPushButton(t("btn_add_expense", "+ Add Expense"))
        self.btn_add.clicked.connect(self.action_add_expense)
        top_bar.addWidget(self.btn_add)

        self.btn_refresh = QPushButton(t("btn_refresh", "Refresh"))
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_expenses)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Table
        self.table_expenses = QTableWidget()
        self.table_expenses.setColumnCount(7)
        self.table_expenses.setHorizontalHeaderLabels([
            "Date", "Category", "Description", "Amount", "Method", "Payee", "Actions"
        ])
        self.table_expenses.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_expenses.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table_expenses.verticalHeader().setDefaultSectionSize(40)
        main_layout.addWidget(self.table_expenses)

        self.load_expenses()

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("expenses_title", "Operating Expenses Management"))
        self.lbl_sub.setText(t("expenses_subtitle", "Record electricity, fuel, water treatment, salaries, vehicle repairs, and rent"))
        self.btn_add.setText(t("btn_add_expense", "+ Add Expense"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
        self.table_expenses.setHorizontalHeaderLabels([
            "Date", "Category", "Description", "Amount", "Method", "Payee", t("actions", "Actions")
        ])

    def load_expenses(self):
        with get_db_session() as session:
            expenses = (
                session.query(Expense)
                .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
                .order_by(Expense.date.desc(), Expense.id.desc())
                .all()
            )
            self.table_expenses.setRowCount(len(expenses))
            for row, e in enumerate(expenses):
                self.table_expenses.setItem(row, 0, QTableWidgetItem(str(e.date.strftime("%Y-%m-%d %I:%M %p"))))
                self.table_expenses.setItem(row, 1, QTableWidgetItem(e.category.name))
                self.table_expenses.setItem(row, 2, QTableWidgetItem(e.description or "-"))
                self.table_expenses.setItem(row, 3, QTableWidgetItem(format_currency(e.amount_cents)))
                self.table_expenses.setItem(row, 4, QTableWidgetItem(e.payment_method))
                self.table_expenses.setItem(row, 5, QTableWidgetItem(e.payee or "-"))

                # Actions button: Delete
                btn_del = QPushButton("🗑 Delete")
                btn_del.setProperty("class", "ActionBtnRemove")
                btn_del.setToolTip("Delete this expense record")
                btn_del.clicked.connect(lambda _, eid=e.id, desc=e.description, amt=e.amount_cents: self.action_delete_expense(eid, desc, amt))

                btn_frame = QWidget()
                b_layout = QHBoxLayout(btn_frame)
                b_layout.setContentsMargins(4, 2, 4, 2)
                b_layout.addWidget(btn_del)
                self.table_expenses.setCellWidget(row, 6, btn_frame)

    def action_add_expense(self):
        dlg = ExpenseDialog(self)
        if dlg.exec():
            self.load_expenses()

    def action_delete_expense(self, expense_id: int, description: str, amount_cents: int):
        amt_str = format_currency(amount_cents)
        prompt = f"{t('confirm_delete_exp', 'Are you sure you want to delete this expense record?')}\n\nAmount: {amt_str}\nDescription: {description or 'N/A'}"
        reply = QMessageBox.question(
            self,
            t("confirm_remove_title", "Confirm Removal"),
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                ExpenseService.delete_expense(expense_id)
                QMessageBox.information(self, "Expense Deleted", "Expense record has been deleted successfully.")
                self.load_expenses()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete expense: {str(e)}")
