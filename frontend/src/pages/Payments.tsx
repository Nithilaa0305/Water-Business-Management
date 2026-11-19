import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { api } from "../services/api";
import type { Customer, Role } from "../types";
import { sampleCustomers } from "../data/sampleData";
import { Icon } from "../components/Icon";
import { formatMoney } from "../utils/formatters";

export function Payments({
  token,
  role = "employee",
  onGoHome,
}: {
  token: string;
  role?: Role;
  onGoHome?: () => void;
}) {
  const { t, lang, speak, showToast } = useApp();
  const [customers, setCustomers] = useState<Customer[]>(sampleCustomers);
  const [customer, setCustomer] = useState<Customer>(sampleCustomers[0]);
  const [query, setQuery] = useState("");
  const [saving, setSaving] = useState(false);
  const [statusState, setStatusState] = useState<"idle" | "saving" | "unknown">("idle");
  const [refreshingBalance, setRefreshingBalance] = useState(false);

  // Settlement Form State (Money & Cans together)
  const [amount, setAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<"cash" | "bank">("cash");
  const [moneyNotes, setMoneyNotes] = useState("");
  const [canQty, setCanQty] = useState("");
  const [canNotes, setCanNotes] = useState("");

  // Partial failure tracking (prevents duplicate writes on retry)
  const [partialFailure, setPartialFailure] = useState<{
    failed: "cans" | "money";
    error: string;
    savedAmount?: number;
    savedCans?: number;
  } | null>(null);

  // Collapsible Secondary Section: Goods Return & Invoice Cancellation
  const [showGoodsReturn, setShowGoodsReturn] = useState(false);
  const [invoiceQuery, setInvoiceQuery] = useState("");
  const [selectedInvoice, setSelectedInvoice] = useState<any | null>(null);
  const [loadingInvoice, setLoadingInvoice] = useState(false);
  const [returnItemId, setReturnItemId] = useState<string>("");
  const [returnQty, setReturnQty] = useState<string>("1");
  const [returnReason, setReturnReason] = useState<string>("");
  const [returnDamaged, setReturnDamaged] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>("");

  // Recent payments & Mistake correction state
  const [recentPayments, setRecentPayments] = useState<any[]>([]);
  const [editingPayment, setEditingPayment] = useState<any | null>(null);
  const [correctedAmount, setCorrectedAmount] = useState("");
  const [correctedMethod, setCorrectedMethod] = useState("cash");
  const [correctionReason, setCorrectionReason] = useState("");

  const isManagerOrOwner = role === "owner" || role === "manager";

  const loadCustomers = () => {
    api
      .get<{ customers?: Partial<Customer>[] } | Partial<Customer>[]>("/customers/list", token)
      .then((result) => {
        const rows = Array.isArray(result) ? result : (result.customers ?? []);
        if (rows.length) {
          const mapped = rows.map((row, index) => ({
            ...sampleCustomers[index % sampleCustomers.length],
            ...row,
            id: row.id ? String(row.id) : index + 1,
            balance: Number(row.balance ?? 0),
            cans: Number(row.cans ?? 0),
          }));
          setCustomers(mapped);
          setCustomer((curr) => mapped.find((m) => String(m.id) === String(curr.id)) || mapped[0]);
        }
      })
      .catch(() => {});
  };

  const loadRecentPayments = (customerId?: string) => {
    const cid = customerId || (customer ? String(customer.id) : "");
    const url = cid ? `/payments/recent?customer_id=${cid}` : "/payments/recent";
    api
      .get<any[]>(url, token)
      .then((rows) => {
        if (Array.isArray(rows)) {
          setRecentPayments(rows);
        }
      })
      .catch(() => {});
  };

  const refreshBalance = async (silent = false) => {
    if (!customer?.id) return;
    setRefreshingBalance(true);
    try {
      const freshCust = await api.get<any>(`/customers/details/${customer.id}`, token);
      if (freshCust) {
        const b = Number(freshCust.balance ?? 0);
        const c = Number(freshCust.cans ?? 0);
        setCustomer((prev) => ({
          ...prev,
          balance: b,
          cans: c,
        }));
        setCustomers((prev) =>
          prev.map((item) =>
            String(item.id) === String(customer.id)
              ? { ...item, balance: b, cans: c }
              : item
          )
        );
        setStatusState("idle");
        if (!silent) {
          showToast(
            lang === "ta"
              ? `இருப்பு புதுப்பிக்கப்பட்டது: கடன் ${formatMoney(b)}, கேன்கள்: ${c}`
              : `Balance updated: Debt ${formatMoney(b)}, Cans: ${c}`,
            "info"
          );
        }
      }
    } catch (e: any) {
      if (!silent) {
        showToast(lang === "ta" ? "இருப்பு புதுப்பிக்க முடியவில்லை" : "Could not refresh balance: " + e.message, "error");
      }
    } finally {
      setRefreshingBalance(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, [token]);

  useEffect(() => {
    const handleRefresh = () => {
      loadCustomers();
      if (customer?.id) {
        refreshBalance(true);
        loadRecentPayments(String(customer.id));
      }
    };
    window.addEventListener("refresh-customer-data", handleRefresh);
    return () => window.removeEventListener("refresh-customer-data", handleRefresh);
  }, [customer?.id]);

  useEffect(() => {
    if (customer && customer.id) {
      loadRecentPayments(String(customer.id));
      setPartialFailure(null);
      setStatusState("idle");
    }
  }, [customer?.id, token]);

  // UNIFIED SETTLEMENT SUBMIT (Money and Cans together)
  const submitSettlement = async () => {
    if (statusState === "unknown") {
      // User clicked "Check whether it saved"
      await refreshBalance(false);
      return;
    }

    const numAmt = Number(amount) || 0;
    const numCans = Number(canQty) || 0;

    // Check if at least one valid entry exists
    const isRetryingCans = partialFailure?.failed === "cans";
    const isRetryingMoney = partialFailure?.failed === "money";

    if (!isRetryingCans && !isRetryingMoney && numAmt <= 0 && numCans <= 0) {
      showToast(
        lang === "ta"
          ? "தொகை அல்லது காலி கேன் எண்ணிக்கையை உள்ளிடவும்"
          : "Please enter money received or empty cans returned (or both)",
        "error"
      );
      return;
    }

    setSaving(true);
    setStatusState("saving");

    const payOpId = "pay-" + Date.now() + "-" + Math.random().toString(36).slice(2, 7);
    const canOpId = "can-" + Date.now() + "-" + Math.random().toString(36).slice(2, 7);

    let moneySucceeded = false;
    let cansSucceeded = false;
    let newBalance = customer.balance;
    let newCans = customer.cans;
    let moneyError = "";
    let canError = "";

    const shouldProcessMoney = !isRetryingCans && numAmt > 0;
    const shouldProcessCans = !isRetryingMoney && numCans > 0;

    // 1. Process Money if entered
    if (shouldProcessMoney) {
      try {
        const res = await api.post<any>(
          "/payments/receive",
          {
            customer_id: customer.id,
            amount: numAmt,
            payment_method: paymentMethod,
            notes: moneyNotes || `Collected via ${paymentMethod.toUpperCase()}`,
            operation_id: payOpId,
          },
          token
        );
        moneySucceeded = true;
        if (res && res.new_balance !== undefined) {
          newBalance = Number(res.new_balance);
        } else {
          newBalance = customer.balance - numAmt;
        }
        // Update balance immediately without full reload
        setCustomer((prev) => ({ ...prev, balance: newBalance }));
        setCustomers((prev) =>
          prev.map((c) => (String(c.id) === String(customer.id) ? { ...c, balance: newBalance } : c))
        );
      } catch (err: any) {
        moneyError = err.message || "Payment collection failed";
      }
    }

    // 2. Process Cans if entered
    if (shouldProcessCans) {
      try {
        const res = await api.post<any>(
          "/containers/movement",
          {
            customer_id: customer.id,
            quantity: numCans,
            action: "return",
            notes: canNotes || "Empty 19L cans returned by customer",
            operation_id: canOpId,
          },
          token
        );
        cansSucceeded = true;
        if (res && (res.held !== undefined || res.new_cans_balance !== undefined)) {
          newCans = Number(res.held ?? res.new_cans_balance);
        } else {
          newCans = Math.max(0, customer.cans - numCans);
        }
        // Update cans immediately without full reload
        setCustomer((prev) => ({ ...prev, cans: newCans }));
        setCustomers((prev) =>
          prev.map((c) => (String(c.id) === String(customer.id) ? { ...c, cans: newCans } : c))
        );
      } catch (err: any) {
        canError = err.message || "Can return failed";
      }
    }

    setSaving(false);

    // Evaluate combinations
    if (shouldProcessMoney && shouldProcessCans) {
      if (moneySucceeded && cansSucceeded) {
        speak("Settlement recorded successfully", "வரவு வெற்றிகரமாக சேமிக்கப்பட்டது");
        showToast(
          lang === "ta"
            ? `${formatMoney(numAmt)} பணம் & ${numCans} காலிகேன்கள் வரவு வைக்கப்பட்டது! புதிய கடன்: ${formatMoney(newBalance)}, கேன்கள்: ${newCans}`
            : `Settlement recorded: ${formatMoney(numAmt)} payment & ${numCans} cans returned! New debt: ${formatMoney(newBalance)}, Cans: ${newCans}`,
          "success"
        );
        setAmount("");
        setMoneyNotes("");
        setCanQty("");
        setCanNotes("");
        setPartialFailure(null);
        setStatusState("idle");
        loadRecentPayments(String(customer.id));
        window.dispatchEvent(new CustomEvent("refresh-customer-data"));
      } else if (moneySucceeded && !cansSucceeded) {
        // Money saved, cans failed: do NOT re-charge money on retry
        setAmount("");
        setMoneyNotes("");
        setPartialFailure({ failed: "cans", error: canError, savedAmount: numAmt });
        setStatusState("idle");
        showToast(
          lang === "ta"
            ? `${formatMoney(numAmt)} பணம் வரவு சேமிக்கப்பட்டது! ஆனால் காலி கேன்கள் பதிவு தோல்வியடைந்தது: ${canError}. கேன்களை மட்டும் மீண்டும் பதிவு செய்யவும்.`
            : `Payment of ${formatMoney(numAmt)} recorded! Cans return failed: ${canError}. Retry cans only below.`,
          "error"
        );
        loadRecentPayments(String(customer.id));
        window.dispatchEvent(new CustomEvent("refresh-customer-data"));
      } else if (!moneySucceeded && cansSucceeded) {
        // Cans saved, money failed: do NOT return duplicate cans on retry
        setCanQty("");
        setCanNotes("");
        setPartialFailure({ failed: "money", error: moneyError, savedCans: numCans });
        setStatusState("idle");
        showToast(
          lang === "ta"
            ? `${numCans} காலிகேன்கள் வரவு சேமிக்கப்பட்டது! ஆனால் பணம் வரவு தோல்வியடைந்தது: ${moneyError}. பணத்தை மட்டும் மீண்டும் பதிவு செய்யவும்.`
            : `${numCans} empty cans returned! Payment failed: ${moneyError}. Retry payment only below.`,
          "error"
        );
        window.dispatchEvent(new CustomEvent("refresh-customer-data"));
      } else {
        setStatusState("idle");
        showToast(
          lang === "ta"
            ? `பதிவு தோல்வியடைந்தது. பணம்: ${moneyError} | கேன்கள்: ${canError}`
            : `Settlement failed. Payment: ${moneyError} | Cans: ${canError}`,
          "error"
        );
      }
    } else if (shouldProcessMoney) {
      if (moneySucceeded) {
        speak("Payment collected successfully", "பணம் வரவு வைக்கப்பட்டது");
        showToast(
          lang === "ta"
            ? `${formatMoney(numAmt)} வரவு வைக்கப்பட்டது (${customer.name}). புதிய கடன்: ${formatMoney(newBalance)}`
            : `${formatMoney(numAmt)} collected for ${customer.name}. New debt: ${formatMoney(newBalance)}`,
          "success"
        );
        setAmount("");
        setMoneyNotes("");
        setPartialFailure(null);
        setStatusState("idle");
        loadRecentPayments(String(customer.id));
        window.dispatchEvent(new CustomEvent("refresh-customer-data"));
      } else {
        setStatusState("idle");
        showToast(moneyError, "error");
      }
    } else if (shouldProcessCans) {
      if (cansSucceeded) {
        speak("Empty cans recorded", "காலி கேன்கள் வரவு வைக்கப்பட்டது");
        showToast(
          lang === "ta"
            ? `${numCans} காலிகேன்கள் வரவு வைக்கப்பட்டது (${customer.name}). மீதமுள்ள கேன்கள்: ${newCans}`
            : `${numCans} empty cans returned by ${customer.name}. Remaining cans: ${newCans}`,
          "success"
        );
        setCanQty("");
        setCanNotes("");
        setPartialFailure(null);
        setStatusState("idle");
        window.dispatchEvent(new CustomEvent("refresh-customer-data"));
      } else {
        setStatusState("idle");
        showToast(canError, "error");
      }
    }
  };

  // Search invoice for returns
  const handleSearchInvoice = async () => {
    if (!invoiceQuery.trim()) return;
    setLoadingInvoice(true);
    try {
      const inv = await api.get<any>(`/invoices/details/${encodeURIComponent(invoiceQuery.trim())}`, token);
      setSelectedInvoice(inv);
      if (inv.items && inv.items.length > 0) {
        setReturnItemId(inv.items[0].sale_item_id);
      }
    } catch (err: any) {
      setSelectedInvoice(null);
      showToast(lang === "ta" ? "இன்வாய்ஸ் காணப்படவில்லை" : (err.message || "Invoice not found"), "error");
    } finally {
      setLoadingInvoice(false);
    }
  };

  // Submit: Return item
  const submitItemReturn = async () => {
    if (!selectedInvoice || !returnItemId) return;
    const qty = Number(returnQty);
    if (!qty || qty <= 0) {
      showToast(lang === "ta" ? "திருப்பி அனுப்பும் எண்ணிக்கையை உள்ளிடவும்" : "Enter valid return quantity", "error");
      return;
    }
    if (!returnReason.trim()) {
      showToast(lang === "ta" ? "காரணத்தை உள்ளிடவும்" : "Please provide a reason for return", "error");
      return;
    }

    setSaving(true);
    try {
      const fullReason = returnDamaged ? `[DAMAGED/SCRAP] ${returnReason.trim()}` : returnReason.trim();
      await api.post(
        "/sales/return-item",
        {
          sale_item_id: returnItemId,
          quantity: qty,
          reason: fullReason,
        },
        token,
      );

      speak("Item return processed", "பொருட்கள் திருப்புதல் ஏற்கப்பட்டது");
      showToast(
        lang === "ta"
          ? `${qty} சரக்கு திருப்பப்பட்டது. வாடிக்கையாளர் கணக்கில் தொகை வரவு வைக்கப்பட்டது.`
          : `Returned ${qty} item(s). Customer balance credited.`,
        "success"
      );

      handleSearchInvoice();
      refreshBalance(true);
      window.dispatchEvent(new CustomEvent("refresh-stock-data"));
      window.dispatchEvent(new CustomEvent("refresh-customer-data"));
      setReturnQty("1");
      setReturnReason("");
    } catch (err: any) {
      showToast(err.message || "Failed to process return", "error");
    } finally {
      setSaving(false);
    }
  };

  // Submit: Cancel entire sale
  const submitSaleCancellation = async () => {
    if (!selectedInvoice) return;
    if (!cancelReason.trim()) {
      showToast(lang === "ta" ? "பில் ரத்து செய்ய காரணம் தேவை" : "Please enter reason for cancellation", "error");
      return;
    }

    const confirmMsg = lang === "ta"
      ? `பில் ${selectedInvoice.invoice_number} ரத்து செய்யப்பட வேண்டுமா? சரக்குகள் மீண்டும் சேர்க்கப்பட்டு வாடிக்கையாளர் கணக்கு சரிசெய்யப்படும்.`
      : `Cancel invoice ${selectedInvoice.invoice_number}? All items will be restored to stock and customer balance will be adjusted.`;
    if (!window.confirm(confirmMsg)) return;

    setSaving(true);
    try {
      await api.post(
        "/sales/cancel",
        {
          sale_id: selectedInvoice.sale_id,
          reason: cancelReason.trim(),
        },
        token,
      );

      speak("Bill cancelled successfully", "பில் ரத்து செய்யப்பட்டது");
      showToast(
        lang === "ta"
          ? `பில் ${selectedInvoice.invoice_number} ரத்து செய்யப்பட்டது. சரக்குகள் மீட்டமைக்கப்பட்டன.`
          : `Invoice ${selectedInvoice.invoice_number} cancelled and stock restored.`,
        "success"
      );

      setSelectedInvoice(null);
      setInvoiceQuery("");
      setCancelReason("");
      refreshBalance(true);
      window.dispatchEvent(new CustomEvent("refresh-stock-data"));
      window.dispatchEvent(new CustomEvent("refresh-customer-data"));
    } catch (err: any) {
      showToast(err.message || "Failed to cancel sale", "error");
    } finally {
      setSaving(false);
    }
  };

  // Payment Mistake Correction (Manager/Owner only)
  const handleSaveCorrection = async () => {
    if (!editingPayment) return;
    const newAmt = Number(correctedAmount);
    if (!newAmt || newAmt <= 0) {
      showToast("Please enter a valid amount greater than zero", "error");
      return;
    }
    if (!correctionReason.trim()) {
      showToast("Reason is required for auditing payment corrections", "error");
      return;
    }

    try {
      await api.post(
        "/payments/correct",
        {
          payment_id: editingPayment.payment_id,
          new_amount: newAmt,
          payment_method: correctedMethod,
          reason: correctionReason.trim(),
        },
        token,
      );
      speak("Payment corrected", "தொகை மாற்றப்பட்டது");
      showToast(
        lang === "ta"
          ? `தவறு திருத்தப்பட்டது: ${formatMoney(editingPayment.amount)} இலிருந்து ${formatMoney(newAmt)} ஆக மாற்றப்பட்டது!`
          : `Amount corrected from ${formatMoney(editingPayment.amount)} to ${formatMoney(newAmt)}! Customer balance updated.`,
        "success"
      );
      setEditingPayment(null);
      setCorrectedAmount("");
      setCorrectionReason("");
      refreshBalance(true);
      loadRecentPayments(String(customer.id));
      window.dispatchEvent(new CustomEvent("refresh-customer-data"));
    } catch (err: unknown) {
      showToast("Failed to correct payment: " + (err instanceof Error ? err.message : String(err)), "error");
    }
  };

  // Payment Void (Manager/Owner only)
  const handleVoidPayment = async (paymentId: string, oldAmt: number) => {
    const reason = window.prompt(
      lang === "ta"
        ? `${formatMoney(oldAmt)} கட்டணத்தை ரத்து செய்து கடன் கணக்கை மீட்டமைக்க காரணம் உள்ளிடவும்:`
        : `Enter reason to void payment of ${formatMoney(oldAmt)} and restore customer debt:`
    );
    if (!reason || !reason.trim()) return;

    try {
      await api.post(
        "/payments/void",
        { payment_id: paymentId, reason: reason.trim() },
        token,
      );
      speak("Payment voided and balance restored", "கட்டணம் ரத்து செய்யப்பட்டு கணக்கு மீட்டமைக்கப்பட்டது");
      showToast(
        lang === "ta"
          ? `${formatMoney(oldAmt)} கட்டணம் ரத்து செய்யப்பட்டது. கடன் மீட்டமைக்கப்பட்டது.`
          : `Payment of ${formatMoney(oldAmt)} voided. Customer debt balance restored.`,
        "success"
      );
      refreshBalance(true);
      loadRecentPayments(String(customer.id));
      window.dispatchEvent(new CustomEvent("refresh-customer-data"));
    } catch (err: unknown) {
      showToast("Failed to void payment: " + (err instanceof Error ? err.message : String(err)), "error");
    }
  };

  const filteredCustomers = customers.filter(
    (c) =>
      c.name.toLowerCase().includes(query.toLowerCase()) ||
      c.phone.includes(query),
  );

  const numEnteredAmt = Number(amount) || 0;
  const numEnteredCans = Number(canQty) || 0;
  const projectedBalance = Math.max(0, customer.balance - numEnteredAmt);
  const projectedCans = Math.max(0, customer.cans - numEnteredCans);

  // Primary button label determination
  let buttonLabel = lang === "ta" ? "வரவு சேமிக்க (Record Settlement)" : "RECORD SETTLEMENT";
  if (saving) {
    buttonLabel = lang === "ta" ? "சேமிக்கப்படுகிறது..." : "Recording...";
  } else if (statusState === "unknown") {
    buttonLabel = lang === "ta" ? "பதிவானதா என சரிபார்க்கவும் (Check whether it saved)" : "Check whether it saved";
  } else if (partialFailure?.failed === "cans") {
    buttonLabel = lang === "ta"
      ? `காலிகேன் மட்டும் மீண்டும் பதிவு செய் (${canQty || 0} கேன்கள்)`
      : `RETRY RECORDING CANS ONLY (${canQty || 0} Cans)`;
  } else if (partialFailure?.failed === "money") {
    buttonLabel = lang === "ta"
      ? `பணம் மட்டும் மீண்டும் பதிவு செய் (${formatMoney(numEnteredAmt)})`
      : `RETRY RECORDING PAYMENT ONLY (${formatMoney(numEnteredAmt)})`;
  } else if (numEnteredAmt > 0 && numEnteredCans > 0) {
    buttonLabel = lang === "ta"
      ? `பணம் ${formatMoney(numEnteredAmt)} & ${numEnteredCans} கேன்கள் வரவு சேமி`
      : `RECORD ${formatMoney(numEnteredAmt)} & ${numEnteredCans} CANS`;
  } else if (numEnteredAmt > 0) {
    buttonLabel = lang === "ta"
      ? `பணம் வரவு சேமிக்க (${formatMoney(numEnteredAmt)})`
      : `RECORD PAYMENT OF ${formatMoney(numEnteredAmt)}`;
  } else if (numEnteredCans > 0) {
    buttonLabel = lang === "ta"
      ? `${numEnteredCans} காலிகேன்கள் வரவு சேமிக்க`
      : `RECORD ${numEnteredCans} EMPTY CANS`;
  }

  const isButtonDisabled =
    saving ||
    (statusState !== "unknown" &&
      partialFailure?.failed !== "cans" &&
      partialFailure?.failed !== "money" &&
      numEnteredAmt <= 0 &&
      numEnteredCans <= 0);

  return (
    <div className="workflow-page payments-page">
      <div className="page-title compact" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <p className="eyebrow">{t("payReturn")}</p>
          <h1>{lang === "ta" ? "வசூல் & காலிகேன் வரவு (Pay & Can Settlement)" : "Pay & Empty Cans Settlement"}</h1>
        </div>
      </div>

      <section className="payments-layout">
        {/* Left Column: Customer Picker */}
        <div className="workflow-card customer-picker-card">
          <label className="customer-search-box">
            <Icon name="search" size={18} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("findCustomer")}
            />
            {query && (
              <button className="clear-search-btn" onClick={() => setQuery("")}>✕</button>
            )}
          </label>
          <div className="choice-list inside-scroll">
            {filteredCustomers.map((c) => (
              <button
                className={`customer-item-btn ${customer.id === c.id ? "selected" : ""}`}
                key={String(c.id)}
                onClick={() => {
                  setCustomer(c);
                  setSelectedInvoice(null);
                  setPartialFailure(null);
                  setStatusState("idle");
                }}
              >
                <span className="cust-info">
                  <b>{c.name}</b>
                  <small>{c.phone}</small>
                </span>
                <div style={{ textAlign: "right" }}>
                  <strong className={c.balance > 0 ? "debt" : "credit"}>
                    {formatMoney(Math.abs(c.balance))}
                  </strong>
                  {c.cans > 0 && <small style={{ display: "block", color: "#64748b" }}>{c.cans} cans</small>}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Right Column: Unified Form with Money + Cans Together */}
        <div className="workflow-card amount-card inside-scroll">
          {/* Customer Summary Banner with Instant Refresh Button */}
          <div className="selected-item-banner" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f8fafc", padding: "10px 14px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <div>
              <b style={{ fontSize: 17, color: "#0f172a" }}>{customer.name}</b>
              <small style={{ display: "block", marginTop: 2, color: "#64748b" }}>
                {customer.phone} {customer.address ? `• ${customer.address}` : ""}
              </small>
            </div>
            <div style={{ textAlign: "right", display: "flex", alignItems: "center", gap: 14 }}>
              <div>
                <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>{lang === "ta" ? "தற்போதைய கடன்:" : "Current Debt:"}</div>
                <strong style={{ fontSize: 19, color: customer.balance > 0 ? "#b45309" : "#15803d" }}>
                  {formatMoney(Math.abs(customer.balance))} {customer.balance > 0 ? (lang === "ta" ? "(கடன்)" : "(Debt)") : (lang === "ta" ? "(வரவு)" : "(Credit)")}
                </strong>
                <div style={{ fontSize: 12, color: "#0284c7", fontWeight: 700, marginTop: 1 }}>
                  {customer.cans} {lang === "ta" ? "கேன்கள் கைவசம்" : "cans held"}
                </div>
              </div>
              <button
                type="button"
                onClick={() => refreshBalance(false)}
                disabled={refreshingBalance}
                title={lang === "ta" ? "இருப்பை மீண்டும் சரிபார்க்க" : "Refresh customer balance from database"}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  borderRadius: 6,
                  border: "1px solid #cbd5e1",
                  background: "#ffffff",
                  color: "#334155",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                }}
              >
                <Icon name="refresh" size={13} className={refreshingBalance ? "spinning" : ""} />
                <span>{refreshingBalance ? "..." : (lang === "ta" ? "சரிபார்" : "Refresh")}</span>
              </button>
            </div>
          </div>

          {/* Partial Failure Warning Banner if applicable */}
          {partialFailure && (
            <div style={{ marginTop: 10, padding: "10px 12px", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 8, color: "#92400e" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 13 }}>
                <Icon name="warning" size={16} />
                <span>
                  {partialFailure.failed === "cans"
                    ? (lang === "ta" ? `பணம் ${formatMoney(partialFailure.savedAmount)} சேமிக்கப்பட்டது! காலிகேன் பதிவு தோல்வியடைந்தது: ${partialFailure.error}` : `Payment of ${formatMoney(partialFailure.savedAmount)} saved! Can return failed: ${partialFailure.error}`)
                    : (lang === "ta" ? `${partialFailure.savedCans} கேன்கள் பதிவு செய்யப்பட்டது! பணம் சேமிப்பு தோல்வியடைந்தது: ${partialFailure.error}` : `${partialFailure.savedCans} cans returned! Payment failed: ${partialFailure.error}`)}
                </span>
              </div>
              <small style={{ display: "block", marginTop: 2, color: "#78350f", fontSize: 11 }}>
                {lang === "ta"
                  ? "ஏற்கனவே சேமிக்கப்பட்ட பகுதி மீண்டும் சேர்க்கப்படாது. தோல்வியடைந்த பகுதியை மட்டும் மீண்டும் சேமிக்க கீழே உள்ள பொத்தானை அழுத்தவும்."
                  : "The saved portion will not be double-charged. You can retry the failed action below without duplicate entries."}
              </small>
            </div>
          )}

          {/* UNIFIED SETTLEMENT FORM: Money and Cans Together in One View (Side-by-side on laptop) */}
          <div className="unified-settlement-form" style={{ marginTop: 12, display: "grid", gap: 12 }}>
            <div className="settlement-grid-2col">
              {/* SECTION 1: MONEY RECEIVED */}
              <div
                className="settlement-section money-section"
                style={{
                  background: partialFailure?.failed === "cans" ? "#f1f5f9" : "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: 8,
                  padding: "12px",
                  opacity: partialFailure?.failed === "cans" ? 0.7 : 1,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <label style={{ fontSize: 14, fontWeight: 800, color: "#1e293b", display: "flex", alignItems: "center", gap: 6 }}>
                    <Icon name="cash" size={18} />
                    <span>{lang === "ta" ? "1. பணம் வரவு (Money Rs.)" : "1. Money Received (Rs.)"}</span>
                  </label>
                  {partialFailure?.failed === "cans" && (
                    <span style={{ fontSize: 11, color: "#15803d", fontWeight: 700 }}>✓ {lang === "ta" ? "சேமிக்கப்பட்டது" : "Saved"}</span>
                  )}
                </div>

                <div className="large-cash-box" style={{ maxWidth: "100%", padding: "6px 12px" }}>
                  <span className="cash-box-prefix">Rs.</span>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0"
                    disabled={partialFailure?.failed === "cans"}
                    style={{ fontSize: 18 }}
                  />
                </div>

                {numEnteredAmt > 0 && (
                  <div style={{ marginTop: 6, fontSize: 12, color: "#15803d", fontWeight: 700, background: "#f0fdf4", padding: "4px 8px", borderRadius: 4, border: "1px solid #bbf7d0" }}>
                    {lang === "ta"
                      ? `கடன்: ${formatMoney(customer.balance)} − ${formatMoney(numEnteredAmt)} = ${formatMoney(projectedBalance)}`
                      : `Debt: ${formatMoney(customer.balance)} − ${formatMoney(numEnteredAmt)} = ${formatMoney(projectedBalance)}`}
                  </div>
                )}

                {/* Payment Method Selector (Cash & Bank Only for New Entries) */}
                <div style={{ marginTop: 8 }}>
                  <div style={{ display: "flex", gap: 6 }}>
                    {(["cash", "bank"] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        disabled={partialFailure?.failed === "cans"}
                        onClick={() => setPaymentMethod(m)}
                        style={{
                          flex: 1,
                          padding: "8px 6px",
                          borderRadius: 6,
                          border: paymentMethod === m ? "2px solid #0284c7" : "1px solid #cbd5e1",
                          background: paymentMethod === m ? "#e0f2fe" : "#ffffff",
                          fontWeight: paymentMethod === m ? 800 : 600,
                          cursor: partialFailure?.failed === "cans" ? "not-allowed" : "pointer",
                          textTransform: "uppercase",
                          fontSize: 12,
                          color: paymentMethod === m ? "#0284c7" : "#475569",
                        }}
                      >
                        {m === "cash" ? (lang === "ta" ? "ரொக்கம் (Cash)" : "Cash") : (lang === "ta" ? "வங்கி (Bank)" : "Bank")}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Memo/Notes Input */}
                <div style={{ marginTop: 8 }}>
                  <input
                    type="text"
                    disabled={partialFailure?.failed === "cans"}
                    placeholder={lang === "ta" ? "குறிப்பு (GPay எண் / காசோலை)" : "Memo / Ref (e.g. GPay ref #)"}
                    value={moneyNotes}
                    onChange={(e) => setMoneyNotes(e.target.value)}
                    style={{ width: "100%", padding: "6px 10px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: 12 }}
                  />
                </div>
              </div>

              {/* SECTION 2: EMPTY CANS RECEIVED */}
              <div
                className="settlement-section cans-section"
                style={{
                  background: partialFailure?.failed === "money" ? "#f1f5f9" : "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: 8,
                  padding: "12px",
                  opacity: partialFailure?.failed === "money" ? 0.7 : 1,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <label style={{ fontSize: 14, fontWeight: 800, color: "#1e293b", display: "flex", alignItems: "center", gap: 6 }}>
                    <Icon name="can" size={18} />
                    <span>{lang === "ta" ? "2. காலிகேன் வரவு (19L Cans)" : "2. Empty Cans Returned"}</span>
                  </label>
                  {partialFailure?.failed === "money" && (
                    <span style={{ fontSize: 11, color: "#15803d", fontWeight: 700 }}>✓ {lang === "ta" ? "சேமிக்கப்பட்டது" : "Saved"}</span>
                  )}
                </div>

                <div className="large-cash-box" style={{ maxWidth: "100%", padding: "6px 12px" }}>
                  <Icon name="can" size={18} />
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={canQty}
                    onChange={(e) => setCanQty(e.target.value)}
                    placeholder="0"
                    disabled={partialFailure?.failed === "money"}
                    style={{ fontSize: 18 }}
                  />
                </div>

                {numEnteredCans > 0 && (
                  <div style={{ marginTop: 6, fontSize: 12, color: "#0284c7", fontWeight: 700, background: "#f0f9ff", padding: "4px 8px", borderRadius: 4, border: "1px solid #bae6fd" }}>
                    {lang === "ta"
                      ? `கைவசம்: ${customer.cans} − வரவு: ${numEnteredCans} = மீதம்: ${projectedCans} கேன்கள்`
                      : `Held: ${customer.cans} − Return: ${numEnteredCans} = Remaining: ${projectedCans} cans`}
                  </div>
                )}

                {/* Can Notes Input */}
                <div style={{ marginTop: 8 }}>
                  <input
                    type="text"
                    disabled={partialFailure?.failed === "money"}
                    placeholder={lang === "ta" ? "கேன் குறிப்பு (ஓட்டுநர் வழி)" : "Can notes (e.g. via driver)"}
                    value={canNotes}
                    onChange={(e) => setCanNotes(e.target.value)}
                    style={{ width: "100%", padding: "6px 10px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: 12 }}
                  />
                </div>
              </div>
            </div>

            {/* ONE PROMINENT ACTION BUTTON */}
            <button
              type="button"
              className="primary-action"
              onClick={submitSettlement}
              disabled={isButtonDisabled}
              style={{
                width: "100%",
                padding: "13px",
                fontSize: 15,
                fontWeight: 900,
                borderRadius: 8,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                cursor: isButtonDisabled ? "not-allowed" : "pointer",
                background: statusState === "unknown" ? "#f59e0b" : "#0284c7",
                color: "#ffffff",
                boxShadow: "0 2px 8px rgba(2, 132, 199, 0.25)",
              }}
            >
              <Icon name={statusState === "unknown" ? "refresh" : "check"} size={18} />
              <span>{buttonLabel}</span>
            </button>
          </div>

          {/* GOODS RETURN & INVOICE CANCELLATION (Collapsible Drawer) */}
          <div style={{ marginTop: 24, borderTop: "2px solid #e2e8f0", paddingTop: 14 }}>
            <button
              type="button"
              onClick={() => setShowGoodsReturn(!showGoodsReturn)}
              style={{
                width: "100%",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "10px 14px",
                background: showGoodsReturn ? "#f8fafc" : "#f1f5f9",
                border: "1px solid #cbd5e1",
                borderRadius: 8,
                fontWeight: 700,
                color: "#334155",
                fontSize: 14,
                cursor: "pointer",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Icon name="return" size={18} />
                <span>{lang === "ta" ? "சரக்கு திருப்புதல் & பில் ரத்து (Goods Return & Invoice Cancellation)" : "Goods Return & Invoice Cancellation"}</span>
              </span>
              <span>{showGoodsReturn ? "▲" : "▼"}</span>
            </button>

            {showGoodsReturn && (
              <div style={{ marginTop: 14, padding: "16px", background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                {!isManagerOrOwner ? (
                  <div style={{ padding: 14, background: "#fffbeb", border: "1px solid #fef3c7", borderRadius: 8, color: "#92400e" }}>
                    <Icon name="warning" size={20} />
                    <b style={{ marginLeft: 8 }}>
                      {lang === "ta" ? "அனுமதி தேவை: சரக்கு திருப்புதல் & பில் ரத்து செய்ய மேலாளர் / உரிமையாளர் PIN தேவை." : "Permission Required: Only Owners and Managers can process item returns or cancel invoices."}
                    </b>
                  </div>
                ) : (
                  <>
                    <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
                      <input
                        type="text"
                        placeholder={lang === "ta" ? "இன்வாய்ஸ் எண் தேடுக (எ.கா. INV-202611-0001)" : "Enter Invoice Number (e.g. INV-202611-0001)"}
                        value={invoiceQuery}
                        onChange={(e) => setInvoiceQuery(e.target.value)}
                        style={{ flex: 1, padding: "10px 12px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                      />
                      <button
                        type="button"
                        onClick={handleSearchInvoice}
                        disabled={loadingInvoice || !invoiceQuery.trim()}
                        style={{ padding: "10px 16px", borderRadius: 8, background: "#0284c7", color: "#fff", border: "none", fontWeight: 700, cursor: "pointer" }}
                      >
                        {loadingInvoice ? "..." : (lang === "ta" ? "தேடு" : "Find Invoice")}
                      </button>
                    </div>

                    {selectedInvoice && (
                      <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: 14 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10, borderBottom: "1px solid #e2e8f0", paddingBottom: 8 }}>
                          <div>
                            <b style={{ fontSize: 16 }}>{selectedInvoice.invoice_number}</b>
                            <small style={{ display: "block", color: "#64748b" }}>{selectedInvoice.date} • {selectedInvoice.customer_name}</small>
                          </div>
                          <div style={{ textAlign: "right" }}>
                            <b>{formatMoney(selectedInvoice.total)}</b>
                            <small style={{ display: "block", color: selectedInvoice.status === "cancelled" ? "#dc2626" : "#16a34a" }}>
                              {selectedInvoice.status.toUpperCase()}
                            </small>
                          </div>
                        </div>

                        {/* Items Return Sub-form */}
                        <h4 style={{ margin: "10px 0 6px 0", fontSize: 14, fontWeight: 700 }}>
                          {lang === "ta" ? "சரக்கு திருப்புதல் (Return Line Item):" : "Return Line Item:"}
                        </h4>
                        <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
                          <select
                            value={returnItemId}
                            onChange={(e) => setReturnItemId(e.target.value)}
                            style={{ padding: "8px 10px", borderRadius: 6, border: "1px solid #cbd5e1" }}
                          >
                            {selectedInvoice.items?.map((it: any) => (
                              <option key={it.sale_item_id} value={it.sale_item_id}>
                                {it.name} (Sold: {it.quantity}, Returned: {it.returned_quantity}) - {formatMoney(it.price)}
                              </option>
                            ))}
                          </select>
                          <div style={{ display: "flex", gap: 8 }}>
                            <input
                              type="number"
                              min="1"
                              value={returnQty}
                              onChange={(e) => setReturnQty(e.target.value)}
                              placeholder="Qty"
                              style={{ width: 100, padding: "8px 10px", borderRadius: 6, border: "1px solid #cbd5e1" }}
                            />
                            <input
                              type="text"
                              placeholder={lang === "ta" ? "காரணம் (Reason)" : "Reason for return"}
                              value={returnReason}
                              onChange={(e) => setReturnReason(e.target.value)}
                              style={{ flex: 1, padding: "8px 10px", borderRadius: 6, border: "1px solid #cbd5e1" }}
                            />
                          </div>
                          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
                            <input
                              type="checkbox"
                              checked={returnDamaged}
                              onChange={(e) => setReturnDamaged(e.target.checked)}
                            />
                            <span>{lang === "ta" ? "சேதமடைந்த சரக்கு (விற்பனை சரக்கில் சேர்க்க வேண்டாம்)" : "Damaged goods (do NOT return to sellable stock)"}</span>
                          </label>
                          <button
                            type="button"
                            onClick={submitItemReturn}
                            disabled={saving || !returnReason.trim()}
                            style={{ padding: "8px 14px", background: "#f59e0b", color: "#fff", border: "none", borderRadius: 6, fontWeight: 700, cursor: "pointer" }}
                          >
                            {saving ? "..." : (lang === "ta" ? "சரக்கு திருப்பத்தை உறுதி செய்" : "Confirm Item Return")}
                          </button>
                        </div>

                        {/* Cancel Whole Sale */}
                        <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 12, marginTop: 14 }}>
                          <h4 style={{ margin: "0 0 6px 0", fontSize: 14, fontWeight: 700, color: "#b91c1c" }}>
                            {lang === "ta" ? "முழு பில்லை ரத்து செய் (Cancel Whole Invoice):" : "Cancel Entire Invoice:"}
                          </h4>
                          <div style={{ display: "flex", gap: 8 }}>
                            <input
                              type="text"
                              placeholder={lang === "ta" ? "பில் ரத்து செய்ய காரணம்..." : "Cancellation reason..."}
                              value={cancelReason}
                              onChange={(e) => setCancelReason(e.target.value)}
                              style={{ flex: 1, padding: "8px 10px", borderRadius: 6, border: "1px solid #cbd5e1" }}
                            />
                            <button
                              type="button"
                              onClick={submitSaleCancellation}
                              disabled={saving || !cancelReason.trim()}
                              style={{ padding: "8px 14px", background: "#ef4444", color: "#fff", border: "none", borderRadius: 6, fontWeight: 700, cursor: "pointer" }}
                            >
                              {saving ? "..." : (lang === "ta" ? "பில் ரத்து செய்" : "Cancel Bill")}
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Recent Payments & Mistake Correction Section */}
          <div className="mistake-correction-section" style={{ marginTop: 24, paddingTop: 18, borderTop: "2px solid #e2e8f0" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>
                  {lang === "ta" ? "சமீபத்திய கட்டணங்கள் & தணிக்கை" : "Recent Payments & Audit Log"}
                </h3>
                <small style={{ color: "#64748b" }}>
                  {isManagerOrOwner
                    ? (lang === "ta" ? "தவறாக உள்ளிட்ட தொகையை மாற்ற அல்லது ரத்து செய்ய" : "Authorized: Correct mistyped amounts or void entries")
                    : (lang === "ta" ? "பார்வைக்கு மட்டும் (தொகை மாற்ற மேலாளர் PIN தேவை)" : "Read-only: Manager/Owner PIN required to edit or void")}
                </small>
              </div>
            </div>

            {/* Inline Modal for Mistake Correction */}
            {editingPayment && isManagerOrOwner && (
              <div className="correction-box-active" style={{ background: "#fefce8", border: "2px solid #facc15", borderRadius: 10, padding: 14, marginBottom: 14 }}>
                <b style={{ color: "#854d0e", display: "block", marginBottom: 6 }}>
                  {lang === "ta" ? "தவறான தொகையை திருத்துக (Mistake Correction):" : "Correct Mistaken Payment:"}
                </b>
                <p style={{ margin: "4px 0", fontSize: 13, color: "#713f12" }}>
                  {lang === "ta" ? `தற்போது பதிவாகியுள்ளது: ${formatMoney(editingPayment.amount)}` : `Currently entered: ${formatMoney(editingPayment.amount)}`}
                </p>
                <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <div className="large-cash-box" style={{ flex: 1, padding: "6px 12px" }}>
                      <span className="cash-box-prefix">Rs.</span>
                      <input
                        type="number"
                        value={correctedAmount}
                        onChange={(e) => setCorrectedAmount(e.target.value)}
                        placeholder="e.g. 2000"
                        autoFocus
                      />
                    </div>
                    <select
                      value={correctedMethod}
                      onChange={(e) => setCorrectedMethod(e.target.value)}
                      style={{ padding: "10px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                    >
                      <option value="cash">CASH</option>
                      <option value="upi">UPI</option>
                      <option value="bank">BANK</option>
                      <option value="cheque">CHEQUE</option>
                    </select>
                  </div>
                  <input
                    type="text"
                    placeholder={lang === "ta" ? "காரணம் (Reason for correction - required)" : "Reason for correction (required)"}
                    value={correctionReason}
                    onChange={(e) => setCorrectionReason(e.target.value)}
                    style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #cbd5e1" }}
                  />
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      className="btn-primary-small"
                      onClick={handleSaveCorrection}
                      disabled={!correctedAmount || !correctionReason.trim()}
                      style={{ padding: "8px 16px", background: "#16a34a", color: "#fff", border: "none", borderRadius: 6, fontWeight: 800, cursor: "pointer" }}
                    >
                      {lang === "ta" ? "திருத்தத்தை சேமி" : "Save Correction"}
                    </button>
                    <button
                      type="button"
                      className="btn-cancel"
                      onClick={() => { setEditingPayment(null); setCorrectedAmount(""); setCorrectionReason(""); }}
                      style={{ padding: "8px 14px", borderRadius: 6, cursor: "pointer" }}
                    >
                      {lang === "ta" ? "ரத்து" : "Cancel"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="recent-payments-list">
              {recentPayments.length > 0 ? (
                recentPayments.map((p) => (
                  <div
                    key={p.payment_id}
                    className="recent-payment-card"
                    style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, marginBottom: 8 }}
                  >
                    <div>
                      <div style={{ fontWeight: 800, fontSize: 15, color: "#0f172a" }}>
                        {formatMoney(Number(p.amount))}
                        <span style={{ fontSize: 12, marginLeft: 8, color: "#64748b", fontWeight: 600 }}>({p.payment_method?.toUpperCase() || p.method?.toUpperCase() || "CASH"})</span>
                      </div>
                      <small style={{ color: "#64748b" }}>
                        {p.payment_date} • {new Date(p.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        {p.notes ? ` • ${p.notes}` : ""}
                      </small>
                    </div>
                    {isManagerOrOwner ? (
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          type="button"
                          className="btn-correct-mistake"
                          onClick={() => {
                            setEditingPayment(p);
                            setCorrectedAmount(String(p.amount));
                            setCorrectedMethod(p.payment_method || p.method?.toLowerCase() || "cash");
                          }}
                          style={{ background: "#fef3c7", color: "#92400e", border: "1px solid #fde68a", padding: "6px 10px", borderRadius: 6, fontWeight: 700, fontSize: 12, cursor: "pointer" }}
                        >
                          ✏️ {lang === "ta" ? "திருத்து" : "Correct"}
                        </button>
                        <button
                          type="button"
                          className="btn-void-mistake"
                          onClick={() => handleVoidPayment(p.payment_id, Number(p.amount))}
                          style={{ background: "#fee2e2", color: "#b91c1c", border: "1px solid #fecaca", padding: "6px 10px", borderRadius: 6, fontWeight: 700, fontSize: 12, cursor: "pointer" }}
                        >
                          🗑️ {lang === "ta" ? "ரத்து செய்" : "Void"}
                        </button>
                      </div>
                    ) : (
                      <span style={{ fontSize: 12, color: "#94a3b8" }}>🔒 Confirmed</span>
                    )}
                  </div>
                ))
              ) : (
                <div style={{ padding: 14, textAlign: "center", color: "#94a3b8", background: "#f8fafc", borderRadius: 8 }}>
                  <small>{lang === "ta" ? "சமீபத்திய கட்டணங்கள் எதுவும் இல்லை" : "No recent payments recorded for this customer"}</small>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
