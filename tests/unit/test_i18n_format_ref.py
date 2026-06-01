"""format_ref i18n + push 이벤트 커밋 레퍼런스 회귀 가드 — 사이클 152 P0-A.

format_ref i18n + push-event commit reference regression guard (cycle 152 P0-A).
"""
from __future__ import annotations

import json
import pathlib

import pytest

from src.notifier._common import format_ref

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
