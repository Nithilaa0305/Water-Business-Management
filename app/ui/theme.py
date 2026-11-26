"""Application theme and modern Qt stylesheet."""

NAVY_BLUE = "#0F172A"
WATER_BLUE = "#0284C7"
WATER_BLUE_HOVER = "#0369A1"
LIGHT_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
BORDER_COLOR = "#E2E8F0"
TEXT_DARK = "#1E293B"
TEXT_MUTED = "#64748B"
SUCCESS_GREEN = "#16A34A"
WARNING_AMBER = "#D97706"
DANGER_RED = "#DC2626"

STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {LIGHT_BG};
    font-family: "Segoe UI", "Nirmala UI", sans-serif;
    font-size: 13px;
    color: {TEXT_DARK};
}}

QWidget {{
    font-family: "Segoe UI", "Nirmala UI", sans-serif;
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

/* Cards */
.Card {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
    padding: 16px;
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
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: {TEXT_DARK};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {{
    border: 1.5px solid {WATER_BLUE};
}}

/* Table view */
QTableWidget, QTableView {{
    background-color: #FFFFFF;
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    gridline-color: #F1F5F9;
    selection-background-color: #E0F2FE;
    selection-color: {TEXT_DARK};
    font-size: 13px;
}}

QHeaderView::section {{
    background-color: #F8FAFC;
    color: {TEXT_MUTED};
    padding: 8px;
    font-weight: 600;
    font-size: 12px;
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

/* Modern Table Action Buttons */
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
