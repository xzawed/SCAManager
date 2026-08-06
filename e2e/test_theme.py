"""E2E — 테마 전환 테스트."""


def _option(theme: str) -> str:
    """테마 드롭다운 항목 셀렉터.

    🔴 항목의 속성은 `data-theme` 이 **아니라** `data-theme-target` 이다 (#639, 5ba9bda).
    `tokens.css` 의 element-agnostic `[data-theme=...]` 선택자가 드롭다운 항목 자체에
    다크 테마 CSS 변수를 주입하던 것을 끊기 위한 의도적 리네임이다.
    반면 **적용된 테마**는 여전히 `body[data-theme]` 로 읽는다 — 두 축을 혼동하지 말 것.

    Selector for a theme dropdown entry. The entry attribute is `data-theme-target`,
    NOT `data-theme` (#639) — while the *applied* theme is still read from
    `body[data-theme]`. Do not conflate the two.

    `.theme-option` 접두사를 항상 붙인다: 접두사 없는 `[data-theme="light"]` 는
    body 에도 매칭될 수 있어 무엇을 클릭했는지 모호해진다(구 코드의 실제 결함).
    """
    return f'.theme-option[data-theme-target="{theme}"]'


def test_default_theme_is_dark(page, base_url):
    """초기 접속 시 다크 테마가 기본값이어야 한다."""
    page.goto(base_url)
    assert page.get_attribute("body", "data-theme") == "dark"


def test_theme_switcher_dropdown_opens(page, base_url):
    """테마 버튼 클릭 시 드롭다운이 열려야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.wait_for_selector(".theme-switcher.open", timeout=2000)
    assert page.is_visible(_option("light"))


def test_switch_to_light_theme(page, base_url):
    """클린(라이트) 테마로 전환되어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click(_option("light"))
    assert page.get_attribute("body", "data-theme") == "light"


def test_switch_to_pastel_theme(page, base_url):
    """파스텔 테마로 전환되어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click(_option("pastel"))
    assert page.get_attribute("body", "data-theme") == "pastel"


def test_theme_persists_after_reload(page, base_url):
    """테마 선택 후 새로고침해도 테마가 유지되어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click(_option("light"))
    page.reload()
    assert page.get_attribute("body", "data-theme") == "light"


def test_theme_saved_to_localstorage(page, base_url):
    """선택한 테마가 localStorage에 저장되어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click(_option("pastel"))
    value = page.evaluate("localStorage.getItem('sca-theme')")
    assert value == "pastel"


def test_active_class_on_selected_theme(page, base_url):
    """선택된 테마 옵션에 active 클래스가 붙어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click(_option("light"))
    # 드롭다운 다시 열기
    # Re-open the dropdown.
    page.click("#themeToggle")
    cls = page.get_attribute(_option("light"), "class") or ""
    assert "active" in cls


def test_dropdown_closes_on_outside_click(page, base_url):
    """드롭다운 외부 클릭 시 닫혀야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.wait_for_selector(".theme-switcher.open", timeout=2000)
    # 외부 영역 클릭
    # Click outside the dropdown.
    page.click("h2, .overview-header h2, body", position={"x": 10, "y": 10})
    assert not page.is_visible(".theme-switcher.open")


def test_catppuccin_theme_switch(page, base_url):
    """PR-D5 회귀 가드 — catppuccin 테마 옵션 클릭 + 적용 검증.

    이전 e2e 는 dark/light/glass 만 검증 → catppuccin 누락. 2026-05-11 UI 리디자인 후 4번째 옵션.
    Previous e2e covered dark/light/glass only; catppuccin (2026-05-11 redesign) was missing.
    """
    page.goto(base_url)
    page.click("#themeToggle")
    page.wait_for_selector(".theme-switcher.open", timeout=2000)
    # catppuccin 옵션 존재 + 클릭 가능
    # catppuccin option must exist + be clickable
    page.click(_option("catppuccin"))
    assert page.get_attribute("body", "data-theme") == "catppuccin"
    # 드롭다운 자동 닫힘
    # Dropdown auto-closes
    assert not page.is_visible(".theme-switcher.open")
