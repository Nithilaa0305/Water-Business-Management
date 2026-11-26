"""Localization and Tamil Unicode rendering tests."""

from app.localization.translator import t, set_language, get_language
from app.services.customer_service import CustomerService
from app.database.models.customer import Customer


def test_bilingual_translations():
    set_language("en")
    assert t("nav_dashboard") == "Dashboard"
    assert t("nav_sales") == "New Bill / Sales"
    assert t("nav_daily_closing") == "Daily Closing"
    assert t("denom_5000") == "Rs. 5,000 Note"

    set_language("ta")
    assert t("nav_dashboard") == "முகப்பு பலகை"
    assert t("nav_sales") == "புதிய பில் / விற்பனை"
    assert t("nav_daily_closing") == "தினசரி கணக்கு முடிவு"
    assert t("denom_5000") == "ரூ. 5,000 தாள்"
    assert t("screen_locked") == "பயன்பாடு பூட்டப்பட்டுள்ளது"
    assert t("btn_repeat_order") == "🔁 முந்தைய ஆர்டரை மீண்டும் செய்க"
    assert t("alloc_current") == "தற்போதைய பில்"

    # Reset
    set_language("en")


def test_tamil_unicode_in_customer_and_search(db_session):
    # Test storing and searching complex Tamil Unicode text
    tamil_name = "கணபதி ஸ்டோர்ஸ்"  # Ganapathi Stores
    tamil_address = "பிரதான வீதி, கொழும்பு"  # Main Street, Colombo
    cust = CustomerService.create_customer(
        session=db_session,
        name=tamil_name,
        phone="0779876543",
        address=tamil_address
    )
    assert cust.id is not None
    assert cust.name == tamil_name
    assert cust.address == tamil_address

    # Search in Tamil
    search_results = CustomerService.search_customers(db_session, "கணபதி")
    assert len(search_results) == 1
    assert search_results[0].name == tamil_name
