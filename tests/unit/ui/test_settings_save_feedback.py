"""설정 저장 in-flight 피드백 정적 가드.

Static guards for the settings save-in-flight feedback:
htmx 로딩 속성(#settingsForm) + 저장 버튼 label/spinner 2 span + `settings_page.saving`
i18n 키의 3 로케일(ko/en/ja) 해소(raw 키 미노출 = render-parity).
htmx loading attributes on the form + label/spinner spans on the save button
+ the `settings_page.saving` i18n key resolving in all 3 locales.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.i18n.loader import get_text

_SETTINGS = Path("src/templates/settings.html")


def _read() -> str:
    return _SETTINGS.read_text(encoding="utf-8")


def test_form_has_htmx_loading_attributes():
    """#settingsForm 은 hx-indicator/hx-disabled-elt 로 저장 버튼을 로딩 대상 지정."""
    # #settingsForm has hx-indicator/hx-disabled-elt pointing at the save button.
    html = _read()
    form = re.search(r'<form[^>]*id="settingsForm"[^>]*>', html)
    assert form, "settingsForm not found"
    tag = form.group(0)
    assert 'hx-indicator="#saveBtn"' in tag, "hx-indicator missing on settingsForm"
    assert 'hx-disabled-elt="#saveBtn"' in tag, "hx-disabled-elt missing on settingsForm"


def test_save_button_has_label_and_spinner():
    """저장 버튼 = save-label + save-spinner 2 span (spinner 는 saving 키 바인딩)."""
    # The save button splits into a label span and a spinner span bound to the saving key.
    html = _read()
    btn = re.search(r'<button[^>]*id="saveBtn"[^>]*>.*?</button>', html, re.DOTALL)
    assert btn, "saveBtn not found"
    markup = btn.group(0)
    assert 'class="save-label"' in markup, "save-label span missing"
    assert 'class="save-spinner"' in markup, "save-spinner span missing"
    assert "settings_page.saving" in markup, "spinner must bind settings_page.saving i18n key"


def test_saving_key_resolves_in_all_locales():
    """settings_page.saving 는 ko/en/ja 모두 번역 존재 (raw 키 미노출 = render-parity)."""
    # The saving key resolves to a real translation in every locale (no raw-key leak).
    for locale in ("ko", "en", "ja"):
        value = get_text("settings_page.saving", locale)
        assert value and value != "settings_page.saving", f"{locale}: saving key not translated"
