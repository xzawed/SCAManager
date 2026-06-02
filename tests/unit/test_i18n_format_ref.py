"""format_ref i18n + push 이벤트 커밋 레퍼런스 회귀 가드 — 사이클 152 P0-A.

format_ref i18n + push-event commit reference regression guard (cycle 152 P0-A).
"""
from __future__ import annotations

import json
import pathlib

import pytest

from src.notifier._common import format_ref, resolve_ai_summary

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]


def _load(locale: str) -> dict:
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
def test_commit_ref_key_exists(locale: str):
    """notifier.common.commit_ref가 모든 locale에 존재해야 한다.
    notifier.common.commit_ref must exist in all locales.
    """
    assert "common" in _load(locale)["notifier"], f"[{locale}] notifier.common 없음"
    assert "commit_ref" in _load(locale)["notifier"]["common"], f"[{locale}] commit_ref 없음"


def test_format_ref_pr_number_unchanged():
    """pr_number 있으면 'PR #N' 반환 (language 무관).
    Returns 'PR #N' when pr_number is present (language-agnostic).
    """
    assert format_ref("abc1234def", 5, "en") == "PR #5"
    assert format_ref("abc1234def", 5, "ja") == "PR #5"


def test_format_ref_commit_english_no_korean():
    """push 이벤트(pr_number=None) + en — '커밋' 한국어 누출 없어야 한다 (P0-A 회귀 가드).
    Push event + en — must not leak '커밋' Korean (P0-A regression guard).
    """
    out = format_ref("abc1234def", None, "en")
    assert "커밋" not in out, f"영어 locale에 한국어 '커밋' 누출: {out!r}"
    assert "Commit" in out


def test_format_ref_commit_japanese():
    """push 이벤트 + ja — 일본어 커밋 레퍼런스.
    Push event + ja — Japanese commit reference.
    """
    out = format_ref("abc1234def", None, "ja")
    assert "커밋" not in out
    assert "コミット" in out


def test_format_ref_commit_korean_default():
    """language 미전달 시 ko default (하위 호환).
    Defaults to ko when language omitted (backward compat).
    """
    out = format_ref("abc1234def", None)
    assert "커밋" in out


# ── resolve_ai_summary — AI 리뷰 fallback 현지화 (사이클 155 P1) ──

class _FakeAi:
    def __init__(self, summary, status):
        self.summary = summary
        self.status = status


@pytest.mark.parametrize("locale", _LOCALES)
def test_ai_unavailable_key_exists(locale: str):
    """notifier.common.ai_unavailable 가 모든 locale 에 존재해야 한다."""
    assert "ai_unavailable" in _load(locale)["notifier"]["common"], f"[{locale}] ai_unavailable 없음"


def test_resolve_ai_summary_success_returns_raw():
    """status='success' + summary 있으면 원본 summary 반환 (정상 AI 리뷰)."""
    assert resolve_ai_summary(_FakeAi("좋은 리팩토링", "success")) == "좋은 리팩토링"


def test_resolve_ai_summary_failure_localizes_english():
    """status!='success' (실패 fallback) + en → 영어 ai_unavailable, 한국어 누출 없음."""
    out = resolve_ai_summary(_FakeAi("", "no_api_key"), "en")
    assert out == "AI review unavailable (defaults applied)"
    assert "리뷰 불가" not in out


def test_resolve_ai_summary_failure_localizes_japanese():
    """status!='success' + ja → 일본어 ai_unavailable."""
    out = resolve_ai_summary(_FakeAi("", "parse_error"), "ja")
    assert "AIレビュー不可" in out
    assert "리뷰 불가" not in out


def test_resolve_ai_summary_none_and_empty():
    """ai_review=None → None. success + 빈 summary → None (라인 생략)."""
    assert resolve_ai_summary(None, "en") is None
    assert resolve_ai_summary(_FakeAi("", "success"), "en") is None
