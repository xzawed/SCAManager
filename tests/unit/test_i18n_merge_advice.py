"""notifier.merge_advice.* i18n + get_advice 언어 적용 — 사이클 149 Sprint 3.

notifier.merge_advice.* i18n + get_advice language application — Cycle 149 Sprint 3.
"""
from __future__ import annotations

import json
import pathlib

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_TAGS = [
    "branch_protection_blocked", "dirty_conflict", "behind_base", "draft_pr", "unstable_ci",
    "unknown_state_timeout", "permission_denied", "not_mergeable", "unprocessable",
    "conflict_sha_changed", "network_error", "auto_merge_disabled_in_repo_settings",
    "enable_permission_denied", "force_pushed", "enable_api_error", "default",
]


def _load(locale):
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("tag", _TAGS)
def test_merge_advice_key_exists(locale, tag):
    """모든 조언 키가 3 언어 JSON 에 존재한다."""
    payload = _load(locale)
    assert "merge_advice" in payload["notifier"], f"[{locale}] notifier.merge_advice 없음"
    assert tag in payload["notifier"]["merge_advice"], f"[{locale}] {tag} 없음"


def test_get_advice_language():
    """언어별로 다른 텍스트 반환 + 미존재 tag 는 default fallback."""
    from src.gate.merge_failure_advisor import get_advice  # pylint: disable=import-outside-toplevel
    out_en = get_advice("branch_protection_blocked", "en")
    out_ko = get_advice("branch_protection_blocked", "ko")
    assert out_en != out_ko, "언어별 다른 텍스트여야 함"
    # 미존재 tag → default
    out_def = get_advice("nonexistent_tag", "en")
    assert out_def == get_advice(None, "en")


def test_get_advice_default_language_ko():
    """하위 호환 — language 미전달 시 ko default."""
    from src.gate.merge_failure_advisor import get_advice  # pylint: disable=import-outside-toplevel
    assert get_advice("dirty_conflict") == get_advice("dirty_conflict", "ko")
