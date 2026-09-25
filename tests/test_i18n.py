import json
from pathlib import Path

import pytest

from i18n import t

I18N = Path(__file__).resolve().parent.parent / "i18n"


def test_en_and_ar_have_identical_keys():
    en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
    ar = json.loads((I18N / "ar.json").read_text(encoding="utf-8"))
    assert set(en) == set(ar)


def test_no_empty_strings():
    for lang in ("en", "ar"):
        strings = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
        assert all(v.strip() for v in strings.values()), lang


def test_template_placeholders_match():
    import re
    en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
    ar = json.loads((I18N / "ar.json").read_text(encoding="utf-8"))
    for key in en:
        assert set(re.findall(r"{(\w+)}", en[key])) == set(re.findall(r"{(\w+)}", ar[key])), key


def test_missing_key_falls_back_with_warning():
    with pytest.warns(UserWarning):
        assert t("no_such_key", "ar") == "no_such_key"
    assert t("brand", "xx") == t("brand", "en")
