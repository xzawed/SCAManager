"""설정 폼 컨트롤 멤버십(orphan) 정적 가드 — form= 데이터손실 봉인 (2026-07-09 회고 후속 ⑤).

Settings form-control membership (orphan) static guard — seals the form= data-loss class.

#1041 Task 4 사고: `railway_deploy_alerts` 컨트롤을 `<form id="settingsForm">` 밖으로 옮기면서
`form="settingsForm"` 속성을 누락 → form-owner null → 제출되지 않아 매 저장 시 False 로 덮어써지는
데이터손실(opus whole-branch 리뷰만 적발, per-task sonnet 놓침). 본 가드는 settings.html 의
모든 `name=` 폼 컨트롤이 어떤 `<form>` 의 멤버(폼 내부 OR `form=` 속성 보유)인지 정적 검증한다.

#1041 Task 4 incident: a control moved outside <form id="settingsForm"> without form="settingsForm"
becomes form-owner-null → never submitted → clobbered to False on every save. This guard statically
asserts every name= control in settings.html is a member of some form (inside a <form> OR has form=).

🔴 이 가드는 필드-parity(scripts/check_config_5way_sync.py 가 의도적으로 범위 밖 둔 semantic 매칭)가
아니라 **구조적 멤버십**만 검사하므로 HTML 파싱 fragility 를 회피한다 — 필드 이름 대조 없이
"어느 폼에도 안 속한 컨트롤(orphan)" 만 찾는다.
This guard checks structural membership only (NOT the semantic field-parity that check_config_5way_sync.py
intentionally leaves out of scope), so it sidesteps HTML-parsing fragility.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

_SETTINGS = Path("src/templates/settings.html")
_CONTROL_TAGS = ("input", "select", "textarea")


class _FormMembershipParser(HTMLParser):
    """`<form>` 중첩 깊이를 추적하며 폼 밖 + `form=` 없는 컨트롤(orphan)을 수집한다.

    Track <form> nesting depth and collect controls that are outside any form AND lack a form= attr.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._form_depth = 0
        self.controls = 0
        # orphan = (tag, name, lineno) — 어느 폼에도 소속되지 않은 제출 컨트롤.
        # orphan = (tag, name, lineno) — a submit control belonging to no form.
        self.orphans: list[tuple[str, str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "form":
            self._form_depth += 1
        if tag in _CONTROL_TAGS and "name" in attr:
            self.controls += 1
            inside_form = self._form_depth > 0
            has_form_attr = "form" in attr
            if not inside_form and not has_form_attr:
                self.orphans.append((tag, attr.get("name") or "", self.getpos()[0]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._form_depth > 0:
            self._form_depth -= 1


def _orphans(html: str) -> list[tuple[str, str, int]]:
    parser = _FormMembershipParser()
    parser.feed(html)
    return parser.orphans


def test_settings_form_controls_are_all_form_members():
    """settings.html 의 모든 name= 컨트롤은 폼 멤버 (폼 내부 OR form=) — orphan 0.

    Every name= control in settings.html is a form member (inside a form OR has form=) — zero orphans.
    """
    orphans = _orphans(_SETTINGS.read_text(encoding="utf-8"))
    assert not orphans, (
        "settings.html 에 orphan 폼 컨트롤(어느 <form> 에도 안 속하고 form= 없음) 발견 — "
        f"제출 안 돼 저장 시 clobber 데이터손실 위험 (#1041 유형): {orphans}. "
        "해당 컨트롤을 <form> 안으로 옮기거나 form=\"settingsForm\" 속성을 추가하라."
    )


def test_orphan_detector_flags_control_outside_form():
    """자기검증: 폼 밖 + form= 없는 컨트롤을 주입하면 detector 가 반드시 잡는다 (#1041 재현).

    Self-check: injecting a control outside any form with no form= MUST be flagged (reproduces #1041).
    이 자기검증이 없으면 detector 가 조용히 항상 통과해도(가드 무력화) 눈치채지 못한다
    (testing.md "기존 테스트가 왜 통과하는가" 규율).
    """
    bugged = (
        "<form id='settingsForm'><input name='inside'></form>\n"
        "<input type='checkbox' name='railway_deploy_alerts'>"  # 폼 밖 + form= 없음
    )
    orphans = _orphans(bugged)
    assert any(name == "railway_deploy_alerts" for _tag, name, _ln in orphans), (
        f"detector 가 orphan 을 못 잡음 — 가드 무력화: {orphans}"
    )
    # form= 부여 시 orphan 아님 (정상 경로 확인).
    # With form= present, it is no longer an orphan (verify the happy path).
    fixed = (
        "<form id='settingsForm'><input name='inside'></form>\n"
        "<input type='checkbox' name='railway_deploy_alerts' form='settingsForm'>"
    )
    assert not _orphans(fixed), "form= 부여 컨트롤을 orphan 으로 오탐"
