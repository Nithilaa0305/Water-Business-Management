"""Daily Cash Drawer Reconciliation and Physical Closing Screen."""

from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QSpinBox, QDoubleSpinBox, QFrame, QMessageBox, QDateEdit, QGridLayout, QTextEdit, QScrollArea, QDialog
)
from PySide6.QtCore import Qt, QDate
from app.database.connection import get_db_session
from app.database.models.operations import DailyCashClosing
from app.services.daily_closing_service import DailyClosingService, SL_DENOMINATIONS
from app.services.auth_service import AuthService
from app.utilities.dates import today_colombo, now_colombo
from app.utilities.currency import to_cents, from_cents, format_currency
from app.localization.translator import t


class DailyClosingPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.denom_spinboxes: Dict[str, QSpinBox] = {}
        self.denom_name_labels: Dict[str, QLabel] = {}
        self.denom_subtotal_labels: Dict[str, QLabel] = {}
        self.current_summary: Dict[str, Any] = {}

        # Outer Layout containing Scroll Area to prevent any overflow or clipping
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: #F8FAFC; border: none; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: #F8FAFC;")
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header Bar
        top_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("daily_closing_title", "Daily Cash Closing & Drawer Reconciliation"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("daily_closing_sub", "Reconcile daily cash collections, expenses, and physical drawer denominations"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_layout.addLayout(header_text)
        top_layout.addStretch()

        # Date Selector
        date_box = QHBoxLayout()
        self.lbl_date_prompt = QLabel(t("closing_date", "Closing Date:"))
        self.lbl_date_prompt.setStyleSheet("font-weight: 600; color: #334155;")
        date_box.addWidget(self.lbl_date_prompt)

        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        today = today_colombo()
        self.date_picker.setDate(QDate(today.year, today.month, today.day))
        self.date_picker.dateChanged.connect(self.load_daily_data)
        date_box.addWidget(self.date_picker)

        self.btn_refresh = QPushButton(t("refresh_totals", "🔄 Refresh Totals"))
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_daily_data)
        date_box.addWidget(self.btn_refresh)
        top_layout.addLayout(date_box)
        main_layout.addLayout(top_layout)

        # Main Split Content: Left = Financial Calculation, Right = Denomination Counter
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # LEFT COLUMN: Expected Cash & Summary Breakdown
        left_frame = QFrame()
        left_frame.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px;")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setSpacing(8)

        self.lbl_sec1 = QLabel(t("drawer_reconciliation", "💵 Drawer Reconciliation Breakdown"))
        self.lbl_sec1.setStyleSheet("font-size: 16px; font-weight: bold; color: #0284C7; border-bottom: 2px solid #E2E8F0; padding-bottom: 6px;")
        left_layout.addWidget(self.lbl_sec1)

        # Opening Float Input
        open_row = QHBoxLayout()
        self.lbl_open_float = QLabel(t("opening_float", "Opening Cash Float (Rs.):"))
        self.lbl_open_float.setStyleSheet("font-weight: 500; color: #334155;")
        open_row.addWidget(self.lbl_open_float)

        self.spin_opening_cash = QDoubleSpinBox()
        self.spin_opening_cash.setRange(0, 10000000)
        self.spin_opening_cash.setDecimals(2)
        self.spin_opening_cash.valueChanged.connect(self.recalculate_variance)
        open_row.addWidget(self.spin_opening_cash)
        left_layout.addLayout(open_row)

        self.lbl_cash_sales = QLabel("Cash Water Sales: Rs. 0.00")
        self.lbl_credit_coll = QLabel("Credit Collections (Cash): Rs. 0.00")
        self.lbl_advances = QLabel("Customer Advances (Cash): Rs. 0.00")
        self.lbl_deposits = QLabel("Bottle Deposits (Cash): Rs. 0.00")

        self.lbl_expenses = QLabel("Cash Expenses: -Rs. 0.00")
        self.lbl_expenses.setStyleSheet("color: #DC2626;")
        self.lbl_supplier_pay = QLabel("Supplier Cash Payments: -Rs. 0.00")
        self.lbl_supplier_pay.setStyleSheet("color: #DC2626;")
        self.lbl_refunds = QLabel("Deposit Refunds Paid: -Rs. 0.00")
        self.lbl_refunds.setStyleSheet("color: #DC2626;")

        for lbl in [self.lbl_cash_sales, self.lbl_credit_coll, self.lbl_advances, self.lbl_deposits]:
            lbl.setStyleSheet("color: #166534; font-size: 13px; font-weight: 500;")
            left_layout.addWidget(lbl)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #E2E8F0;")
        left_layout.addWidget(line)

        for lbl in [self.lbl_expenses, self.lbl_supplier_pay, self.lbl_refunds]:
            lbl.setStyleSheet("color: #B91C1C; font-size: 13px; font-weight: 500;")
            left_layout.addWidget(lbl)

        # Expected Total Box
        exp_box = QFrame()
        exp_box.setStyleSheet("background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 6px; padding: 10px;")
        exp_layout = QVBoxLayout(exp_box)
        self.lbl_expected_cash = QLabel("EXPECTED DRAWER CASH: Rs. 0.00")
        self.lbl_expected_cash.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E40AF;")
        exp_layout.addWidget(self.lbl_expected_cash)
        left_layout.addWidget(exp_box)

        # Variance Indicator Badge
        var_box = QFrame()
        var_box.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px;")
        var_layout = QVBoxLayout(var_box)
        self.lbl_counted_total = QLabel("PHYSICAL COUNTED CASH: Rs. 0.00")
        self.lbl_counted_total.setStyleSheet("font-size: 16px; font-weight: bold; color: #0F172A;")
        self.lbl_variance = QLabel("VARIANCE: BALANCED (Rs. 0.00)")
        self.lbl_variance.setStyleSheet("font-size: 15px; font-weight: bold; color: #16A34A;")
        var_layout.addWidget(self.lbl_counted_total)
        var_layout.addWidget(self.lbl_variance)
        left_layout.addWidget(var_box)

        # Notes
        self.lbl_notes_prompt = QLabel(t("notes_label", "Notes / Variance Explanation:"))
        self.lbl_notes_prompt.setStyleSheet("font-weight: 500; color: #334155;")
        left_layout.addWidget(self.lbl_notes_prompt)

        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("Optional notes or explanation for any cash difference...")
        left_layout.addWidget(self.txt_notes)

        # Action Buttons
        btn_action_row = QHBoxLayout()
        self.btn_finalize = QPushButton(t("finalize_closing", "💾 Finalize Daily Closing"))
        self.btn_finalize.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 10px 18px;")
        self.btn_finalize.clicked.connect(self.action_finalize_closing)
        btn_action_row.addWidget(self.btn_finalize)

        self.btn_print = QPushButton(t("print_report", "🖨 Print Report"))
        self.btn_print.setObjectName("SecondaryButton")
        self.btn_print.clicked.connect(self.action_print_report)
        btn_action_row.addWidget(self.btn_print)
        left_layout.addLayout(btn_action_row)

        content_layout.addWidget(left_frame, 5)

        # RIGHT COLUMN: Physical Denomination Counter
        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px;")
        right_layout = QVBoxLayout(right_frame)

        self.lbl_sec2 = QLabel(t("drawer_reconciliation", "🔢 Currency Denomination Counter"))
        self.lbl_sec2.setStyleSheet("font-size: 16px; font-weight: bold; color: #0284C7; border-bottom: 2px solid #E2E8F0; padding-bottom: 6px;")
        right_layout.addWidget(self.lbl_sec2)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.lbl_hdr_denom = QLabel("<b>Denomination</b>")
        self.lbl_hdr_count = QLabel("<b>Count</b>")
        self.lbl_hdr_subtot = QLabel("<b>Subtotal (Rs.)</b>")
        grid.addWidget(self.lbl_hdr_denom, 0, 0)
        grid.addWidget(self.lbl_hdr_count, 0, 1)
        grid.addWidget(self.lbl_hdr_subtot, 0, 2)

        for row, d in enumerate(SL_DENOMINATIONS, start=1):
            key = str(d["value_rs"])
            t_key = f"denom_{d['value_rs']}"
            display_name = t(t_key, d["name"])

            name_lbl = QLabel(display_name)
            name_lbl.setStyleSheet("font-weight: 500; font-size: 13px; color: #334155;")
            grid.addWidget(name_lbl, row, 0)
            self.denom_name_labels[key] = name_lbl

            spin = QSpinBox()
            spin.setRange(0, 100000)
            spin.setValue(0)
            spin.valueChanged.connect(self.on_denomination_changed)
            grid.addWidget(spin, row, 1)
            self.denom_spinboxes[key] = spin

            sub_lbl = QLabel("Rs. 0.00")
            sub_lbl.setStyleSheet("color: #475569; font-weight: 600; font-size: 13px;")
            grid.addWidget(sub_lbl, row, 2)
            self.denom_subtotal_labels[key] = sub_lbl

        right_layout.addLayout(grid)

        # Clear Denominations button
        self.btn_clear_denom = QPushButton(t("clear_denominations", "Clear Denomination Counts"))
        self.btn_clear_denom.setObjectName("SecondaryButton")
        self.btn_clear_denom.clicked.connect(self.clear_denominations)
        right_layout.addWidget(self.btn_clear_denom)
        right_layout.addStretch()

        content_layout.addWidget(right_frame, 5)
        main_layout.addLayout(content_layout)

        # Bottom Past Closings Table
        self.lbl_hist = QLabel(t("recent_closings_history", "Recent Daily Closings History"))
        self.lbl_hist.setStyleSheet("font-size: 15px; font-weight: bold; color: #334155; margin-top: 10px;")
        main_layout.addWidget(self.lbl_hist)

        self.table_history = QTableWidget()
        self.table_history.setColumnCount(7)
        self.table_history.setHorizontalHeaderLabels([
            t("col_ref_num", "Ref #"),
            t("col_date", "Date"),
            t("col_open_cash", "Opening Cash"),
            t("col_expected_cash", "Expected Cash"),
            t("col_actual_counted", "Actual Counted"),
            t("col_difference", "Difference"),
            t("col_status", "Status")
        ])
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_history.setMinimumHeight(180)
        main_layout.addWidget(self.table_history)

        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll)

        self.load_daily_data()
        self.load_history_table()

    def get_selected_date(self) -> any:
        qd = self.date_picker.date()
        return today_colombo().replace(year=qd.year(), month=qd.month(), day=qd.day())

    def load_daily_data(self):
        c_date = self.get_selected_date()
        with get_db_session() as session:
            # Check if there is already a closing for this day
            existing = session.query(DailyCashClosing).filter_by(closing_date=c_date).first()
            if existing:
                self.spin_opening_cash.setValue(float(from_cents(existing.opening_cash_cents)))
                summary = DailyClosingService.calculate_daily_summary(
                    session, closing_date=c_date, opening_cash_cents=existing.opening_cash_cents
                )
            else:
                summary = DailyClosingService.calculate_daily_summary(session, closing_date=c_date)
                self.spin_opening_cash.setValue(float(from_cents(summary["opening_cash_cents"])))

            self.current_summary = summary

        # Populate labels with localized prefixes
        self.lbl_cash_sales.setText(f"{t('cash_sales_label', 'Cash Water Sales:')} {summary['cash_sales_display']}")
        self.lbl_credit_coll.setText(f"{t('credit_coll_label', 'Credit Collections (Cash):')} {summary['credit_collections_display']}")
        self.lbl_advances.setText(f"{t('advances_label', 'Customer Advances (Cash):')} {summary['customer_advances_display']}")
        self.lbl_deposits.setText(f"{t('deposits_label', 'Bottle Deposits (Cash):')} {summary['deposits_collected_display']}")

        self.lbl_expenses.setText(f"{t('expenses_label', 'Cash Expenses:')} -{summary['cash_expenses_display']}")
        self.lbl_supplier_pay.setText(f"{t('supplier_pay_label', 'Supplier Cash Payments:')} -{summary['supplier_payments_display']}")
        self.lbl_refunds.setText(f"{t('refunds_label', 'Deposit Refunds Paid:')} -{summary['deposit_refunds_display']}")

        self.recalculate_variance()

    def on_denomination_changed(self):
        counts = {k: sp.value() for k, sp in self.denom_spinboxes.items()}
        for d in SL_DENOMINATIONS:
            k = str(d["value_rs"])
            cnt = counts.get(k, 0)
            subtot_cents = cnt * d["value_cents"]
            if k in self.denom_subtotal_labels:
                self.denom_subtotal_labels[k].setText(format_currency(subtot_cents))

        total_counted_cents = DailyClosingService.calculate_counted_from_denominations(counts)
        self.lbl_counted_total.setText(f"{t('counted_cash_label', 'PHYSICAL COUNTED CASH:')} {format_currency(total_counted_cents)}")
        self.recalculate_variance()

    def recalculate_variance(self):
        open_cents = to_cents(self.spin_opening_cash.value())
        total_inflow = self.current_summary.get("total_inflow_cents", 0)
        total_outflow = self.current_summary.get("total_outflow_cents", 0)
        expected_cents = open_cents + total_inflow - total_outflow
        self.lbl_expected_cash.setText(f"{t('expected_cash_label', 'EXPECTED DRAWER CASH:')} {format_currency(expected_cents)}")

        counts = {k: sp.value() for k, sp in self.denom_spinboxes.items()}
        actual_cents = DailyClosingService.calculate_counted_from_denominations(counts)

        diff = actual_cents - expected_cents
        if diff == 0:
            self.lbl_variance.setText(f"{t('variance_balanced', 'VARIANCE: BALANCED')} (Rs. 0.00)")
            self.lbl_variance.setStyleSheet("font-size: 15px; font-weight: bold; color: #16A34A;")
        elif diff > 0:
            self.lbl_variance.setText(f"{t('variance_surplus', 'VARIANCE: SURPLUS')} (+{format_currency(diff)})")
            self.lbl_variance.setStyleSheet("font-size: 15px; font-weight: bold; color: #0284C7;")
        else:
            self.lbl_variance.setText(f"{t('variance_shortage', 'VARIANCE: SHORTAGE')} ({format_currency(diff)})")
            self.lbl_variance.setStyleSheet("font-size: 15px; font-weight: bold; color: #DC2626;")

    def clear_denominations(self):
        for sp in self.denom_spinboxes.values():
            sp.setValue(0)

    def action_finalize_closing(self):
        c_date = self.get_selected_date()
        open_cents = to_cents(self.spin_opening_cash.value())
        counts = {k: sp.value() for k, sp in self.denom_spinboxes.items()}
        actual_cents = DailyClosingService.calculate_counted_from_denominations(counts)
        notes = self.txt_notes.text().strip()

        reply = QMessageBox.question(
            self,
            "Confirm Daily Closing",
            f"Are you sure you want to finalize the cash closing for {c_date.strftime('%Y-%m-%d')}?\n\n"
            f"Actual Counted Cash: {format_currency(actual_cents)}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        try:
            curr_user = AuthService.get_current_user()
            with get_db_session() as session:
                closing = DailyClosingService.record_daily_closing(
                    session=session,
                    closing_date=c_date,
                    opening_cash_cents=open_cents,
                    actual_cash_cents=actual_cents,
                    denominations_counts=counts,
                    notes=notes,
                    user_id=curr_user.id if curr_user else None
                )
                cls_num = closing.closing_number

            QMessageBox.information(
                self, "Closing Finalized", f"Daily closing {cls_num} recorded successfully!"
            )
            self.load_history_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to record daily closing: {str(e)}")

    def action_print_report(self):
        c_date = self.get_selected_date()
        with get_db_session() as session:
            closing = session.query(DailyCashClosing).filter_by(closing_date=c_date).first()
            if not closing:
                # If not yet closed, generate report from current live calculation
                open_cents = to_cents(self.spin_opening_cash.value())
                counts = {k: sp.value() for k, sp in self.denom_spinboxes.items()}
                actual_cents = DailyClosingService.calculate_counted_from_denominations(counts)
                closing = DailyClosingService.record_daily_closing(
                    session=session,
                    closing_date=c_date,
                    opening_cash_cents=open_cents,
                    actual_cash_cents=actual_cents,
                    denominations_counts=counts,
                    notes=self.txt_notes.text().strip()
                )

            report_text = DailyClosingService.generate_closing_report_text(closing)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Closing Report — {closing.closing_number}")
        dlg.resize(550, 600)
        d_layout = QVBoxLayout(dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFontFamily("Consolas")
        txt.setText(report_text)
        d_layout.addWidget(txt)
        dlg.exec()

    def load_history_table(self):
        with get_db_session() as session:
            closings = session.query(DailyCashClosing).order_by(DailyCashClosing.closing_date.desc()).limit(15).all()
            self.table_history.setRowCount(len(closings))
            for row, c in enumerate(closings):
                self.table_history.setItem(row, 0, QTableWidgetItem(c.closing_number))
                self.table_history.setItem(row, 1, QTableWidgetItem(c.closing_date.strftime("%Y-%m-%d")))
                self.table_history.setItem(row, 2, QTableWidgetItem(format_currency(c.opening_cash_cents)))
                self.table_history.setItem(row, 3, QTableWidgetItem(format_currency(c.expected_cash_cents)))
                self.table_history.setItem(row, 4, QTableWidgetItem(format_currency(c.actual_cash_cents)))

                diff_str = format_currency(c.difference_cents)
                diff_item = QTableWidgetItem(diff_str)
                if c.difference_cents < 0:
                    diff_item.setForeground(Qt.red)
                elif c.difference_cents > 0:
                    diff_item.setForeground(Qt.darkGreen)
                self.table_history.setItem(row, 5, diff_item)

                self.table_history.setItem(row, 6, QTableWidgetItem(c.status))

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("daily_closing_title", "Daily Cash Closing & Drawer Reconciliation"))
        self.lbl_sub.setText(t("daily_closing_sub", "Reconcile daily cash collections, expenses, and physical drawer denominations"))
        self.lbl_date_prompt.setText(t("closing_date", "Closing Date:"))
        self.btn_refresh.setText(t("refresh_totals", "🔄 Refresh Totals"))
        self.lbl_sec1.setText(t("drawer_reconciliation", "💵 Drawer Reconciliation Breakdown"))
        self.lbl_open_float.setText(t("opening_float", "Opening Cash Float (Rs.):"))
        self.lbl_sec2.setText(t("drawer_reconciliation", "🔢 Currency Denomination Counter"))
        self.lbl_notes_prompt.setText(t("notes_label", "Notes / Variance Explanation:"))
        self.btn_finalize.setText(t("finalize_closing", "💾 Finalize Daily Closing"))
        self.btn_print.setText(t("print_report", "🖨 Print Report"))
        self.btn_clear_denom.setText(t("clear_denominations", "Clear Denomination Counts"))
        self.lbl_hist.setText(t("recent_closings_history", "Recent Daily Closings History"))

        # Update denomination names in grid
        for d in SL_DENOMINATIONS:
            key = str(d["value_rs"])
            t_key = f"denom_{d['value_rs']}"
            if key in self.denom_name_labels:
                self.denom_name_labels[key].setText(t(t_key, d["name"]))

        # Update table history headers
        self.table_history.setHorizontalHeaderLabels([
            t("col_ref_num", "Ref #"),
            t("col_date", "Date"),
            t("col_open_cash", "Opening Cash"),
            t("col_expected_cash", "Expected Cash"),
            t("col_actual_counted", "Actual Counted"),
            t("col_difference", "Difference"),
            t("col_status", "Status")
        ])

        self.load_daily_data()
        self.load_history_table()
