import { useApp } from "../context/AppContext";
import en from "../locales/en.json";

export function Stepper({ step }: { step: number }) {
  const { t } = useApp();
  const steps: { n: number; label: keyof typeof en }[] = [
    { n: 1, label: "customer" },
    { n: 2, label: "items" },
    { n: 3, label: "paySave" },
  ];
  return (
    <div className="stepper">
      {steps.map((s, index) => (
        <div
          key={s.n}
          className={`step-item ${step === s.n ? "active" : step > s.n ? "done" : ""}`}
        >
          <span>{step > s.n ? "✓" : s.n}</span>
          <b>{t(s.label)}</b>
          {index < steps.length - 1 && <i />}
        </div>
      ))}
    </div>
  );
}
