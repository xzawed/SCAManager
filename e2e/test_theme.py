"""E2E — 테마 전환 테스트."""
import pytest


def test_default_theme_is_dark(page, base_url):
    """초기 접속 시 다크 테마가 기본값이어야 한다."""
    page.goto(base_url)
    assert page.get_attribute("body", "data-theme") == "dark"


def test_theme_switcher_dropdown_opens(page, base_url):
    """테마 버튼 클릭 시 드롭다운이 열려야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.wait_for_selector(".theme-switcher.open", timeout=2000)
    assert page.is_visible('[data-theme="light"]')


def test_switch_to_light_theme(page, base_url):
    """클린(라이트) 테마로 전환되어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click('[data-theme="light"]')
    assert page.get_attribute("body", "data-theme") == "light"


def test_switch_to_glass_theme(page, base_url):
    """글래스모피즘 테마로 전환되어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click('[data-theme="glass"]')
    assert page.get_attribute("body", "data-theme") == "glass"


def test_theme_persists_after_reload(page, base_url):
    """테마 선택 후 새로고침해도 테마가 유지되어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click('[data-theme="light"]')
    page.reload()
    assert page.get_attribute("body", "data-theme") == "light"


def test_theme_saved_to_localstorage(page, base_url):
    """선택한 테마가 localStorage에 저장되어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click('[data-theme="glass"]')
    value = page.evaluate("localStorage.getItem('sca-theme')")
    assert value == "glass"


def test_active_class_on_selected_theme(page, base_url):
    """선택된 테마 옵션에 active 클래스가 붙어야 한다."""
    page.goto(base_url)
    page.click("#themeToggle")
    page.click('.theme-option[data-theme="light"]')
    # 드롭다운 다시 열기
    # Re-open the dropdown.
    page.click("#themeToggle")
    cls = page.get_attribute('.theme-option[data-theme="light"]', "class") or ""
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
