import { useState, useEffect, type FormEvent } from "react";
import { useApp } from "../../context/AppContext";
import { api } from "../../services/api";
import type { Product, Role } from "../../types";
import { Icon } from "../Icon";

export function AddProductModal({
  isOpen,
  onClose,
  token,
  role = "employee",
  onSuccess,
}: {
  isOpen: boolean;
  onClose: () => void;
  token: string;
  role?: Role;
  onSuccess: (newProd: Product) => void;
}) {
  const { lang, speak } = useApp();
  const [name, setName] = useState("");
  const [taName, setTaName] = useState("");
  const [sku, setSku] = useState("");
  const [unit, setUnit] = useState("bottle");
  const [sellingPrice, setSellingPrice] = useState("");
  const [buyingPrice, setBuyingPrice] = useState("");
  const [initialStock, setInitialStock] = useState("");
  const [isReturnable, setIsReturnable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isManagerOrOwner = role === "owner" || role === "manager";

  // Clear fields whenever modal opens
  useEffect(() => {
    if (isOpen) {
      setName("");
      setTaName("");
      setSku("");
      setUnit("bottle");
      setSellingPrice("");
      setBuyingPrice("");
      setInitialStock("");
      setIsReturnable(false);
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError(lang === "ta" ? "பொருளின் பெயர் தேவை" : "Product name is required");
      return;
    }
    const sPrice = Number(sellingPrice);
    if (isNaN(sPrice) || sPrice < 0) {
      setError(lang === "ta" ? "விற்பனை விலை 0 அல்லது அதற்கு மேல் இருக்க வேண்டும்" : "Selling price must be greater than or equal to 0");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload: Record<string, any> = {
        name: name.trim(),
        selling_price: sPrice,
        unit,
        is_returnable: isReturnable,
      };

      if (sku.trim()) {
        payload.sku = sku.trim();
      }

      if (isManagerOrOwner) {
        if (buyingPrice.trim()) payload.buying_price = Number(buyingPrice) || 0;
        if (initialStock.trim()) payload.initial_stock = Number(initialStock) || 0;
      }

      const res = await api.post<{ status: string; type_id: string; sku?: string; message: string }>(
        "/products/create",
        payload,
        token
      );

      speak("Product created successfully", "புதிய பொருள் சேர்க்கப்பட்டது");
      onSuccess({
        id: Date.now(),
        type_id: res.type_id,
        name: name.trim(),
        ta: taName.trim() || name.trim(),
        price: sPrice,
        stock: isManagerOrOwner ? (Number(initialStock) || 0) : 0,
        unit,
        icon: isReturnable || unit === "can" ? "can" : "bottle",
        is_returnable: isReturnable,
        buying_price: isManagerOrOwner && buyingPrice.trim() ? Number(buyingPrice) : null,
      });
      window.dispatchEvent(new CustomEvent("refresh-stock-data"));

      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create product";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog add-product-modal-dialog" style={{ maxWidth: 540 }}>
        <div className="modal-header">
          <h3>
            <Icon name="bottle" size={20} />
            <span>{lang === "ta" ? "புதிய பொருள் சேர்க்க" : "Add New Product"}</span>
          </h3>
          <button className="modal-close-btn" onClick={onClose} type="button">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="modal-error">{error}</div>}

          {/* Section: Product Details */}
          <div className="form-section-header" style={{ fontWeight: 800, fontSize: 12, color: "#64748b", letterSpacing: 0.5, marginBottom: 8, textTransform: "uppercase" }}>
            {lang === "ta" ? "பொருள் விவரங்கள் (Product Details)" : "Product Details"}
          </div>

          <label>
            <span>{lang === "ta" ? "பொருள் பெயர் (ஆங்கிலம்) *" : "Product Name (English) *"}</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={lang === "ta" ? "எ.கா. 20L Water Can, 500ml Bottle" : "e.g. 20L Water Can, 500ml Bottle"}
              autoFocus
              required
            />
          </label>

          <label>
            <span>{lang === "ta" ? "தமிழ் பெயர் (விருப்பம்):" : "Tamil Name (Optional):"}</span>
            <input
              value={taName}
              onChange={(e) => setTaName(e.target.value)}
              placeholder="எ.கா. 20 லிட்டர் கேன்"
            />
          </label>

          <div className="modal-grid-2">
            <label>
              <span>{lang === "ta" ? "விற்பனை அலகு (Sold by) *" : "Sold by (Unit) *"}</span>
              <select
                value={unit}
                onChange={(e) => {
                  const u = e.target.value;
                  setUnit(u);
                  if (u === "can") setIsReturnable(true);
                }}
              >
                <option value="bottle">{lang === "ta" ? "Bottle (பாட்டில்)" : "Bottle"}</option>
                <option value="can">{lang === "ta" ? "Can (கேன்)" : "Can"}</option>
                <option value="pack">{lang === "ta" ? "Pack (பேக்)" : "Pack"}</option>
                <option value="case">{lang === "ta" ? "Case (பெட்டி)" : "Case"}</option>
                <option value="piece">{lang === "ta" ? "Piece (துண்டு / ஒற்றை)" : "Piece"}</option>
              </select>
            </label>

            <label>
              <span>{lang === "ta" ? "SKU குறியீடு (விருப்பம்):" : "SKU / Code (Optional):"}</span>
              <input
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                placeholder="e.g. SKU-WATER-20L"
              />
            </label>
          </div>

          {/* Section: Prices */}
          <div className="form-section-header" style={{ fontWeight: 800, fontSize: 12, color: "#64748b", letterSpacing: 0.5, marginTop: 16, marginBottom: 8, textTransform: "uppercase" }}>
            {lang === "ta" ? "விலை விவரங்கள் (Prices)" : "Prices"}
          </div>

          <div className="modal-grid-2">
            <label>
              <span>{lang === "ta" ? "விற்பனை விலை (வாடிக்கையாளர் செலுத்துவது) *" : "Selling Price (Customer pays) *"}</span>
              <div className="price-input-wrapper" style={{ display: "flex", alignItems: "center", border: "1px solid #cbd5e1", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
                <span style={{ padding: "8px 10px", background: "#f1f5f9", fontWeight: 700, color: "#475569", fontSize: 13, borderRight: "1px solid #cbd5e1" }}>Rs.</span>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={sellingPrice}
                  onChange={(e) => setSellingPrice(e.target.value)}
                  placeholder="0"
                  style={{ border: "none", outline: "none", padding: "8px 10px", flex: 1, fontSize: 14 }}
                  required
                />
                <span style={{ padding: "8px 10px", color: "#64748b", fontSize: 12 }}>/ {unit}</span>
              </div>
            </label>

            {isManagerOrOwner ? (
              <label>
                <span>{lang === "ta" ? "அடக்க விலை (கடை வாங்குவது):" : "Default Buying Cost (Shop pays):"}</span>
                <div className="price-input-wrapper" style={{ display: "flex", alignItems: "center", border: "1px solid #cbd5e1", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
                  <span style={{ padding: "8px 10px", background: "#f1f5f9", fontWeight: 700, color: "#475569", fontSize: 13, borderRight: "1px solid #cbd5e1" }}>Rs.</span>
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    value={buyingPrice}
                    onChange={(e) => setBuyingPrice(e.target.value)}
                    placeholder="0"
                    style={{ border: "none", outline: "none", padding: "8px 10px", flex: 1, fontSize: 14 }}
                  />
                  <span style={{ padding: "8px 10px", color: "#64748b", fontSize: 12 }}>/ {unit}</span>
                </div>
                <small style={{ color: "#64748b", fontSize: 11, display: "block", marginTop: 4 }}>
                  {lang === "ta" ? "லாப கணக்கீட்டிற்கு மட்டும் (மேலாளர் பார்வை)" : "Manager only for profit margin"}
                </small>
              </label>
            ) : (
              <div style={{ display: "flex", alignItems: "center", padding: "10px", background: "#f8fafc", borderRadius: 8, color: "#94a3b8", fontSize: 12 }}>
                🔒 {lang === "ta" ? "அடக்க விலை மேலாளருக்கு மட்டும்" : "Buying cost is manager only"}
              </div>
            )}
          </div>

          {/* Returnable Container Checkbox */}
          <div style={{ marginTop: 12, padding: "10px 12px", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", margin: 0 }}>
              <input
                type="checkbox"
                checked={isReturnable}
                onChange={(e) => setIsReturnable(e.target.checked)}
                style={{ width: 18, height: 18, cursor: "pointer" }}
              />
              <div>
                <b style={{ fontSize: 13, color: "#1e293b" }}>
                  {lang === "ta" ? "காலி கேன் திரும்பப் பெறும் பொருள் (Returnable Container)" : "Returnable Container (Track held / returned empties)"}
                </b>
                <small style={{ display: "block", color: "#64748b" }}>
                  {lang === "ta" ? "வாடிக்கையாளர் கைவசமுள்ள காலி கேன்களைக் கணக்கிடும்" : "Tracks empty container balances per customer"}
                </small>
              </div>
            </label>
          </div>

          {/* Initial Stock (Manager only) */}
          {isManagerOrOwner && (
            <div style={{ marginTop: 12 }}>
              <label>
                <span>{lang === "ta" ? "ஆரம்ப சரக்கு இருப்பு (விருப்பம்):" : "Initial Stock Quantity (Optional):"}</span>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={initialStock}
                  onChange={(e) => setInitialStock(e.target.value)}
                  placeholder="0"
                />
                <small style={{ color: "#64748b", fontSize: 11 }}>
                  {lang === "ta" ? "பொருள் உருவாக்கியதும் சரக்கு இருப்பில் உடனடியாக சேரும்" : "Added as initial batch in stock immediately upon creation"}
                </small>
              </label>
            </div>
          )}

          {/* Footer Actions */}
          <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
            <button type="button" className="btn-cancel" onClick={onClose}>
              {lang === "ta" ? "ரத்து" : "Cancel"}
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "..." : (lang === "ta" ? "பொருளை சேமி" : "Save Product")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
