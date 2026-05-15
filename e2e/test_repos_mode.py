"""Dashboard repos 모드 E2E 회귀가드.
E2E regression guard for Dashboard repos mode.
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_repos_tab_visible(page: Page, base_url: str, auth_cookies):
    """repos 탭 링크가 Dashboard에 표시된다."""
    page.goto(f"{base_url}/dashboard")
    expect(page.get_by_role("link", name="Repos")).to_be_visible()


@pytest.mark.e2e
def test_repos_mode_summary_visible(page: Page, base_url: str, auth_cookies):
    """repos 모드 진입 시 KPI 카드와 드롭다운이 렌더링된다."""
    page.goto(f"{base_url}/dashboard?mode=repos")
    expect(page.locator(".repos-kpi-grid")).to_be_visible()
    expect(page.locator(".repos-selector")).to_be_visible()


@pytest.mark.e2e
def test_repos_mode_empty_state(page: Page, base_url: str, auth_cookies):
    """Repo 미선택 시 레포트 섹션이 없어야 한다."""
    page.goto(f"{base_url}/dashboard?mode=repos")
    expect(page.locator(".repos-report")).not_to_be_visible()
