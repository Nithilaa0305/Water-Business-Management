"""UI Smoke and Workflow Automated Tests using PySide6 offscreen mode."""

import pytest
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.ui.dialogs.payment_dialog import PaymentDialog
from app.ui.dialogs.stock_adjustment_dialog import StockAdjustmentDialog
from app.ui.dialogs.refill_dialog import RefillDialog
from app.ui.dialogs.bottle_return_dialog import BottleReturnDialog
from app.ui.dialogs.customer_dialog import CustomerDialog
from app.ui.dialogs.expense_dialog import ExpenseDialog
from app.database.connection import get_engine
from app.database.migrations.migration_manager import init_database


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_pages_and_navigation(qapp, db_session):
    win = MainWindow()
    assert win.pages_stack.count() == 13

    for pid in win.pages_map:
        win.navigate_to(pid)
        assert win.pages_stack.currentWidget() == win.pages_map[pid][1]

    win.toggle_language()
    assert win.btn_lang.text() == "Language: தமிழ் (Tamil)"
    assert win.nav_buttons["dashboard"].text() == "முகப்பு பலகை"
    assert win.page_dashboard.lbl_title.text() == "முகப்பு பலகை"
    assert win.page_daily_closing.lbl_title.text() == "தினசரி பணப்பெட்டி கணக்கு சரிபார்த்தல்"

    win.toggle_language()
    assert win.btn_lang.text() == "Language: English"
    assert win.nav_buttons["dashboard"].text() == "Dashboard"
    assert win.page_dashboard.lbl_title.text() == "Dashboard"
    assert win.page_daily_closing.lbl_title.text() == "Daily Cash Closing & Drawer Reconciliation"
    win.close()


def test_dialogs_instantiation(qapp, db_session):
    from app.ui.dialogs.lock_screen_dialog import LockScreenDialog
    d_lock = LockScreenDialog()
    assert d_lock.lbl_lock_title is not None
    d_lock.close()

    d1 = PaymentDialog()
    assert d1.cmb_customer.count() >= 0
    d1.close()

    d2 = StockAdjustmentDialog()
    assert d2.cmb_type.count() == 5
    d2.close()

    d3 = RefillDialog()
    assert d3.spin_selected.value() >= 1
    d3.close()

    d4 = BottleReturnDialog()
    assert d4.spin_qty.value() == 1
    d4.close()

    d5 = CustomerDialog()
    assert d5.txt_name is not None
    d5.close()

    d6 = ExpenseDialog()
    assert d6.cmb_category.count() >= 0
    d6.close()

    from app.ui.dialogs.customer_price_dialog import CustomerPriceDialog
    from app.services.customer_service import CustomerService
    cust = CustomerService.create_customer(db_session, name="UI Test Customer", phone="0771239999")
    d_price = CustomerPriceDialog(customer_id=cust.id)
    assert d_price.table_prices.rowCount() >= 5
    d_price.close()
