import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import type { Role } from "../types";
import { Icon } from "../components/Icon";

export function Settings({ role }: { role: Role; onGoHome?: () => void }) {
  const { t, lang, setLang, voice, setVoice, speak, showToast } = useApp();
  const [printFormat, setPrintFormatState] = useState<"thermal" | "a4">("thermal");

  useEffect(() => {
    const saved = localStorage.getItem("preferred_print_format") as "thermal" | "a4";
    if (saved === "thermal" || saved === "a4") {
      setPrintFormatState(saved);
    }
  }, []);

  const handlePrintFormatChange = (fmt: "thermal" | "a4") => {
    setPrintFormatState(fmt);
    localStorage.setItem("preferred_print_format", fmt);
    showToast(
      lang === "ta"
        ? `விருப்பமான அச்சு வடிவம்: ${fmt === "thermal" ? "80mm Thermal Slip" : "A4 Tax Invoice"} ஆக மாற்றப்பட்டது`
        : `Default print format set to: ${fmt === "thermal" ? "80mm Thermal Slip" : "A4 Tax Invoice"}`,
      "info"
    );
  };

  return (
    <div className="workflow-page settings-page inside-scroll">
      <div className="page-title">
        <p className="eyebrow">{t("settings")}</p>
        <h1>{lang === "ta" ? "கடை அமைப்புகள்" : "Shop Settings & Preferences"}</h1>
      </div>

      <section className="settings-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        {/* Language Control */}
        <button
          className="setting-card"
          type="button"
          onClick={() => {
            const next = lang === "en" ? "ta" : "en";
            setLang(next);
            speak("Language switched", "மொழி மாற்றப்பட்டது");
          }}
          style={{ cursor: "pointer", textAlign: "left" }}
        >
          <span className="settings-icon blue">
            <Icon name="language" />
          </span>
          <span style={{ flex: 1 }}>
            <b>{t("language")}</b>
            <small style={{ display: "block", color: "#64748b" }}>English ⇄ தமிழ்</small>
          </span>
          <strong style={{ fontSize: 16, color: "#0284c7" }}>{lang === "ta" ? "தமிழ்" : "English"}</strong>
        </button>

        {/* Voice Assistance Control */}
        <button
          className="setting-card"
          type="button"
          onClick={() => {
            const next = !voice;
            setVoice(next);
            if (next) speak("Voice help enabled", "குரல் வழிகாட்டி இயக்கப்பட்டது");
          }}
          style={{ cursor: "pointer", textAlign: "left" }}
        >
          <span className="settings-icon purple">
            <Icon name="speaker" />
          </span>
          <span style={{ flex: 1 }}>
            <b>{t("voice")}</b>
            <small style={{ display: "block", color: "#64748b" }}>
              {lang === "ta" ? "விற்பனை மற்றும் கட்டணத்தில் குரல் உதவி" : "Speaks confirmations after billing and payments"}
            </small>
          </span>
          <i className={`toggle ${voice ? "on" : ""}`}>
            <span />
          </i>
        </button>

        {/* Default Print Receipt Format Control */}
        <div
          className="setting-card"
          style={{ display: "flex", flexDirection: "column", gap: 10, background: "#ffffff", padding: "16px", borderRadius: 12, border: "1px solid #e2e8f0" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span className="settings-icon green">
              <Icon name="print" />
            </span>
            <div style={{ flex: 1 }}>
              <b style={{ fontSize: 15, display: "block" }}>{lang === "ta" ? "விருப்பமான அச்சு வடிவம்" : "Default Invoice Format"}</b>
              <small style={{ color: "#64748b" }}>{lang === "ta" ? "இன்வாய்ஸ் அச்சிடும் போது ஆரம்ப வடிவம்" : "Auto-selected format when printing"}</small>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button
              type="button"
              onClick={() => handlePrintFormatChange("thermal")}
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: 8,
                border: printFormat === "thermal" ? "2px solid #0284c7" : "1px solid #cbd5e1",
                background: printFormat === "thermal" ? "#e0f2fe" : "#ffffff",
                color: printFormat === "thermal" ? "#0284c7" : "#475569",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              80mm Thermal Slip
            </button>
            <button
              type="button"
              onClick={() => handlePrintFormatChange("a4")}
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: 8,
                border: printFormat === "a4" ? "2px solid #0284c7" : "1px solid #cbd5e1",
                background: printFormat === "a4" ? "#e0f2fe" : "#ffffff",
                color: printFormat === "a4" ? "#0284c7" : "#475569",
                fontWeight: 700,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              A4 Tax Invoice
            </button>
          </div>
        </div>

        {/* Shop Configuration Info Card */}
        <div
          className="setting-card"
          style={{ background: "#f8fafc", padding: "16px", borderRadius: 12, border: "1px solid #e2e8f0" }}
        >
          <span className="settings-icon yellow">
            <Icon name="home" />
          </span>
          <div style={{ flex: 1 }}>
            <b style={{ fontSize: 15, color: "#0f172a" }}>Namma Wholesale Distributors</b>
            <small style={{ display: "block", color: "#64748b", marginTop: 2 }}>
              GSTIN: 33AAAAA0000A1Z5 • Trichy, TN
            </small>
            <span style={{ fontSize: 11, color: "#16a34a", fontWeight: 700, display: "inline-block", marginTop: 6, background: "#dcfce7", padding: "2px 8px", borderRadius: 4 }}>
              ● Windows Offline Mode • Local PostgreSQL
            </span>
          </div>
        </div>
      </section>

      {/* Owner-Only Offline Windows Backup Workflow (Authoritative instructions, no fake buttons) */}
      {role === "owner" && (
        <section style={{ marginTop: 24, background: "#ffffff", padding: "20px", borderRadius: 12, border: "1px solid #cbd5e1" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <Icon name="archive" size={22} />
            <div>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
                {lang === "ta" ? "உரிமையாளர் தரவுத்தள காப்பு வழிகாட்டி (Offline Windows Backup)" : "Owner Offline Backup & Recovery Workflow"}
              </h3>
              <small style={{ color: "#64748b" }}>
                {lang === "ta" ? "இணையம் இல்லாத லேப்டாப்பில் பாதுகாப்பான தரவு சேமிப்பு வழிமுறைகள்" : "Real Windows PostgreSQL commands for offline laptop data safety"}
              </small>
            </div>
          </div>

          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 14, fontSize: 13, color: "#334155" }}>
            <p style={{ margin: "0 0 8px 0", fontWeight: 700 }}>
              {lang === "ta" ? "1. பரிந்துரைக்கப்படும் சேமிப்பு இடம் (Backup Location):" : "1. Recommended Backup Location:"}
            </p>
            <code style={{ background: "#e2e8f0", padding: "3px 8px", borderRadius: 4, display: "inline-block", marginBottom: 12 }}>
              C:\WholesaleBillingBackups\ (or an external USB flash drive)
            </code>

            <p style={{ margin: "0 0 8px 0", fontWeight: 700 }}>
              {lang === "ta" ? "2. தினசரி காப்பு கட்டளை (Daily Backup Command via PowerShell):" : "2. Daily Backup Command (Run in PowerShell / Windows Batch):"}
            </p>
            <pre style={{ background: "#0f172a", color: "#38bdf8", padding: "10px 12px", borderRadius: 6, overflowX: "auto", fontSize: 12, margin: "0 0 12px 0" }}>
              &amp; &quot;C:\Program Files\PostgreSQL\18\bin\pg_dump.exe&quot; -U postgres -d billing -F c -b -v -f &quot;C:\WholesaleBillingBackups\billing_backup.dump&quot;
            </pre>

            <p style={{ margin: "0 0 8px 0", fontWeight: 700 }}>
              {lang === "ta" ? "3. சோதனை மீட்டமைத்தல் (Safe Test Restore without touching live data):" : "3. Safe Test Restore (Restores to test DB billing_test):"}
            </p>
            <pre style={{ background: "#0f172a", color: "#a7f3d0", padding: "10px 12px", borderRadius: 6, overflowX: "auto", fontSize: 12, margin: 0 }}>
              &amp; &quot;C:\Program Files\PostgreSQL\18\bin\pg_restore.exe&quot; -U postgres -d billing_test -v &quot;C:\WholesaleBillingBackups\billing_backup.dump&quot;
            </pre>
          </div>
        </section>
      )}
    </div>
  );
}
