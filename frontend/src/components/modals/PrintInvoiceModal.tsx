import { useState } from "react";
import { createPortal } from "react-dom";
import { useApp } from "../../context/AppContext";
import type { CreatedInvoice, Lang } from "../../types";
import { Icon } from "../Icon";
import { formatMoney } from "../../utils/formatters";
import { shopConfig } from "../../config/shopConfig";

export function PrintInvoiceModal({
  invoice,
  onClose,
  initialFormat,
  onRetry,
}: {
  invoice: CreatedInvoice;
  onClose: () => void;
  initialFormat?: "thermal" | "a4";
  onRetry?: () => void;
}) {
  const { lang, showToast } = useApp();
  const savedPref = (typeof window !== "undefined" ? localStorage.getItem("preferred_print_format") : null) as "thermal" | "a4" | null;
  const [printFormat, setPrintFormat] = useState<"thermal" | "a4">(initialFormat || savedPref || "thermal");
  const [printLang, setPrintLang] = useState<Lang>(lang);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const isTa = printLang === "ta";
  const cancelled = invoice.status === "cancelled";
  const cancelledLabel = isTa ? "ரத்து செய்யப்பட்டது" : "Cancelled";
  const chooseFormat = (format: "thermal" | "a4") => {
    setPrintFormat(format);
    localStorage.setItem("preferred_print_format", format);
  };

  // Helper to detect and avoid showing internal UUIDs in the UI
  const isUUID = (val?: string) =>
    Boolean(val && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(val.trim()));

  const handleDownloadPdf = async () => {
    const elementId = printFormat === "thermal" ? "thermal-slip" : "a4-tax-invoice";
    const el = document.getElementById(elementId);
    if (!el) return;

    setDownloadingPdf(true);
    showToast(isTa ? "PDF உருவாக்கப்படுகிறது..." : "Generating PDF...", "info");

    try {
      const [{default: jsPDF}, {default: html2canvas}] = await Promise.all([import("jspdf"), import("html2canvas")]);
      await document.fonts.ready;
      const canvas = await html2canvas(el, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: "#ffffff",
      });

      const imgData = canvas.toDataURL("image/png");
      const isThermal = printFormat === "thermal";
      const pdfWidth = isThermal ? 80 : 210;
      const pdfHeight = isThermal ? Math.max(100, (canvas.height * 80) / canvas.width) : 297;

      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: isThermal ? [80, pdfHeight] : "a4",
      });

      const imgHeight = (canvas.height * pdfWidth) / canvas.width;

      if (isThermal || imgHeight <= pdfHeight) {
        pdf.addImage(imgData, "PNG", 0, 0, pdfWidth, imgHeight);
      } else {
        const origin = el.getBoundingClientRect();
        const scale = canvas.height / origin.height;
        const rowBreaks = Array.from(el.querySelectorAll("tbody tr, .a4-totals-box"))
          .map((row) => Math.round((row.getBoundingClientRect().top - origin.top) * scale))
          .filter((y) => y > 0);
        const margin = 8;
        const contentWidth = pdfWidth - margin * 2;
        const pagePixels = Math.floor((pdfHeight - margin * 2) * canvas.width / contentWidth);
        for (let top = 0; top < canvas.height;) {
          const limit = Math.min(canvas.height, top + pagePixels);
          const boundary = limit === canvas.height ? limit : Math.max(0, ...rowBreaks.filter((y) => y > top && y <= limit));
          const end = boundary > top ? boundary : limit;
          const slice = document.createElement("canvas");
          slice.width = canvas.width;
          slice.height = end - top;
          const ctx = slice.getContext("2d");
          if (!ctx) throw new Error("Could not prepare invoice page");
          ctx.drawImage(canvas, 0, top, canvas.width, slice.height, 0, 0, slice.width, slice.height);
          if (top) pdf.addPage();
          pdf.addImage(slice.toDataURL("image/png"), "PNG", margin, margin, contentWidth, slice.height * contentWidth / slice.width);
          top = end;
        }
      }

      pdf.save(`${invoice.invoice_number}.pdf`);
      showToast(
        isTa ? `PDF பதிவிறக்கப்பட்டது (${invoice.invoice_number}.pdf)` : `Downloaded ${invoice.invoice_number}.pdf`,
        "success"
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(isTa ? "PDF பதிவிறக்க தோல்வி: " + msg : "Failed to download PDF: " + msg, "error");
    } finally {
      setDownloadingPdf(false);
    }
  };

  const hasItems = Boolean(invoice.items && invoice.items.length > 0);

  return createPortal(
    <div className={`modal-backdrop invoice-print-host invoice-print-${printFormat}`}>
      <div className="modal-dialog print-modal-dialog">
        <div className="modal-header no-print">
          <div className="print-header-info">
            <Icon name="check" size={20} />
            <div>
              <h3>{isTa ? "இன்வாய்ஸ் விவரம்" : "Invoice Document"}</h3>
              <small>{invoice.invoice_number} • {invoice.customer_name}</small>
            </div>
          </div>
          <div className="print-controls-bar">
            <div className="format-pills">
              <button
                className={printFormat === "thermal" ? "active" : ""}
                onClick={() => chooseFormat("thermal")}
              >
                80mm Thermal
              </button>
              <button
                className={printFormat === "a4" ? "active" : ""}
                onClick={() => chooseFormat("a4")}
              >
                A4 Tax Invoice
              </button>
            </div>
            <div className="format-pills">
              <button
                className={printLang === "en" ? "active" : ""}
                onClick={() => setPrintLang("en")}
              >
                EN
              </button>
              <button
                className={printLang === "ta" ? "active" : ""}
                onClick={() => setPrintLang("ta")}
              >
                தமிழ்
              </button>
            </div>
            <button
              type="button"
              className="btn-print-action"
              onClick={handleDownloadPdf}
              disabled={downloadingPdf || !hasItems}
              title={isTa ? "நேரடியாக PDF கோப்பை பதிவிறக்கம் செய்ய" : "Download PDF file directly"}
              style={{ background: "#0284c7", color: "#fff", border: "none" }}
            >
              <Icon name="download" size={16} />
              <span>{downloadingPdf ? (isTa ? "தயாராகிறது..." : "Downloading...") : (isTa ? "PDF பதிவிறக்கம்" : "Download PDF")}</span>
            </button>
            <button className="btn-print-action" onClick={() => window.print()} disabled={!hasItems} title="Print Invoice">
              <Icon name="print" size={16} />
              <span>{isTa ? "அச்சிடு" : "Print"}</span>
            </button>
            <button className="modal-close-btn" onClick={onClose}>✕</button>
          </div>
        </div>

        {/* Printable View Container */}
        <div className="printable-scroll-wrapper">
          {printFormat === "thermal" ? (
            /* 80mm THERMAL SLIP VIEW */
            <div className="thermal-receipt" id="thermal-slip">
              <div className="receipt-header">
                <h2>{isTa ? shopConfig.nameTa : shopConfig.name}</h2>
                {(isTa ? shopConfig.taglineTa : shopConfig.tagline) && (
                  <p style={{ fontWeight: 600 }}>{isTa ? shopConfig.taglineTa : shopConfig.tagline}</p>
                )}
                {(isTa ? (shopConfig.addressTa || shopConfig.address) : shopConfig.address) && (
                  <p>{isTa ? (shopConfig.addressTa || shopConfig.address) : shopConfig.address}</p>
                )}
                {(shopConfig.phone || shopConfig.taxNumber) && (
                  <p>
                    {shopConfig.phone && <span>Tel: {shopConfig.phone}</span>}
                    {shopConfig.phone && shopConfig.taxNumber && <span> • </span>}
                    {shopConfig.taxNumber && <span>Tax/GSTIN: {shopConfig.taxNumber}</span>}
                  </p>
                )}
                <div className="receipt-divider" />
                <div className="receipt-meta-grid">
                  {cancelled && <strong className="receipt-cancelled">{cancelledLabel}</strong>}
                  <span>{isTa ? "இன்வாய்ஸ் எண்:" : "Invoice No:"} <b>{invoice.invoice_number}</b></span>
                  <span>{isTa ? "தேதி:" : "Date:"} <b>{new Date(invoice.date).toLocaleDateString()}</b></span>
                  <span>{isTa ? "வாடிக்கையாளர்:" : "Customer:"} <b>{invoice.customer_name}</b></span>
                  {invoice.customer_phone && <span>{isTa ? "தொலைபேசி:" : "Phone:"} <b>{invoice.customer_phone}</b></span>}
                  <span>{isTa ? "பணியாளர்:" : "Staff:"} <b>{invoice.staff_name || "Cashier"}</b></span>
                </div>
                <div className="receipt-divider" />
              </div>

              {!hasItems ? (
                <div style={{ padding: 16, textAlign: "center", color: "#b45309", background: "#fef3c7", borderRadius: 6, margin: "10px 0" }}>
                  <p style={{ fontWeight: 700, margin: "0 0 4px" }}>
                    {isTa ? "பொருட்கள் விவரம் ஏற்றப்படவில்லை" : "Line Items Unavailable"}
                  </p>
                  <small style={{ fontSize: 11 }}>
                    {isTa ? "இன்வாய்ஸ் பொருட்களை ஏற்ற முடியவில்லை." : "Unable to load saved items for this invoice."}
                  </small>
                  {onRetry && (
                    <div style={{ marginTop: 8 }}>
                      <button type="button" className="btn-primary" style={{ fontSize: 11, padding: "4px 10px" }} onClick={onRetry}>
                        {isTa ? "மீண்டும் ஏற்று" : "Retry"}
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <table className="receipt-items-table">
                  <thead>
                    <tr>
                      <th>{isTa ? "பொருள் விளக்கம்" : "Item & Variant"}</th>
                      <th className="text-right">{isTa ? "அளவு" : "Qty"}</th>
                      <th className="text-right">{isTa ? "விலை" : "Rate"}</th>
                      <th className="text-right">{isTa ? "தொகை" : "Total"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoice.items.map((line, idx) => {
                      const unitName = line.unit || (line.name?.toLowerCase().includes("can") ? (isTa ? "கேன்" : "can") : (isTa ? "பாட்டில்" : "bottle"));
                      const displayName = isTa && line.ta ? line.ta : line.name;
                      const showVariant = line.variant && !isUUID(line.variant) && line.variant !== line.name && line.variant !== displayName;
                      return (
                        <tr key={idx}>
                          <td>
                            <div><b>{displayName}</b></div>
                            {showVariant && (
                              <small style={{ color: "#64748b", fontSize: 11, display: "block" }}>{line.variant}</small>
                            )}
                          </td>
                          <td className="text-right">{line.quantity} {unitName}</td>
                          <td className="text-right">{formatMoney(line.price)}</td>
                          <td className="text-right">{formatMoney(line.subtotal)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}

              <div className="receipt-divider" />

              <div className="receipt-totals-box">
                <div className="receipt-line">
                  <span>{isTa ? "மொத்த தொகை:" : "Total Amount:"}</span>
                  <b>{formatMoney(invoice.subtotal)}</b>
                </div>
                <div className="receipt-line" style={{ color: "#15803d" }}>
                  <span>{isTa ? "இன்று செலுத்தியது:" : "Paid Today:"}</span>
                  <b>{formatMoney(invoice.amount_paid)}</b>
                </div>
                {invoice.cash_received !== undefined && invoice.cash_received > invoice.amount_paid && (
                  <div className="receipt-line">
                    <span>{isTa ? "பெற்ற ரொக்கம்:" : "Cash Tendered:"}</span>
                    <b>{formatMoney(invoice.cash_received)}</b>
                  </div>
                )}
                {invoice.applied_to_old_debt !== undefined && invoice.applied_to_old_debt > 0 && (
                  <div className="receipt-line" style={{ color: "#b45309" }}>
                    <span>{isTa ? "பழைய கடனுக்கு சென்றது:" : "Applied to Old Debt:"}</span>
                    <b>{formatMoney(-invoice.applied_to_old_debt)}</b>
                  </div>
                )}
                {invoice.change_returned !== undefined && invoice.change_returned > 0 && (
                  <div className="receipt-line" style={{ color: "#15803d" }}>
                    <span>{isTa ? "கொடுத்த சில்லறை:" : "Change Returned:"}</span>
                    <b>{formatMoney(invoice.change_returned)}</b>
                  </div>
                )}
                {invoice.balance_due > 0 && (
                  <div className="receipt-line" style={{ color: "#b45309" }}>
                    <span>{isTa ? "இன்றைய பாக்கி:" : "Balance Due:"}</span>
                    <b>{formatMoney(invoice.balance_due)}</b>
                  </div>
                )}
                {typeof invoice.customer_balance === "number" && (
                  <div className="receipt-line font-bold" style={{ color: "#b45309" }}>
                    <span>{isTa ? "வாடிக்கையாளர் நிலுவை:" : "Account Balance:"}</span>
                    <b>{formatMoney(Math.max(0, invoice.customer_balance))}</b>
                  </div>
                )}
                {invoice.cans_returned > 0 && (
                  <div className="receipt-line" style={{ color: "#0284c7" }}>
                    <span>{isTa ? "காலி கேன் வரவு:" : "Empties Returned:"}</span>
                    <b>{invoice.cans_returned} {isTa ? "கேன்கள்" : "cans"}</b>
                  </div>
                )}
              </div>

              <div className="receipt-divider" />
              <div className="receipt-footer">
                <p>{isTa ? "வாங்கியமைக்கு நன்றி! மீண்டும் வருக!" : "Thank you for your business!"}</p>
                <small>Computer Generated Invoice • No Signature Required</small>
              </div>
            </div>
          ) : (
            /* A4 TAX INVOICE VIEW - CONTINUOUS WHITE SHEET */
            <div className="a4-invoice" id="a4-tax-invoice">
              <div className="a4-header">
                <div>
                  <h1>{isTa ? shopConfig.nameTa : shopConfig.name}</h1>
                  {(isTa ? shopConfig.taglineTa : shopConfig.tagline) && (
                    <p style={{ fontWeight: 600, color: "#1e3a8a", margin: "2px 0 4px" }}>
                      {isTa ? shopConfig.taglineTa : shopConfig.tagline}
                    </p>
                  )}
                  {(isTa ? (shopConfig.addressTa || shopConfig.address) : shopConfig.address) && (
                    <p>{isTa ? (shopConfig.addressTa || shopConfig.address) : shopConfig.address}</p>
                  )}
                  {(shopConfig.phone || shopConfig.email || shopConfig.taxNumber) && (
                    <p style={{ fontSize: 12, color: "#475569", margin: "2px 0 0" }}>
                      {shopConfig.taxNumber && <span>Tax/GSTIN: {shopConfig.taxNumber} • </span>}
                      {shopConfig.email && <span>Email: {shopConfig.email} • </span>}
                      {shopConfig.phone && <span>Tel: {shopConfig.phone}</span>}
                    </p>
                  )}
                </div>
                <div className="a4-invoice-badge">
                  <h2>{isTa ? "வரி இன்வாய்ஸ்" : "TAX INVOICE"}</h2>
                  <p><b>{invoice.invoice_number}</b></p>
                  <small>{new Date(invoice.date).toLocaleString()}</small>
                </div>
              </div>

              <div className="a4-addresses-grid">
                <div className="a4-address-box">
                  <small>{isTa ? "வாடிக்கையாளர் விவரம் (Billed To):" : "Billed To (Customer):"}</small>
                  <h3>{invoice.customer_name}</h3>
                  <p>{invoice.customer_phone || (isTa ? "நேரடி வாடிக்கையாளர்" : "Direct Customer")}</p>
                  {invoice.customer_address && <p>{invoice.customer_address}</p>}
                </div>
                <div className="a4-address-box">
                  <small>{isTa ? "கட்டண விவரம்:" : "Payment & Dispatch:"}</small>
                  <p>{isTa ? "பணியாளர்:" : "Billed By:"} <b>{invoice.staff_name || "Cashier"}</b></p>
                  <p>{isTa ? "நிலை:" : "Status:"} <b>{cancelled ? cancelledLabel : invoice.balance_due > 0 ? (isTa ? "பகுதி / கடன்" : "Credit / Partial") : (isTa ? "முழுவதும் செலுத்தப்பட்டது" : "Fully Paid")}</b></p>
                </div>
              </div>

              {!hasItems ? (
                <div style={{ padding: 24, textAlign: "center", color: "#b45309", background: "#fef3c7", borderRadius: 8, margin: "16px 0" }}>
                  <Icon name="warning" size={28} />
                  <p style={{ fontWeight: 700, margin: "8px 0 4px", fontSize: 15 }}>
                    {isTa ? "இன்வாய்ஸ் பொருட்கள் ஏற்றப்படவில்லை" : "Invoice Items Unavailable"}
                  </p>
                  <small style={{ fontSize: 13, color: "#78350f" }}>
                    {isTa
                      ? "இந்த இன்வாய்ஸிற்கான முழு பொருட்கள் தரவுத்தளத்தில் இருந்து பெற முடியவில்லை."
                      : "Could not load itemized lines for this saved invoice. Please retry loading."}
                  </small>
                  {onRetry && (
                    <div style={{ marginTop: 12 }}>
                      <button type="button" className="btn-primary" onClick={onRetry}>
                        {isTa ? "மீண்டும் ஏற்று" : "Retry Loading"}
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <table className="a4-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>{isTa ? "பொருள் விளக்கம்" : "Item & Variant"}</th>
                      <th className="text-right">{isTa ? "அளவு & அலகு" : "Qty & Unit"}</th>
                      <th className="text-right">{isTa ? "விலை (Rs.)" : "Rate (Rs.)"}</th>
                      <th className="text-right">{isTa ? "மொத்தம் (Rs.)" : "Total (Rs.)"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoice.items.map((line, idx) => {
                      const unitName = line.unit || (line.name?.toLowerCase().includes("can") ? (isTa ? "கேன்" : "can") : (isTa ? "பாட்டில்" : "bottle"));
                      const displayName = isTa && line.ta ? line.ta : line.name;
                      const showVariant = line.variant && !isUUID(line.variant) && line.variant !== line.name && line.variant !== displayName;
                      return (
                        <tr key={idx}>
                          <td>{idx + 1}</td>
                          <td>
                            <b>{displayName}</b>
                            {showVariant && (
                              <small style={{ display: "block", color: "#64748b", fontSize: 12 }}>{line.variant}</small>
                            )}
                          </td>
                          <td className="text-right">
                            <b>{line.quantity}</b> <small style={{ color: "#64748b" }}>{unitName}</small>
                          </td>
                          <td className="text-right">{formatMoney(line.price)}</td>
                          <td className="text-right"><b>{formatMoney(line.subtotal)}</b></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}

              <div className="a4-bottom-grid">
                <div className="a4-notes">
                  <p><b>{isTa ? "கேன் விபரம்:" : "Container Note:"}</b> {invoice.cans_returned > 0 ? `${invoice.cans_returned} ${isTa ? "கேன்கள் வரவு வைக்கப்பட்டது." : "empty cans returned during this transaction."}` : (isTa ? "காலி கேன் வரவு இல்லை." : "No empty return recorded.")}</p>
                  <p className="terms-note">{isTa ? "சரக்குகள் நல்ல நிலையில் பெற்றுக்கொள்ளப்பட்டது. கணினி மூலம் உருவாக்கப்பட்ட இன்வாய்ஸ்." : "Goods received in good condition. Computer generated invoice."}</p>
                </div>
                <div className="a4-totals-box">
                  <div className="a4-line">
                    <span>{isTa ? "உப மொத்தம்:" : "Subtotal:"}</span>
                    <b>{formatMoney(invoice.subtotal)}</b>
                  </div>
                  <div className="a4-line" style={{ color: "#15803d" }}>
                    <span>{isTa ? "இன்று செலுத்தியது:" : "Amount Paid:"}</span>
                    <b>{formatMoney(invoice.amount_paid)}</b>
                  </div>
                  {invoice.cash_received !== undefined && invoice.cash_received > invoice.amount_paid && (
                    <div className="a4-line">
                      <span>{isTa ? "பெற்ற ரொக்கம்:" : "Cash Tendered:"}</span>
                      <b>{formatMoney(invoice.cash_received)}</b>
                    </div>
                  )}
                  {invoice.applied_to_old_debt !== undefined && invoice.applied_to_old_debt > 0 && (
                    <div className="a4-line" style={{ color: "#b45309" }}>
                      <span>{isTa ? "பழைய கடனுக்கு செலுத்தியது:" : "Applied to Old Debt:"}</span>
                      <b>{formatMoney(-invoice.applied_to_old_debt)}</b>
                    </div>
                  )}
                  {invoice.change_returned !== undefined && invoice.change_returned > 0 && (
                    <div className="a4-line" style={{ color: "#15803d" }}>
                      <span>{isTa ? "கொடுத்த சில்லறை:" : "Change Returned:"}</span>
                      <b>{formatMoney(invoice.change_returned)}</b>
                    </div>
                  )}
                  <div className="a4-line total">
                    <span>{isTa ? "மீதமுள்ள இன்வாய்ஸ் தொகை:" : "Balance Due:"}</span>
                    <strong style={{ color: invoice.balance_due > 0 ? "#b45309" : "#0f172a" }}>{formatMoney(invoice.balance_due)}</strong>
                  </div>
                  {typeof invoice.customer_balance === "number" && (
                    <div className="a4-line" style={{ color: "#b45309" }}>
                      <span>{isTa ? "வாடிக்கையாளர் கணக்கு நிலுவை:" : "Account Balance:"}</span>
                      <b>{formatMoney(Math.max(0, invoice.customer_balance))}</b>
                    </div>
                  )}
                </div>
              </div>

              <div className="a4-footer-signatures">
                <div>
                  <div className="sign-line" />
                  <small>{isTa ? "வாடிக்கையாளர் கையொப்பம்" : "Customer Signature"}</small>
                </div>
                <div>
                  <div className="sign-line" />
                  <small>{isTa ? "அங்கீகரிக்கப்பட்ட கையொப்பம்" : "Authorized Signatory"}</small>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="modal-actions no-print" style={{ padding: "12px 20px", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="btn-cancel" onClick={onClose}>
            {isTa ? "மூடு" : "Close"}
          </button>
          <button
            type="button"
            className="btn-primary"
            style={{ background: "#0284c7" }}
            onClick={handleDownloadPdf}
            disabled={downloadingPdf || !hasItems}
            title={isTa ? "நேரடியாக PDF கோப்பை பதிவிறக்கம் செய்ய" : "Download PDF file directly"}
          >
            <Icon name="download" size={16} />
            <span>{downloadingPdf ? (isTa ? "தயாராகிறது..." : "Downloading...") : (isTa ? "PDF பதிவிறக்கம்" : "Download PDF")}</span>
          </button>
          <button className="btn-primary" onClick={() => window.print()} disabled={!hasItems}>
            <Icon name="print" size={18} />
            <span>{isTa ? "இன்வாய்ஸ் அச்சிடு" : "Print Invoice"}</span>
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
