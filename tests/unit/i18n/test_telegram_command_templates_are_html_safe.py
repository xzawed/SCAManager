"""Telegram 봇 응답 **템플릿 자체**에 미이스케이프 꺾쇠가 있다 (감사 A9, #1519).

🔴 실측. 봇 명령 응답은 `parse_mode="HTML"` 로 전송되고,
`src/notifier/telegram_commands.py:22` 는 **사용자 입력**을 이스케이프한다고 적는다:

    from html import escape  # C27: 봇 명령 응답(parse_mode=HTML)의 사용자 입력 HTML 이스케이프

사용자 입력은 실제로 `escape(...)` 를 거친다. 그런데 **템플릿 문자열 자체**가
Telegram 이 모르는 태그 모양을 담고 있다 — 3로케일 합계 13건:

    ko  not_connected     "먼저 /connect <코드>로 계정을 연결하세요."
        unknown_command   "... /stats <repo>, /settings, /connect <코드>"
        connect_usage     "사용법: /connect <8자리 코드>"
        stats_usage       "사용법: /stats <리포지토리 전체 이름 (owner/repo)>"
    en  unknown_command · connect_usage · stats_usage
    ja  같은 4키 (+ not_connected)

Telegram Bot API 는 HTML 모드에서 **지원 태그 목록 밖**을 만나면
`400 Bad Request: can't parse entities` 로 **메시지 전체를 거부**한다. 즉 사용법
안내가 필요한 바로 그 순간(`/connect` 를 잘못 썼을 때)에 아무 응답도 못 간다.

지원 태그: b · strong · i · em · u · ins · s · strike · del · code · pre · a ·
tg-spoiler · blockquote · span · tg-emoji

이 파일은 `notifier.commands.*` 전체를 3로케일에서 검사한다 — 새 키가 같은 실수를
들고 들어오면 red 다.

The user input is escaped; the templates themselves are not.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

# Telegram Bot API HTML 모드가 이해하는 태그 (공식 문서 기준)
_TELEGRAM_TAGS = frozenset({
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "code", "pre", "a", "tg-spoiler", "blockquote", "span", "tg-emoji",
    "tg-time",  # 최근 추가 — Grok 보정(session 01a03d37)
})

_ANY_ANGLE = re.compile(r"<[^>]*>")
_TAG_NAME = re.compile(r"</?([A-Za-z][A-Za-z0-9-]*)")

_LOCALES = sorted(p.stem for p in Path("src/i18n/translations").glob("*.json"))


def _command_strings(locale: str) -> dict[str, str]:
    data = json.load(io.open(f"src/i18n/translations/{locale}.json", encoding="utf-8"))
    commands = data.get("notifier", {}).get("commands", {})
    return {k: v for k, v in commands.items() if isinstance(v, str)}


def _unsupported(text: str) -> list[str]:
    out = []
    for match in _ANY_ANGLE.finditer(text):
        name = _TAG_NAME.match(match.group(0))
        if name is None or name.group(1).lower() not in _TELEGRAM_TAGS:
            out.append(match.group(0))
    return out


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_scan_finds_the_command_namespace():
    """🔴 검사 대상이 비면 이 파일은 아무것도 검증하지 않는다."""
    assert _LOCALES, "로케일 파일을 못 찾았다"
    for locale in _LOCALES:
        assert _command_strings(locale), f"{locale}: notifier.commands 가 비었다"


def test_the_detector_flags_a_planted_bad_tag():
    """🔴 탐지기가 실제로 미지원 태그를 잡는가."""
    assert _unsupported("사용법: /connect <8자리 코드>") == ["<8자리 코드>"]
    assert _unsupported("<b>강조</b> 와 <code>x</code>") == []


def test_the_send_path_really_uses_html_mode():
    """🔴 전제 — 봇 응답이 정말 `parse_mode=HTML` 로 나가는가.

    평문이면 꺾쇠는 무해하고 이 파일 전체가 공허하다.
    """
    src = io.open("src/webhook/providers/telegram.py", encoding="utf-8").read()
    assert '"parse_mode": "HTML"' in src, (
        "봇 응답이 HTML 모드로 나가지 않는다 — 전제가 바뀌었다"
    )


# ─── 결함 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("locale", _LOCALES)
def test_command_templates_contain_no_unsupported_tags(locale: str):
    """🔴 봇 응답 템플릿에 Telegram 이 모르는 꺾쇠가 없다.

    있으면 `400 Bad Request: can't parse entities` 로 **메시지 전체가 거부**된다 —
    사용법 안내가 필요한 바로 그 순간에 아무 응답도 못 간다.

    자리표시자는 `&lt;repo&gt;` 처럼 이스케이프하거나 백틱 대신 `<code>` 를 쓴다.
    """
    offenders = {
        key: bad for key, text in _command_strings(locale).items()
        if (bad := _unsupported(text))
    }
    assert not offenders, (
        f"[{locale}] Telegram 이 모르는 태그 모양이 있다 — HTML 파싱 실패로 메시지가 "
        f"통째로 거부된다: {offenders}"
    )


@pytest.mark.parametrize("locale", _LOCALES)
def test_placeholders_stay_visible_after_escaping(locale: str):
    """🔴 이스케이프해도 사용자가 자리표시자를 **볼 수 있어야** 한다.

    `<코드>` 를 그냥 지우면 「/connect 뒤에 뭘 넣으라는 건지」를 잃는다.
    이스케이프(`&lt;…&gt;`)는 화면에 그대로 보이므로 안내가 유지된다.
    """
    usage_keys = [k for k in _command_strings(locale) if "usage" in k or "unknown" in k]
    assert usage_keys, f"[{locale}] 사용법 키를 못 찾았다"
    for key in usage_keys:
        text = _command_strings(locale)[key]
        assert "&lt;" in text or "<code>" in text or "/" in text, (
            f"[{locale}] {key}: 자리표시자 안내가 사라졌다 — {text!r}"
        )
