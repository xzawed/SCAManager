"""E2E — 설정 페이지 테스트."""
import pytest

SETTINGS_URL = "/repos/owner%2Ftestrepo/settings"


def test_settings_page_loads(seeded_page, base_url):
    """설정 페이지가 정상적으로 로드되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    assert seeded_page.title() == "설정 — owner/testrepo"


def test_gate_mode_disabled_is_default(seeded_page, base_url):
    """초기 Gate 모드는 비활성 상태여야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    cls = seeded_page.get_attribute('[data-mode="disabled"]', "class") or ""
    assert "active" in cls


def test_gate_mode_auto_button_click(seeded_page, base_url):
    """자동 모드 버튼 클릭 시 active 클래스와 hidden input 값이 변경되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.click('[data-mode="auto"]')
    # hidden input 값 확인
    assert seeded_page.input_value("#gateModeValue") == "auto"
    # active 클래스 확인
    cls = seeded_page.get_attribute('[data-mode="auto"]', "class") or ""
    assert "active" in cls
    # 다른 버튼에는 active 없어야 함
    cls_disabled = seeded_page.get_attribute('[data-mode="disabled"]', "class") or ""
    assert "active" not in cls_disabled


def test_gate_mode_semi_auto_button_click(seeded_page, base_url):
    """반자동 모드 버튼 클릭이 동작해야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.click('[data-mode="semi-auto"]')
    assert seeded_page.input_value("#gateModeValue") == "semi-auto"
    cls = seeded_page.get_attribute('[data-mode="semi-auto"]', "class") or ""
    assert "active" in cls


def test_approve_slider_updates_badge(seeded_page, base_url):
    """승인 임계값 슬라이더 조작 시 배지 숫자가 업데이트되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    slider = seeded_page.locator('input[name="auto_approve_threshold"]')
    # JavaScript로 값 변경 + input 이벤트 발생
    seeded_page.evaluate(
        """() => {
            const el = document.querySelector('input[name="auto_approve_threshold"]');
            el.value = '85';
            el.dispatchEvent(new Event('input'));
        }"""
    )
    assert seeded_page.text_content("#approveVal") == "85"


def test_reject_slider_updates_badge(seeded_page, base_url):
    """반려 임계값 슬라이더 조작 시 배지 숫자가 업데이트되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.evaluate(
        """() => {
            const el = document.querySelector('input[name="auto_reject_threshold"]');
            el.value = '30';
            el.dispatchEvent(new Event('input'));
        }"""
    )
    assert seeded_page.text_content("#rejectVal") == "30"


def test_auto_merge_toggle_switches_checkbox(seeded_page, base_url):
    """auto_merge 토글 클릭 시 체크박스 상태가 반전되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    checkbox = seeded_page.locator('input[name="auto_merge"]')
    initial = checkbox.is_checked()
    seeded_page.click(".toggle-track")
    assert checkbox.is_checked() != initial


def test_settings_form_submit_redirects(seeded_page, base_url):
    """설정 저장 후 같은 설정 페이지로 리다이렉트되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.click('[data-mode="auto"]')
    seeded_page.click('button[type="submit"]')
    # redirect URL은 디코딩된 경로(/repos/owner/testrepo/settings)
    seeded_page.wait_for_url("**/settings", timeout=5000)
    assert "/settings" in seeded_page.url


def test_gate_mode_persists_after_save(seeded_page, base_url):
    """저장한 Gate 모드가 리로드 후에도 유지되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.click('[data-mode="auto"]')
    seeded_page.click('button[type="submit"]')
    # redirect URL은 디코딩된 경로(/repos/owner/testrepo/settings)
    seeded_page.wait_for_url("**/settings", timeout=5000)
    # 저장 후 active 버튼 확인
    cls = seeded_page.get_attribute('[data-mode="auto"]', "class") or ""
    assert "active" in cls
