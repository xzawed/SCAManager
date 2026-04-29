"""E2E — 설정 페이지 테스트."""
import pytest

SETTINGS_URL = "/repos/owner%2Ftestrepo/settings"


def _expand_advanced(page):
    """고급 설정 아코디언이 접혀 있으면 펼친다 (멱등).

    UI 리디자인(a1aedd1 + PR #89)으로 Gate 모드 버튼·임계값 슬라이더가
    <details class="advanced-details"> 안으로 이동해 기본 상태에서 invisible.
    또한 Settings UI/UX 리디자인 후 'simple/advanced' 모드 토글이 추가되어
    기본값이 'simple' 일 때 advanced-details 가 CSS `display:none !important` —
    Playwright actionability check 에서 30s timeout 발생.

    헬퍼는 두 단계 보정:
      1) data-settings-mode 를 'advanced' 로 설정 + localStorage 영속화
      2) <details> 가 닫혀있으면 summary 클릭으로 펼침
    """
    # 1단계 — Simple/Advanced 모드 토글: Simple 이 기본이면 advanced-details 가
    # display:none 이라 클릭 자체 불가능. 직접 attribute 설정으로 강제 advanced.
    # Step 1 — Force advanced mode so .advanced-details becomes visible
    page.evaluate(
        "document.body.setAttribute('data-settings-mode','advanced'); "
        "(document.querySelector('main')||{}).setAttribute"
        "&&document.querySelector('main').setAttribute('data-settings-mode','advanced'); "
        "try{localStorage.setItem('sca-settings-mode','advanced')}catch(e){}"
    )
    # 2단계 — <details> 펼침
    # Step 2 — Open the <details> if collapsed
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


def test_preset_minimal_apply_button_applies_settings(seeded_page, base_url):
    """최소 프리셋 카드 펼침 → '이 프리셋 적용 →' 버튼 클릭 시 설정이 적용되어야 한다.

    P1 재설계(renderPresetDiff): 펼침 시 diff 미리보기만 렌더, 버튼 클릭으로 적용.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-minimal summary").click()
    seeded_page.wait_for_timeout(300)
    # 펼침 직후에는 아직 적용되지 않음 — diff 미리보기만 렌더
    # Immediately after expanding, it is not yet applied — only the diff preview is rendered.
    assert seeded_page.locator("#preset-diff-minimal tr").count() == 9
    # Apply 버튼 클릭 → 적용
    seeded_page.locator("#preset-minimal .preset-apply-btn").click()
    seeded_page.wait_for_timeout(300)
    assert seeded_page.locator('input[name="pr_review_comment"]').is_checked()
    assert not seeded_page.locator('input[name="commit_comment"]').is_checked()
    assert seeded_page.input_value("#approveModeValue") == "disabled"
    assert seeded_page.locator("#pt-label-minimal").is_visible()


def test_preset_standard_apply_button_applies_settings(seeded_page, base_url):
    """표준 프리셋 카드 펼침 → Apply 버튼 클릭 시 설정이 적용되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-standard summary").click()
    seeded_page.wait_for_timeout(300)
    assert seeded_page.locator("#preset-diff-standard tr").count() == 9
    seeded_page.locator("#preset-standard .preset-apply-btn").click()
    seeded_page.wait_for_timeout(300)
    assert seeded_page.locator('input[name="pr_review_comment"]').is_checked()
    assert seeded_page.locator('input[name="commit_comment"]').is_checked()
    assert seeded_page.input_value("#approveModeValue") == "auto"
    assert not seeded_page.locator('input[name="auto_merge"]').is_checked()
    assert seeded_page.locator("#pt-label-standard").is_visible()


def test_preset_strict_apply_button_applies_settings(seeded_page, base_url):
    """엄격 프리셋 카드 펼침 → Apply 버튼 클릭 시 설정이 적용되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-strict summary").click()
    seeded_page.wait_for_timeout(300)
    assert seeded_page.locator("#preset-diff-strict tr").count() == 9
    seeded_page.locator("#preset-strict .preset-apply-btn").click()
    seeded_page.wait_for_timeout(300)
    assert seeded_page.locator('input[name="create_issue"]').is_checked()
    assert seeded_page.locator('input[name="auto_merge"]').is_checked()
    assert seeded_page.input_value("#approveModeValue") == "auto"
    assert seeded_page.input_value('input[name="approve_threshold"]') == "85"
    assert seeded_page.input_value('input[name="reject_threshold"]') == "60"
    assert seeded_page.locator("#pt-label-strict").is_visible()


def test_preset_accordion_closes_others(seeded_page, base_url):
    """한 프리셋 카드를 열면 다른 카드는 닫혀야 한다 (아코디언)."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    # 최소 먼저 펼침
    # Expand minimal preset first.
    seeded_page.locator("#preset-minimal summary").click()
    seeded_page.wait_for_timeout(200)
    assert seeded_page.evaluate("document.getElementById('preset-minimal').open")
    # 표준 펼침 → 최소가 닫혀야 함
    # Expand standard → minimal must collapse.
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
    # Other buttons must not have the active class.
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
    # Expand the advanced settings accordion (Gate mode buttons are inside and invisible by default).
    _expand_advanced(seeded_page)
    # disabled 모드에서는 슬라이더가 숨겨져 있으므로 먼저 auto로 전환
    # In disabled mode the slider is hidden, so switch to auto first.
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


# ── Telegram 연결 카드 E2E 테스트 ──────────────────────────────────────
# ── Telegram connect card E2E tests ──────────────────────────────────────


def test_telegram_connect_section_visible(seeded_page, base_url):
    """카드 ⑤ 내 Telegram 연결 서브섹션이 설정 페이지에 렌더링되어야 한다.
    Telegram connection subsection must render inside card ⑤ of the settings page.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    # Settings UI/UX 리디자인 (PR #89) 으로 id 가 -notify suffix 로 갱신됨
    # Settings UI/UX redesign (PR #89) renamed the section id with `-notify` suffix
    assert seeded_page.locator("#telegram-connect-section-notify").count() == 1
    assert seeded_page.locator("#telegram-connect-section-notify").is_visible()


def test_telegram_otp_button_visible_when_not_connected(seeded_page, base_url):
    """미연결 사용자에게는 '연결 코드 발급' 버튼이 표시되어야 한다.
    The 'Issue Code' button must be visible for a user without a linked Telegram account.

    E2E 시드 사용자는 telegram_user_id = NULL 이므로 미연결 상태.
    The E2E seeded user has telegram_user_id = NULL, so it is in the unlinked state.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    btn = seeded_page.locator("#issueTelegramOtp")
    assert btn.count() == 1
    assert btn.is_visible()
    assert not btn.is_disabled()


def test_telegram_otp_issue_shows_six_digit_code(seeded_page, base_url):
    """'연결 코드 발급' 버튼 클릭 시 6자리 숫자 OTP가 화면에 표시되어야 한다.
    Clicking 'Issue Code' must display a 6-digit numeric OTP on screen.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    # OTP 표시 영역은 초기에 숨겨져 있어야 한다 / OTP display must be hidden initially.
    assert seeded_page.evaluate(
        "document.getElementById('telegramOtpDisplay').style.display === 'none' || "
        "!document.getElementById('telegramOtpDisplay')"
    )
    seeded_page.locator("#issueTelegramOtp").click()
    # OTP API 응답 및 DOM 업데이트 대기 / Wait for OTP API response and DOM update.
    seeded_page.wait_for_selector("#telegramOtpDisplay", state="visible", timeout=5000)
    otp_text = seeded_page.locator("#telegramOtpCode").inner_text()
    # 6자리 숫자 문자열이어야 한다 / Must be a 6-digit numeric string.
    assert len(otp_text) == 6, f"OTP 길이 오류: {otp_text!r}"
    assert otp_text.isdigit(), f"OTP에 비숫자 문자 포함: {otp_text!r}"


def test_telegram_otp_button_disabled_while_timer_runs(seeded_page, base_url):
    """OTP 발급 후 타이머 실행 중에는 버튼이 비활성화되어야 한다.
    The issue button must be disabled while the countdown timer is running.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#issueTelegramOtp").click()
    seeded_page.wait_for_selector("#telegramOtpDisplay", state="visible", timeout=5000)
    # 타이머 실행 중이므로 버튼은 비활성화 상태여야 한다
    # Button must be disabled while the timer is running.
    assert seeded_page.locator("#issueTelegramOtp").is_disabled()
    # 카운트다운 텍스트가 "4:" 또는 "5:" 로 시작해야 한다 (5분 이내)
    # Countdown text must start with "4:" or "5:" (within 5 minutes).
    countdown = seeded_page.locator("#telegramOtpCountdown").inner_text()
    assert countdown.startswith(("5:", "4:")), f"카운트다운 형식 오류: {countdown!r}"


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
    seeded_page.locator('button[type="submit"].btn-save-new').click()
    seeded_page.wait_for_load_state("networkidle", timeout=5000)
    assert "/settings" in seeded_page.url


def test_gate_mode_persists_after_save(seeded_page, base_url):
    """저장한 Gate 모드가 리로드 후에도 유지되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    _expand_advanced(seeded_page)
    seeded_page.click('[data-mode="auto"]')
    seeded_page.locator('button[type="submit"].btn-save-new').click()
    seeded_page.wait_for_load_state("networkidle", timeout=5000)
    # 리로드 후에도 advanced-details 펼쳐야 버튼 class 를 읽을 수 있음
    _expand_advanced(seeded_page)
    cls = seeded_page.get_attribute('[data-mode="auto"]', "class") or ""
    assert "active" in cls


def test_preset_standard_persists_after_save(seeded_page, base_url):
    """표준 프리셋 Apply 버튼 클릭 후 저장하면 리로드 후에도 값이 유지되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-standard summary").click()
    seeded_page.wait_for_timeout(300)
    seeded_page.locator("#preset-standard .preset-apply-btn").click()
    seeded_page.wait_for_timeout(300)
    seeded_page.locator('button[type="submit"].btn-save-new').click()
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
    # Single column: one value (e.g. "860px" or "375px").
    assert columns.count(" ") == 0 or columns.strip().split() == [columns.strip().split()[0]]


def test_two_column_layout_on_desktop(seeded_page, base_url):
    """1024px 뷰포트에서 설정 그리드가 2컬럼이어야 한다."""
    seeded_page.set_viewport_size({"width": 1024, "height": 768})
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    columns = seeded_page.evaluate(
        "getComputedStyle(document.querySelector('.settings-grid')).gridTemplateColumns"
    )
    # 2열: 값 사이에 공백이 있어야 함 (예: "430px 430px")
    # Two columns: values must be space-separated (e.g. "430px 430px").
    parts = columns.strip().split()
    assert len(parts) == 2, f"데스크탑에서 2열이어야 하는데 '{columns}' 반환됨"


# ── Settings 재설계 E2E 테스트 (2026-04-21) ──────────────────────────

def test_six_card_titles_present(seeded_page, base_url):
    """6 카드 의도 기반 제목이 모두 렌더링되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    body = seeded_page.content()
    # ① 빠른 설정 제목은 기존 유지 — 개별 프리셋 카드로 대체
    # ① Quick settings heading is preserved — replaced by individual preset cards.
    # PR #89 카드명 변경 — 의도 기반 명칭으로 갱신
    # PR #89 renamed cards to intent-based labels
    assert "분석 동작 규칙" in body, "카드 ② 분석 동작 규칙 누락"
    assert "Push / 배포 이벤트" in body, "카드 ③ Push / 배포 이벤트 누락"
    assert "통합 &amp; 연결" in body or "통합 & 연결" in body, "카드 ⑤ 통합 & 연결 누락"
    assert "위험 구역" in body, "카드 ⑥ 위험 구역 누락"


def test_preset_diff_preview_has_nine_rows(seeded_page, base_url):
    """프리셋 카드 펼침 시 9개 필드 diff 테이블이 렌더링되어야 한다.

    P1: renderPresetDiff() — 펼침 이벤트에 diff 테이블 채움 (자동 적용 아님).
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-minimal summary").click()
    seeded_page.wait_for_timeout(300)
    rows = seeded_page.locator("#preset-diff-minimal tr").count()
    assert rows == 9, f"프리셋 diff 행 9개 기대, 실제 {rows}"


def test_preset_diff_has_unchanged_fields_dimmed(seeded_page, base_url):
    """현재값과 같은 필드는 opacity:.45 로 흐리게 표시되어야 한다.

    P1: 초기 상태(기본값) 에서 minimal 프리셋 대부분이 불변 → 여러 행이 흐림.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    seeded_page.locator("#preset-minimal summary").click()
    seeded_page.wait_for_timeout(300)
    dim_count = seeded_page.evaluate(
        """() => {
            const rows = document.querySelectorAll('#preset-diff-minimal tr');
            let n = 0;
            rows.forEach(r => {
                if ((r.getAttribute('style') || '').includes('opacity:.45')) n++;
            });
            return n;
        }"""
    )
    # 기본 config 는 minimal 에 가까워 최소 3개 이상 불변 필드 존재
    assert dim_count >= 3, f"흐린(opacity:.45) 행 3개 이상 기대, 실제 {dim_count}"


def test_p2_highlight_applied_on_apply(seeded_page, base_url):
    """프리셋 Apply 버튼 클릭 시 변경된 필드에 .preset-just-applied 클래스가 부착되어야 한다.

    P2: flashPresetChanges() + @keyframes preset-flash 2.5s.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    # strict 프리셋 — 현재(기본)와 차이가 많아 하이라이트 대상 다수
    # strict preset — many differences from the current (default) state → many highlighted fields.
    seeded_page.locator("#preset-strict summary").click()
    seeded_page.wait_for_timeout(200)
    seeded_page.locator("#preset-strict .preset-apply-btn").click()
    # 클릭 직후 곧바로 클래스 존재 확인 (2.5초 타이머 전)
    # Verify class presence immediately after click (before the 2.5s timer fires).
    seeded_page.wait_for_timeout(100)
    highlighted = seeded_page.evaluate(
        "document.querySelectorAll('.preset-just-applied').length"
    )
    assert highlighted >= 1, f"preset-just-applied 클래스 1개 이상 기대, 실제 {highlighted}"


def test_railway_alerts_toggle_switch_visible(seeded_page, base_url):
    """railway_deploy_alerts 가 toggle-switch label 안에 있고 보여야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    is_in_toggle_switch = seeded_page.evaluate(
        """() => {
            const input = document.querySelector('input[name="railway_deploy_alerts"]');
            if (!input) return false;
            const parent = input.closest('label');
            return parent ? parent.classList.contains('toggle-switch') : false;
        }"""
    )
    assert is_in_toggle_switch, "railway_deploy_alerts 가 toggle-switch label 내부에 없음"


def test_railway_api_token_mask_toggle(seeded_page, base_url):
    """Railway API 토큰 👁️ mask-toggle 버튼으로 password ↔ text 전환."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    token_input = seeded_page.locator('input[name="railway_api_token"]')
    # 초기 password 타입
    assert token_input.get_attribute("type") == "password"
    # mask-toggle 버튼 클릭 → text 전환
    seeded_page.evaluate(
        """() => {
            const input = document.querySelector('input[name="railway_api_token"]');
            const btn = input.nextElementSibling;
            btn.click();
        }"""
    )
    seeded_page.wait_for_timeout(100)
    assert token_input.get_attribute("type") == "text"


def test_railway_api_token_in_main_form(seeded_page, base_url):
    """Railway API 토큰 input 이 form='settingsForm' 속성으로 메인 폼에 바인딩되어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    form_attr = seeded_page.get_attribute('input[name="railway_api_token"]', "form")
    assert form_attr == "settingsForm", f"railway_api_token form 속성이 'settingsForm' 이어야 하는데 {form_attr!r}"


def test_save_error_opens_advanced_accordion(seeded_page, base_url):
    """?save_error=1 쿼리로 접근 시 고급설정 아코디언이 자동 펼쳐져야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}?save_error=1")
    seeded_page.wait_for_timeout(300)
    is_open = seeded_page.evaluate(
        "document.querySelector('.advanced-details')?.open"
    )
    assert is_open is True, "save_error=1 쿼리 시 .advanced-details 가 펼쳐져야 함"


def test_save_success_keeps_advanced_accordion_closed(seeded_page, base_url):
    """?saved=1 (성공) 쿼리로 접근 시 고급설정 아코디언은 펼쳐지지 않아야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}?saved=1")
    seeded_page.wait_for_timeout(300)
    is_open = seeded_page.evaluate(
        "document.querySelector('.advanced-details')?.open"
    )
    assert not is_open, "saved=1 쿼리 시 .advanced-details 는 기본 접힘 유지"


def test_auto_merge_in_pr_card_not_push_card(seeded_page, base_url):
    """auto_merge 체크박스가 PR 카드('분석 동작 규칙') 안에 있어야 한다 (Push 카드 아님).

    PR #89 Settings UI/UX 리디자인으로 카드명이 의도 기반('분석 동작 규칙') 으로 갱신됨.
    PR #89 renamed the card to intent-based '분석 동작 규칙'.
    """
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    # auto_merge input 의 가장 가까운 s-card 헤더 타이틀 확인
    card_title = seeded_page.evaluate(
        """() => {
            const input = document.querySelector('input[name="auto_merge"]');
            if (!input) return null;
            const card = input.closest('.s-card');
            if (!card) return null;
            const title = card.querySelector('.hdr-title');
            return title ? title.textContent.trim() : null;
        }"""
    )
    assert card_title == "분석 동작 규칙", (
        f"auto_merge 의 상위 카드 타이틀이 '분석 동작 규칙' 여야 하는데 '{card_title}' 임"
    )


def test_danger_zone_outside_main_form(seeded_page, base_url):
    """위험 구역(리포 삭제 form)이 메인 <form id='settingsForm'> 바깥에 있어야 한다."""
    seeded_page.goto(f"{base_url}{SETTINGS_URL}")
    outside = seeded_page.evaluate(
        """() => {
            const main = document.getElementById('settingsForm');
            if (!main) return false;
            const dangerBtn = document.querySelector('form[action$="/delete"] button[type="submit"]');
            if (!dangerBtn) return false;
            return !main.contains(dangerBtn);
        }"""
    )
    assert outside, "위험 구역 삭제 버튼이 메인 폼 바깥에 있어야 함"
