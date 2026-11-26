"""First-time setup wizard dialog."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt
from app.database.connection import get_db_session
from app.database.models.auth import BusinessProfile, User
from app.database.migrations.migration_manager import hash_password
from app.services.audit_service import AuditService
from app.localization.translator import set_language
from app.utilities.validators import validate_name, validate_phone_number


class SetupWizardDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Water Business Manager - First Time Setup")
        self.setFixedSize(540, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)  # Must complete or cancel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel("Welcome to Water Business Manager")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #0284C7;")
        layout.addWidget(header)

        sub = QLabel("Please set up your business details and owner credentials.")
        sub.setStyleSheet("color: #64748B; font-size: 13px;")
        layout.addWidget(sub)

        # Form
        form = QFormLayout()
        form.setSpacing(12)

        self.txt_business_name = QLineEdit("Pure Life Bottled Water")
        self.txt_address = QLineEdit("123 Galle Road, Colombo 03")
        self.txt_phone = QLineEdit("+94 11 234 5678")
        self.txt_email = QLineEdit("info@watermanager.lk")
        self.txt_prefix = QLineEdit("INV-")

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItem("English", "en")
        self.cmb_lang.addItem("தமிழ் (Tamil)", "ta")

        self.txt_owner_name = QLineEdit("Business Owner")
        self.txt_pin = QLineEdit("1234")
        self.txt_pin.setEchoMode(QLineEdit.Password)
        self.txt_pin.setMaxLength(6)

        form.addRow("Business Name*:", self.txt_business_name)
        form.addRow("Business Address:", self.txt_address)
        form.addRow("Contact Phone*:", self.txt_phone)
        form.addRow("Email Address:", self.txt_email)
        form.addRow("Invoice Prefix:", self.txt_prefix)
        form.addRow("Language:", self.cmb_lang)
        form.addRow("Owner Name*:", self.txt_owner_name)
        form.addRow("Owner 4-Digit PIN*:", self.txt_pin)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_finish = QPushButton("Complete Setup & Start")
        self.btn_finish.setStyleSheet("background-color: #0284C7; color: white; padding: 8px 20px; font-weight: bold;")
        self.btn_finish.clicked.connect(self.save_setup)
        btn_layout.addWidget(self.btn_finish)

        layout.addLayout(btn_layout)

    def save_setup(self):
        biz_name = self.txt_business_name.text().strip()
        raw_phone = self.txt_phone.text().strip()
        pin = self.txt_pin.text().strip()
        owner_name = self.txt_owner_name.text().strip()

        if not biz_name or not raw_phone or not pin or not owner_name:
            QMessageBox.warning(self, "Validation Error", "Please fill in all required fields (*).")
            return

        valid_phone, clean_phone, err_phone = validate_phone_number(raw_phone, required=True)
        if not valid_phone:
            QMessageBox.warning(self, "Validation Error", err_phone)
            self.txt_phone.setFocus()
            return

        lang_code = self.cmb_lang.currentData()
        set_language(lang_code)

        with get_db_session() as session:
            profile = session.query(BusinessProfile).first()
            if not profile:
                profile = BusinessProfile()
                session.add(profile)

            profile.business_name = biz_name
            profile.address = self.txt_address.text().strip()
            profile.phone = clean_phone
            profile.email = self.txt_email.text().strip()
            profile.invoice_prefix = self.txt_prefix.text().strip() or "INV-"
            profile.language = lang_code
            profile.is_setup_completed = True

            # Update owner
            owner = session.query(User).filter_by(username="admin").first()
            if owner:
                owner.full_name = owner_name
                owner.pin_hash = hash_password(pin)

            AuditService.log_action(
                session=session,
                action_type="SETUP_COMPLETE",
                entity_name="BusinessProfile",
                entity_id=profile.id,
                new_values={"business_name": biz_name, "owner": owner_name},
                reason="Initial setup wizard completed"
            )

        self.accept()
