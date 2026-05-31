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


# 사이클 149 Sprint 2 — Telegram 반자동 Gate 메시지 키
# Cycle 149 Sprint 2 — Telegram semi-auto gate message keys
_TG_KEYS = [
    "tg_review_title", "tg_repo_line", "tg_score_line",
    "tg_choose", "tg_btn_approve", "tg_btn_reject",
]


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _TG_KEYS)
def test_gate_tg_key_exists(locale, key):
    assert key in _load(locale)["notifier"]["gate"], f"[{locale}] notifier.gate.{key} 없음"


def test_get_text_renders_tg_score():
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel
    out = get_text("notifier.gate.tg_score_line", "en", score=85, grade="B")
    assert "85" in out and "B" in out


def test_tg_repo_line_preserves_markdown():
    """리포 라인은 Telegram Markdown 백틱을 보존한다 (parse_mode=Markdown)."""
    g_ko = _load("ko")["notifier"]["gate"]
    assert "`{repo}`" in g_ko["tg_repo_line"], "ko tg_repo_line 백틱 누락"
    g_en = _load("en")["notifier"]["gate"]
    assert "`{repo}`" in g_en["tg_repo_line"], "en tg_repo_line 백틱 누락"


# 사이클 149 Sprint 4 — 머지 재시도 Telegram 알림 키 (HTML parse_mode)
# Cycle 149 Sprint 4 — merge retry Telegram notification keys (HTML parse_mode)
_RETRY_KEYS = [
    "retry_stopped_title", "retry_repo_line", "retry_stopped_reason",
    "retry_succeeded_title", "retry_score_attempts", "retry_view_github",
    "retry_terminal_title", "retry_terminal_reason", "retry_advice_line",
]


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _RETRY_KEYS)
def test_gate_retry_key_exists(locale, key):
    assert key in _load(locale)["notifier"]["gate"], f"[{locale}] notifier.gate.{key} 없음"


def test_retry_score_attempts_renders():
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel
    out = get_text("notifier.gate.retry_score_attempts", "en", score=85, attempts=3)
    assert "85" in out and "3" in out


def test_retry_view_github_preserves_html():
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel
    out = get_text("notifier.gate.retry_view_github", "en", url="http://x")
    assert "<a href=" in out
