"""repo_detail i18n 키 존재 테스트 — Sprint 2+3 (사이클 143).

Tests that repo_detail.* keys exist in all 3 locales.
Sprint 3 keys will be appended to this same file.
"""
from __future__ import annotations
import json
import pathlib
import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]

_SPRINT2_TOP_KEYS = [
    "recent_score",
    "analysis_unit",
    "history_empty",
    "history_empty_hint",
]
_SPRINT2_COST_KEYS = [
    "title",
    "period",
    "tokens",
    "no_data",
    "disclaimer",
    "model_change",
    "settings_link",
]


def _load(locale: str) -> dict:
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_TOP_KEYS)
def test_repo_detail_sprint2_top_key_exists(locale: str, key: str):
    """repo_detail.<key>가 모든 locale에 존재해야 한다.
    repo_detail.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "repo_detail" in data, f"[{locale}] repo_detail 없음"
    assert key in data["repo_detail"], f"[{locale}] repo_detail.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_TOP_KEYS)
def test_repo_detail_sprint2_top_value_non_empty(locale: str, key: str):
    """repo_detail.<key> 값이 비어있지 않아야 한다.
    Value must be non-empty.
    """
    val = _load(locale).get("repo_detail", {}).get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] repo_detail.{key} 비어있음: {val!r}"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_COST_KEYS)
def test_repo_detail_sprint2_cost_key_exists(locale: str, key: str):
    """repo_detail.cost.<key>가 모든 locale에 존재해야 한다.
    repo_detail.cost.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "repo_detail" in data
    assert "cost" in data["repo_detail"], f"[{locale}] repo_detail.cost 서브키 없음"
    assert key in data["repo_detail"]["cost"], f"[{locale}] repo_detail.cost.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_COST_KEYS)
def test_repo_detail_sprint2_cost_value_non_empty(locale: str, key: str):
    """repo_detail.cost.<key> 값이 비어있지 않아야 한다.
    Value must be non-empty.
    """
    val = _load(locale).get("repo_detail", {}).get("cost", {}).get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] repo_detail.cost.{key} 비어있음: {val!r}"


# ---------------------------------------------------------------------------
# 사이클 145 Sprint 2 — js_msg 동적 텍스트 키
# Cycle 145 Sprint 2 — js_msg dynamic text keys
# ---------------------------------------------------------------------------
# 🔴 이슈 등록 패널이 쓰던 9키(label_*·status_*·bulk_submit_final·btn_*·err_*)는
#    그 패널과 함께 제거됐다. 같은 이름의 키가 analysis_detail 네임스페이스에 «따로»
#    살아 있으니 혼동하지 말 것 — 여기는 repo_detail 전용이다.
# The 9 keys the issue panel used were removed with it; identically-named keys still
# exist under the analysis_detail namespace and are a different set.
_JS_MSG_KEYS_145 = [
    "chart_avg", "chart_max", "chart_min",
    "tooltip_score", "grade_suffix",
]


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _JS_MSG_KEYS_145)
def test_repo_detail_js_msg_key_exists(locale: str, key: str):
    """repo_detail.js_msg.<key>가 모든 locale에 존재해야 한다."""
    data = _load(locale)
    assert "js_msg" in data["repo_detail"], f"[{locale}] js_msg 없음"
    assert key in data["repo_detail"]["js_msg"], f"[{locale}] js_msg.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _JS_MSG_KEYS_145)
def test_repo_detail_js_msg_non_empty(locale: str, key: str):
    """repo_detail.js_msg.<key> 값이 비어있지 않아야 한다."""
    val = _load(locale).get("repo_detail", {}).get("js_msg", {}).get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] js_msg.{key} 비어있음"


@pytest.mark.parametrize("locale", _LOCALES)
def test_repo_detail_js_msg_placeholders(locale: str):
    """플레이스홀더 키 검증."""
    js = _load(locale)["repo_detail"]["js_msg"]
    assert "{score}" in js["tooltip_score"]
    assert "{grade}" in js["grade_suffix"]
