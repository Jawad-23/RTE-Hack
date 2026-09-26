"""UI strings in English and Arabic. Owned by Salih."""

import json
import warnings
from functools import lru_cache
from pathlib import Path

LANGS = ("en", "ar")
_DIR = Path(__file__).resolve().parent


def _load(lang: str) -> dict:
    """Strings for one language, re-read whenever the JSON file changes.

    Keyed on the file's modification time: a long-running server (Streamlit Cloud reloads changed code
    but keeps this module) would otherwise keep serving the strings from before a deploy.
    """
    path = _DIR / f"{lang}.json"
    return _read(path, path.stat().st_mtime_ns)


@lru_cache(maxsize=8)
def _read(path: Path, mtime_ns: int) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, lang: str = "en") -> str:
    """Label key + language ("en"/"ar") -> string; falls back to English, then to the key itself."""
    strings = _load(lang if lang in LANGS else "en")
    if key in strings:
        return strings[key]
    warnings.warn(f"Missing i18n key {key!r} for {lang!r}", stacklevel=2)
    return _load("en").get(key, key)


def has(key: str) -> bool:
    """True if the English strings define this key."""
    return key in _load("en")
