"""Application theme, high-contrast light palette, and modern Qt stylesheet."""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor

NAVY_BLUE = "#0F172A"
WATER_BLUE = "#0284C7"
WATER_BLUE_HOVER = "#0369A1"
LIGHT_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
BORDER_COLOR = "#CBD5E1"
TEXT_DARK = "#0F172A"
TEXT_MUTED = "#475569"
SUCCESS_GREEN = "#16A34A"
WARNING_AMBER = "#D97706"
DANGER_RED = "#DC2626"

STYLESHEET = f"""
/* Universal Global Typography & Colors */
QWidget {{
    font-family: "Segoe UI", "Nirmala UI", sans-serif;
    color: {TEXT_DARK};
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {LIGHT_BG};
    color: {TEXT_DARK};
}}

/* Universal Labels - Force Dark Slate Text everywhere */
QLabel {{
    color: {TEXT_DARK};
    background-color: transparent;
}}

QDialog QLabel {{
    color: {TEXT_DARK};
}}

QFormLayout QLabel {{
    color: {TEXT_DARK};
    font-weight: 600;
}}

/* Sidebar */
#Sidebar {{
    background-color: {NAVY_BLUE};
    border-right: 1px solid #1E293B;
    min-width: 260px;
    max-width: 285px;
}}

#SidebarHeader {{
    padding: 18px 16px 14px 16px;
    border-bottom: 1px solid #1E293B;
    background-color: #0B1120;
}}

#AppTitle {{
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 0.3px;
}}

#AppSubtitle {{
    color: #38BDF8;
    font-size: 12px;
    font-weight: 500;
    margin-top: 4px;
}}

#NavButton {{
    background-color: transparent;
    color: #94A3B8;
    border: none;
    text-align: left;
    padding: 11px 16px;
    font-size: 13px;
    font-weight: 500;
    border-radius: 6px;
    margin: 2px 8px;
    border-left: 4px solid transparent;
}}

#NavButton:hover {{
    background-color: #1E293B;
    color: #F8FAFC;
}}

#NavButton:checked {{
    background-color: #0284C7;
    color: #FFFFFF;
    font-weight: 700;
    border-left: 4px solid #38BDF8;
    border-radius: 6px;
}}

/* Cards & Frames */
.Card, QFrame {{
    color: {TEXT_DARK};
}}

/* Buttons */
QPushButton {{
    background-color: {WATER_BLUE};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: {WATER_BLUE_HOVER};
}}

QPushButton:pressed {{
    background-color: #075985;
}}

QPushButton:disabled {{
    background-color: #CBD5E1;
    color: #94A3B8;
}}

QPushButton#SecondaryButton {{
    background-color: #FFFFFF;
    color: {TEXT_DARK};
    border: 1px solid {BORDER_COLOR};
}}

QPushButton#SecondaryButton:hover {{
    background-color: #F1F5F9;
    border-color: #94A3B8;
}}

QPushButton#DangerButton {{
    background-color: {DANGER_RED};
    color: #FFFFFF;
}}

QPushButton#DangerButton:hover {{
    background-color: #B91C1C;
}}

QPushButton#SuccessButton {{
    background-color: {SUCCESS_GREEN};
    color: #FFFFFF;
}}

QPushButton#SuccessButton:hover {{
    background-color: #15803D;
}}

/* Form inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTextEdit {{
    background-color: #FFFFFF;
    border: 1.5px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: {TEXT_DARK};
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {{
    border: 1.5px solid {WATER_BLUE};
    background-color: #FFFFFF;
}}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background-color: #F1F5F9;
    color: {TEXT_MUTED};
    border: 1px solid #E2E8F0;
}}

/* QComboBox Dropdown & Popup Item View */
QComboBox {{
    background-color: #FFFFFF;
    color: {TEXT_DARK};
    border: 1.5px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: #FFFFFF;
    color: {TEXT_DARK};
    border: 1px solid {BORDER_COLOR};
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
    padding: 4px;
}}

/* Checkbox & Radio */
QCheckBox, QRadioButton {{
    color: {TEXT_DARK};
    font-size: 13px;
    font-weight: 500;
}}

/* Table view */
QTableWidget, QTableView {{
    background-color: #FFFFFF;
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    gridline-color: #F1F5F9;
    selection-background-color: #E0F2FE;
    selection-color: {TEXT_DARK};
    color: {TEXT_DARK};
    font-size: 13px;
}}

QHeaderView::section {{
    background-color: #F8FAFC;
    color: {TEXT_MUTED};
    padding: 8px;
    font-weight: 700;
    font-size: 12px;
    border: none;
    border-bottom: 2px solid {BORDER_COLOR};
}}

QTableCornerButton::section {{
    background-color: #F8FAFC;
    border: none;
    border-bottom: 2px solid {BORDER_COLOR};
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background: #F1F5F9;
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: #CBD5E1;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #94A3B8;
}}

/* Action Buttons */
QPushButton.ActionBtnEdit {{
    background-color: #F1F5F9;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton.ActionBtnEdit:hover {{
    background-color: #E2E8F0;
    border-color: #94A3B8;
}}

QPushButton.ActionBtnRemove {{
    background-color: #FEF2F2;
    color: #DC2626;
    border: 1px solid #FECACA;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton.ActionBtnRemove:hover {{
    background-color: #FEE2E2;
    color: #B91C1C;
    border-color: #FCA5A5;
}}

QPushButton.ActionBtnPay {{
    background-color: #EFF6FF;
    color: #0284C7;
    border: 1px solid #BFDBFE;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton.ActionBtnPay:hover {{
    background-color: #DBEAFE;
    border-color: #93C5FD;
}}

QPushButton.ActionBtnReactivate {{
    background-color: #F0FDF4;
    color: #16A34A;
    border: 1px solid #BBF7D0;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton.ActionBtnReactivate:hover {{
    background-color: #DCFCE7;
    border-color: #86EFAC;
}}

QPushButton.ActionBtnPrice {{
    background-color: #F0FDF4;
    color: #15803D;
    border: 1px solid #BBF7D0;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton.ActionBtnPrice:hover {{
    background-color: #DCFCE7;
    color: #166534;
    border-color: #86EFAC;
}}
"""


def apply_app_theme(app: QApplication) -> None:
    """
    Apply a forced high-contrast light palette and unified stylesheet to QApplication.
    Prevents Windows Dark Mode from causing white-on-white text in dialogs and inputs.
    """
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F8FAFC"))
    palette.setColor(QPalette.WindowText, QColor("#0F172A"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F1F5F9"))
    palette.setColor(QPalette.ToolTipBase, QColor("#0F172A"))
    palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
    palette.setColor(QPalette.Text, QColor("#0F172A"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#0F172A"))
    palette.setColor(QPalette.BrightText, QColor("#DC2626"))
    palette.setColor(QPalette.Link, QColor("#0284C7"))
    palette.setColor(QPalette.Highlight, QColor("#0284C7"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
