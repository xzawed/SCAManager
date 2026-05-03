"""E2E 회귀 가드 — claude-dark 토큰 누락 + WCAG 2.5.5 모바일 클릭 영역.

7-에이전트 정합성 검증 (2026-05-02) P1 #5 후속.
도입 배경:
  - cleanup PR #169 — claude-dark 테마가 settings 페이지 토큰 8종 (`--save-btn-bg`,
    `--grad-gate/merge/notify/hook`, `--title-gradient`, `--btn-gate-active-*`,
    `--hint-*`, `--hook-btn-*`) 미정의로 카드 헤더가 흰색/투명 깨졌던 사고.
  - UI 감사 Step A — WCAG 2.5.5 Target Size — 모바일 (≤768px) 인터랙티브 요소
    `.btn`/`.btn--sm`/`.nav-hamburger`/`.nav-logout-btn` min-height ≥40~44px 의무.

본 테스트는 두 영역의 회귀를 e2e 레벨에서 차단한다.
"""
# E2E regression guards — claude-dark token regression + WCAG 2.5.5 mobile click area.

import pytest


# ── A. claude-dark 토큰 회귀 가드 (cleanup PR #169 사고 차단) ────────────────


def _set_claude_dark(page) -> None:
    """헬퍼 — claude-dark 테마로 전환 후 적용 확인.

    드롭다운 → claude-dark 옵션 클릭 → body[data-theme=claude-dark] 단언.
    """
    # Helper — switch to claude-dark theme and assert it applied.
    page.click("#themeToggle")
    page.wait_for_selector(".theme-switcher.open", timeout=2000)
    page.click('.theme-option[data-theme="claude-dark"]')
    assert page.get_attribute("body", "data-theme") == "claude-dark"


def test_claude_dark_settings_tokens_defined(seeded_page, base_url):
    """claude-dark 테마에서 settings 페이지의 8 토큰 모두 정의되어 있어야 한다.

    회귀 사례: cleanup PR #169 이전 settings 페이지가 claude-dark 토큰 미정의로
    `var(--save-btn-bg)` 등이 invalid → 카드 헤더 흰색 / 저장 버튼 투명 깨짐.
    """
    # Regression guard: cleanup PR #169 — claude-dark settings tokens were missing,
    # causing card headers / save button to render blank.
    seeded_page.goto(f"{base_url}/repos/owner/testrepo/settings")
    _set_claude_dark(seeded_page)

    # 8 토큰 모두 :root 에 정의되어 있어야 함 (빈 문자열이면 미정의 = invalid var())
    # All 8 tokens must be defined on :root (empty value = undefined = invalid).
    required = [
        "--grad-gate",
        "--grad-merge",
        "--grad-notify",
        "--grad-hook",
        "--title-gradient",
        "--save-btn-bg",
        "--hint-bg",
        "--hook-btn-bg",
    ]
    # claude-dark 토큰은 body[data-theme="claude-dark"] 스코프 → document.body 에서 조회
    # claude-dark tokens scoped to body[data-theme=claude-dark] — query document.body.
    for token in required:
        value = seeded_page.evaluate(
            f"getComputedStyle(document.body).getPropertyValue('{token}').trim()"
        )
        assert value, f"claude-dark 테마에 {token} 미정의 (settings 페이지 깨짐 위험)"


def test_claude_dark_dashboard_renders_without_token_failure(page, base_url):
    """claude-dark 테마 적용 후 dashboard 페이지가 정상 렌더되고 body 배경이 투명이 아니어야 한다.

    회귀 사례: --bg-app 등 핵심 토큰 미정의 시 body 배경이 transparent → 시각 깨짐.
    """
    # Regression guard: missing --bg-app etc. would render body bg transparent.
    page.goto(f"{base_url}/dashboard")
    _set_claude_dark(page)

    # body 배경이 transparent / rgba(0,0,0,0) 가 아니어야 함
    # body bg must not be transparent / rgba(0,0,0,0).
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg not in ("rgba(0, 0, 0, 0)", "transparent"), (
        f"claude-dark dashboard body 배경 투명 — 토큰 누락 의심: {bg}"
    )


def test_claude_dark_grade_aliases_defined(page, base_url):
    """claude-dark 테마에서 등급 색 alias (--grade-a/b/c/d/f) 가 모두 정의되어 있어야 한다.

    회귀 사례: 등급 색 미정의 시 overview 카드의 등급 뱃지가 색상 없이 렌더.
    """
    # Regression guard: missing --grade-* aliases would render overview grade badges colorless.
    page.goto(base_url)
    _set_claude_dark(page)

    # 등급 alias 도 body[data-theme="claude-dark"] 스코프
    # Grade aliases scoped to body[data-theme=claude-dark] too.
    for grade in ["a", "b", "c", "d", "f"]:
        token = f"--grade-{grade}"
        value = page.evaluate(
            f"getComputedStyle(document.body).getPropertyValue('{token}').trim()"
        )
        assert value, f"claude-dark 테마에 {token} 미정의"


# ── B. WCAG 2.5.5 모바일 클릭 영역 회귀 가드 (UI 감사 Step A) ─────────────────

_MOBILE_VIEWPORT = {"width": 375, "height": 812}  # iPhone X/11/12/13 sm
_DESKTOP_VIEWPORT = {"width": 1024, "height": 768}


def _min_height_px(page, selector: str) -> float:
    """헬퍼 — 셀렉터의 computed min-height 를 px 단위 float 반환.

    'auto' / 'normal' 등 비숫자 반환 시 0.0 으로 처리 (가드 통과 X).
    """
    # Helper — return computed min-height in px as float; 'auto'/'normal' → 0.0 (fail-fast).
    # Playwright page.evaluate 는 단일 expression 또는 arrow function 만 허용
    # Playwright page.evaluate accepts a single expression OR an arrow function.
    raw = page.evaluate(
        f"() => {{"
        f"  const el = document.querySelector({selector!r});"
        f"  if (!el) return null;"
        f"  return getComputedStyle(el).minHeight;"
        f"}}"
    )
    if raw is None:
        pytest.skip(f"셀렉터 '{selector}' 미존재 — 페이지 구조 변경 가능성")
    if not raw.endswith("px"):
        return 0.0
    return float(raw[:-2])


def _measure_injected_btn_min_height(page, btn_class: str) -> float:
    """헬퍼 — `<a class="{btn_class}">` 를 nav 외부에 동적 주입해 computed min-height 측정.

    overview 페이지가 `.btn--sm` 만 가지므로 정적 셀렉터로는 base `.btn` 규칙 측정 불가.
    DOM 주입 방식이 매체 쿼리 + 클래스 룰을 모두 적용한 결과를 안정적으로 노출한다.
    """
    # Helper — inject a stub <a> with the desired class to measure CSS @media + class rule output.
    raw = page.evaluate(
        "(cls) => {"
        "  const el = document.createElement('a');"
        "  el.className = cls;"
        "  el.href = '#';"
        "  el.textContent = 'probe';"
        "  document.body.appendChild(el);"
        "  const h = getComputedStyle(el).minHeight;"
        "  el.remove();"
        "  return h;"
        "}",
        btn_class,
    )
    if not raw or not raw.endswith("px"):
        return 0.0
    return float(raw[:-2])


def test_mobile_btn_min_height_44(page, base_url):
    """모바일 viewport (375px) 에서 .btn 의 min-height 가 44px 이상이어야 한다 (WCAG 2.5.5).

    회귀 사례: @media (max-width: 768px) 분기에서 .btn min-height: 44px 누락 시
    iOS 사용자 클릭 영역 작아 mis-tap 빈발.
    """
    # WCAG 2.5.5 Target Size — .btn must be ≥44px on mobile.
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(base_url)
    height = _measure_injected_btn_min_height(page, "btn btn-primary")
    assert height >= 44, f"모바일 .btn min-height = {height}px (≥44px 필요 — WCAG 2.5.5)"


def test_mobile_btn_sm_min_height_40(page, base_url):
    """모바일 viewport 에서 .btn--sm 의 min-height 가 40px 이상이어야 한다.

    .btn--sm 은 보조 액션 — WCAG 권장 최소(40px) 적용.
    """
    # WCAG 2.5.5 — .btn--sm minimum 40px on mobile (reduced for secondary actions).
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(base_url)
    # overview 의 실제 .btn--sm 셀렉터 사용 — 정적 존재 보장
    # Use real .btn--sm selector on overview — guaranteed to exist.
    height = _min_height_px(page, "a.btn--sm")
    assert height >= 40, f"모바일 .btn--sm min-height = {height}px (≥40px 필요)"


def test_mobile_nav_hamburger_44x44(page, base_url):
    """모바일 viewport 에서 .nav-hamburger 가 ≥44x44 영역이어야 한다.

    회귀 사례: nav 햄버거 버튼이 모바일에서 24x24 정도면 mis-tap 빈발.
    """
    # WCAG 2.5.5 — .nav-hamburger must be ≥44x44 on mobile.
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(base_url)
    raw_height = page.evaluate(
        "() => {"
        "  const el = document.querySelector('.nav-hamburger');"
        "  if (!el) return null;"
        "  const cs = getComputedStyle(el);"
        "  return [cs.minWidth, cs.minHeight];"
        "}"
    )
    if raw_height is None:
        pytest.skip(".nav-hamburger 셀렉터 미존재 — 페이지 구조 변경 가능성")
    min_w_str, min_h_str = raw_height
    assert min_w_str.endswith("px") and min_h_str.endswith("px"), (
        f".nav-hamburger min-w/h px 단위 아님 — minWidth={min_w_str}, minHeight={min_h_str}"
    )
    min_w, min_h = float(min_w_str[:-2]), float(min_h_str[:-2])
    assert min_w >= 44, f".nav-hamburger min-width = {min_w}px (≥44px 필요)"
    assert min_h >= 44, f".nav-hamburger min-height = {min_h}px (≥44px 필요)"


def test_desktop_btn_no_mobile_min_height(page, base_url):
    """데스크탑 viewport (1024px) 에서 .btn min-height 가 44px 미만이어야 한다.

    회귀 가드: 모바일 분기 (@media max-width: 768px) 가 데스크탑에 누수되지 않는지 확인.
    @media 가 잘못 작성되어 데스크탑에도 44px 가 적용되면 데스크탑 UI 가 어색해짐.
    """
    # Regression guard: ensure mobile @media rules don't leak into desktop viewport.
    page.set_viewport_size(_DESKTOP_VIEWPORT)
    page.goto(base_url)
    # DOM 주입 .btn 으로 데스크탑 분기에서 min-height 가 44px 미만임을 확인
    # Use DOM-injected .btn to verify desktop has no mobile-only min-height.
    height = _measure_injected_btn_min_height(page, "btn btn-primary")
    assert height < 44, (
        f"데스크탑 .btn min-height = {height}px — 모바일 분기 누수 의심"
        " (@media max-width:768px 가 데스크탑 적용 중)"
    )
