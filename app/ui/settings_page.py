"""Application Settings, Dynamic Localization, and Backup & Restore Page."""

import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QFrame, QMessageBox, QComboBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from app.database.connection import get_db_session
from app.database.models.auth import BusinessProfile
from app.services.backup_service import BackupService
from app.utilities.validators import validate_phone_number
from app.localization.translator import set_language, get_language, t


class SettingsPage(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        self.lbl_title = QLabel(t("settings_title", "System Settings & Data Safety"))
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0F172A;")
        self.lbl_sub = QLabel(t("settings_subtitle", "Configure business details, invoice prefix, language, and transactional backups"))
        self.lbl_sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_title)
        header_text.addWidget(self.lbl_sub)
        top_bar.addLayout(header_text)
        top_bar.addStretch()

        self.btn_save = QPushButton(t("btn_save_settings", "Save Settings"))
        self.btn_save.clicked.connect(self.save_settings)
        top_bar.addWidget(self.btn_save)
        main_layout.addLayout(top_bar)

        # Business Profile Form
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; color: #0F172A;")
        self.form = QFormLayout(form_frame)
        self.form.setSpacing(12)

        self.txt_biz_name = QLineEdit()
        self.txt_address = QLineEdit()
        self.txt_phone = QLineEdit()
        self.txt_email = QLineEdit()
        self.txt_prefix = QLineEdit()

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItem("English", "en")
        self.cmb_lang.addItem("தமிழ் (Tamil)", "ta")

        self.lbl_biz_name = QLabel(t("biz_name", "Business Name:"))
        self.lbl_biz_name.setStyleSheet("color: #0F172A; font-weight: 600;")
        self.lbl_address = QLabel(t("address", "Address:"))
        self.lbl_address.setStyleSheet("color: #0F172A; font-weight: 600;")
        self.lbl_phone = QLabel(t("phone", "Contact Phone:"))
        self.lbl_phone.setStyleSheet("color: #0F172A; font-weight: 600;")
        self.lbl_email = QLabel(t("email", "Email:"))
        self.lbl_email.setStyleSheet("color: #0F172A; font-weight: 600;")
        self.lbl_prefix = QLabel(t("invoice_prefix", "Invoice Prefix:"))
        self.lbl_prefix.setStyleSheet("color: #0F172A; font-weight: 600;")
        self.lbl_lang = QLabel(t("app_language", "Application Language:"))
        self.lbl_lang.setStyleSheet("color: #0F172A; font-weight: 600;")

        self.form.addRow(self.lbl_biz_name, self.txt_biz_name)
        self.form.addRow(self.lbl_address, self.txt_address)
        self.form.addRow(self.lbl_phone, self.txt_phone)
        self.form.addRow(self.lbl_email, self.txt_email)
        self.form.addRow(self.lbl_prefix, self.txt_prefix)
        self.form.addRow(self.lbl_lang, self.cmb_lang)
        main_layout.addWidget(form_frame)

        # Backup & Safety Section
        backup_frame = QFrame()
        backup_frame.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; color: #0F172A;")
        b_layout = QVBoxLayout(backup_frame)
        b_layout.setSpacing(12)

        b_top = QHBoxLayout()
        self.lbl_backup_title = QLabel(t("backup_safety", "Transactional Database Backups & Data Safety:"))
        self.lbl_backup_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #0F172A;")
        b_top.addWidget(self.lbl_backup_title)
        b_top.addStretch()

        self.btn_backup_now = QPushButton(t("btn_create_backup", "Create Backup Now"))
        self.btn_backup_now.setStyleSheet("background-color: #16A34A; color: white;")
        self.btn_backup_now.clicked.connect(self.action_create_backup)
        b_top.addWidget(self.btn_backup_now)

        self.btn_restore = QPushButton(t("btn_restore_backup", "Restore from File..."))
        self.btn_restore.setObjectName("SecondaryButton")
        self.btn_restore.clicked.connect(self.action_restore_backup)
        b_top.addWidget(self.btn_restore)
        b_layout.addLayout(b_top)

        # Configured Backup Folder Path & Explorer button
        folder_row = QHBoxLayout()
        self.lbl_folder = QLabel(t("backup_folder", "Backup Storage Folder:"))
        self.lbl_folder.setStyleSheet("font-weight: 500; color: #334155;")
        folder_row.addWidget(self.lbl_folder)

        self.txt_backup_dir = QLineEdit()
        self.txt_backup_dir.setReadOnly(True)
        self.txt_backup_dir.setStyleSheet("background-color: #F8FAFC; color: #0F172A; font-family: Consolas, monospace;")
        folder_row.addWidget(self.txt_backup_dir, 1)

        self.btn_browse_dir = QPushButton(t("btn_browse", "Browse Folder..."))
        self.btn_browse_dir.setObjectName("SecondaryButton")
        self.btn_browse_dir.clicked.connect(self.action_browse_backup_dir)
        folder_row.addWidget(self.btn_browse_dir)

        self.btn_open_folder = QPushButton(t("btn_open_folder", "Open Folder in Explorer"))
        self.btn_open_folder.setObjectName("SecondaryButton")
        self.btn_open_folder.clicked.connect(self.action_open_folder_explorer)
        folder_row.addWidget(self.btn_open_folder)

        b_layout.addLayout(folder_row)

        # Backup History Table
        self.table_backups = QTableWidget()
        self.table_backups.setColumnCount(3)
        self.table_backups.setHorizontalHeaderLabels([
            t("col_filename", "Filename"),
            t("col_size", "Size"),
            t("col_datetime", "Date & Time")
        ])
        self.table_backups.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_backups.setMinimumHeight(180)
        b_layout.addWidget(self.table_backups)

        main_layout.addWidget(backup_frame)

        self.load_settings()
        self.load_backups()

    def retranslate_ui(self):
        """Dynamic text update when language changes."""
        self.lbl_title.setText(t("settings_title", "System Settings & Data Safety"))
        self.lbl_sub.setText(t("settings_subtitle", "Configure business details, invoice prefix, language, and transactional backups"))
        self.btn_save.setText(t("btn_save_settings", "Save Settings"))
        self.lbl_biz_name.setText(t("biz_name", "Business Name:"))
        self.lbl_address.setText(t("address", "Address:"))
        self.lbl_phone.setText(t("phone", "Contact Phone:"))
        self.lbl_email.setText(t("email", "Email:"))
        self.lbl_prefix.setText(t("invoice_prefix", "Invoice Prefix:"))
        self.lbl_lang.setText(t("app_language", "Application Language:"))
        self.lbl_backup_title.setText(t("backup_safety", "Transactional Database Backups & Data Safety:"))
        self.btn_backup_now.setText(t("btn_create_backup", "Create Backup Now"))
        self.btn_restore.setText(t("btn_restore_backup", "Restore from File..."))
        self.lbl_folder.setText(t("backup_folder", "Backup Storage Folder:"))
        self.btn_browse_dir.setText(t("btn_browse", "Browse Folder..."))
        self.btn_open_folder.setText(t("btn_open_folder", "Open Folder in Explorer"))
        self.table_backups.setHorizontalHeaderLabels([
            t("col_filename", "Filename"),
            t("col_size", "Size"),
            t("col_datetime", "Date & Time")
        ])

    def load_settings(self):
        with get_db_session() as session:
            p = session.query(BusinessProfile).first()
            if p:
                self.txt_biz_name.setText(p.business_name or "")
                self.txt_address.setText(p.address or "")
                self.txt_phone.setText(p.phone or "")
                self.txt_email.setText(p.email or "")
                self.txt_prefix.setText(p.invoice_prefix or "INV-")

                # Language
                idx = self.cmb_lang.findData(p.language)
                if idx >= 0:
                    self.cmb_lang.setCurrentIndex(idx)

                # Backup directory
                configured_dir = BackupService.get_configured_backup_dir()
                self.txt_backup_dir.setText(str(configured_dir.resolve()))

    def save_settings(self):
        raw_phone = self.txt_phone.text().strip()
        valid_phone, clean_phone, err_phone = validate_phone_number(raw_phone, required=True)
        if not valid_phone:
            QMessageBox.warning(self, "Validation Error", err_phone)
            self.txt_phone.setFocus()
            return

        with get_db_session() as session:
            p = session.query(BusinessProfile).first()
            if not p:
                p = BusinessProfile()
                session.add(p)
            p.business_name = self.txt_biz_name.text().strip() or "Pure Life Water"
            p.address = self.txt_address.text().strip()
            p.phone = clean_phone
            p.email = self.txt_email.text().strip()
            p.invoice_prefix = self.txt_prefix.text().strip() or "INV-"
            
            selected_folder = self.txt_backup_dir.text().strip()
            if selected_folder:
                p.backup_folder = selected_folder

            lang = self.cmb_lang.currentData()
            p.language = lang
            set_language(lang)

        # Dynamically trigger UI retranslation across all pages and sidebar
        if hasattr(self.main_window, "retranslate_ui"):
            self.main_window.retranslate_ui()
        if hasattr(self.main_window, "load_profile_branding"):
            self.main_window.load_profile_branding()

        msg = "System settings have been updated successfully." if get_language() == "en" else "அமைப்புகள் வெற்றிகரமாக சேமிக்கப்பட்டன."
        QMessageBox.information(self, t("btn_save_settings", "Save Settings"), msg)

    def action_browse_backup_dir(self):
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select Backup Storage Directory",
            self.txt_backup_dir.text().strip() or str(Path.home())
        )
        if chosen:
            self.txt_backup_dir.setText(chosen)
            # Auto-save folder to profile
            with get_db_session() as session:
                p = session.query(BusinessProfile).first()
                if p:
                    p.backup_folder = chosen
            self.load_backups()

    def action_open_folder_explorer(self):
        folder_path = self.txt_backup_dir.text().strip()
        if not folder_path:
            folder_path = str(BackupService.get_configured_backup_dir().resolve())
        p = Path(folder_path)
        p.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(p))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def load_backups(self):
        backups = BackupService.list_backups()
        self.table_backups.setRowCount(len(backups))
        for row, b in enumerate(backups):
            self.table_backups.setItem(row, 0, QTableWidgetItem(b["filename"]))
            self.table_backups.setItem(row, 1, QTableWidgetItem(b["size_mb"]))
            self.table_backups.setItem(row, 2, QTableWidgetItem(str(b["modified_at"].strftime("%Y-%m-%d %I:%M %p"))))

    def action_create_backup(self):
        try:
            dest = BackupService.create_backup()
            size_mb = f"{dest.stat().st_size / (1024 * 1024):.2f}"
            msg = t("backup_success", "").format(
                path=str(dest.resolve()),
                size=size_mb
            ) if t("backup_success", "") else f"Backup created successfully:\n{dest.resolve()}\nSize: {size_mb} MB"

            QMessageBox.information(self, "Backup Complete", msg)
            self.load_backups()
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Failed to create backup: {str(e)}")

    def action_restore_backup(self):
        curr_dir = self.txt_backup_dir.text().strip() or str(BackupService.get_configured_backup_dir())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Backup File to Restore",
            curr_dir,
            "Database Files (*.db *.bak)"
        )
        if not file_path:
            return

        confirm_msg = t("restore_confirm", "") or (
            "Restoring a backup will replace your current business data with the backup.\n"
            "A safety backup of the current database will be created automatically before restoring.\n\n"
            "Are you sure you want to proceed?"
        )
        reply = QMessageBox.warning(
            self,
            "Confirm Restore",
            confirm_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                BackupService.restore_backup(Path(file_path))
                QMessageBox.information(
                    self,
                    "Restore Successful",
                    "Database restored successfully. Application data will now reload."
                )
                self.main_window.refresh_all_pages()
            except Exception as e:
                QMessageBox.critical(self, "Restore Error", f"Failed to restore backup: {str(e)}")
