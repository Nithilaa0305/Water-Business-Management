"""Invoice and Receipt HTML/PDF Generator supporting A4, A5, and 80mm Thermal Receipts with Tamil Unicode support."""

from typing import Dict, Any, Optional
from pathlib import Path
from PySide6.QtGui import QTextDocument, QFont
from PySide6.QtPrintSupport import QPrinter
from app.config.settings import EXPORTS_DIR
from app.database.models.sales import SalesInvoice
from app.database.models.auth import BusinessProfile
from app.utilities.currency import format_currency, from_cents
from app.utilities.dates import format_datetime


class InvoiceGenerator:
    @staticmethod
    def generate_invoice_html(invoice: SalesInvoice, profile: Optional[BusinessProfile] = None, layout: str = "A4") -> str:
        """Generate professional HTML template for the invoice."""
        biz_name = profile.business_name if profile else "Pure Life Bottled Water"
        biz_addr = profile.address if profile else "123 Galle Road, Colombo, Sri Lanka"
        biz_phone = profile.phone if profile else "+94 11 234 5678"
        biz_email = profile.email if profile else "info@watermanager.lk"

        cust_name = invoice.customer.name if invoice.customer else "Walk-in Cash Customer"
        cust_phone = invoice.customer.phone if invoice.customer else "-"
        cust_addr = invoice.customer.address if invoice.customer else ""

        items_rows = ""
        for idx, item in enumerate(invoice.items, start=1):
            prod_name = item.product.name
            uom = item.packaging_unit.name if item.packaging_unit else item.product.uom
            qty = item.quantity
            price = format_currency(item.unit_price_cents)
            disc = format_currency(item.line_discount_cents) if item.line_discount_cents > 0 else "-"
            total = format_currency(item.line_total_cents)

            items_rows += f"""
            <tr>
                <td style="text-align: center; padding: 6px; border-bottom: 1px solid #E2E8F0;">{idx}</td>
                <td style="padding: 6px; border-bottom: 1px solid #E2E8F0;"><b>{prod_name}</b> ({uom})</td>
                <td style="text-align: center; padding: 6px; border-bottom: 1px solid #E2E8F0;">{qty}</td>
                <td style="text-align: right; padding: 6px; border-bottom: 1px solid #E2E8F0;">{price}</td>
                <td style="text-align: right; padding: 6px; border-bottom: 1px solid #E2E8F0;">{disc}</td>
                <td style="text-align: right; padding: 6px; border-bottom: 1px solid #E2E8F0;">{total}</td>
            </tr>
            """

        bottle_section = ""
        if invoice.bottles_delivered_19l > 0 or invoice.bottles_returned_19l > 0:
            bottle_section = f"""
            <div style="margin-top: 15px; padding: 10px; background-color: #F0F9FF; border-left: 4px solid #0284C7; border-radius: 4px;">
                <b style="color: #0369A1;">19 L Returnable Container Summary:</b><br/>
                • Full Bottles Delivered: <b>{invoice.bottles_delivered_19l}</b><br/>
                • Empty Bottles Returned: <b>{invoice.bottles_returned_19l}</b><br/>
                • Net Change in Customer Obligation: <b>+{invoice.bottles_delivered_19l - invoice.bottles_returned_19l} bottles</b>
            </div>
            """

        font_size = "10px" if layout == "80mm" else "12px"
        width = "280px" if layout == "80mm" else "100%"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Segoe UI', 'Nirmala UI', Arial, sans-serif;
                    font-size: {font_size};
                    color: #1E293B;
                    margin: 0;
                    padding: 15px;
                }}
                .header-table {{ width: 100%; border-bottom: 2px solid #0284C7; padding-bottom: 10px; margin-bottom: 15px; }}
                .invoice-title {{ font-size: 20px; font-weight: bold; color: #0284C7; text-align: right; }}
                .meta-table {{ width: 100%; margin-bottom: 15px; }}
                .items-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                .items-table th {{ background-color: #F8FAFC; color: #475569; padding: 8px; text-align: left; border-bottom: 2px solid #CBD5E1; }}
                .totals-table {{ width: 45%; margin-left: auto; margin-top: 15px; border-collapse: collapse; }}
                .totals-table td {{ padding: 6px; }}
                .grand-total {{ font-size: 15px; font-weight: bold; color: #0284C7; border-top: 2px solid #0284C7; }}
                .footer {{ margin-top: 30px; text-align: center; color: #94A3B8; font-size: 10px; border-top: 1px solid #E2E8F0; padding-top: 10px; }}
            </style>
        </head>
        <body style="max-width: {width};">
            <table class="header-table">
                <tr>
                    <td>
                        <b style="font-size: 16px; color: #0F172A;">{biz_name}</b><br/>
                        {biz_addr}<br/>
                        Phone: {biz_phone} | Email: {biz_email}
                    </td>
                    <td class="invoice-title">
                        TAX INVOICE<br/>
                        <span style="font-size: 13px; color: #64748B;">#{invoice.invoice_number}</span>
                    </td>
                </tr>
            </table>

            <table class="meta-table">
                <tr>
                    <td style="width: 60%; vertical-align: top;">
                        <b style="color: #64748B;">BILL TO:</b><br/>
                        <b style="font-size: 14px;">{cust_name}</b><br/>
                        Phone: {cust_phone}<br/>
                        {cust_addr}
                    </td>
                    <td style="width: 40%; vertical-align: top; text-align: right;">
                        <b>Date:</b> {format_datetime(invoice.invoice_date)}<br/>
                        <b>Payment Method:</b> {invoice.payment_method}<br/>
                        <b>Status:</b> <span style="color: #16A34A; font-weight: bold;">{invoice.status}</span>
                    </td>
                </tr>
            </table>

            <table class="items-table">
                <thead>
                    <tr>
                        <th style="width: 5%; text-align: center;">#</th>
                        <th style="width: 45%;">Description</th>
                        <th style="width: 10%; text-align: center;">Qty</th>
                        <th style="width: 15%; text-align: right;">Price</th>
                        <th style="width: 10%; text-align: right;">Disc</th>
                        <th style="width: 15%; text-align: right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {items_rows}
                </tbody>
            </table>

            <table class="totals-table">
                <tr>
                    <td>Subtotal:</td>
                    <td style="text-align: right;">{format_currency(invoice.subtotal_cents)}</td>
                </tr>
                {"<tr><td>Discount:</td><td style='text-align: right; color: #DC2626;'>-" + format_currency(invoice.discount_cents) + "</td></tr>" if invoice.discount_cents > 0 else ""}
                {"<tr><td>Delivery:</td><td style='text-align: right;'>+" + format_currency(invoice.delivery_charge_cents) + "</td></tr>" if invoice.delivery_charge_cents > 0 else ""}
                <tr class="grand-total">
                    <td>Invoice Total:</td>
                    <td style="text-align: right;">{format_currency(invoice.total_amount_cents)}</td>
                </tr>
                <tr>
                    <td>Amount Paid:</td>
                    <td style="text-align: right; font-weight: bold;">{format_currency(invoice.amount_paid_cents)}</td>
                </tr>
                <tr>
                    <td><b>Outstanding on Invoice:</b></td>
                    <td style="text-align: right; font-weight: bold; color: #DC2626;">
                        {format_currency(max(0, invoice.total_amount_cents - invoice.amount_paid_cents))}
                    </td>
                </tr>
            </table>

            {bottle_section}

            <div class="footer">
                Thank you for your business! Fresh & Pure Bottled Drinking Water.<br/>
                For deliveries and inquiries, please call {biz_phone}.
            </div>
        </body>
        </html>
        """
        return html

    @staticmethod
    def export_invoice_pdf(invoice: SalesInvoice, profile: Optional[BusinessProfile] = None, output_path: Optional[Path] = None, layout: str = "A4") -> Path:
        """Export invoice to PDF file using Qt QTextDocument and QPrinter."""
        dest = output_path or (EXPORTS_DIR / f"Invoice_{invoice.invoice_number}.pdf")
        html_content = InvoiceGenerator.generate_invoice_html(invoice, profile, layout)

        doc = QTextDocument()
        doc.setDefaultFont(QFont("Segoe UI", 10))
        doc.setHtml(html_content)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(dest))
        if layout == "A5":
            printer.setPageSize(QPrinter.A5)
        else:
            printer.setPageSize(QPrinter.A4)

        doc.print_(printer)
        return dest
