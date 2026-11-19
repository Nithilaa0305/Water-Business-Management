import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import en from "../locales/en.json";
import ta from "../locales/ta.json";
import type { AppContextValue, Lang, Toast, ToastType } from "../types";

const AppContext = createContext<AppContextValue | null>(null);

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem("language") as Lang) || "ta");
  const [voice, setVoice] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dictionary = lang === "ta" ? ta : en;

  useEffect(() => {
    localStorage.setItem("language", lang);
  }, [lang]);

  const t = (key: keyof typeof en) => (dictionary as Record<string, string>)[key] ?? key;

  const speak = (enText: string, taText: string) => {
    if (!voice || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const message = new SpeechSynthesisUtterance(lang === "ta" ? taText : enText);
    message.lang = lang === "ta" ? "ta-IN" : "en-IN";
    message.rate = 0.88;
    window.speechSynthesis.speak(message);
  };

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((message: string, type: ToastType = "success") => {
    const id = "toast-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6);
    const newToast: Toast = { id, type, message };
    setToasts((prev) => [...prev, newToast]);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  return (
    <AppContext.Provider value={{ lang, setLang, voice, setVoice, t, speak, showToast }}>
      {children}

      {/* Floating Toast Notification Container (Overlay - does not move page content) */}
      <div className="floating-toast-container" aria-live="polite">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`floating-toast ${toast.type}`}
            role="status"
          >
            <span className="toast-icon">
              {toast.type === "success" ? "✓" : toast.type === "error" ? "⚠" : "ℹ"}
            </span>
            <span className="toast-message">{toast.message}</span>
            <button
              type="button"
              className="toast-close-btn"
              onClick={() => removeToast(toast.id)}
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </AppContext.Provider>
  );
}
