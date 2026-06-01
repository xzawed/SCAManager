"""웹 UI 에러 메시지 i18n 키 — 사이클 150 Sprint 1.

Web UI error message i18n keys — cycle 150 Sprint 1.
"""
from __future__ import annotations
import json
import pathlib

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_ERROR_KEYS = [
    "issue_duplicate",
    "issue_no_write_permission",
    "github_api_error",
    "invalid_url",
    "repo_name_required",
]


def _load(locale):
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _ERROR_KEYS)
def test_error_key_exists(locale, key):
    assert key in _load(locale)["errors"], f"[{locale}] errors.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
def test_add_repo_already_registered_key(locale):
    assert "error_already_registered" in _load(locale)["add_repo"], \
        f"[{locale}] add_repo.error_already_registered 없음"


def test_get_text_renders_issue_duplicate():
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel
    out = get_text("errors.issue_duplicate", "en", num=42)
    assert "42" in out and "{num}" not in out
