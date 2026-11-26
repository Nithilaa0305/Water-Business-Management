"""Unit tests for Packaging Unit calculations, Product Price History, and equivalent pricing."""

import pytest
from app.services.pricing_service import PricingService
from app.database.models.product import Product, PackagingUnit, ProductPriceHistory


def test_packaging_unit_calculations():
    # Case of 24 bottles at Rs. 1,440.00
    res24 = PricingService.calculate_packaging_pricing(
        unit_price_cents=144000,
        unit_factor=24,
        quantity=5
    )
    assert res24["equivalent_bottle_price_cents"] == 6000  # Rs. 60.00
    assert res24["total_bottles"] == 120
    assert res24["line_total_cents"] == 720000  # Rs. 7,200.00

    # Case of 12 bottles at Rs. 960.00
    res12 = PricingService.calculate_packaging_pricing(
        unit_price_cents=96000,
        unit_factor=12,
        quantity=2
    )
    assert res12["equivalent_bottle_price_cents"] == 8000  # Rs. 80.00
    assert res12["total_bottles"] == 24
    assert res12["line_total_cents"] == 192000


def test_product_price_history_recording(db_session):
    p = db_session.query(Product).filter_by(code="W0500").first()
    pkg_case24 = db_session.query(PackagingUnit).filter_by(name="Case of 24").first()
    assert pkg_case24 is not None

    # Record selling price change for Case of 24
    h = PricingService.record_price_change(
        session=db_session,
        product_id=p.id,
        price_type="SELLING",
        old_price_cents=132000,
        new_price_cents=144000,
        packaging_unit_id=pkg_case24.id,
        reason="Manufacturer price hike"
    )

    assert h.unit_factor == 24
    assert h.old_price_cents == 132000
    assert h.new_price_cents == 144000
    assert h.equivalent_bottle_price_cents == 6000
    assert h.reason == "Manufacturer price hike"

    # Query report
    report = PricingService.get_price_history_report(db_session, product_id=p.id)
    assert len(report) >= 1
    latest = report[0]
    assert latest["product_code"] == "W0500"
    assert latest["packaging_unit"] == "Case of 24"
    assert latest["equivalent_bottle_price_cents"] == 6000
