"""repo_insights.* i18n 키 존재 테스트 — 사이클 146 Sprint 2.

repo_insights.* i18n key existence test — Cycle 146 Sprint 2.
"""
from __future__ import annotations

import json
import pathlib

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_KEYS = [
    "back_dashboard", "period_basis", "day_label", "kpi_avg_score", "grade_label",
    "kpi_total_analyses", "recent_days", "kpi_top_recurring", "recurring_count",
    "kpi_security_high", "narrative_title", "refresh", "recurring_ranking_title",
    "th_message", "th_tool", "th_count", "empty_recurring", "category_ratio_title",
    "empty_category", "problem_files_title", "count_suffix", "ai_suggestions_title",
    "mention_count", "empty_no_data", "empty_no_data_hint",
    "chart_sec_err", "chart_sec_warn", "chart_qual_err", "chart_qual_warn",
]


def _load(locale):
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_repo_insights_key_exists(locale, key):
    """repo_insights.<key>가 모든 locale에 존재.

    repo_insights.<key> exists in all locales.
    """
    assert key in _load(locale)["repo_insights"], f"[{locale}] repo_insights.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_repo_insights_non_empty(locale, key):
    """값 비어있지 않음.

    Value is non-empty.
    """
    val = _load(locale)["repo_insights"].get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] {key} 비어있음"
