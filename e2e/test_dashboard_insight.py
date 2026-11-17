"""E2E — /dashboard?mode=insight 회귀 가드 (Phase 3 PR 6).

Phase 3 PR 1~5 (#218~#223) 머지 후속 — 본 모듈은 회귀 가드만 포함 (구현 변경 0).

검증 범위:
- A. Insight 모드 페이지 로드 + 4 카드 또는 status fallback (4건)
- B. localStorage persist + URL 우선순위 (3건)

e2e 환경에서는 ANTHROPIC_API_KEY 미설정 (e2e/conftest.py L97~L111 — 환경변수 주입 없음)
→ settings.anthropic_api_key = "" (default) → insight_narrative status="no_api_key" 반환
→ 템플릿이 .dash-insight-status div + "🔑 ANTHROPIC_API_KEY ..." 표시.

In e2e there is no ANTHROPIC_API_KEY → insight_narrative returns status="no_api_key"
→ template renders the .dash-insight-status div with the missing-key prompt.

run: `make test-e2e` (Chromium Playwright, e2e/conftest.py 의 live_server fixture 사용).
"""
import pytest
from playwright.sync_api import expect

from e2e.conftest import INSIGHT_LANGUAGE, insight_call_held


# ─── A. Insight 모드 페이지 로드 + status fallback ──────────────────────


def test_dashboard_insight_mode_page_loads(page, base_url):
    """GET /dashboard?mode=insight → 200 + `.dash-insight-status` 안내 표시.

    🔴 이전 판은 **`no_api_key` 분기만** 인정했다. 그런데 어느 안내가 뜨는지는
    시드된 분석 데이터 양에 달려 있다 — 데이터가 부족하면 `insufficient_data`
    분기가 먼저 걸린다. 그래서 같은 커밋이 CI(🔑 no_api_key)와 로컬(📭 부족)에서
    **서로 다르게** 실패/통과했다: 122건 중 **유일한 환경 의존 실패**였다(R52 실측).
    이 테스트의 계약은 "insight 모드가 렌더되고 상태 안내가 뜬다" 이지
    "어느 사유인가" 가 아니다 — 사유는 시드 상태에 종속시키지 않는다.

    Which status renders depends on how much analysis data happens to be seeded, so
    pinning it to `no_api_key` made this the suite's only environment-dependent failure.
    The contract is that insight mode renders *a* status notice.
    """
    response = page.goto(f"{base_url}/dashboard?mode=insight")
    assert response.status == 200, f"5xx 발생: {response.status}"

    # status fallback div 존재 확인 (4 카드 grid 가 아닌 status div 가 렌더링되어야 함)
    # The .dash-insight-status div should render (not the 4-card grid) on no_api_key.
    status = page.locator(".dash-insight-status")
    assert status.count() >= 1, "dash-insight-status 셀렉터 누락 (no_api_key fallback 미표시)"

    # 상태 안내가 **비어 있지 않아야** 한다 — 사유(no_api_key / insufficient_data / disabled)는
    # 시드 데이터에 종속되므로 특정 분기를 못박지 않는다.
    # The status notice must be non-empty; the specific reason depends on seeded data.
    text = status.first.inner_text().strip()
    assert text, "dash-insight-status 가 비어 있다 — 상태 안내가 렌더되지 않았다"


def test_dashboard_insight_mode_toggle_visible_in_overview(page, base_url):
    """overview 모드 진입 시에도 .dash-mode-toggle 노출 + 양쪽 링크 모두 존재.

    Mode toggle nav must render in overview mode with both links present (PR 3 정합).
    """
    page.goto(f"{base_url}/dashboard?mode=overview")
    toggle = page.locator(".dash-mode-toggle")
    assert toggle.count() == 1, ".dash-mode-toggle 미렌더 (PR 3 회귀)"

    overview_link = page.locator('.dash-mode-toggle a[data-mode="overview"]')
    insight_link = page.locator('.dash-mode-toggle a[data-mode="insight"]')
    assert overview_link.count() == 1, "data-mode=overview 링크 누락"
    assert insight_link.count() == 1, "data-mode=insight 링크 누락"


def test_dashboard_insight_mode_toggle_active_state(page, base_url):
    """?mode=insight 시 insight 링크에 .active 클래스 + overview 는 미가짐.

    The active class must follow the URL `?mode=` parameter (template L327, L330).
    """
    page.goto(f"{base_url}/dashboard?mode=insight")

    insight_link = page.locator('.dash-mode-toggle a[data-mode="insight"]')
    overview_link = page.locator('.dash-mode-toggle a[data-mode="overview"]')

    insight_class = insight_link.first.get_attribute("class") or ""
    overview_class = overview_link.first.get_attribute("class") or ""

    assert "active" in insight_class, (
        f"mode=insight 시 insight 링크 .active 누락. class={insight_class!r}"
    )
    assert "active" not in overview_class, (
        f"mode=insight 시 overview 링크 .active 잘못 부여됨. class={overview_class!r}"
    )


def test_dashboard_insight_mode_no_chart_canvas(page, base_url):
    """Insight 모드 = narrative only — chart canvas 미렌더 (PR 3 정합).

    Insight mode is narrative-only; no <canvas> for the trend chart should render
    (overview-only branch in dashboard.html).
    """
    page.goto(f"{base_url}/dashboard?mode=insight")

    # dashTrendChart canvas 는 overview 모드에서만 렌더링 (template if mode == 'insight' / else 분기)
    # The dashTrendChart canvas only renders in overview mode.
    canvas = page.locator("canvas#dashTrendChart")
    assert canvas.count() == 0, (
        f"Insight 모드인데 canvas#dashTrendChart 렌더됨 (count={canvas.count()}) — PR 3 회귀"
    )


# ─── B. localStorage persist + URL 우선순위 ─────────────────────────────


def test_mode_toggle_navigates_without_persisting(page, base_url):
    """모드 토글은 **이동만** 한다 — localStorage 저장은 #649 에서 의도적으로 제거됐다.

    🔴 이 테스트는 원래 `localStorage['sca-dashboard-mode']` 저장을 요구했다. 그 JS 는
    2026-05-26 `e601464`(#649, *"localStorage redirect IIFE 제거 — /dashboard 항상 개요 표시"*)
    에서 **삭제됐다**. 즉 없어진 기능을 요구하던 테스트라, 되살리는 게 아니라
    **그 삭제 결정을 지키는 회귀 가드**로 방향을 뒤집는다.

    The mode toggle only navigates. localStorage persistence was deliberately removed in
    #649; this now guards that removal instead of demanding the deleted behaviour.
    """
    page.goto(f"{base_url}/dashboard?mode=overview")
    page.click('.dash-mode-toggle a[data-mode="insight"]')
    # 🔴 `wait_for_load_state("networkidle")` 로는 부족하다 — body 가 hx-boost 라
    # htmx 가 스왑 후 pushState 를 하는데 networkidle 이 그보다 먼저 풀린다(실측).
    # networkidle resolves before htmx's pushState under hx-boost; wait on the URL itself.
    page.wait_for_url("**mode=insight**", timeout=5000)

    assert "mode=insight" in page.url, f"토글이 이동하지 않았다: {page.url}"
    stored = page.evaluate("() => localStorage.getItem('sca-dashboard-mode')")
    assert stored is None, (
        f"#649 에서 제거한 localStorage 저장이 되살아났다: {stored!r}"
    )


def test_no_url_mode_always_shows_overview(page, base_url):
    """`?mode=` 부재 시 localStorage 와 무관하게 **항상 개요**를 보여야 한다 (#649).

    🔴 방향 반전: 이전 판은 localStorage='insight' 면 `?mode=insight` 로 **리다이렉트되기를**
    요구했다. `e601464`(#649)가 그 IIFE 를 제거해 */dashboard 는 항상 개요*가 정본이 됐다.
    남은 localStorage 값이 있어도 리다이렉트되지 않음을 단언한다.

    Inverted: `#649` removed the localStorage redirect IIFE, so `/dashboard` must always
    render the overview even when a stale localStorage value is present.
    """
    page.goto(f"{base_url}/dashboard?mode=overview")
    page.evaluate("() => localStorage.setItem('sca-dashboard-mode', 'insight')")

    page.goto(f"{base_url}/dashboard")
    # 부재를 단언하므로 리다이렉트가 일어났다면 발화할 만큼만 기다린다.
    # Asserting absence: wait just long enough for a redirect to have fired.
    page.wait_for_timeout(1500)

    assert "mode=insight" not in page.url, (
        f"#649 에서 제거한 localStorage 리다이렉트가 되살아났다: {page.url}"
    )


def test_localStorage_url_mode_takes_precedence(page, base_url):
    """URL ?mode= 명시 > localStorage — URL 명시 우선, redirect 발생 X (PR 4 정합).

    URL `?mode=` takes precedence over localStorage; no redirect should occur
    (template L660 — `if (url.searchParams.has('mode')) return;`).
    """
    # 사전 단계 — localStorage 에 'insight' 저장해 둠 (URL 우선순위 검증용)
    # Setup — pre-store 'insight' in localStorage to verify URL precedence.
    page.goto(f"{base_url}/dashboard")
    page.evaluate("() => localStorage.setItem('sca-dashboard-mode', 'insight')")

    # URL 에 명시적으로 mode=overview 부여 → URL 우선이므로 overview 유지 (insight 로 redirect X)
    # Visit with explicit ?mode=overview → URL wins, no redirect to insight.
    page.goto(f"{base_url}/dashboard?mode=overview")
    page.wait_for_load_state("networkidle")

    assert "mode=overview" in page.url, (
        f"URL ?mode=overview 명시 시에도 redirect 발생. 실제: {page.url}"
    )

    # overview 링크가 .active — URL 명시 우선 검증
    # The overview link must be active (URL precedence verified).
    overview_link = page.locator('.dash-mode-toggle a[data-mode="overview"]')
    overview_class = overview_link.first.get_attribute("class") or ""
    assert "active" in overview_class, (
        f"URL mode=overview 명시 시 overview 링크 .active 누락. class={overview_class!r}"
    )


# ─── C. 서술 자리 표시 → 조각 (회고 원장 #1706 안 C) ────────────────────────
#
# 캐시 미스 — 페이지는 유료 호출을 하지 않고 자리(aria-busy · 로딩 문구)만 그린다. htmx 가 `GET /dashboard/insight`
# 로 조각을 받아 그 자리를 통째로 바꾼다. 조각 요청 자체가 실패하면(5xx · 연결 끊김) 자리가 들고 있던 실패 상자
# (`<template>`)로 바꾼다. Claude 호출은 `insight_call_held` 가 붙잡아 두므로 자리 상태를 시간에 기대지 않고 본다.

_FRAGMENT_PATH = "/dashboard/insight"


def _pin_language(page, base_url):
    page.context.add_cookies([{"name": "preferred_language", "value": INSIGHT_LANGUAGE, "url": base_url}])


def test_insight_placeholder_is_swapped_for_the_fragment(seeded_page, base_url, seeded_analysis):
    """자리(aria-busy · 로딩 문구)가 먼저 보이고, 호출이 풀리면 조각의 네 카드가 그 자리를 바꾼다 — 자리는 하나만 남는다."""
    _pin_language(seeded_page, base_url)
    with insight_call_held() as release:
        with seeded_page.expect_request(lambda r: r.url.split("?")[0].endswith(_FRAGMENT_PATH)) as req:
            seeded_page.goto(f"{base_url}/dashboard?mode=insight&days=7")
        busy = seeded_page.locator('#dashInsight[aria-busy="true"] .dash-insight-status[role="status"]')
        expect(busy).to_be_visible()
        assert req.value.headers.get("hx-request") == "true", "조각 요청이 htmx 요청이 아니다"
        assert seeded_page.locator("#dashInsight .dash-insight-grid").count() == 0, "호출이 멈춰 있는데 카드가 있다"
        release()
        expect(seeded_page.locator("#dashInsight .dash-insight-grid")).to_be_visible(timeout=15000)
    expect(seeded_page.locator("#dashInsight .dash-insight-list li").first).to_contain_text("Held narrative")
    assert seeded_page.locator("#dashInsight").count() == 1
    assert seeded_page.locator("#dashInsight[aria-busy], #dashInsight[hx-get]").count() == 0, (
        "바꿔 낀 뒤에도 자리 속성이 남았다 — 조각이 또 불리거나 «바쁨» 이 안 풀린다")


@pytest.mark.parametrize("failure", ["server_error", "network_error"])
def test_a_failed_fragment_request_falls_back_to_the_failure_box(seeded_page, base_url, seeded_analysis, failure):
    """조각 요청이 5xx(`htmx:responseError`)이거나 끊기면(`htmx:sendError`) 실패 상자 · 새로 고침 링크로 바꾼다."""
    _pin_language(seeded_page, base_url)

    def _fail(route):
        if failure == "server_error":
            route.fulfill(status=500, body="boom")
        else:
            route.abort()

    seeded_page.route(f"**{_FRAGMENT_PATH}?*", _fail)
    try:
        with insight_call_held():
            seeded_page.goto(f"{base_url}/dashboard?mode=insight&days=7")
            expect(seeded_page.locator("#dashInsight .dash-insight-status")).to_contain_text(
                "request_failed", timeout=15000)
    finally:
        seeded_page.unroute(f"**{_FRAGMENT_PATH}?*")
    expect(seeded_page.locator('#dashInsight a[href*="refresh=1"]')).to_be_visible()
    assert seeded_page.locator("#dashInsight").count() == 1
    assert seeded_page.locator("#dashInsight[aria-busy], #dashInsight[hx-get]").count() == 0
