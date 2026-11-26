"""Tests for LockScreenDialog and DailyClosingPage responsive scrolling and localization."""

import pytest
from PySide6.QtWidgets import QApplication, QScrollArea
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from app.ui.main_window import MainWindow
from app.ui.dialogs.lock_screen_dialog import LockScreenDialog
from app.ui.daily_closing_page import DailyClosingPage
from app.services.auth_service import AuthService
from app.database.connection import get_db_session
from app.localization.translator import set_language, t


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_lock_screen_dialog_non_dismissable(qapp, db_session):
    # Ensure owner exists
    owner = db_session.query(AuthService.get_current_user().__class__).filter_by(role="OWNER").first() if AuthService.get_current_user() else None
    if owner:
        AuthService.set_current_user(owner)

    dlg = LockScreenDialog()
    assert dlg.isModal() is True

    # Esc key should NOT dismiss dialog
    dlg.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    assert dlg.result() != 1

    # Standard reject should NOT close dialog unless unlocked
    dlg.reject()
    assert dlg.result() != 1

    # Unlock with valid PIN
    dlg.txt_pass.setText("1234")
    dlg.try_unlock()
    assert dlg._is_unlocked is True
    dlg.close()


def test_daily_closing_scroll_area_and_localization(qapp, db_session):
    win = MainWindow()
    closing_page = win.page_daily_closing

    # Verify QScrollArea exists and wraps the page contents
    scrolls = closing_page.findChildren(QScrollArea)
    assert len(scrolls) >= 1
    assert scrolls[0].widgetResizable() is True

    # Test Tamil localization
    set_language("ta")
    closing_page.retranslate_ui()
    assert closing_page.lbl_title.text() == "தினசரி பணப்பெட்டி கணக்கு சரிபார்த்தல்"
    assert "ரூ. 5,000 தாள்" in closing_page.denom_name_labels["5000"].text()
    assert closing_page.btn_finalize.text() == "💾 தினசரி கணக்கை முடித்து சேமி"

    # Reset
    set_language("en")
    closing_page.retranslate_ui()
    assert closing_page.lbl_title.text() == "Daily Cash Closing & Drawer Reconciliation"
    assert "Rs. 5,000 Note" in closing_page.denom_name_labels["5000"].text()
    win.close()
