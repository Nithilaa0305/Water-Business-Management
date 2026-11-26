"""Secure, non-bypassable lock screen dialog for terminal security."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from app.database.connection import get_db_session
from app.database.models.auth import User
from app.services.auth_service import AuthService
from app.localization.translator import t
from app.config.settings import APP_NAME


class LockScreenDialog(QDialog):
    """
    Full modal lock screen that CANNOT be dismissed by Esc, Alt+F4, or window controls.
    Unlocks only with valid PIN/password or by switching user/signing out.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_unlocked = False
        self._switch_user_requested = False

        self.setWindowTitle(f"Terminal Locked — {APP_NAME}")
        # Frameless and Stay on top to prevent window close / bypass
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setStyleSheet("background-color: rgba(15, 23, 42, 0.95);")

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Centered Card Frame
        card = QFrame()
        card.setFixedWidth(440)
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #CBD5E1;
                padding: 24px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignCenter)

        # App Logo & Title
        lbl_app = QLabel(f"💧 {APP_NAME}")
        lbl_app.setStyleSheet("font-size: 14px; font-weight: bold; color: #64748B; border: none; background: transparent;")
        lbl_app.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(lbl_app)

        # Lock Header
        self.lbl_lock_title = QLabel(f"🔒 {t('screen_locked', 'Terminal Locked')}")
        self.lbl_lock_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0284C7; border: none; background: transparent;")
        self.lbl_lock_title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_lock_title)

        # Current User Badge
        curr = AuthService.get_current_user()
        u_name = "Owner"
        u_role = "ADMIN"
        if curr:
            try:
                curr_id = getattr(curr, "id", None)
                if curr_id:
                    with get_db_session() as session:
                        db_u = session.query(User).filter_by(id=curr_id).first()
                        if db_u:
                            u_name = db_u.full_name or db_u.username
                            u_role = db_u.role
            except Exception:
                u_name = "Owner"
                u_role = "ADMIN"
        self.lbl_user_badge = QLabel(f"👤 {u_name} ({u_role})")
        self.lbl_user_badge.setStyleSheet("""
            background-color: #F1F5F9;
            color: #0F172A;
            padding: 6px 14px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            border: 1px solid #E2E8F0;
        """)
        self.lbl_user_badge.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_user_badge)

        # Prompt
        self.lbl_prompt = QLabel(t("enter_pin_or_pass", "Enter 4-digit PIN or Password to unlock:"))
        self.lbl_prompt.setStyleSheet("color: #334155; font-size: 13px; border: none; background: transparent;")
        self.lbl_prompt.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_prompt)

        # Input Field
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password)
        self.txt_pass.setPlaceholderText("••••")
        self.txt_pass.setAlignment(Qt.AlignCenter)
        self.txt_pass.setStyleSheet("""
            QLineEdit {
                font-size: 18px;
                font-weight: bold;
                letter-spacing: 4px;
                padding: 10px;
                border: 2px solid #CBD5E1;
                border-radius: 8px;
                background-color: #F8FAFC;
                color: #0F172A;
            }
            QLineEdit:focus {
                border-color: #0284C7;
                background-color: #FFFFFF;
            }
        """)
        self.txt_pass.returnPressed.connect(self.try_unlock)
        card_layout.addWidget(self.txt_pass)

        # Error / Feedback Label
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #DC2626; font-size: 12px; font-weight: 500; border: none; background: transparent;")
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setVisible(False)
        card_layout.addWidget(self.lbl_error)

        # Buttons
        self.btn_unlock = QPushButton(t("btn_unlock", "🔓 Unlock Terminal"))
        self.btn_unlock.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
        """)
        self.btn_unlock.clicked.connect(self.try_unlock)
        card_layout.addWidget(self.btn_unlock)

        self.btn_switch = QPushButton(t("btn_switch_user", "🚪 Switch User / Sign Out"))
        self.btn_switch.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748B;
                font-size: 12px;
                padding: 6px;
                border: none;
            }
            QPushButton:hover {
                color: #DC2626;
                text-decoration: underline;
            }
        """)
        self.btn_switch.clicked.connect(self.action_switch_user)
        card_layout.addWidget(self.btn_switch)

        # Hint text
        self.lbl_hint = QLabel(t("lock_hint", "Owner PIN: 1234 or Password: admin123"))
        self.lbl_hint.setStyleSheet("color: #94A3B8; font-size: 11px; border: none; background: transparent;")
        self.lbl_hint.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_hint)

        main_layout.addWidget(card)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            self.setGeometry(self.parent().geometry())
        self.txt_pass.setFocus()

    def reject(self):
        """Prevent Escape key or standard reject from dismissing lock screen."""
        if self._is_unlocked or self._switch_user_requested:
            super().reject()

    def closeEvent(self, event):
        """Prevent window close events from bypassing lock screen."""
        if self._is_unlocked or self._switch_user_requested:
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        """Intercept Escape key to prevent closing."""
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def try_unlock(self):
        code = self.txt_pass.text().strip()
        if not code:
            self.lbl_error.setText("Please enter your PIN or password.")
            self.lbl_error.setVisible(True)
            return

        with get_db_session() as session:
            valid, msg = AuthService.unlock_screen(session, code)
            if valid:
                self._is_unlocked = True
                self.accept()
            else:
                self.lbl_error.setText(msg or t("invalid_credentials", "Invalid PIN or password. Try again."))
                self.lbl_error.setVisible(True)
                self.txt_pass.selectAll()
                self.txt_pass.setFocus()

    def action_switch_user(self):
        """Allow switching user by clearing auto-login session and re-logging in."""
        reply = QMessageBox.question(
            self,
            "Sign Out",
            "Are you sure you want to sign out and switch user?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            AuthService.logout()
            self._switch_user_requested = True
            self.accept()
