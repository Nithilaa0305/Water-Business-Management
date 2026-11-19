import type { IconName } from "../types";
import { Icon } from "./Icon";

export function Metric({
  icon,
  label,
  value,
  tone,
  onClick,
}: {
  icon: IconName;
  label: string;
  value: string;
  tone: string;
  onClick?: () => void;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag className={`metric-card ${tone}`} onClick={onClick}>
      <span className="metric-icon">
        <Icon name={icon} size={28} />
      </span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
      {onClick && <span className="arrow">→</span>}
    </Tag>
  );
}
