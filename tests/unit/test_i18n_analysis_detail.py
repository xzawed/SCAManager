"""analysis_detail i18n 키 존재 테스트 — Sprint 1-A (사이클 143).

Tests that analysis_detail.issue_form.* keys exist in all 3 locales.
"""
from __future__ import annotations
import json
import pathlib
import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_ISSUE_FORM_KEYS = ["title", "body", "labels"]


def _load(locale: str) -> dict:
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _ISSUE_FORM_KEYS)
def test_analysis_detail_issue_form_key_exists(locale: str, key: str):
    """analysis_detail.issue_form.<key>가 모든 locale에 존재해야 한다.
    analysis_detail.issue_form.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "analysis_detail" in data, f"[{locale}] analysis_detail 네임스페이스 없음"
    assert "issue_form" in data["analysis_detail"], f"[{locale}] issue_form 서브키 없음"
    assert key in data["analysis_detail"]["issue_form"], (
        f"[{locale}] analysis_detail.issue_form.{key} 없음"
    )


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _ISSUE_FORM_KEYS)
def test_analysis_detail_issue_form_value_non_empty(locale: str, key: str):
    """analysis_detail.issue_form.<key> 값이 비어있지 않아야 한다.
    Value of analysis_detail.issue_form.<key> must be non-empty.
    """
    data = _load(locale)
    val = data.get("analysis_detail", {}).get("issue_form", {}).get(key)
    assert isinstance(val, str) and val.strip(), (
        f"[{locale}] analysis_detail.issue_form.{key} 값이 비어있음: {val!r}"
    )


# ---------------------------------------------------------------------------
# 사이클 144 Sprint 1 — issue_panel 서브 네임스페이스
# ---------------------------------------------------------------------------
_ISSUE_PANEL_KEYS = [
    "panel_title",
    "tab_ai",
    "tab_static",
    "modal_title",
    "btn_cancel",
    "btn_submit",
]


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _ISSUE_PANEL_KEYS)
def test_analysis_detail_issue_panel_key_exists(locale: str, key: str):
    """analysis_detail.issue_panel.<key>가 모든 locale에 존재해야 한다.
    analysis_detail.issue_panel.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "analysis_detail" in data
    assert "issue_panel" in data["analysis_detail"], f"[{locale}] issue_panel 없음"
    assert key in data["analysis_detail"]["issue_panel"], (
        f"[{locale}] analysis_detail.issue_panel.{key} 없음"
    )


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _ISSUE_PANEL_KEYS)
def test_analysis_detail_issue_panel_value_non_empty(locale: str, key: str):
    """analysis_detail.issue_panel.<key> 값이 비어있지 않아야 한다.
    Value must be non-empty.
    """
    val = _load(locale).get("analysis_detail", {}).get("issue_panel", {}).get(key)
    assert isinstance(val, str) and val.strip(), (
        f"[{locale}] analysis_detail.issue_panel.{key} 비어있음: {val!r}"
    )


# ---------------------------------------------------------------------------
# 사이클 145 Sprint 1 — js_msg 동적 텍스트 키
# Cycle 145 Sprint 1 — js_msg dynamic text keys
# ---------------------------------------------------------------------------
_JS_MSG_KEYS = [
    "suggestion_prefix",
    "status_resolved",
    "status_open",
    "btn_register",
    "body_ai",
    "body_static",
    "btn_creating",
    "err_generic",
    "toast_created",
    "err_network",
]


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _JS_MSG_KEYS)
def test_analysis_detail_js_msg_key_exists(locale: str, key: str):
    """analysis_detail.js_msg.<key>가 모든 locale에 존재해야 한다."""
    data = _load(locale)
    assert "js_msg" in data["analysis_detail"], f"[{locale}] js_msg 없음"
    assert key in data["analysis_detail"]["js_msg"], f"[{locale}] js_msg.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _JS_MSG_KEYS)
def test_analysis_detail_js_msg_non_empty(locale: str, key: str):
    """analysis_detail.js_msg.<key> 값이 비어있지 않아야 한다."""
    val = _load(locale).get("analysis_detail", {}).get("js_msg", {}).get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] js_msg.{key} 비어있음"


@pytest.mark.parametrize("locale", _LOCALES)
def test_analysis_detail_js_msg_count_placeholders(locale: str):
    """카운트 키는 {num} 플레이스홀더를 가져야 한다."""
    js = _load(locale)["analysis_detail"]["js_msg"]
    for key in ["status_resolved", "status_open", "toast_created"]:
        assert "{num}" in js[key], f"[{locale}] {key}에 {{num}} 없음: {js[key]!r}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_analysis_detail_js_msg_body_placeholders(locale: str):
    """본문 빌더 키는 {id} 플레이스홀더를 가져야 한다."""
    js = _load(locale)["analysis_detail"]["js_msg"]
    assert "{id}" in js["body_ai"], f"[{locale}] body_ai에 {{id}} 없음"
    assert "{id}" in js["body_static"], f"[{locale}] body_static에 {{id}} 없음"
