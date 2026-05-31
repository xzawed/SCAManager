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
# Sprint 3 — issue_mgmt 서브 네임스페이스 (사이클 143)
# ---------------------------------------------------------------------------
_SPRINT3_ISSUE_MGMT_KEYS = [
    "title",
    "tab_static",
    "tab_ai",
    "filter_unregistered",
    "modal_title",
    "form_title",
    "form_body",
    "form_labels",
    "btn_cancel",
    "btn_skip",
    "btn_create_next",
]


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT3_ISSUE_MGMT_KEYS)
def test_repo_detail_sprint3_issue_mgmt_key_exists(locale: str, key: str):
    """repo_detail.issue_mgmt.<key>가 모든 locale에 존재해야 한다.
    repo_detail.issue_mgmt.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "repo_detail" in data
    assert "issue_mgmt" in data["repo_detail"], f"[{locale}] repo_detail.issue_mgmt 없음"
    assert key in data["repo_detail"]["issue_mgmt"], (
        f"[{locale}] repo_detail.issue_mgmt.{key} 없음"
    )


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT3_ISSUE_MGMT_KEYS)
def test_repo_detail_sprint3_issue_mgmt_value_non_empty(locale: str, key: str):
    """repo_detail.issue_mgmt.<key> 값이 비어있지 않아야 한다.
    Value must be non-empty.
    """
    val = _load(locale).get("repo_detail", {}).get("issue_mgmt", {}).get(key)
    assert isinstance(val, str) and val.strip(), (
        f"[{locale}] repo_detail.issue_mgmt.{key} 비어있음: {val!r}"
    )


# ---------------------------------------------------------------------------
# 사이클 144 Sprint 2 — issue_mgmt 동적 카운트 키 (data-i18n 패턴)
# Cycle 144 Sprint 2 — issue_mgmt dynamic count keys (data-i18n pattern)
# ---------------------------------------------------------------------------
_SPRINT2_144_BULK_KEYS = ["bulk_register", "bulk_complete"]


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_144_BULK_KEYS)
def test_repo_detail_bulk_key_exists(locale: str, key: str):
    """repo_detail.issue_mgmt.<bulk_key>가 모든 locale에 존재해야 한다.
    repo_detail.issue_mgmt.<bulk_key> must exist in all locales.
    """
    data = _load(locale)
    assert "issue_mgmt" in data["repo_detail"]
    assert key in data["repo_detail"]["issue_mgmt"], (
        f"[{locale}] repo_detail.issue_mgmt.{key} 없음"
    )


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_144_BULK_KEYS)
def test_repo_detail_bulk_value_has_count_placeholder(locale: str, key: str):
    """repo_detail.issue_mgmt.<bulk_key> 값에 {count} 플레이스홀더가 있어야 한다.
    Value must contain the {count} placeholder for dynamic count injection.
    """
    val = _load(locale).get("repo_detail", {}).get("issue_mgmt", {}).get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] {key} 비어있음"
    assert "{count}" in val, f"[{locale}] {key}에 {{count}} 플레이스홀더 없음: {val!r}"
