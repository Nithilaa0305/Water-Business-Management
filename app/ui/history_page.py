"""Activity History & Append-Only Audit Trail Page."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
)
from app.database.connection import get_db_session
from app.database.models.operations import AuditLog
from app.localization.translator import t


class HistoryPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("history_title", "Activity History & Audit Trail"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("history_subtitle", "Append-only audit records of sales, payments, stock movements, and user actions"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_refresh = QPushButton(t("btn_refresh", "Refresh"))
        self.btn_refresh.setObjectName("SecondaryButton")
        self.btn_refresh.clicked.connect(self.load_audit_logs)
        top_bar.addWidget(self.btn_refresh)
        main_layout.addLayout(top_bar)

        # Table
        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(7)
        self.table_logs.setHorizontalHeaderLabels([
            "Timestamp", "User", "Role", "Action Type", "Entity", "Reference", "Reason / Notes"
        ])
        self.table_logs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table_logs)

        self.load_audit_logs()

    def load_audit_logs(self):
        with get_db_session() as session:
            logs = session.query(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(100).all()
            self.table_logs.setRowCount(len(logs))

            for row, l in enumerate(logs):
                self.table_logs.setItem(row, 0, QTableWidgetItem(str(l.timestamp.strftime("%Y-%m-%d %I:%M %p"))))
                self.table_logs.setItem(row, 1, QTableWidgetItem(l.user_name or "System"))
                self.table_logs.setItem(row, 2, QTableWidgetItem(l.role or "SYSTEM"))
                self.table_logs.setItem(row, 3, QTableWidgetItem(l.action_type))
                self.table_logs.setItem(row, 4, QTableWidgetItem(f"{l.entity_name} #{l.entity_id or ''}"))
                self.table_logs.setItem(row, 5, QTableWidgetItem(l.reference_no or "-"))
                self.table_logs.setItem(row, 6, QTableWidgetItem(l.reason or "-"))

    def retranslate_ui(self):
        """Update texts when language toggles."""
        self.lbl_title.setText(t("history_title", "Activity History & Audit Trail"))
        self.lbl_sub.setText(t("history_subtitle", "Append-only audit records of sales, payments, stock movements, and user actions"))
        self.btn_refresh.setText(t("btn_refresh", "Refresh"))
