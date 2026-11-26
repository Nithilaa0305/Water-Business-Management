"""Invoice preview and printing dialog."""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextBrowser, QComboBox, QMessageBox, QFileDialog
)
from app.database.connection import get_db_session
from app.database.models.sales import SalesInvoice
from app.database.models.auth import BusinessProfile
from app.reports.invoice_generator import InvoiceGenerator
from app.utilities.whatsapp import generate_invoice_whatsapp_text, open_whatsapp_share, clean_sri_lankan_phone
from app.utilities.currency import format_currency
from PySide6.QtWidgets import QInputDialog


class InvoicePreviewDialog(QDialog):
    def __init__(self, invoice_id: int, parent=None):
        super().__init__(parent)
        self.invoice_id = invoice_id
        self.setWindowTitle("Invoice Preview & Print")
        self.resize(750, 800)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                color: #0F172A;
            }
            QLabel {
                color: #0F172A;
            }
            QComboBox {
                background-color: #FFFFFF;
                color: #0F172A;
            }
        """)

        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.cmb_layout = QComboBox()
        self.cmb_layout.addItem("Standard A4 Invoice", "A4")
        self.cmb_layout.addItem("Compact A5 Invoice", "A5")
        self.cmb_layout.addItem("80mm Thermal Receipt", "80mm")
        self.cmb_layout.currentIndexChanged.connect(self.render_preview)
        toolbar.addWidget(self.cmb_layout)

        toolbar.addStretch()

        self.btn_export_pdf = QPushButton("Export PDF")
        self.btn_export_pdf.setObjectName("SecondaryButton")
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        toolbar.addWidget(self.btn_export_pdf)

        self.btn_whatsapp = QPushButton("📲 Share via WhatsApp")
        self.btn_whatsapp.setStyleSheet("background-color: #25D366; color: white; font-weight: bold;")
        self.btn_whatsapp.clicked.connect(self.share_whatsapp)
        toolbar.addWidget(self.btn_whatsapp)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        toolbar.addWidget(self.btn_close)

        layout.addLayout(toolbar)

        # Preview Browser
        self.browser = QTextBrowser()
        self.browser.setStyleSheet("background-color: white; color: #0F172A; border: 1px solid #CBD5E1;")
        layout.addWidget(self.browser)

        self.render_preview()

    def render_preview(self):
        layout_mode = self.cmb_layout.currentData()
        with get_db_session() as session:
            inv = session.query(SalesInvoice).filter_by(id=self.invoice_id).first()
            prof = session.query(BusinessProfile).first()
            if inv:
                html = InvoiceGenerator.generate_invoice_html(inv, prof, layout=layout_mode)
                self.browser.setHtml(html)

    def export_pdf(self):
        with get_db_session() as session:
            inv = session.query(SalesInvoice).filter_by(id=self.invoice_id).first()
            prof = session.query(BusinessProfile).first()
            if not inv:
                return

            default_name = f"Invoice_{inv.invoice_number}.pdf"
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Invoice PDF", default_name, "PDF Files (*.pdf)")
            if file_path:
                try:
                    out = InvoiceGenerator.export_invoice_pdf(inv, prof, output_path=Path(file_path), layout=self.cmb_layout.currentData())
                    QMessageBox.information(self, "PDF Exported", f"Invoice successfully exported to:\n{out}")
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"Could not export PDF: {str(e)}")

    def share_whatsapp(self):
        with get_db_session() as session:
            inv = session.query(SalesInvoice).filter_by(id=self.invoice_id).first()
            prof = session.query(BusinessProfile).first()
            if not inv:
                return

            cust = inv.customer
            phone = cust.phone if cust else ""
            cust_name = cust.name if cust else "Walk-in Customer"

            if not phone:
                input_phone, ok = QInputDialog.getText(
                    self, "Recipient Phone", "Enter recipient WhatsApp phone number (e.g. 0771234567):"
                )
                if not ok or not input_phone.strip():
                    return
                phone = input_phone.strip()

            items_list = []
            for item in inv.items:
                items_list.append({
                    "product_name": item.product.name if item.product else "Water Bottle",
                    "quantity": item.quantity,
                    "line_total_display": format_currency(item.line_total_cents)
                })

            b_name = prof.business_name if prof else "Pure Life Bottled Water"
            tot_str = format_currency(inv.total_amount_cents)
            paid_str = format_currency(inv.amount_paid_cents)
            due_cents = max(0, inv.total_amount_cents - inv.amount_paid_cents)
            due_str = format_currency(due_cents)

            msg = generate_invoice_whatsapp_text(
                business_name=b_name,
                invoice_number=inv.invoice_number,
                date_str=inv.invoice_date.strftime("%Y-%m-%d"),
                customer_name=cust_name,
                items=items_list,
                total_display=tot_str,
                paid_display=paid_str,
                balance_display=due_str,
                bottles_19l_returned=inv.bottles_returned_19l or 0
            )

            ok = open_whatsapp_share(phone, msg)
            if ok:
                QMessageBox.information(self, "WhatsApp Launched", "WhatsApp Web/Desktop opened with your invoice summary!")
            else:
                QMessageBox.warning(self, "WhatsApp Error", "Could not automatically launch browser.")

