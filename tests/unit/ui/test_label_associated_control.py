"""접근성 회귀 가드 — field-label <label> 가 폼 컨트롤과 연결됨 (SonarCloud Web:S6853).

Accessibility regression guard — every `field-label` <label> is associated with a
form control (SonarCloud Web:S6853 LabelHasAssociatedControlCheck).

배경 (Background):
    Web:S6853 = "A form label must be associated with a control and have accessible
    text." 룰은 <label> 종료 시점에 `for` 속성도 없고 내부에 컨트롤
    (input/select/textarea/meter/output/progress)도 없으면 MAJOR 코드 스멜로 검출.
    settings.html 알림 채널 카드의 <label class="field-label"> 7건이 형제 input 과
    미연결(dangling) 상태였음 → 6건은 for/id 연결, 컨트롤 없는 1건(telegram_link)은
    <div> 전환으로 해소.
    Web:S6853 flags a <label> that has neither a `for` attribute nor a nested control.
    Six channel labels are now associated via for/id; the control-less telegram_link
    caption is now a <div>.

검사 방식 (Method):
    SonarCloud 룰과 동일하게 **raw 템플릿** 을 정적 파싱 — for/id 연결과 dangling 부재를 단언.
    Statically parse the raw template, asserting for/id association and no dangling label.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SETTINGS = Path("src/templates/settings.html")

# for/id 로 연결돼야 하는 6 알림 채널 input name
# The 6 notification-channel input names that must be associated via for/id.
_ASSOCIATED = [
    "notify_chat_id",
    "discord_webhook_url",
    "slack_webhook_url",
    "email_recipients",
    "custom_webhook_url",
    "n8n_webhook_url",
]


def _html() -> str:
    return _SETTINGS.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", _ASSOCIATED)
def test_field_label_associated_with_control(name: str):
    """각 채널 input 이 id 를, 매칭 라벨이 for 를 보유 (Web:S6853 해소)."""
    html = _html()
    input_pat = re.compile(r'<input\b[^>]*name="' + re.escape(name) + r'"[^>]*>')
    match = input_pat.search(html)
    assert match, f"input name={name} not found in settings.html"
    assert f'id="{name}"' in match.group(0), (
        f"input name={name} 에 id 부재 — for/id 연결 끊김 (Web:S6853 회귀). "
        f"tag={match.group(0)!r}"
    )
    assert f'<label class="field-label" for="{name}"' in html, (
        f"label for={name} 부재 — Web:S6853 회귀 (dangling label)"
    )


def test_no_dangling_field_label():
    """모든 <label class="field-label"> 는 for= 를 보유 (Web:S6853 — dangling 금지)."""
    html = _html()
    dangling = [
        tag
        for tag in re.findall(r'<label class="field-label"[^>]*>', html)
        if "for=" not in tag
    ]
    assert not dangling, (
        f"for 속성 없는 field-label 라벨 = Web:S6853 dangling 회귀: {dangling!r}"
    )


def test_telegram_link_caption_is_not_label_element():
    """컨트롤 없는 telegram_link 캡션은 <label> 대신 <div> (Web:S6853 — 연결 컨트롤 부재)."""
    html = _html()
    key = "settings_page.notify.telegram_link_label"
    div_pat = re.compile(r'<div class="field-label">\s*\{\{\s*\'' + re.escape(key))
    label_pat = re.compile(r'<label class="field-label">\s*\{\{\s*\'' + re.escape(key))
    assert div_pat.search(html), (
        "telegram_link 캡션이 <div class=\"field-label\"> 로 전환되지 않음 (Web:S6853)"
    )
    assert not label_pat.search(html), (
        "telegram_link 이 여전히 <label class=\"field-label\"> — Web:S6853 회귀 "
        "(연결할 폼 컨트롤이 없는 라벨)"
    )


def test_associated_channel_count_is_locked():
    """for/id 연결 대상 채널 수 = 6 (누락/중복 방지 동결)."""
    assert len(_ASSOCIATED) == 6
