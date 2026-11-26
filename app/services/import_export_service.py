"""Excel import and export service using openpyxl."""

from pathlib import Path
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy.orm import Session
from app.config.settings import EXPORTS_DIR
from app.database.models.product import Product
from app.database.models.customer import Customer
from app.database.models.sales import SalesInvoice
from app.database.models.inventory import InventoryBatch
from app.services.inventory_service import InventoryService
from app.services.customer_service import CustomerService
from app.utilities.currency import from_cents, to_cents
from app.utilities.dates import now_colombo, format_date


class ExportService:
    @staticmethod
    def export_products_to_excel(session: Session, file_path: Optional[Path] = None) -> Path:
        """Export all products with current stock to an Excel spreadsheet."""
        target = file_path or (EXPORTS_DIR / f"Products_Export_{now_colombo().strftime('%Y%m%d_%H%M%S')}.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Products"

        headers = ["Code", "Name", "Category", "Size", "UOM", "Selling Price (Rs.)", "Min Stock", "Available Stock", "Returnable"]
        ws.append(headers)

        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        products = session.query(Product).order_by(Product.code.asc()).all()
        for p in products:
            stock = InventoryService.get_available_stock(session, p.id)
            ws.append([
                p.code,
                p.name,
                p.category.name if p.category else "",
                p.bottle_size,
                p.uom,
                float(from_cents(p.default_selling_price_cents)),
                p.min_stock_level,
                stock,
                "Yes" if p.is_returnable else "No"
            ])

        # Auto-fit column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max(max_len + 4, 12)

        wb.save(target)
        return target

    @staticmethod
    def generate_import_templates(output_dir: Optional[Path] = None) -> Dict[str, Path]:
        """Generate standardized blank Excel import templates for master data."""
        d = output_dir or (EXPORTS_DIR / "templates")
        d.mkdir(parents=True, exist_ok=True)

        templates = {}

        # 1. Products Template
        wb_p = openpyxl.Workbook()
        ws_p = wb_p.active
        ws_p.title = "Products_Template"
        ws_p.append(["Product Code*", "Product Name*", "Category", "Bottle Size*", "UOM*", "Default Price (Rs.)*", "Min Stock", "Is Returnable (Yes/No)"])
        ws_p.append(["W0500", "500 ml Water Bottle", "Bottled Water", "500 ml", "Bottle", 60.0, 50, "No"])
        ws_p.append(["W19000", "19 L Returnable Water Bottle", "Returnable Water", "19 L", "Bottle", 300.0, 20, "Yes"])
        path_p = d / "Template_Products.xlsx"
        wb_p.save(path_p)
        templates["products"] = path_p

        # 2. Customers Template
        wb_c = openpyxl.Workbook()
        ws_c = wb_c.active
        ws_c.title = "Customers_Template"
        ws_c.append(["Customer Code", "Customer Name*", "Business Name", "Phone*", "Area", "Credit Limit (Rs.)", "Opening Balance (Rs.)"])
        ws_c.append(["CUST-001", "Kamal Perera", "Perera Grocery", "0771234567", "Colombo 03", 50000.0, 0.0])
        path_c = d / "Template_Customers.xlsx"
        wb_c.save(path_c)
        templates["customers"] = path_c

        return templates


class ImportService:
    @staticmethod
    def import_customers_from_excel(session: Session, file_path: Path) -> Dict[str, Any]:
        """Import customers from an Excel workbook with row-by-row validation in a single transaction."""
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active

        success_count = 0
        errors = []

        rows = list(ws.iter_rows(values_only=True))
        if len(rows) <= 1:
            return {"imported": 0, "errors": ["Spreadsheet contains no data rows."]}

        for idx, row in enumerate(rows[1:], start=2):
            if not any(row):
                continue
            name = str(row[1] or "").strip() if len(row) > 1 else ""
            phone = str(row[3] or "").strip() if len(row) > 3 else ""

            if not name:
                errors.append(f"Row {idx}: Customer Name is missing.")
                continue
            if not phone:
                errors.append(f"Row {idx}: Phone Number is missing for customer '{name}'.")
                continue

            code = str(row[0] or "").strip() if len(row) > 0 and row[0] else None
            biz = str(row[2] or "").strip() if len(row) > 2 and row[2] else None
            area = str(row[4] or "").strip() if len(row) > 4 and row[4] else None
            credit_limit = to_cents(row[5]) if len(row) > 5 and row[5] is not None else 5000000
            opening_bal = to_cents(row[6]) if len(row) > 6 and row[6] is not None else 0

            try:
                CustomerService.create_customer(
                    session=session,
                    name=name,
                    phone=phone,
                    business_name=biz,
                    code=code,
                    area=area,
                    credit_limit_cents=credit_limit,
                    opening_balance_cents=opening_bal
                )
                success_count += 1
            except Exception as e:
                errors.append(f"Row {idx} ('{name}'): {str(e)}")

        return {
            "imported": success_count,
            "errors": errors
        }
