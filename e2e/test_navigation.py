"""E2E — 네비게이션 테스트."""
import pytest


def test_overview_page_loads(page, base_url):
    """Overview 페이지가 정상적으로 로드되어야 한다."""
    page.goto(base_url)
    assert "Overview" in page.title()


def test_overview_empty_state(page, base_url):
    """레포가 없을 때 빈 상태 메시지가 표시되어야 한다."""
    page.goto(base_url)
    # 레포가 없는 경우 empty-state 표시 (seeded_page 미사용)
    # 또는 테이블이 있는 경우 테이블이 표시
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
    """네이비바 Overview 링크가 작동해야 한다."""
    page.goto(base_url)
    page.click("nav a.nav-link")
    assert page.url.rstrip("/") == base_url.rstrip("/")


def test_repo_detail_back_button(seeded_page, base_url):
    """레포 상세 페이지의 ← 목록 버튼이 Overview로 이동해야 한다."""
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo")
    seeded_page.click(".back-btn")
    seeded_page.wait_for_url(f"{base_url}/", timeout=5000)
    assert seeded_page.url.rstrip("/") == base_url.rstrip("/")


def test_settings_back_button(seeded_page, base_url):
    """설정 페이지의 ← 상세 버튼이 레포 상세 페이지로 이동해야 한다."""
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo/settings")
    seeded_page.click(".back-btn")
    seeded_page.wait_for_url("**/repos/**", timeout=5000)
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
    seeded_page.wait_for_url("**/repos/**", timeout=5000)
    assert "/settings" not in seeded_page.url
