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


def test_strings_reload_when_the_file_changes(tmp_path, monkeypatch):
    import os
    import i18n
    (tmp_path / "en.json").write_text('{"hello": "Hi"}', encoding="utf-8")
    monkeypatch.setattr(i18n, "_DIR", tmp_path)
    assert i18n.t("hello") == "Hi"
    (tmp_path / "en.json").write_text('{"hello": "Hello", "new_key": "New"}', encoding="utf-8")
    os.utime(tmp_path / "en.json", ns=(1, 2_000_000_000_000_000_000))  # make sure the modification time moves
    assert i18n.t("hello") == "Hello" and i18n.t("new_key") == "New"  # a deploy's new strings show without a restart


def test_kit_page_without_plan_shows_pod_area():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=60)
    at.run()
    at.switch_page("views/operate.py").run()
    text = " ".join(m.value for m in at.markdown)
    assert not at.exception and "per 500 m²" in text and "kit_empty" not in text
