import { useApp } from "../context/AppContext";
import { Icon } from "./Icon";

export function LanguageButton() {
  const { lang, setLang, speak } = useApp();
  const toggle = () => {
    const next = lang === "en" ? "ta" : "en";
    setLang(next);
    setTimeout(() => speak("Language changed to English", "மொழி தமிழுக்கு மாற்றப்பட்டது"), 50);
  };
  return (
    <button className="utility-btn" onClick={toggle} title="Toggle Language">
      <Icon name="language" size={20} />
      <b>{lang === "en" ? "தமிழ்" : "EN"}</b>
    </button>
  );
}
