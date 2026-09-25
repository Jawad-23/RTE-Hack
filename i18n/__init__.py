"""UI strings in English and Arabic. Owned by Salih."""

import json
import warnings
from functools import lru_cache
from pathlib import Path

LANGS = ("en", "ar")
_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def _load(lang: str) -> dict:
    return json.loads((_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def t(key: str, lang: str = "en") -> str:
    """Label key + language ("en"/"ar") -> string; falls back to English, then to the key itself."""
    strings = _load(lang if lang in LANGS else "en")
    if key in strings:
        return strings[key]
    warnings.warn(f"Missing i18n key {key!r} for {lang!r}", stacklevel=2)
    return _load("en").get(key, key)
