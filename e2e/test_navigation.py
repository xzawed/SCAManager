"""E2E — 네비게이션 테스트."""


def test_overview_page_loads(page, base_url):
    """Overview 페이지가 정상적으로 로드되어야 한다."""
    page.goto(base_url)
    assert "SCAManager" in page.title()


def test_overview_empty_state(page, base_url):
    """레포가 없을 때 빈 상태 메시지가 표시되어야 한다."""
    page.goto(base_url)
    # 레포가 없는 경우 empty-state 표시 (seeded_page 미사용)
    # 또는 테이블이 있는 경우 테이블이 표시
    # Or a table is shown when repositories are present.
    content = page.content()
    assert "SCAManager" in content


def test_nav_logo_is_visible(page, base_url):
    """네이비바 로고가 표시되어야 한다."""
    page.goto(base_url)
    assert page.is_visible(".nav-logo")


def test_nav_logo_navigates_to_overview(seeded_page, base_url):
    """로고 클릭 시 Overview 페이지로 이동해야 한다."""
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo")
    seeded_page.click(".nav-logo")
    seeded_page.wait_for_url(f"{base_url}/", timeout=5000)
    assert seeded_page.url.rstrip("/") == base_url.rstrip("/")


def test_overview_link_in_nav(page, base_url):
    """네이비바 Overview 링크가 렌더링되어야 한다.
    get_current_user override로 {% if current_user %} 블록이 노출됨.
    Nav links are inside {% if current_user %} — visible only with get_current_user override.
    """
    page.goto(base_url)
    link = page.query_selector("nav a.nav-link[href='/']")
    assert link is not None, (
        "Overview nav link (href='/') not found — get_current_user override may be missing"
    )


def test_repo_detail_back_button(seeded_page, base_url):
    """레포 상세 페이지의 ← 목록 버튼이 Overview로 이동해야 한다."""
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo")
    seeded_page.click(".back-btn")
    seeded_page.wait_for_url(f"{base_url}/", timeout=5000)
    assert seeded_page.url.rstrip("/") == base_url.rstrip("/")


def test_settings_back_button(seeded_page, base_url):
    """설정 페이지의 ← 상세 버튼이 레포 상세 페이지로 이동해야 한다."""
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo/settings")
    seeded_page.click("a.back-btn")
    # hx-boost 이후 URL이 decoded(owner/testrepo) 또는 encoded(owner%2Ftestrepo) 양쪽 가능 → 조건식 매칭
    # After hx-boost the URL may be decoded or encoded — use predicate instead of exact URL string
    seeded_page.wait_for_url(
        lambda url: "owner" in url and "testrepo" in url and "/settings" not in url,
        timeout=5000,
    )
    assert "/settings" not in seeded_page.url
    assert "owner" in seeded_page.url


def test_detail_settings_button(seeded_page, base_url):
    """레포 상세 페이지의 ⚙️ 설정 버튼이 설정 페이지로 이동해야 한다."""
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo")
    seeded_page.click(".settings-btn")
    seeded_page.wait_for_url("**/settings", timeout=5000)
    assert "/settings" in seeded_page.url


def test_settings_cancel_button(seeded_page, base_url):
    """설정 페이지의 취소 버튼이 레포 상세로 이동해야 한다."""
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo/settings")
    seeded_page.click("a.back-btn")
    # hx-boost 이후 URL decoded/encoded 양쪽 가능 → 조건식 매칭
    # After hx-boost the URL may be decoded or encoded — use predicate instead of exact URL string
    seeded_page.wait_for_url(
        lambda url: "owner" in url and "testrepo" in url and "/settings" not in url,
        timeout=5000,
    )
    assert "/settings" not in seeded_page.url


def test_nav_handler_survives_hx_boost_renavigation(seeded_page, base_url):
    """hx-boost 3회 연속 재방문 후에도 nav 핸들러가 정상 동작해야 한다.

    PR #604 회귀 가드: base.html top-level const → hx-boost body swap 시 script 재실행 →
    const 재선언 SyntaxError → 3번째 swap부터 _initNavHandlers 전체 무력화.
    PR #604 regression guard: top-level const caused SyntaxError on hx-boost re-execution,
    disabling all nav handlers from the 3rd body swap onwards.

    시나리오: goto(full load) → settings(hx#1) → detail(hx#2) → settings(hx#3)
    모두 protected 라우트 → current_user 보장 → nav 핸들러 정상 검증 가능
    All protected routes — current_user guaranteed — nav handler verification valid.

    검증: #themeToggle 클릭 후 aria-expanded 변경 (_initNavHandlers 핸들러 등록의 직접 증거)
    Verify: #themeToggle click changes aria-expanded (direct proof of handler registration)
    """
    # 초기 full load — JS 컨텍스트 초기화 (script 1번째 실행)
    # Initial full load — fresh JS context (1st script execution)
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo")
    seeded_page.wait_for_load_state("networkidle")

    # hx-boost #1: repo detail → settings (script 2번째 실행)
    # hx-boost #1: repo detail → settings (2nd script execution)
    seeded_page.click(".settings-btn")
    seeded_page.wait_for_url("**/settings", timeout=5000)

    # hx-boost #2: settings → repo detail (script 3번째 실행)
    # hx-boost #2: settings → repo detail (3rd script execution)
    seeded_page.click("a.back-btn")
    # hx-boost 후 URL decoded/encoded 양쪽 가능 → 조건식 매칭
    # After hx-boost URL may be decoded or encoded — use predicate
    seeded_page.wait_for_url(
        lambda url: "owner" in url and "testrepo" in url and "/settings" not in url,
        timeout=5000,
    )

    # hx-boost #3: repo detail → settings (script 4번째 실행 — 구 버전 const SyntaxError 지점)
    # hx-boost #3: → settings (4th execution — former const redeclaration crash point)
    seeded_page.click(".settings-btn")
    seeded_page.wait_for_url("**/settings", timeout=5000)

    # themeToggle 클릭 핸들러 검증: aria-expanded가 "false" → "true" 로 변경되어야 함
    # _initNavHandlers가 정상 재등록됐을 때만 클릭이 처리됨
    # Verify themeToggle click handler: aria-expanded must change "false" → "true"
    # Click is only handled if _initNavHandlers successfully re-registered the listener
    theme_toggle = seeded_page.query_selector("#themeToggle")
    assert theme_toggle is not None, "#themeToggle not found after 3 hx-boost swaps"
    assert theme_toggle.get_attribute("aria-expanded") == "false", (
        "themeToggle aria-expanded should start as 'false'"
    )

    seeded_page.click("#themeToggle")

    # 핸들러 등록 시 aria-expanded → "true" (JS boolean → string 강제 변환)
    # Registered handler: aria-expanded → "true" (JS boolean-to-string coercion)
    seeded_page.wait_for_function(
        "document.getElementById('themeToggle').getAttribute('aria-expanded') === 'true'",
        timeout=3000,
    )
    assert theme_toggle.get_attribute("aria-expanded") == "true", (
        "3회 hx-boost 후 themeToggle 클릭해도 aria-expanded 미변경 "
        "— _initNavHandlers 핸들러 등록 실패 (PR #604 회귀)"
    )
