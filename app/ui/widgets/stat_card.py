"""Dashboard statistic card widget."""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "Rs. 0.00", subtitle: str = "", accent_color: str = "#0284C7", parent=None):
        super().__init__(parent)
        self.setProperty("class", "Card")
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #64748B; font-size: 12px; font-weight: 600; text-transform: uppercase;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("color: #0F172A; font-size: 20px; font-weight: bold;")
        layout.addWidget(self.value_label)

        if subtitle:
            self.sub_label = QLabel(subtitle)
            self.sub_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
            layout.addWidget(self.sub_label)
        else:
            self.sub_label = None

    def update_value(self, value: str, subtitle: str = ""):
        self.value_label.setText(value)
        if self.sub_label and subtitle:
            self.sub_label.setText(subtitle)
