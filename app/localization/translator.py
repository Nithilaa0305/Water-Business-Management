"""Localization translator helper."""

from app.localization.translations import TRANSLATIONS

_current_lang = "en"


def set_language(lang: str) -> None:
    """Set active application language ('en' or 'ta')."""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_language() -> str:
    """Get active language code."""
    return _current_lang


def t(key: str, default: str = "") -> str:
    """Translate key into active language, falling back to English or default."""
    dict_active = TRANSLATIONS.get(_current_lang, TRANSLATIONS["en"])
    if key in dict_active:
        return dict_active[key]
    dict_en = TRANSLATIONS.get("en", {})
    return dict_en.get(key, default or key)
