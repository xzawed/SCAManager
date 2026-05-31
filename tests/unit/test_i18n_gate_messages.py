"""notifier.gate.* i18n 키 + approve.py 언어 적용 테스트 — 사이클 149 Sprint 1.
notifier.gate.* i18n keys + approve.py language application test — Cycle 149 Sprint 1.
"""
from __future__ import annotations
import json, pathlib, pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_KEYS = ["auto_approve", "auto_reject"]


def _load(locale): return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_gate_key_exists(locale, key):
    assert "gate" in _load(locale)["notifier"], f"[{locale}] notifier.gate 없음"
    assert key in _load(locale)["notifier"]["gate"], f"[{locale}] notifier.gate.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
def test_gate_placeholders(locale):
    g = _load(locale)["notifier"]["gate"]
    for key in _KEYS:
        assert "{score}" in g[key], f"[{locale}] {key}에 {{score}} 없음"
        assert "{threshold}" in g[key], f"[{locale}] {key}에 {{threshold}} 없음"


def test_get_text_renders_gate_approve():
    """get_text가 notifier.gate.auto_approve를 score/threshold로 렌더."""
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel
    out = get_text("notifier.gate.auto_approve", "en", score=85, threshold=75)
    assert "85" in out and "75" in out and "{score}" not in out
