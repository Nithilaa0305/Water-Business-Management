"""Excel import and export integration tests."""

from pathlib import Path
from app.services.import_export_service import ExportService, ImportService
from app.database.models.customer import Customer


def test_export_and_templates(db_session, tmp_path):
    # Test template generation
    templates = ExportService.generate_import_templates(output_dir=tmp_path)
    assert "products" in templates
    assert "customers" in templates
    assert templates["products"].exists()
    assert templates["customers"].exists()

    # Test export
    export_file = ExportService.export_products_to_excel(db_session, file_path=tmp_path / "Products.xlsx")
    assert export_file.exists()
    assert export_file.stat().st_size > 0


def test_import_customers_validation(db_session, tmp_path):
    templates = ExportService.generate_import_templates(output_dir=tmp_path)
    result = ImportService.import_customers_from_excel(db_session, templates["customers"])
    assert result["imported"] == 1
    assert len(result["errors"]) == 0

    cust = db_session.query(Customer).filter_by(name="Kamal Perera").first()
    assert cust is not None
    assert cust.phone == "0771234567"
