import { type ReactNode } from "react";
import { useApp } from "../context/AppContext";
import type { IconName, Role, Screen } from "../types";
import en from "../locales/en.json";
import { Icon } from "./Icon";
import { Logo } from "./Logo";
import { LanguageButton } from "./LanguageButton";

export function Shell({
  children,
  screen,
  setScreen,
  role,
  name,
  onLogout,
  goHome,
}: {
  children: ReactNode;
  screen: Screen;
  setScreen: (s: Screen) => void;
  role: Role;
  name: string;
  onLogout: () => void;
  goHome: () => void;
}) {
  const { t, voice, setVoice } = useApp();

  const navTabs: { id: Screen; icon: IconName; label: keyof typeof en }[] = [
    { id: "home", icon: "home", label: "home" },
    { id: "sale", icon: "sale", label: "sell" },
    { id: "stock", icon: "stock", label: "stock" },
    { id: "customers", icon: "user", label: "customers" },
    { id: "payments", icon: "wallet", label: "payReturn" },
    { id: "reports", icon: "chart", label: "reports" },
    { id: "settings", icon: "settings", label: "settings" },
  ];

  return (
    <div className="app-shell">
      {/* Top Header: Clean, responsive, WITHOUT Home/Back/Next arrows */}
      <header className="app-header">
        <div className="header-left">
          <button className="brand-button" onClick={goHome} title={t("home")}>
            <Logo compact />
          </button>

          {/* Horizontally scrollable Screen Tabs */}
          <nav className="header-nav-tabs">
            {navTabs.map((tab) => (
              <button
                key={tab.id}
                className={`nav-tab-pill ${screen === tab.id ? "active" : ""}`}
                onClick={() => setScreen(tab.id)}
              >
                <Icon name={tab.icon} size={15} />
                <span>{t(tab.label)}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="header-tools">
          <div className="session-info">
            <span className={`role-dot ${role}`} />
            <div>
              <small>{t(role)}</small>
              <b>{name}</b>
            </div>
          </div>
          <LanguageButton />
          <button
            className={`icon-button ${voice ? "active" : ""}`}
            onClick={() => setVoice(!voice)}
            aria-label={t("voice")}
            title={voice ? "Voice help: ON" : "Voice help: OFF"}
          >
            <Icon name="speaker" size={17} />
          </button>
          <button className="signout-button" onClick={onLogout} title={t("signOut")}>
            <Icon name="logout" size={15} />
            <b>{t("signOut")}</b>
          </button>
        </div>
      </header>

      <main className="page-content">{children}</main>
    </div>
  );
}
