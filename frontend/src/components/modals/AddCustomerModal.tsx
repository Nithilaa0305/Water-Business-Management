import { useState, useEffect, type FormEvent } from "react";
import { useApp } from "../../context/AppContext";
import { api } from "../../services/api";
import type { Customer, Role } from "../../types";
import { Icon } from "../Icon";

export function AddCustomerModal({
  isOpen,
  onClose,
  onSuccess,
  token,
  role = "employee",
}: {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newCust: Customer) => void;
  token: string;
  role?: Role;
}) {
  const { lang, speak } = useApp();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [area, setArea] = useState("");
  const [creditLimit, setCreditLimit] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Clear fields whenever modal opens
  useEffect(() => {
    if (isOpen) {
      setName("");
      setPhone("");
      setAddress("");
      setArea("");
      setCreditLimit("");
      setNotes("");
      setError("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !phone.trim()) {
      setError(lang === "ta" ? "பெயர் மற்றும் தொலைபேசி தேவை" : "Name and Phone are required");
      return;
    }
    setLoading(true);
    setError("");
    const isManagerOrOwner = role === "owner" || role === "manager";
    const numericCreditLimit = isManagerOrOwner ? (Number(creditLimit) || 0) : 0;
    try {
      const res = await api.post<{ customer_id?: string; id?: string }>(
        "/customers/create",
        {
          name: name.trim(),
          phone: phone.trim(),
          address: address.trim(),
          area_id: area.trim() || "Central",
          credit_limit: numericCreditLimit,
          notes: notes.trim(),
        },
        token
      );
      speak("Customer created", "புதிய வாடிக்கையாளர் சேர்க்கப்பட்டார்");
      const createdCustomer: Customer = {
        id: res?.customer_id || res?.id || String(Date.now()),
        name: name.trim(),
        phone: phone.trim(),
        address: address.trim(),
        balance: 0,
        cans: 0,
        credit_limit: numericCreditLimit,
      };
      // Reset form on success
      setName("");
      setPhone("");
      setAddress("");
      setArea("");
      setCreditLimit("");
      setNotes("");
      onSuccess(createdCustomer);
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create customer";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog">
        <div className="modal-header">
          <h3>
            <Icon name="user" size={20} />
            {lang === "ta" ? "புதிய வாடிக்கையாளர் சேர்க்க" : "Add New Customer"}
          </h3>
          <button className="modal-close-btn" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="modal-error">{error}</div>}
          <label>
            <span>{lang === "ta" ? "வாடிக்கையாளர் பெயர் *" : "Customer Name *"}</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={lang === "ta" ? "எ.கா. ராஜா ஸ்டோர்ஸ்" : "e.g. Raja Stores"}
              autoFocus
            />
          </label>
          <label>
            <span>{lang === "ta" ? "தொலைபேசி எண் *" : "Phone Number *"}</span>
            <input
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="077-XXXXXXX / 9840XXXXXX"
            />
          </label>
          <div className="modal-grid-2">
            <label>
              <span>{lang === "ta" ? "பகுதி / வழித்தடம்" : "Area / Route"}</span>
              <input
                value={area}
                onChange={(e) => setArea(e.target.value)}
                placeholder="Market / Main Road"
              />
            </label>
            <label>
              <span>{lang === "ta" ? "கடன் வரம்பு (Rs.)" : "Credit Limit (Rs.)"}</span>
              <input
                type="number"
                value={creditLimit}
                onChange={(e) => setCreditLimit(e.target.value)}
                placeholder={role === "employee" ? "0 (Manager only)" : "0"}
                disabled={role === "employee"}
              />
              {role === "employee" && (
                <small style={{ color: "#94a3b8", fontSize: 11 }}>
                  {lang === "ta" ? "கடன் வரம்பு நிர்ணயிக்க மேலாளர் PIN தேவை" : "Manager PIN required to set credit limit"}
                </small>
              )}
            </label>
          </div>
          <label>
            <span>{lang === "ta" ? "முகவரி" : "Address"}</span>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder={lang === "ta" ? "கடை முகவரி" : "Shop / street address"}
            />
          </label>
          <label>
            <span>{lang === "ta" ? "குறிப்பு" : "Notes"}</span>
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Morning delivery"
            />
          </label>
          <div className="modal-actions">
            <button type="button" className="btn-cancel" onClick={onClose}>
              {lang === "ta" ? "ரத்து" : "Cancel"}
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "..." : (lang === "ta" ? "வாடிக்கையாளரை சேமி" : "Save Customer")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
