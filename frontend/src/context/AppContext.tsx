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
    if (!voice) return;
    const preferredLanguage = lang === "ta" ? "ta-IN" : "en-IN";
    const speech = window.speechSynthesis;
    const available = speech?.getVoices().filter((speaker) => speaker.localService) || [];
    const speaker = available.find((option) => option.lang === preferredLanguage) ||
      available.find((option) => option.lang.toLowerCase().startsWith(lang + "-"));
    if (speaker) {
      speech.cancel();
      const message = new SpeechSynthesisUtterance(lang === "ta" ? taText : enText);
      message.voice = speaker;
      message.lang = speaker.lang;
      message.rate = 0.88;
      speech.speak(message);
    } else if (typeof AudioContext !== "undefined" && navigator.userActivation?.hasBeenActive) {
      const audio = new AudioContext();
      const tone = audio.createOscillator();
      const volume = audio.createGain();
      const now = audio.currentTime;
      tone.frequency.value = 660;
      volume.gain.setValueAtTime(0.1, now);
      volume.gain.exponentialRampToValueAtTime(0.001, now + 0.16);
      tone.connect(volume).connect(audio.destination);
      tone.start(now);
      tone.stop(now + 0.16);
      tone.onended = () => { void audio.close().catch(() => {}); };
    }
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
