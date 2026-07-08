"""접근성 회귀 가드 — 폼 입력 요소 aria-label 부여 (SonarCloud Web:InputWithoutLabelCheck).

Accessibility regression guard — form controls carry an aria-label
(SonarCloud Web:InputWithoutLabelCheck).

배경 (Background):
    SonarCloud Quality Gate 가 settings.html(15) + repo_detail.html(5) 의 라벨 없는
    input/select 20건을 MAJOR 신뢰성 버그(Web:InputWithoutLabelCheck)로 검출 →
    new_reliability_rating C → 게이트 ERROR. 각 컨트롤에 i18n 바인딩 aria-label 부여로 해소.
    SonarCloud flagged 20 unlabeled input/select controls as MAJOR reliability bugs,
    failing the Quality Gate. Each control gets an i18n-bound aria-label.

검사 방식 (Method):
    SonarCloud 룰과 동일하게 **raw 템플릿** 의 컨트롤 태그를 추출해 aria-label 존재를 단언.
    aria-label 값은 반드시 i18n `{{ ... }}` 바인딩 (하드코딩 금지 — i18n.md 규칙).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_TEMPLATES = Path("src/templates")


def _control_tag(html: str, attr: str) -> str:
    """`attr` 를 포함하는 첫 input/select/textarea 태그 전체를 반환.

    Returns the first input/select/textarea tag containing `attr`.
    `<input ... attr ... >` — 속성값에 '>' 가 없음을 전제(이 템플릿들에서 성립).
    """
    pat = re.compile(
        r"<(?:input|select|textarea)\b[^>]*" + re.escape(attr) + r"[^>]*>"
    )
    match = pat.search(html)
    assert match, f"control with {attr} not found in template"
    return match.group(0)


# (템플릿 파일, 컨트롤 식별 속성) — SonarCloud 가 지목한 20 컨트롤
# (template file, identifying attribute) — the 20 controls SonarCloud flagged
_FLAGGED_CONTROLS = [
    # settings.html — PR 임계값 슬라이더/숫자 (pr_rules)
    ("settings.html", 'name="merge_threshold"'),
    ("settings.html", 'id="mergeVal"'),
    ("settings.html", 'name="approve_threshold"'),
    ("settings.html", 'id="approveVal"'),
    ("settings.html", 'name="reject_threshold"'),
    ("settings.html", 'id="rejectVal"'),
    # settings.html — 알림 채널 masked 입력 (notify)
    ("settings.html", 'name="notify_chat_id"'),
    ("settings.html", 'name="discord_webhook_url"'),
    ("settings.html", 'name="slack_webhook_url"'),
    ("settings.html", 'name="email_recipients"'),
    ("settings.html", 'name="custom_webhook_url"'),
    ("settings.html", 'name="n8n_webhook_url"'),
    # settings.html — 인바운드 토큰/URL + 모델 select
    ("settings.html", 'name="railway_api_token"'),
    ("settings.html", 'id="railway-webhook-url"'),
    ("settings.html", 'name="review_model"'),
    # repo_detail.html — 필터 바 (검색/날짜/점수 슬라이더)
    ("repo_detail.html", 'id="searchInput"'),
    ("repo_detail.html", 'id="dateFrom"'),
    ("repo_detail.html", 'id="dateTo"'),
    ("repo_detail.html", 'id="scoreMin"'),
    ("repo_detail.html", 'id="scoreMax"'),
]


@pytest.mark.parametrize("template, attr", _FLAGGED_CONTROLS)
def test_flagged_control_has_i18n_aria_label(template: str, attr: str):
    """플래그된 각 컨트롤이 i18n 바인딩 aria-label 을 보유 (Web:InputWithoutLabelCheck 해소)."""
    html = (_TEMPLATES / template).read_text(encoding="utf-8")
    tag = _control_tag(html, attr)
    assert 'aria-label="{{' in tag, (
        f"{template} 의 {attr} 컨트롤에 i18n aria-label 부재 — "
        f"Web:InputWithoutLabelCheck 회귀. tag={tag!r}"
    )


def test_flagged_control_count_is_locked():
    """가드 대상 컨트롤 수 = 20 (SonarCloud 검출 건수와 동결 — 누락/중복 방지).

    Note (Task 2.4): the new `ai_review_enabled` toggle is NOT added here —
    it is a toggle-switch checkbox wrapped in `<label class="toggle-switch">`,
    which already satisfies SonarCloud's Web:InputWithoutLabelCheck via the
    "wrapping <label>" exemption (see .claude/rules/ui.md). None of the other
    5 existing toggle-switch checkboxes (pr_review_comment, auto_merge,
    commit_comment, create_issue, railway_deploy_alerts) are in this list
    either — this list is scoped to the original 20 SonarCloud-flagged plain
    inputs/selects, not toggle-switches.
    """
    assert len(_FLAGGED_CONTROLS) == 20
