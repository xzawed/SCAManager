"""E2E — 설정 페이지 테스트."""
import pytest

SETTINGS_URL = "/repos/owner%2Ftestrepo/settings"


def _expand_advanced(page):
    """고급 설정 아코디언이 접혀 있으면 펼친다 (멱등).

    UI 리디자인(a1aedd1)으로 Gate 모드 버튼·임계값 슬라이더가
    <details class="advanced-details"> 안으로 이동해 기본 상태에서 invisible.
    click() 이 필요한 테스트는 이 헬퍼를 먼저 호출해야 한다.
    """
    is_open = page.evaluate(
        "document.querySelector('.advanced-details')?.open ?? false"
    )
    if not is_open:
        page.locator(".advanced-details > summary").click()
        page.wait_for_timeout(200)


def test_settings_page_loads(seeded_page, base_url):
    """설정 페이지가 정상적으로 로드되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    assert seeded_page.title() == "설정 — owner/testrepo"


def test_preset_cards_exist(seeded_page, base_url):
    """프리셋 아코디언 카드 3개가 렌더링되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    assert seeded_page.locator("#preset-minimal").count() == 1
    assert seeded_page.locator("#preset-standard").count() == 1
    assert seeded_page.locator("#preset-strict").count() == 1


def test_preset_cards_collapsed_by_default(seeded_page, base_url):
    """프리셋 카드는 초기에 모두 접혀 있어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    for preset_id in ["preset-minimal", "preset-standard", "preset-strict"]:
        is_open = seeded_page.evaluate(
            f"document.getElementById('{preset_id}').open"
        )
        assert not is_open, f"{preset_id} 는 초기에 접혀 있어야 합니다"


def test_preset_minimal_expand_applies_settings(seeded_page, base_url):
    """최소 프리셋 카드 펼침 시 설정이 자동 적용되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-minimal summary").click()
    seeded_page.wait_for_timeout(300)
    # PR 코드리뷰 댓글 활성, 커밋 코멘트 비활성 확인
    assert seeded_page.locator('input[name="pr_review_comment"]').is_checked()
    assert not seeded_page.locator('input[name="commit_comment"]').is_checked()
    # Approve mode = disabled
    assert seeded_page.input_value("#approveModeValue") == "disabled"
    # 적용됨 레이블 표시
    assert seeded_page.locator("#pt-label-minimal").is_visible()


def test_preset_standard_expand_applies_settings(seeded_page, base_url):
    """표준 프리셋 카드 펼침 시 설정이 자동 적용되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-standard summary").click()
    seeded_page.wait_for_timeout(300)
    assert seeded_page.locator('input[name="pr_review_comment"]').is_checked()
    assert seeded_page.locator('input[name="commit_comment"]').is_checked()
    assert seeded_page.input_value("#approveModeValue") == "auto"
    assert not seeded_page.locator('input[name="auto_merge"]').is_checked()
    assert seeded_page.locator("#pt-label-standard").is_visible()


def test_preset_strict_expand_applies_settings(seeded_page, base_url):
    """엄격 프리셋 카드 펼침 시 설정이 자동 적용되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-strict summary").click()
    seeded_page.wait_for_timeout(300)
    assert seeded_page.locator('input[name="create_issue"]').is_checked()
    assert seeded_page.locator('input[name="auto_merge"]').is_checked()
    assert seeded_page.input_value("#approveModeValue") == "auto"
    # 엄격 임계값 확인
    assert seeded_page.input_value('input[name="approve_threshold"]') == "85"
    assert seeded_page.input_value('input[name="reject_threshold"]') == "60"
    assert seeded_page.locator("#pt-label-strict").is_visible()


def test_preset_accordion_closes_others(seeded_page, base_url):
    """한 프리셋 카드를 열면 다른 카드는 닫혀야 한다 (아코디언)."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    # 최소 먼저 펼침
    seeded_page.locator("#preset-minimal summary").click()
    seeded_page.wait_for_timeout(200)
    assert seeded_page.evaluate("document.getElementById('preset-minimal').open")
    # 표준 펼침 → 최소가 닫혀야 함
    seeded_page.locator("#preset-standard summary").click()
    seeded_page.wait_for_timeout(200)
    assert seeded_page.evaluate("document.getElementById('preset-standard').open")
    assert not seeded_page.evaluate("document.getElementById('preset-minimal').open")


def test_gate_mode_disabled_is_default(seeded_page, base_url):
    """초기 Gate 모드는 비활성 상태여야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    cls = seeded_page.get_attribute('[data-mode="disabled"]', "class") or ""
    assert "active" in cls


def test_gate_mode_auto_button_click(seeded_page, base_url):
    """자동 모드 버튼 클릭 시 active 클래스와 hidden input 값이 변경되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    seeded_page.click('[data-mode="auto"]')
    # hidden input 값 확인 (현재 필드명: approveModeValue)
    assert seeded_page.input_value("#approveModeValue") == "auto"
    # active 클래스 확인
    cls = seeded_page.get_attribute('[data-mode="auto"]', "class") or ""
    assert "active" in cls
    # 다른 버튼에는 active 없어야 함
    cls_disabled = seeded_page.get_attribute('[data-mode="disabled"]', "class") or ""
    assert "active" not in cls_disabled


def test_gate_mode_semi_auto_button_click(seeded_page, base_url):
    """반자동 모드 버튼 클릭이 동작해야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    seeded_page.click('[data-mode="semi-auto"]')
    assert seeded_page.input_value("#approveModeValue") == "semi-auto"
    cls = seeded_page.get_attribute('[data-mode="semi-auto"]', "class") or ""
    assert "active" in cls


def test_approve_slider_updates_number_input(seeded_page, base_url):
    """승인 임계값 슬라이더 조작 시 숫자 인풋이 업데이트되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    # 고급 설정 아코디언 펼치기 (Gate 모드 버튼이 내부에 있어 기본 상태에서 invisible)
    _expand_advanced(seeded_page)
    # disabled 모드에서는 슬라이더가 숨겨져 있으므로 먼저 auto로 전환
    seeded_page.click('[data-mode="auto"]')
    seeded_page.evaluate(
        """() => {
            const el = document.querySelector('input[name="approve_threshold"]');
            el.value = '85';
            el.dispatchEvent(new Event('input'));
        }"""
    )
    assert seeded_page.input_value("#approveVal") == "85"


def test_reject_slider_updates_number_input(seeded_page, base_url):
    """반려 임계값 슬라이더 조작 시 숫자 인풋이 업데이트되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    seeded_page.click('[data-mode="auto"]')
    seeded_page.evaluate(
        """() => {
            const el = document.querySelector('input[name="reject_threshold"]');
            el.value = '30';
            el.dispatchEvent(new Event('input'));
        }"""
    )
    assert seeded_page.input_value("#rejectVal") == "30"


def test_approve_threshold_hidden_when_disabled(seeded_page, base_url):
    """Approve 모드 비활성 시 임계값 슬라이더 영역이 숨겨져야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    seeded_page.click('[data-mode="disabled"]')
    is_hidden = seeded_page.evaluate(
        "document.getElementById('approveThresholds').classList.contains('is-hidden')"
    )
    assert is_hidden


def test_approve_threshold_visible_when_auto(seeded_page, base_url):
    """Approve 모드 자동 선택 시 임계값 슬라이더 영역이 표시되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    seeded_page.click('[data-mode="auto"]')
    is_hidden = seeded_page.evaluate(
        "document.getElementById('approveThresholds').classList.contains('is-hidden')"
    )
    assert not is_hidden


def test_semi_auto_hint_visible_only_when_semi_auto(seeded_page, base_url):
    """반자동 모드 선택 시에만 반자동 안내 힌트(#semiAutoHint)가 노출되어야 한다.

    UI 리디자인(a1aedd1) 이후 Telegram Chat ID 는 ③ 알림 채널 카드로 이동했으므로
    telegramChatRow 대신 semiAutoHint 가시성으로 검증한다.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    # 기본(disabled): semiAutoHint 숨김
    hidden_default = seeded_page.evaluate(
        "document.getElementById('semiAutoHint').classList.contains('is-hidden')"
    )
    assert hidden_default
    # semi-auto: semiAutoHint 노출
    seeded_page.click('[data-mode="semi-auto"]')
    hidden_semi = seeded_page.evaluate(
        "document.getElementById('semiAutoHint').classList.contains('is-hidden')"
    )
    assert not hidden_semi


def test_merge_threshold_hidden_when_auto_merge_off(seeded_page, base_url):
    """Auto Merge 비활성 시 Merge 임계값 영역이 숨겨져야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    # 초기에는 auto_merge 꺼져 있음
    is_hidden = seeded_page.evaluate(
        "document.getElementById('mergeThresholdRow').classList.contains('is-hidden')"
    )
    assert is_hidden


def test_settings_form_submit_redirects(seeded_page, base_url):
    """설정 저장 후 같은 설정 페이지로 리다이렉트되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    seeded_page.click('[data-mode="auto"]')
    seeded_page.locator('.btn-save-new').click()
    seeded_page.wait_for_load_state("networkidle", timeout=5000)
    assert "/settings" in seeded_page.url


def test_gate_mode_persists_after_save(seeded_page, base_url):
    """저장한 Gate 모드가 리로드 후에도 유지되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    seeded_page.click('[data-mode="auto"]')
    seeded_page.locator('.btn-save-new').click()
    seeded_page.wait_for_load_state("networkidle", timeout=5000)
    # 리로드 후에도 advanced-details 펼쳐야 버튼 class 를 읽을 수 있음
    _expand_advanced(seeded_page)
    cls = seeded_page.get_attribute('[data-mode="auto"]', "class") or ""
    assert "active" in cls


def test_preset_standard_persists_after_save(seeded_page, base_url):
    """표준 프리셋 적용 후 저장하면 리로드 후에도 값이 유지되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-standard summary").click()
    seeded_page.wait_for_timeout(300)
    seeded_page.locator('.btn-save-new').click()
    seeded_page.wait_for_load_state("networkidle", timeout=5000)
    # 저장 후 approve_mode=auto 확인
    cls = seeded_page.get_attribute('[data-mode="auto"]', "class") or ""
    assert "active" in cls


def test_single_column_layout_on_mobile(seeded_page, base_url):
    """375px 뷰포트에서 설정 그리드가 1컬럼이어야 한다."""
    seeded_page.set_viewport_size({"width": 375, "height": 812})
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    columns = seeded_page.evaluate(
        "getComputedStyle(document.querySelector('.settings-grid')).gridTemplateColumns"
    )
    # 1열이면 단일 값(예: "860px" 또는 "375px" 등 하나의 값)
    assert columns.count(" ") == 0 or columns.strip().split() == [columns.strip().split()[0]]


def test_two_column_layout_on_desktop(seeded_page, base_url):
    """1024px 뷰포트에서 설정 그리드가 2컬럼이어야 한다."""
    seeded_page.set_viewport_size({"width": 1024, "height": 768})
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    columns = seeded_page.evaluate(
        "getComputedStyle(document.querySelector('.settings-grid')).gridTemplateColumns"
    )
    # 2열: 값 사이에 공백이 있어야 함 (예: "430px 430px")
    parts = columns.strip().split()
    assert len(parts) == 2, f"데스크탑에서 2열이어야 하는데 '{columns}' 반환됨"
