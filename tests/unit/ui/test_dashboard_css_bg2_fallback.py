"""회귀 가드 — dashboard.html CSS --bg-2 폴백 변수 검증.
Regression guard — dashboard.html CSS --bg-2 fallback variable verification.

사이클 113 P0-F 회귀 가드: dashboard.html 의 repos-selector / repos-cat-card /
repos-suggestion-count 3개 CSS 선택자에 var(--bg-2, ...) 폴백이 존재하는지 검증한다.
--bg-2 가 정의되지 않은 테마(legacy/커스텀)에서 시각 깨짐을 방지한다.
Cycle 113 P0-F regression guard: verifies that the 3 CSS selectors in dashboard.html
(repos-selector / repos-cat-card / repos-suggestion-count) contain var(--bg-2, ...) fallbacks.
Prevents visual breakage in themes that do not define --bg-2.

검증 방법:
  template 파일 텍스트 직접 검사 — FastAPI app import 없이 정적 검사.
  실제 브라우저 렌더링 없이 폴백 패턴 회귀 차단.

Verification method:
  Direct template file text inspection — no FastAPI app import needed.
  Catches fallback pattern regressions without browser rendering.
"""
from __future__ import annotations

from pathlib import Path


# 템플릿 파일 경로 — 프로젝트 루트 기준
# Template file path — relative to project root
_DASHBOARD_TMPL = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "src" / "templates" / "dashboard.html"
)


def test_dashboard_html_bg2_fallback_input_variant_present():
    """dashboard.html에 repos-selector 용 var(--bg-2, var(--bg-input)) 폴백이 존재한다.
    dashboard.html contains var(--bg-2, var(--bg-input)) fallback for repos-selector.

    사이클 113 P0-F: --bg-2 미정의 테마에서 input 배경색 폴백 보장.
    Cycle 113 P0-F: ensures input background color fallback when --bg-2 is undefined.
    """
    content = _DASHBOARD_TMPL.read_text(encoding="utf-8")
    assert "var(--bg-2, var(--bg-input))" in content, (
        "dashboard.html에 var(--bg-2, var(--bg-input)) 폴백이 없습니다. "
        "repos-selector 배경색 폴백이 제거됐을 수 있습니다."
    )


def test_dashboard_html_bg2_fallback_card_variant_present():
    """dashboard.html에 repos-cat-card 및 repos-suggestion-count 용
    var(--bg-2, var(--bg-card)) 폴백이 존재한다.
    dashboard.html contains var(--bg-2, var(--bg-card)) fallback for
    repos-cat-card and repos-suggestion-count selectors.

    사이클 113 P0-F: --bg-2 미정의 테마에서 카드 배경색 폴백 보장.
    Cycle 113 P0-F: ensures card background color fallback when --bg-2 is undefined.
    """
    content = _DASHBOARD_TMPL.read_text(encoding="utf-8")
    assert "var(--bg-2, var(--bg-card))" in content, (
        "dashboard.html에 var(--bg-2, var(--bg-card)) 폴백이 없습니다. "
        "repos-cat-card 또는 repos-suggestion-count 배경색 폴백이 제거됐을 수 있습니다."
    )


def test_dashboard_html_bg2_fallback_all_three_selectors():
    """dashboard.html의 --bg-2 폴백이 3개 선택자 모두에 적용됐는지 총 개수로 검증한다.
    Verifies the total count of --bg-2 fallbacks covers all 3 expected selectors.

    사이클 113 P0-F: var(--bg-2, ... 패턴이 최소 3회 등장해야 3개 선택자 모두 적용된 것.
    Cycle 113 P0-F: var(--bg-2, ... pattern must appear at least 3 times to cover all selectors.
    """
    content = _DASHBOARD_TMPL.read_text(encoding="utf-8")
    # "var(--bg-2," 패턴이 3개 이상 존재해야 함 (각 CSS 선택자 1건)
    # "var(--bg-2," pattern must appear at least 3 times (one per CSS selector)
    count = content.count("var(--bg-2,")
    assert count >= 3, (
        f"dashboard.html에 var(--bg-2, 폴백이 {count}개만 존재합니다. "
        f"최소 3개 선택자 모두 폴백이 필요합니다."
    )
