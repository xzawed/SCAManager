"""notifier.cron.* i18n 키 + 메시지 언어 적용 — 사이클 153 Sprint 2.

notifier.cron.* i18n keys + per-message language application — cycle 153 Sprint 2.
"""
from __future__ import annotations

import json
import pathlib

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_KEYS = [
    "weekly_title",
    "weekly_analyses",
    "weekly_avg",
    "trend_title",
    "trend_prev",
    "trend_current",
    "trend_drop",
]


def _load(locale):
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_cron_key_exists(locale, key):
    assert "cron" in _load(locale)["notifier"], f"[{locale}] notifier.cron 없음"
    assert key in _load(locale)["notifier"]["cron"], f"[{locale}] {key} 없음"


def test_weekly_message_english_no_korean():
    from src.services.cron_service import _format_weekly_message  # pylint: disable=import-outside-toplevel
    out = _format_weekly_message("o/r", {"avg_score": 85.0, "count": 10}, "en")
    assert "주간" not in out and "분석 건수" not in out, f"en에 한국어 누출: {out!r}"
    assert "Weekly Report" in out and "Analyses: 10" in out


def test_trend_alert_japanese():
    from src.services.cron_service import _format_trend_alert  # pylint: disable=import-outside-toplevel
    out = _format_trend_alert("o/r", 70.0, 85.0, 15.0, "ja")
    assert "점수 하락" not in out
    assert "スコア低下警告" in out
