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


# ─── A. Insight 모드 페이지 로드 + status fallback ──────────────────────


def test_dashboard_insight_mode_page_loads(page, base_url):
    """GET /dashboard?mode=insight → 200 + .dash-insight-status (no_api_key fallback) 표시.

    e2e = ANTHROPIC_API_KEY 미설정 → status=no_api_key → 🔑 텍스트 노출.
    """
    response = page.goto(f"{base_url}/dashboard?mode=insight")
    assert response.status == 200, f"5xx 발생: {response.status}"

    # status fallback div 존재 확인 (4 카드 grid 가 아닌 status div 가 렌더링되어야 함)
    # The .dash-insight-status div should render (not the 4-card grid) on no_api_key.
    status = page.locator(".dash-insight-status")
    assert status.count() >= 1, "dash-insight-status 셀렉터 누락 (no_api_key fallback 미표시)"

    # 본문에 ANTHROPIC_API_KEY 또는 🔑 marker 노출 (template L380~L382 정합)
    # The body must include the missing-key prompt (dashboard.html L380-L382).
    text = status.first.inner_text()
    assert ("ANTHROPIC_API_KEY" in text) or ("🔑" in text), (
        f"no_api_key 메시지 누락. 실제 텍스트: {text[:120]}"
    )


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


def test_localStorage_persist_on_mode_toggle_click(page, base_url):
    """모드 토글 클릭 시 localStorage 'sca-dashboard-mode' 저장 (PR 4 정합).

    Clicking the mode toggle persists the choice to localStorage (PR 4).
    """
    page.goto(f"{base_url}/dashboard?mode=overview")

    # insight 링크 클릭 — 페이지 이동 발생 (handler 가 setItem 후 navigate)
    # Click the insight link — navigation will follow but the handler stores first.
    page.click('.dash-mode-toggle a[data-mode="insight"]')
    page.wait_for_load_state("networkidle")

    stored = page.evaluate("() => localStorage.getItem('sca-dashboard-mode')")
    assert stored == "insight", (
        f"localStorage 'sca-dashboard-mode' 미저장 또는 잘못된 값: {stored!r}"
    )


def test_localStorage_redirect_on_no_url_mode(page, base_url):
    """URL ?mode= 부재 + localStorage 'insight' 저장 → 1회 redirect 로 ?mode=insight 로 이동.

    With no ?mode= in URL but localStorage='insight', the page redirects once
    to add ?mode=insight (template L657-L670 — server initial_mode != stored).
    """
    # 1단계: dashboard 진입 후 localStorage 직접 setItem
    # Step 1: visit dashboard, then setItem on localStorage directly.
    page.goto(f"{base_url}/dashboard?mode=overview")
    page.evaluate("() => localStorage.setItem('sca-dashboard-mode', 'insight')")

    # 2단계: URL 에서 ?mode= 제거하고 재진입 — JS 가 stored != initial_mode 감지하여 redirect
    # Step 2: visit /dashboard with no ?mode=; JS detects stored != initial and redirects.
    page.goto(f"{base_url}/dashboard")
    page.wait_for_load_state("networkidle")

    # URL 에 mode=insight 가 포함되어야 함 (1회 redirect 후 안정 상태)
    # Final URL must include mode=insight (post-redirect).
    assert "mode=insight" in page.url, (
        f"localStorage='insight' 인데 URL 에 mode=insight 미포함. 실제: {page.url}"
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
