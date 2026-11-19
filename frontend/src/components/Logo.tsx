import { useApp } from "../context/AppContext";
import { Icon } from "./Icon";

export function Logo({ compact = false }: { compact?: boolean }) {
  const { t } = useApp();
  return (
    <div className={`logo ${compact ? "compact" : ""}`}>
      <span className="logo-mark">
        <Icon name="shop" size={compact ? 22 : 28} />
      </span>
      <div>
        <strong>{t("appName")}</strong>
        {!compact && <small>{t("tagline")}</small>}
      </div>
    </div>
  );
}
