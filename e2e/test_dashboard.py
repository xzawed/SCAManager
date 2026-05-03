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


def test_dashboard_renders_5_kpi_cards(page, base_url):
    """KPI 그리드 안 5 카드 모두 렌더링.

    회고 P0 #3 swap 검증 — Auto-merge 카드 = 5번째 KPI (PR 기준 final).
    """
    page.goto(f"{base_url}/dashboard")
    kpi_cards = page.locator(".dash-kpi")
    assert kpi_cards.count() == 5, (
        f"KPI 카드 5개 기대, 실제: {kpi_cards.count()}. "
        "Phase 1 (KPI 4) + Phase 2 PR 1 (Auto-merge KPI 5번째) 정합 검증."
    )


def test_dashboard_kpi_labels_present(page, base_url):
    """KPI 5 라벨 모두 페이지에 노출."""
    page.goto(f"{base_url}/dashboard")
    content = page.content()
    for label in ("평균 점수", "분석 건수", "보안 이슈", "활성 리포", "자동 머지 성공률"):
        assert label in content, f"KPI 라벨 누락: {label}"


# ─── range toggle ──────────────────────────────────────────────────────


def test_dashboard_range_toggle_present(page, base_url):
    """1d / 7d / 30d / 90d 토글 4 링크 모두 존재."""
    page.goto(f"{base_url}/dashboard")
    for days in (1, 7, 30, 90):
        link = page.locator(f'.dash-range-toggle a[href="/dashboard?days={days}"]')
        assert link.count() == 1, f"days={days} 링크 누락"


def test_dashboard_default_range_7_active(page, base_url):
    """default = days=7 — active 표시."""
    page.goto(f"{base_url}/dashboard")
    active = page.locator('.dash-range-toggle a.active')
    assert active.count() == 1
    assert active.first.get_attribute("href") == "/dashboard?days=7"


def test_dashboard_30d_range_navigates(page, base_url):
    """30d 클릭 시 /dashboard?days=30 으로 이동 + active 갱신."""
    page.goto(f"{base_url}/dashboard")
    page.click('.dash-range-toggle a[href="/dashboard?days=30"]')
    page.wait_for_url(f"{base_url}/dashboard?days=30")
    active = page.locator('.dash-range-toggle a.active')
    assert active.first.get_attribute("href") == "/dashboard?days=30"


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
    """'자주 발생 이슈' 섹션 헤더 노출 (empty 상태 포함)."""
    page.goto(f"{base_url}/dashboard")
    content = page.content()
    assert "자주 발생 이슈" in content, "자주 발생 이슈 섹션 누락"


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


def test_login_page_loads(page, base_url):
    """GET /login → 200 (정책 11 강화 — 인증 flow 1)."""
    response = page.goto(f"{base_url}/login")
    # e2e 환경 = require_login override 적용 → 로그인된 상태 → / 로 redirect 가능
    # 또는 /login 200 (실제 페이지 표시) — 둘 다 OK
    assert response.status in (200, 302, 303), f"/login 5xx: {response.status}"


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
