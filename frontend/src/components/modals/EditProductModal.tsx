import { useState, useEffect, useRef, type FormEvent } from "react";
import { useApp } from "../../context/AppContext";
import { api } from "../../services/api";
import type { Product, Role } from "../../types";
import { Icon } from "../Icon";

export function EditProductModal({
  isOpen,
  onClose,
  product,
  token,
  role = "employee",
  initialFocusPrice = false,
  onUpdated,
  onDeleted,
}: {
  isOpen: boolean;
  onClose: () => void;
  product: Product | null;
  token: string;
  role?: Role;
  initialFocusPrice?: boolean;
  onUpdated: (updated: Product) => void;
  onDeleted?: (productId: number) => void;
}) {
  const { lang, speak } = useApp();
  const [name, setName] = useState("");
  const [taName, setTaName] = useState("");
  const [unit, setUnit] = useState("bottle");
  const [sellingPrice, setSellingPrice] = useState("");
  const [buyingPrice, setBuyingPrice] = useState("");
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const priceInputRef = useRef<HTMLInputElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const isManagerOrOwner = role === "owner" || role === "manager";

  useEffect(() => {
    if (product && isOpen) {
      setName(product.name || "");
      setTaName(product.ta || "");
      setUnit(product.unit || (product.icon === "can" || product.is_returnable ? "can" : "bottle"));
      setSellingPrice(product.price !== undefined ? String(product.price) : "");
      setBuyingPrice(
        product.buying_price !== null && product.buying_price !== undefined
          ? String(product.buying_price)
          : ""
      );
      setError(null);

      setTimeout(() => {
        if (initialFocusPrice && priceInputRef.current) {
          priceInputRef.current.focus();
          priceInputRef.current.select();
        } else if (nameInputRef.current) {
          nameInputRef.current.focus();
        }
      }, 50);
    }
  }, [product, isOpen, initialFocusPrice]);

  if (!isOpen || !product) return null;

  const handleUpdate = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError(lang === "ta" ? "பொருளின் பெயர் தேவை" : "Product name is required");
      return;
    }
    const sPrice = Number(sellingPrice);
    if (isNaN(sPrice) || sPrice < 0) {
      setError(lang === "ta" ? "சரியான விற்பனை விலையை உள்ளிடவும் (>= 0)" : "Enter a valid selling price (>= 0)");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload: Record<string, any> = {
        type_id: product.type_id || product.id,
        name: name.trim(),
        selling_price: sPrice,
      };

      if (isManagerOrOwner) {
        payload.buying_price = buyingPrice.trim() !== "" ? Number(buyingPrice) : null;
      }

      await api.post("/products/update", payload, token);

      speak("Product updated", "பொருள் விவரங்கள் மாற்றப்பட்டன");
      onUpdated({
        ...product,
        name: name.trim(),
        ta: taName.trim() || name.trim(),
        unit,
        price: sPrice,
        buying_price: isManagerOrOwner
          ? (buyingPrice.trim() !== "" ? Number(buyingPrice) : null)
          : product.buying_price,
      });
      window.dispatchEvent(new CustomEvent("refresh-stock-data"));
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update product");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!onDeleted) return;
    const confirmMsg = lang === "ta"
      ? `பொருள் '${product.name}' ஐ நிச்சயமாக நீக்க வேண்டுமா?`
      : `Are you sure you want to delete product '${product.name}'?`;
    if (!window.confirm(confirmMsg)) return;

    setDeleting(true);
    setError(null);
    try {
      await api.post("/products/delete", { type_id: product.type_id || product.id }, token);
      speak("Product deleted", "பொருள் நீக்கப்பட்டது");
      window.dispatchEvent(new CustomEvent("refresh-stock-data"));
      onDeleted(product.id);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete product");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog edit-product-modal-dialog" style={{ maxWidth: 540 }}>
        <div className="modal-header">
          <h3>
            <Icon name="edit" size={20} />
            <span>{lang === "ta" ? "பொருளை மாற்று" : "Edit Product"}</span>
          </h3>
          <button className="modal-close-btn" onClick={onClose} type="button">✕</button>
        </div>

        <form onSubmit={handleUpdate} className="modal-form">
          {error && <div className="modal-error">{error}</div>}

          {/* Section: Product Details */}
          <div className="form-section-header" style={{ fontWeight: 800, fontSize: 12, color: "#64748b", letterSpacing: 0.5, marginBottom: 8, textTransform: "uppercase" }}>
            {lang === "ta" ? "பொருள் விவரங்கள் (Product Details)" : "Product Details"}
          </div>

          <label>
            <span>{lang === "ta" ? "பொருள் பெயர் (ஆங்கிலம்) *" : "Product Name (English) *"}</span>
            <input
              ref={nameInputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. 500 ml Water"
              required
            />
          </label>

          <label>
            <span>{lang === "ta" ? "தமிழ் பெயர் (விருப்பம்):" : "Tamil Name (Optional):"}</span>
            <input
              value={taName}
              onChange={(e) => setTaName(e.target.value)}
              placeholder="எ.கா. 500மிலி தண்ணீர்"
            />
          </label>

          <div className="modal-grid-2">
            <label>
              <span>{lang === "ta" ? "விற்பனை அலகு (Sold by) *" : "Sold by (Unit) *"}</span>
              <select value={unit} onChange={(e) => setUnit(e.target.value)}>
                <option value="bottle">{lang === "ta" ? "Bottle (பாட்டில்)" : "Bottle"}</option>
                <option value="can">{lang === "ta" ? "Can (கேன்)" : "Can"}</option>
                <option value="pack">{lang === "ta" ? "Pack (பேக்)" : "Pack"}</option>
                <option value="case">{lang === "ta" ? "Case (பெட்டி)" : "Case"}</option>
                <option value="piece">{lang === "ta" ? "Piece (துண்டு / ஒற்றை)" : "Piece"}</option>
              </select>
            </label>

            <label>
              <span>{lang === "ta" ? "SKU குறியீடு:" : "SKU / Code:"}</span>
              <input
                value={product.sku || ""}
                disabled
                style={{ background: "#f8fafc", color: "#64748b" }}
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
                    ref={priceInputRef}
                    type="number"
                    min="0"
                    step="0.5"
                    value={buyingPrice}
                    onChange={(e) => setBuyingPrice(e.target.value)}
                    placeholder="Not set"
                    style={{ border: "none", outline: "none", padding: "8px 10px", flex: 1, fontSize: 14 }}
                  />
                  <span style={{ padding: "8px 10px", color: "#64748b", fontSize: 12 }}>/ {unit}</span>
                </div>
                <small style={{ color: "#64748b", fontSize: 11, display: "block", marginTop: 4 }}>
                  {lang === "ta" ? "புதிய வரவுகளுக்கு மட்டும். பழைய பேட்ச்களை மாற்றாது." : "For new batches. Never alters past batches or invoices."}
                </small>
              </label>
            ) : (
              <div style={{ display: "flex", alignItems: "center", padding: "10px", background: "#f8fafc", borderRadius: 8, color: "#94a3b8", fontSize: 12 }}>
                🔒 {lang === "ta" ? "அடக்க விலை மேலாளருக்கு மட்டும்" : "Buying cost is manager only"}
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="modal-actions" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20 }}>
            {onDeleted && isManagerOrOwner ? (
              <button
                type="button"
                className="btn-delete-profile"
                onClick={handleDelete}
                disabled={deleting || loading}
                style={{ padding: "8px 14px" }}
              >
                <Icon name="trash" size={15} />
                <span>{deleting ? "..." : (lang === "ta" ? "நீக்கு" : "Delete")}</span>
              </button>
            ) : <div />}

            <div style={{ display: "flex", gap: 10 }}>
              <button type="button" className="btn-cancel" onClick={onClose}>
                {lang === "ta" ? "ரத்து" : "Cancel"}
              </button>
              <button type="submit" className="btn-primary" disabled={loading || deleting}>
                {loading ? "..." : (lang === "ta" ? "மாற்றங்களைச் சேமி" : "Save Changes")}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
