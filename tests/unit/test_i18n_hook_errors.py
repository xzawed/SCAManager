"""hook.py CLI 에러 i18n 키 + repo owner locale 해소 — 사이클 151 Sprint 1.

hook.py CLI error i18n keys + repo owner locale resolution — Cycle 151 Sprint 1.
"""
from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_KEYS = [
    "hook_token_required",
    "hook_invalid_repo_or_token",
    "hook_invalid_token",
    "hook_repo_not_found",
]


def _load(locale):
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_hook_error_key_exists(locale, key):
    # 3 언어 모두 errors.<key> 존재 의무 (en 누락 시 fallback 깨짐)
    # All 3 locales must contain errors.<key> (en missing breaks fallback)
    assert key in _load(locale)["errors"], f"[{locale}] errors.{key} 없음"


def test_get_text_hook_errors():
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel

    assert get_text("errors.hook_token_required", "en") != get_text(
        "errors.hook_token_required", "ko"
    )


def _make_db_with(repo, user):
    """repo / user 조회 결과를 순차 반환하는 mock db 생성.

    Build a mock db returning repo then user on successive .first() calls.
    """
    db = MagicMock()
    query_chain = MagicMock()
    db.query.return_value.filter.return_value = query_chain
    # 1st .first() → repo, 2nd .first() → user
    query_chain.first.side_effect = [repo, user]
    return db


def test_resolve_hook_locale_owner_language():
    from src.api.hook import _resolve_hook_locale  # pylint: disable=import-outside-toplevel

    repo = MagicMock()
    repo.user_id = 7
    user = MagicMock()
    user.preferred_language = "en"
    db = _make_db_with(repo, user)

    assert _resolve_hook_locale(db, "owner/repo") == "en"


def test_resolve_hook_locale_repo_not_found_returns_default():
    from src.api.hook import _resolve_hook_locale  # pylint: disable=import-outside-toplevel
    from src.config import settings  # pylint: disable=import-outside-toplevel

    db = _make_db_with(None, None)
    assert _resolve_hook_locale(db, "owner/missing") == settings.default_locale


def test_resolve_hook_locale_unsupported_language_returns_default():
    from src.api.hook import _resolve_hook_locale  # pylint: disable=import-outside-toplevel
    from src.config import settings  # pylint: disable=import-outside-toplevel

    repo = MagicMock()
    repo.user_id = 1
    user = MagicMock()
    user.preferred_language = "zz"  # 미지원 언어 → default fallback
    db = _make_db_with(repo, user)

    assert _resolve_hook_locale(db, "owner/repo") == settings.default_locale
