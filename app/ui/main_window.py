"""Main Application Window with Sidebar Navigation, Stacked Pages, and Setup Wizard check."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QFrame, QButtonGroup, QScrollArea
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont
from app.config.settings import APP_NAME, APP_VERSION
from app.database.connection import get_db_session
from app.database.models.auth import BusinessProfile
from app.ui.theme import STYLESHEET
from app.ui.setup_wizard import SetupWizardDialog
from app.ui.dashboard_page import DashboardPage
from app.ui.sales_page import SalesPage
from app.ui.stock_page import StockPage
from app.ui.purchases_page import PurchasesPage
from app.ui.bottles_page import BottlesPage
from app.ui.customers_page import CustomersPage
from app.ui.credit_page import CreditPage
from app.ui.daily_closing_page import DailyClosingPage
from app.ui.suppliers_page import SuppliersPage
from app.ui.expenses_page import ExpensesPage
from app.ui.reports_page import ReportsPage
from app.ui.history_page import HistoryPage
from app.ui.settings_page import SettingsPage
from app.services.auth_service import AuthService
from app.database.models.auth import User
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox
from app.localization.translator import t, set_language, get_language


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1280, 720)
        self.showMaximized()
        self.setStyleSheet(STYLESHEET)

        # Main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_h_layout = QHBoxLayout(central_widget)
        main_h_layout.setContentsMargins(0, 0, 0, 0)
        main_h_layout.setSpacing(0)

        # 1. Left Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 16)
        sidebar_layout.setSpacing(4)

        # Header in sidebar
        sb_header = QFrame()
        sb_header.setObjectName("SidebarHeader")
        sb_header_layout = QVBoxLayout(sb_header)
        sb_header_layout.setContentsMargins(16, 20, 16, 20)

        self.app_title = QLabel(f"💧 {APP_NAME}")
        self.app_title.setObjectName("AppTitle")
        self.app_title.setWordWrap(True)
        self.app_sub = QLabel("Bottled Water & Billing System")
        self.app_sub.setObjectName("AppSubtitle")
        self.app_sub.setWordWrap(True)
        sb_header_layout.addWidget(self.app_title)
        sb_header_layout.addWidget(self.app_sub)
        sidebar_layout.addWidget(sb_header)

        # Navigation Buttons Group
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.nav_buttons = {}
        self.pages_def = [
            ("dashboard", "Dashboard", "nav_dashboard"),
            ("sales", "New Bill / Sales", "nav_sales"),
            ("daily_closing", "Daily Closing", "nav_daily_closing"),
            ("stock", "Stock Management", "nav_stock"),
            ("purchases", "Purchases", "nav_purchases"),
            ("bottles", "19 L Bottles", "nav_bottles"),
            ("customers", "Customers", "nav_customers"),
            ("credit", "Credit & Payments", "nav_credit"),
            ("suppliers", "Suppliers", "nav_suppliers"),
            ("expenses", "Expenses", "nav_expenses"),
            ("reports", "Reports", "nav_reports"),
            ("history", "Activity History", "nav_history"),
            ("settings", "Settings & Backup", "nav_settings"),
        ]

        # Scrollable sidebar for smaller laptop displays
        sb_scroll = QScrollArea()
        sb_scroll.setWidgetResizable(True)
        sb_scroll.setFrameShape(QFrame.NoFrame)
        sb_scroll.setStyleSheet("background: transparent; border: none;")
        sb_btn_container = QWidget()
        sb_btn_layout = QVBoxLayout(sb_btn_container)
        sb_btn_layout.setContentsMargins(8, 8, 8, 8)
        sb_btn_layout.setSpacing(3)

        for page_id, default_label, trans_key in self.pages_def:
            btn = QPushButton(t(trans_key, default_label))
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, pid=page_id: self.navigate_to(pid))
            self.nav_group.addButton(btn)
            self.nav_buttons[page_id] = btn
            sb_btn_layout.addWidget(btn)

        sb_btn_layout.addStretch()
        sb_scroll.setWidget(sb_btn_container)
        sidebar_layout.addWidget(sb_scroll)

        main_h_layout.addWidget(sidebar)

        # 2. Main Content Area (Header + Stacked Pages)
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top App Header
        top_header = QFrame()
        top_header.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #E2E8F0; padding: 8px 20px;")
        th_layout = QHBoxLayout(top_header)
        th_layout.setContentsMargins(16, 8, 16, 8)

        self.lbl_business_brand = QLabel("Pure Life Bottled Water Wholesale")
        self.lbl_business_brand.setStyleSheet("font-size: 15px; font-weight: bold; color: #0284C7;")
        th_layout.addWidget(self.lbl_business_brand)
        th_layout.addStretch()

        # Quick Language Toggle
        self.btn_lang = QPushButton("Language: English")
        self.btn_lang.setObjectName("SecondaryButton")
        self.btn_lang.clicked.connect(self.toggle_language)
        th_layout.addWidget(self.btn_lang)

        # User Badge
        self.lbl_user = QLabel("👤 Owner (Admin)")
        self.lbl_user.setStyleSheet("background-color: #F1F5F9; color: #0F172A; padding: 4px 12px; border-radius: 12px; font-weight: 500;")
        th_layout.addWidget(self.lbl_user)

        # Screen Lock Button
        self.btn_lock = QPushButton("🔒 Lock Screen")
        self.btn_lock.setObjectName("SecondaryButton")
        self.btn_lock.setToolTip("Lock screen with PIN/Password (Ctrl+L)")
        self.btn_lock.clicked.connect(self.action_lock_screen)
        th_layout.addWidget(self.btn_lock)

        content_layout.addWidget(top_header)

        # Stacked Pages
        self.pages_stack = QStackedWidget()
        self.pages_map = {}

        # Instantiate all pages
        self.page_dashboard = DashboardPage(self)
        self.page_sales = SalesPage(self)
        self.page_daily_closing = DailyClosingPage(self)
        self.page_stock = StockPage(self)
        self.page_purchases = PurchasesPage(self)
        self.page_bottles = BottlesPage(self)
        self.page_customers = CustomersPage(self)
        self.page_credit = CreditPage(self)
        self.page_suppliers = SuppliersPage(self)
        self.page_expenses = ExpensesPage(self)
        self.page_reports = ReportsPage(self)
        self.page_history = HistoryPage(self)
        self.page_settings = SettingsPage(self)

        self.register_page("dashboard", self.page_dashboard)
        self.register_page("sales", self.page_sales)
        self.register_page("daily_closing", self.page_daily_closing)
        self.register_page("stock", self.page_stock)
        self.register_page("purchases", self.page_purchases)
        self.register_page("bottles", self.page_bottles)
        self.register_page("customers", self.page_customers)
        self.register_page("credit", self.page_credit)
        self.register_page("suppliers", self.page_suppliers)
        self.register_page("expenses", self.page_expenses)
        self.register_page("reports", self.page_reports)
        self.register_page("history", self.page_history)
        self.register_page("settings", self.page_settings)

        content_layout.addWidget(self.pages_stack)
        main_h_layout.addWidget(content_area)

        # Keyboard shortcuts
        QShortcut(QKeySequence("F1"), self, lambda: self.navigate_to("sales"))
        QShortcut(QKeySequence("F2"), self, lambda: self.navigate_to("stock"))
        QShortcut(QKeySequence("F3"), self, lambda: self.navigate_to("daily_closing"))
        QShortcut(QKeySequence("Ctrl+L"), self, self.action_lock_screen)

        # Auto-login setup
        self.init_user_session()

        # Default to Dashboard
        self.navigate_to("dashboard")
        self.load_profile_branding()

    def register_page(self, page_id: str, widget: QWidget):
        idx = self.pages_stack.addWidget(widget)
        self.pages_map[page_id] = (idx, widget)

    def navigate_to(self, page_id: str):
        if page_id in self.pages_map:
            idx, widget = self.pages_map[page_id]
            self.pages_stack.setCurrentIndex(idx)
            if page_id in self.nav_buttons:
                self.nav_buttons[page_id].setChecked(True)

            # Auto-refresh page data when navigated to
            if hasattr(widget, "refresh_dashboard"):
                widget.refresh_dashboard()
            elif hasattr(widget, "load_stock_data"):
                widget.load_stock_data()
            elif hasattr(widget, "load_bottle_data"):
                widget.load_bottle_data()
            elif hasattr(widget, "load_customers"):
                widget.load_customers()
            elif hasattr(widget, "load_credit_data"):
                widget.load_credit_data()
            elif hasattr(widget, "load_expenses"):
                widget.load_expenses()
            elif hasattr(widget, "load_audit_logs"):
                widget.load_audit_logs()
            elif hasattr(widget, "load_all_reports"):
                widget.load_all_reports()

    def load_profile_branding(self):
        with get_db_session() as session:
            p = session.query(BusinessProfile).first()
            if p:
                self.lbl_business_brand.setText(p.business_name or APP_NAME)
                set_language(p.language or "en")
        self.retranslate_ui()

    def toggle_language(self):
        curr = get_language()
        new_lang = "ta" if curr == "en" else "en"
        set_language(new_lang)
        with get_db_session() as session:
            p = session.query(BusinessProfile).first()
            if p:
                p.language = new_lang
        self.retranslate_ui()

    def retranslate_ui(self):
        """Dynamic cascade retranslation of sidebar buttons, header, and active pages."""
        # Sidebar branding
        self.app_title.setText(f"💧 {t('app_title', APP_NAME)}")
        self.app_sub.setText(t("app_subtitle", "Bottled Water & Billing System"))

        # Nav buttons
        for page_id, default_label, trans_key in self.pages_def:
            if page_id in self.nav_buttons:
                self.nav_buttons[page_id].setText(t(trans_key, default_label))

        # Top bar toggle
        self.btn_lang.setText("Language: English" if get_language() == "en" else "Language: தமிழ் (Tamil)")

        # Cascade to all registered pages
        for page_id, (idx, widget) in self.pages_map.items():
            if hasattr(widget, "retranslate_ui"):
                try:
                    widget.retranslate_ui()
                except Exception as e:
                    print(f"Warning: retranslating {page_id} failed: {e}")

    def refresh_all_pages(self):
        self.load_profile_branding()
        self.page_dashboard.refresh_dashboard()
        self.page_stock.load_stock_data()
        self.page_bottles.load_bottle_data()
        self.page_customers.load_customers()
        self.page_credit.load_credit_data()
        self.page_settings.load_settings()

    def check_first_time_setup(self):
        with get_db_session() as session:
            p = session.query(BusinessProfile).first()
            if not p or not p.is_setup_completed:
                wizard = SetupWizardDialog(self)
                wizard.exec()
                self.load_profile_branding()
                self.refresh_all_pages()

    def init_user_session(self):
        """User-friendly auto-login session on this PC without annoying prompts."""
        with get_db_session() as session:
            ok, user, _ = AuthService.try_auto_login(session)
            if not ok or not user:
                owner = session.query(User).filter_by(role="OWNER", is_active=True).first()
                if not owner:
                    owner = session.query(User).filter_by(is_active=True).first()
                if owner:
                    AuthService.set_current_user(owner)
                    token = owner.remember_token or "owner_token_2026"
                    owner.remember_token = token
                    AuthService._save_remember_session(owner.id, token, owner.username)
                    session.commit()
                    user = owner

            if user:
                self.lbl_user.setText(f"👤 {user.full_name} ({user.role})")

    def action_lock_screen(self):
        """Quick lock screen for security; quick unlock via 4-digit PIN or password."""
        AuthService.lock_screen()
        dlg = QDialog(self)
        dlg.setWindowTitle("Screen Locked — Water Business Manager")
        dlg.setFixedSize(380, 240)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        lbl = QLabel("🔒 Application Locked")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #0284C7;")
        layout.addWidget(lbl)

        curr = AuthService.get_current_user()
        u_name = curr.full_name if curr else "Owner"
        layout.addWidget(QLabel(f"Enter PIN or Password for <b>{u_name}</b> to unlock:"))

        txt_pass = QLineEdit()
        txt_pass.setEchoMode(QLineEdit.Password)
        txt_pass.setPlaceholderText("Enter 4-digit PIN or password...")
        layout.addWidget(txt_pass)

        btn_row = QHBoxLayout()
        btn_unlock = QPushButton("🔓 Unlock")
        btn_unlock.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 8px 16px;")

        def try_unlock():
            code = txt_pass.text().strip()
            if not code:
                return
            with get_db_session() as session:
                valid, msg = AuthService.unlock_screen(session, code)
                if valid:
                    dlg.accept()
                else:
                    QMessageBox.warning(dlg, "Access Denied", msg)
                    txt_pass.clear()

        btn_unlock.clicked.connect(try_unlock)
        txt_pass.returnPressed.connect(try_unlock)
        btn_row.addWidget(btn_unlock)
        layout.addLayout(btn_row)
        dlg.exec()

