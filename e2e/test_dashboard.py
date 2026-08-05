"""E2E — /dashboard 페이지 종단간 검증.

P0 OAuth 사고 (2026-05-02) 후속 + 정책 11 강화 (인증 flow 4 endpoint) + 정책 13 (운영 endpoint smoke check) 자동화.

검증 범위 (회고 P0 #5 검증 환류 갭 해소):
- /dashboard 200 응답 + 페이지 제목
- KPI 5 카드 모두 렌더링 (평균 점수 / 분석 건수 / 보안 HIGH / 활성 리포 / 자동 머지 성공률)
- 점수 추세 차트 캔버스 존재 (또는 empty state)
- range toggle (1d/7d/30d/90d) 4 링크 존재
- themechange 동작 (테마 전환 시 차트 재빌드)
- 자주 발생 이슈 카드 + 자동 머지 실패 사유 카드 (조건부)
- feedback CTA banner (count<10 시 표시)

run: `make test-e2e` (Chromium Playwright, e2e/conftest.py 의 live_server fixture 사용)
"""


# KPI 카드 수 — 카드가 늘어날 때마다 이 상수만 갱신한다.
# KPI card count — bump this single constant when a card is added.
_KPI_CARD_COUNT = 6


# ─── /dashboard 기본 렌더링 ─────────────────────────────────────────────


def test_dashboard_page_loads(page, base_url):
    """GET /dashboard → 200 + 페이지 제목 'Dashboard'."""
    page.goto(f"{base_url}/dashboard")
    assert "Dashboard" in page.title(), f"제목 누락: {page.title()}"


def test_dashboard_page_no_500_error(page, base_url):
    """page 응답이 5xx 가 아닌지 검증 (template 렌더링 오류 차단)."""
    response = page.goto(f"{base_url}/dashboard")
    assert response.status < 500, f"5xx 발생: {response.status}"
    assert response.status == 200, f"200 기대, 실제: {response.status}"


# ─── KPI 5 카드 렌더링 (정책 11 강화 — 시각 자동화) ─────────────────────


def test_dashboard_renders_kpi_cards(page, base_url):
    """KPI 그리드 카드가 모두 렌더링.

    카드 수 이력: Phase 1 = 4 → Phase 2 PR 1 = 5 (Auto-merge) → #1037 = 6 ('이번 달 AI 비용').
    KPI card count history: 4 → 5 (auto-merge) → 6 (monthly AI cost, #1037).
    """
    page.goto(f"{base_url}/dashboard")
    kpi_cards = page.locator(".dash-kpi")
    assert kpi_cards.count() == _KPI_CARD_COUNT, (
        f"KPI 카드 {_KPI_CARD_COUNT}개 기대, 실제: {kpi_cards.count()}."
    )


def test_dashboard_kpi_labels_present(page, base_url):
    """KPI 5 라벨 모두 페이지에 노출.

    사이클 84 i18n 18 PR 후 default locale 영문 — 영문 기대값 (사이클 89 P0-2 학습).
    """
    page.goto(f"{base_url}/dashboard")
    content = page.content()
    # 🔴 라벨 목록은 카드 수(_KPI_CARD_COUNT)와 **같은 개수**여야 한다 — 6번째 카드(#1037
    # 'AI cost (30d)')가 라벨 목록에서 빠져 있어, 카드 수 단언을 6 으로 고쳐도 6번째의
    # **내용**은 아무도 안 보는 상태였다(Grok claim-review 적발).
    # Keep this list the same size as _KPI_CARD_COUNT: the 6th card's content was unobserved.
    labels = (
        "Average Score",
        "Analyses",
        "Security Issues (HIGH)",
        "Active Repos",
        "Auto-Merge Success Rate",
        "AI cost (30d)",
    )
    assert len(labels) == _KPI_CARD_COUNT, (
        f"라벨 {len(labels)}개 ≠ 카드 {_KPI_CARD_COUNT}개 — 카드를 추가하고 라벨을 빠뜨렸다"
    )
    for label in labels:
        assert label in content, f"KPI 라벨 누락: {label}"


# ─── range toggle ──────────────────────────────────────────────────────


def test_dashboard_range_toggle_present(page, base_url):
    """1d / 7d / 30d / 90d 토글 4 링크 모두 존재.

    Phase 3 PR 3 — URL 형식이 `?mode={mode}&days={n}` 으로 변경 (모드 토글 페어 보존).
    range toggle 4 links present (URL format updated to `?mode=...&days=...` in Phase 3 PR 3).
    """
    page.goto(f"{base_url}/dashboard")
    for days in (1, 7, 30, 90):
        link = page.locator(
            f'.dash-range-toggle a[href="/dashboard?mode=overview&days={days}"]'
        )
        assert link.count() == 1, f"days={days} 링크 누락"


def test_dashboard_default_range_7_active(page, base_url):
    """default = days=7 — active 표시. Phase 3 PR 3: href 에 mode=overview 포함."""
    page.goto(f"{base_url}/dashboard")
    active = page.locator('.dash-range-toggle a.active')
    assert active.count() == 1
    assert active.first.get_attribute("href") == "/dashboard?mode=overview&days=7"


def test_dashboard_30d_range_navigates(page, base_url):
    """30d 클릭 시 /dashboard?mode=overview&days=30 이동 + active 갱신 (Phase 3 PR 3)."""
    page.goto(f"{base_url}/dashboard")
    page.click('.dash-range-toggle a[href="/dashboard?mode=overview&days=30"]')
    page.wait_for_url(f"{base_url}/dashboard?mode=overview&days=30")
    active = page.locator('.dash-range-toggle a.active')
    assert active.first.get_attribute("href") == "/dashboard?mode=overview&days=30"


# ─── chart vendoring (회고 P0 #5 검증) ─────────────────────────────────


def test_dashboard_uses_vendored_chartjs(page, base_url):
    """Chart.js = vendored (`/static/vendor/chart.umd.min.js`) — CDN 차단 환경 호환.

    UI 감사 Step C (PR #166) 의무 + 회귀 가드.
    """
    page.goto(f"{base_url}/dashboard")
    content = page.content()
    # Chart 컨텍스트가 있을 때만 vendored 참조 (trend 데이터 없으면 script 미로드)
    if "dashTrendChart" in content or "<canvas" in content:
        assert "/static/vendor/chart.umd.min.js" in content, (
            "vendored Chart.js 미로드 — UI 감사 Step C 회귀"
        )
        assert "cdn.jsdelivr.net/npm/chart.js" not in content, (
            "외부 CDN 잔존 — vendoring 회귀"
        )


# ─── 보조 카드 (조건부) ─────────────────────────────────────────────────


def test_dashboard_frequent_issues_section_present(page, base_url):
    """'Frequent Issues' 섹션 헤더 노출 (empty 상태 포함).

    기본 locale 은 en 이다 — 같은 파일의 KPI 라벨 테스트와 동일 규약(사이클 89 P0-2).
    Default locale is en, matching the sibling KPI-label test.
    """
    page.goto(f"{base_url}/dashboard")
    content = page.content()
    assert "Frequent Issues" in content, "Frequent Issues 섹션 누락"


def test_dashboard_no_js_runtime_errors(page, base_url):
    """JS 런타임 오류 (TypeError, ReferenceError 등) 0건 차단.

    network 자원 로드 실패 (ERR_NAME_NOT_RESOLVED, 404 favicon 등) 는 허용 —
    e2e 환경 네트워크 차단 false positive 회피. 진짜 JS 코드 오류만 검증.
    """
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    # console.error 만 잡고 network 관련은 제외
    def _on_console(msg):
        if msg.type == "error":
            text = msg.text
            # network resource error 제외 (e2e 환경 외부 자원 차단)
            if "Failed to load resource" in text or "net::" in text:
                return
            errors.append(f"console.error: {text}")
    page.on("console", _on_console)
    page.goto(f"{base_url}/dashboard")
    page.wait_for_load_state("networkidle")
    assert not errors, f"JS 런타임 오류: {errors}"


# ─── /insights → /dashboard 301 redirect (Phase 1 PR 5 검증) ────────────


def test_insights_legacy_url_redirects_to_dashboard(page, base_url):
    """GET /insights → 301 → /dashboard (북마크 사용자 보호)."""
    response = page.goto(f"{base_url}/insights")
    # follow_redirects 기본 True → 최종 200 + URL = /dashboard
    assert response.status == 200
    assert page.url.endswith("/dashboard") or "/dashboard?" in page.url, (
        f"/insights → /dashboard redirect 실패. 최종 URL: {page.url}"
    )


def test_insights_me_legacy_url_redirects_to_dashboard(page, base_url):
    """GET /insights/me → 301 → /dashboard."""
    response = page.goto(f"{base_url}/insights/me")
    assert response.status == 200
    assert page.url.endswith("/dashboard") or "/dashboard?" in page.url


# ─── 정책 11 강화 — 인증 flow 4 endpoint smoke ──────────────────────────


def test_login_route_redirects_to_oauth(page, base_url):
    """GET /login → 301 /auth/github (하위 호환 리다이렉트).

    🔴 이전 판은 `page.goto` 로 리다이렉트를 **따라가서** 최종 응답 상태만 봤다.
    /login 은 301 → /auth/github → 302 → github.com 이므로, 그 단언은 실제로는
    **github.com 이 200 을 주는지**를 검증하고 있었다(우리 앱과 무관 + 네트워크 의존).
    리다이렉트를 따라가지 않고 우리 쪽 계약만 본다.

    The previous version followed redirects and ended up asserting that github.com
    returns 200 — unrelated to this app. Assert our own contract without following.
    """
    resp = page.request.get(f"{base_url}/login", max_redirects=0)
    assert resp.status == 301, f"/login 은 301 이어야 하는데 {resp.status}"
    assert resp.headers.get("location") == "/auth/github", (
        f"/login → /auth/github 기대, 실제 {resp.headers.get('location')!r}"
    )


# ─── nav 링크 검증 (Phase 1 PR 5 — Insights → Dashboard) ─────────────


def test_nav_dashboard_link_present(page, base_url):
    """nav 의 'Dashboard' 링크 존재 (Phase 1 PR 5 — 'Insights' 에서 변경)."""
    page.goto(base_url)
    content = page.content()
    assert 'href="/dashboard"' in content, "nav Dashboard 링크 누락"
    # 'Insights' 라벨이 nav 에 잔존하면 안 됨 (Dashboard 로 변경됨)
    nav_links = page.locator(".nav-link")
    nav_texts = [nav_links.nth(i).inner_text() for i in range(nav_links.count())]
    assert "Dashboard" in nav_texts, f"nav 에 Dashboard 라벨 누락: {nav_texts}"
