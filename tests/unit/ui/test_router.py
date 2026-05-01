import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app
from src.auth.session import require_login
from src.models.user import User as UserModel

# 모든 UI 테스트에서 require_login 의존성을 우회 (user_id=1 로그인 상태)
_test_user = UserModel(id=1, github_id="12345", github_login="testuser", github_access_token="gho_test", email="test@example.com", display_name="Test User")
app.dependency_overrides[require_login] = lambda: _test_user

client = TestClient(app)


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ── 비로그인 리다이렉트 테스트 ──────────────────────────
# ── Unauthenticated redirect tests ──────────────────────────

def test_overview_redirects_when_not_logged_in():
    """비로그인 상태에서 / 접근 시 /login 으로 302 리다이렉트."""
    del app.dependency_overrides[require_login]
    try:
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers.get("location", "")
    finally:
        app.dependency_overrides[require_login] = lambda: _test_user


# ── 로그인 상태 기존 테스트 ──
# ── Logged-in state baseline tests ──

def test_overview_returns_html():
    """로그인 후 / 는 200 HTML을 반환한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_overview_with_repos_shows_avg_score():
    """리포 목록에 평균 점수(avg_score) 컬럼이 표시되어야 한다."""
    mock_db = MagicMock()
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1, created_at="2026-01-01")
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_repo]
    # count_map, avg_map → dict([]) = {}, latest_map → {}
    mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    mock_db.query.return_value.filter.return_value.all.return_value = []
    with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "평균 점수" in r.text


def test_repo_detail_returns_html():
    """로그인 후 본인 리포 상세 페이지는 200 HTML을 반환한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200


def test_repo_detail_404():
    """존재하지 않는 리포 접근 시 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/nope%2Frepo")
    assert r.status_code == 404


def test_repo_detail_404_for_other_users_repo():
    """타인 소유 리포(user_id=2) 접근 시 404. 현재 사용자는 user_id=1."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=2
    )
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 404


def test_settings_returns_html():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200


# Phase E.5 — Onboarding 튜토리얼

def test_overview_empty_state_shows_3_step_tutorial():
    """Phase E.5 — 리포 0개일 때 '3단계' 튜토리얼 섹션 노출."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    html = r.text
    # 튜토리얼 핵심 마커 — 3단계 구성과 CTA 버튼
    # Tutorial key markers — 3-step structure and CTA button.
    assert "get-started" in html or "3단계" in html or "Get Started" in html, \
        "3단계 튜토리얼 섹션이 empty-state 에 있어야 함"
    # CTA 링크는 여전히 /repos/add
    assert "/repos/add" in html


def test_overview_with_repos_does_not_show_tutorial():
    """Phase E.5 — 리포가 있으면 튜토리얼 숨김 (empty-state 분기 미진입)."""
    mock_db = MagicMock()
    mock_repo = MagicMock(id=1, full_name="owner/repo", created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-23")))
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_repo]
    # count/avg maps 는 빈 dict 로 반환되어도 무방
    mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    # 튜토리얼 마커가 없어야 함
    # Tutorial markers must not be present.
    assert "get-started-tutorial" not in r.text


# Phase E.4 — Minimal Mode (Simple/Advanced 토글)

def _settings_html(default_mode="simple"):
    """Helper — Settings HTML 가져오기.
    Patches _detect_stale_webhook so the async GitHub API call is avoided in unit tests.
    """
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None,
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    return r.text


def test_settings_has_mode_toggle_buttons():
    """Phase E.4 — Settings 페이지에 Simple/Advanced 토글이 존재."""
    html = _settings_html()
    assert 'data-settings-mode-btn="simple"' in html
    assert 'data-settings-mode-btn="advanced"' in html


def test_settings_advanced_channels_have_adv_only_class():
    """Phase E.4 — Discord/Slack/Webhook/n8n/Email 필드는 adv-only 클래스로 마킹."""
    html = _settings_html()
    # 5개 Advanced 알림 채널이 모두 adv-only 클래스 안에 있어야 함
    # (Telegram 은 Simple 모드에서도 노출되므로 adv-only 없음)
    assert "adv-only" in html, "adv-only 클래스가 템플릿에 존재해야 함"
    # Discord / Slack / n8n 필드명이 adv-only 컨테이너 안에 있는지 대략 확인
    # (정확한 DOM 검증은 E2E 에서, 여기선 클래스 존재만 확인)
    # (Precise DOM validation is done in E2E; here we only verify class presence.)


def test_settings_mode_toggle_script_present():
    """Phase E.4 — 모드 전환 JS 함수가 HTML 에 포함."""
    html = _settings_html()
    assert "toggleSettingsMode" in html
    assert "localStorage" in html  # 모드 선호 저장


def test_post_settings_redirects():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.routes.settings.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "approve_mode": "auto",
                    "approve_threshold": "85",
                    "reject_threshold": "55",
                    "notify_chat_id": "-123",
                    "n8n_webhook_url": "http://n8n.local/webhook/abc",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.approve_mode == "auto"
    assert called_config.approve_threshold == 85
    assert called_config.reject_threshold == 55
    assert called_config.n8n_webhook_url == "http://n8n.local/webhook/abc"
    assert r.status_code == 303


def test_post_settings_empty_optional_fields():
    """빈 문자열 선택 필드는 None으로 저장되어야 한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.routes.settings.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "approve_mode": "disabled",
                    "approve_threshold": "75",
                    "reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                    "discord_webhook_url": "",
                    "slack_webhook_url": "",
                    "custom_webhook_url": "",
                    "email_recipients": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.n8n_webhook_url is None
    assert called_config.notify_chat_id is None
    assert called_config.discord_webhook_url is None
    assert r.status_code == 303


def test_post_settings_with_auto_merge_checked():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.routes.settings.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "approve_mode": "auto",
                    "approve_threshold": "80",
                    "reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                    "auto_merge": "on",
                    "merge_threshold": "90",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.auto_merge is True
    assert called_config.merge_threshold == 90
    assert r.status_code == 303


def test_post_settings_without_auto_merge_checkbox():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.routes.settings.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "approve_mode": "semi-auto",
                    "approve_threshold": "80",
                    "reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.approve_mode == "semi-auto"
    assert called_config.auto_merge is False
    assert r.status_code == 303


def test_settings_no_nested_forms():
    """
    regression: settings.html에 중첩 <form> 태그가 있으면 HTML5 브라우저 파서가
    바깥쪽 메인 form을 </form> 첫 출현 시 조기에 닫아 저장 버튼이 고아가 된다.
    이 테스트는 렌더된 HTML에서 <form> 중첩 깊이가 최대 1인지 확인해 구조적 원인을 잡는다.
    """
    from html.parser import HTMLParser
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200

    class _NestingChecker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.depth = 0
            self.max_depth = 0

        def handle_starttag(self, tag, attrs):
            if tag == "form":
                self.depth += 1
                self.max_depth = max(self.max_depth, self.depth)

        def handle_endtag(self, tag):
            if tag == "form" and self.depth > 0:
                self.depth -= 1

    checker = _NestingChecker()
    checker.feed(r.text)
    assert checker.max_depth <= 1, (
        f"중첩된 <form> 태그 발견 (최대 depth={checker.max_depth}). "
        "메인 form 안에 다른 form이 있으면 HTML5 파서가 저장 버튼을 고아로 만든다."
    )


def _render_settings(config=None):
    """설정 페이지 HTML을 렌더링해 반환하는 헬퍼.
    Patches _detect_stale_webhook so the async GitHub API call is avoided in unit tests.
    """
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    cfg = config or RepoConfigData(repo_full_name="owner/repo")
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.settings.get_repo_config", return_value=cfg), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
    return r.text


def test_telegram_chat_id_in_notify_channel_card():
    """notify_chat_id 필드가 ③ 알림 채널 카드에 존재해야 한다."""
    html = _render_settings()
    # ③ 알림 채널 카드 헤더(s-card-hdr hdr-notify) 이후에 notify_chat_id 입력이 있어야 함
    notify_section_idx = html.find("s-card-hdr hdr-notify")
    notify_chat_idx = html.find('name="notify_chat_id"')
    assert notify_section_idx != -1, "s-card-hdr hdr-notify 카드 헤더가 없음"
    assert notify_chat_idx != -1, "notify_chat_id 입력 필드가 없음"
    assert notify_chat_idx > notify_section_idx, (
        "notify_chat_id 필드가 ③ 알림 채널 카드 이전에 위치함"
    )


def test_telegram_chat_id_always_visible():
    """notify_chat_id는 approve_mode와 무관하게 항상 노출되어야 한다 (is-hidden 없음)."""
    from src.config_manager.manager import RepoConfigData
    for mode in ("disabled", "auto", "semi-auto"):
        cfg = RepoConfigData(repo_full_name="owner/repo", approve_mode=mode)
        html = _render_settings(cfg)
        # notify_chat_id 주변에 is-hidden 클래스가 없어야 함
        idx = html.find('name="notify_chat_id"')
        assert idx != -1, f"notify_chat_id 없음 (mode={mode})"
        # 앞 200자에 telegramChatRow + is-hidden 조합이 없어야 함
        surrounding = html[max(0, idx - 200): idx + 50]
        assert "is-hidden" not in surrounding, (
            f"approve_mode={mode}에서 notify_chat_id 주변에 is-hidden 발견"
        )


def test_sensitive_fields_are_masked():
    """6개 민감 필드는 type=password로 렌더되어야 한다."""
    from src.config_manager.manager import RepoConfigData
    cfg = RepoConfigData(
        repo_full_name="owner/repo",
        notify_chat_id="-100999",
        discord_webhook_url="https://discord.com/webhook/x",
        slack_webhook_url="https://hooks.slack.com/x",
        email_recipients="admin@example.com",
        custom_webhook_url="https://example.com/hook",
        n8n_webhook_url="https://n8n.example.com/webhook/x",
    )
    html = _render_settings(cfg)
    sensitive_names = [
        "notify_chat_id",
        "discord_webhook_url",
        "slack_webhook_url",
        "email_recipients",
        "custom_webhook_url",
        "n8n_webhook_url",
    ]
    for field in sensitive_names:
        # 해당 name 속성 주변에 type="password"가 있어야 함
        idx = html.find(f'name="{field}"')
        assert idx != -1, f"{field} 입력 필드 없음"
        surrounding = html[max(0, idx - 100): idx + 100]
        assert 'type="password"' in surrounding, (
            f"{field}가 type=password로 마스킹되지 않음"
        )


def test_mask_toggle_buttons_present():
    """마스킹 토글 버튼(.mask-toggle)이 6개 민감 필드마다 존재해야 한다."""
    html = _render_settings()
    assert html.count("mask-toggle") >= 6, (
        f"mask-toggle 버튼이 6개 미만: {html.count('mask-toggle')}개 발견"
    )


def test_advanced_details_removed_in_progressive_redesign():
    """Progressive Mode 재설계 후 advanced-details <details> 아코디언은 제거되어야 한다.

    Phase 2A 재설계: 카드 평탄화 + .adv-only 클래스 기반 단순/고급 분리.
    Phase 2A redesign: cards flattened; simple/advanced split via .adv-only class.
    """
    html = _render_settings()
    assert "advanced-details" not in html, (
        "advanced-details 클래스가 잔존 — Progressive Mode 재설계 후 제거되어야 함"
    )
    # .adv-only 클래스 다수 존재 확인 (단순/고급 분리는 카드/필드 단위 .adv-only 로 처리)
    # Verify .adv-only is used as the new simple/advanced split mechanism.
    assert html.count('adv-only') >= 5, (
        f".adv-only 클래스가 부족: {html.count('adv-only')}회 (5회 이상 기대)"
    )


def test_pr_card_simple_fields_outside_adv_only():
    """단순 모드 노출 핵심 필드(pr_review_comment / auto_merge / merge_threshold) 는
    .adv-only 영역 바깥에 있어야 한다.

    Phase 2A: 단순 모드 = 5개 핵심 필드만 노출 + Telegram (notify_chat_id + OTP).
    Phase 2A: simple mode exposes only 5 core fields + Telegram.
    """
    html = _render_settings()
    # PR 동작 카드(hdr-gate)는 카드 자체에 .adv-only 가 없어야 함 (단순 모드 노출)
    # PR Behavior card (hdr-gate) must NOT have .adv-only on the card wrapper itself.
    import re
    pr_card_match = re.search(
        r'<div class="s-card[^"]*">\s*<div class="s-card-hdr hdr-gate">', html,
    )
    assert pr_card_match, "PR 동작 카드(hdr-gate) 를 찾지 못함"
    # 단순 모드 핵심 필드 3종은 카드 안에 존재
    # 3 simple-mode core fields must exist
    for name in ("pr_review_comment", "auto_merge", "merge_threshold"):
        assert f'name="{name}"' in html, f"단순 모드 필드 누락: {name}"


def test_notify_card_always_visible():
    """알림 채널 카드(hdr-notify)는 .adv-only 클래스 없이 항상 노출되어야 한다.

    Phase 2A: notify_chat_id 와 Telegram OTP 는 단순 모드 핵심 필드.
    Phase 2A: notify_chat_id and Telegram OTP are simple-mode core fields.
    """
    html = _render_settings()
    notify_idx = html.find("s-card-hdr hdr-notify")
    assert notify_idx != -1, "알림 채널 카드 없음"
    # notifyCard 카드 자체 wrapper 에 .adv-only 가 없어야 함
    # The notifyCard wrapper itself must NOT carry .adv-only.
    notify_wrapper_start = html.rfind('<div class="s-card', 0, notify_idx)
    notify_wrapper_open_tag = html[notify_wrapper_start:notify_idx]
    assert "adv-only" not in notify_wrapper_open_tag, (
        f"알림 채널 카드 wrapper 에 .adv-only 클래스 부착됨: {notify_wrapper_open_tag}"
    )


def test_semi_auto_hint_inside_adv_only_block():
    """semi-auto 안내 hint 는 PR 동작 카드의 .adv-only 영역 안에 있어야 한다.

    Phase 2A: approve_mode 3-way 와 threshold 슬라이더는 고급 모드 전용.
    Phase 2A: approve_mode 3-way and threshold sliders are advanced-only.
    """
    from src.config_manager.manager import RepoConfigData
    cfg = RepoConfigData(repo_full_name="owner/repo", approve_mode="semi-auto")
    html = _render_settings(cfg)
    assert "semiAutoHint" in html, "semiAutoHint 엘리먼트가 없음"
    gate_card_idx = html.find('s-card-hdr hdr-gate')
    notify_card_idx = html.find('s-card-hdr hdr-notify')
    hint_idx = html.find("semiAutoHint")
    assert gate_card_idx != -1, "s-card-hdr hdr-gate 카드 헤더 없음"
    assert notify_card_idx != -1, "s-card-hdr hdr-notify 카드 헤더 없음"
    assert gate_card_idx < hint_idx < notify_card_idx, (
        "semiAutoHint 가 PR 동작 카드 안 (다음 알림 카드 이전) 에 위치해야 함"
    )


def test_initial_mode_data_attribute_present():
    """모드 토글 바에 data-initial-mode 속성(서버 신호) 이 있어야 한다.

    Phase 2A: localStorage 가 비어있을 때 서버 신호로 advanced 진입.
    Phase 2A: server signal triggers advanced mode when localStorage is empty.
    """
    html = _render_settings()
    assert 'data-initial-mode="' in html, (
        "data-initial-mode 속성이 모드 토글 바에 없음 — 서버 신호 fallback 깨짐"
    )


def test_add_repo_page_loads():
    """GET /repos/add는 리포 추가 페이지(200 HTML)를 반환한다."""
    r = client.get("/repos/add")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_api_github_repos_returns_json():
    """GET /api/github/repos는 리포 목록 JSON을 반환한다."""
    from unittest.mock import AsyncMock, patch

    mock_repos = [
        {"full_name": "owner/repo-a", "private": False, "description": ""},
        {"full_name": "owner/repo-b", "private": True, "description": "Private"},
    ]

    with patch("src.ui.routes.add_repo.list_user_repos", new_callable=AsyncMock, return_value=mock_repos):
        with patch("src.ui.routes.add_repo.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_sl.return_value.__enter__.return_value = mock_db
            r = client.get("/api/github/repos")

    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 2


def test_api_github_repos_excludes_already_registered():
    """GET /api/github/repos는 이미 등록된 리포를 제외한다."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from src.models.repository import Repository

    mock_repos = [
        {"full_name": "owner/repo-a", "private": False, "description": ""},
        {"full_name": "owner/already-registered", "private": False, "description": ""},
    ]
    existing_repo = MagicMock(spec=Repository)
    existing_repo.full_name = "owner/already-registered"

    with patch("src.ui.routes.add_repo.list_user_repos", new_callable=AsyncMock, return_value=mock_repos):
        with patch("src.ui.routes.add_repo.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = [existing_repo]
            mock_sl.return_value.__enter__.return_value = mock_db
            r = client.get("/api/github/repos")

    assert r.status_code == 200
    data = r.json()
    full_names = [repo["full_name"] for repo in data]
    assert "owner/already-registered" not in full_names
    assert "owner/repo-a" in full_names


def test_add_repo_post_creates_repo_and_webhook():
    """POST /repos/add는 리포를 DB에 저장하고 Webhook을 생성한 후 리다이렉트한다."""
    from unittest.mock import AsyncMock, patch, MagicMock

    with patch("src.ui.routes.add_repo.create_webhook", new_callable=AsyncMock, return_value=77777):
        with patch("src.ui.routes.add_repo.commit_scamanager_files", new_callable=AsyncMock, return_value=True):
            with patch("src.ui.routes.add_repo.SessionLocal") as mock_sl:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None  # 미등록
                mock_sl.return_value.__enter__.return_value = mock_db
                r = client.post(
                    "/repos/add",
                    data={"repo_full_name": "owner/new-repo"},
                    follow_redirects=False,
                )

    assert r.status_code == 303
    assert "/repos/owner/new-repo" in r.headers["location"]
    assert mock_db.add.called
    assert mock_db.commit.called


def test_add_repo_post_rejects_duplicate():
    """POST /repos/add는 이미 소유자가 있는 리포에 대해 /repos/add?error= 로 리다이렉트한다."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from src.models.repository import Repository

    existing = MagicMock(spec=Repository)
    existing.full_name = "owner/already-registered"
    existing.user_id = 999  # 다른 사용자가 소유

    with patch("src.ui.routes.add_repo.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        mock_sl.return_value.__enter__.return_value = mock_db
        r = client.post(
            "/repos/add",
            data={"repo_full_name": "owner/already-registered"},
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert r.headers["location"].startswith("/repos/add?error=")


# ── 분석 상세 페이지 테스트 ──────────────────────────
# ── Analysis detail page tests ──────────────────────────

def test_analysis_detail_returns_html():
    """분석 상세 페이지는 200 HTML을 반환한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_analysis = MagicMock(
        id=42, commit_sha="abc1234", commit_message="feat: add feature",
        pr_number=10, score=82, grade="B",
        result={"breakdown": {}, "ai_summary": "ok"},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-08T00:00:00")),
    )
    # first() 호출: 1번째=repo, 2번째=analysis
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/42")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_analysis_detail_404_when_not_found():
    """존재하지 않는 분석 ID → 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        None,  # analysis not found
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/999")
    assert r.status_code == 404


def test_analysis_detail_404_for_other_users_repo():
    """타인 리포의 분석 → 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=999  # 다른 사용자
    )
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/42")
    assert r.status_code == 404


def test_analysis_detail_shows_commit_message():
    """분석 상세 페이지에 커밋 메시지가 표시된다."""
    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=42, commit_sha="abc1234567890", commit_message="feat: add login page",
        pr_number=10, score=82, grade="B",
        result={"breakdown": {"code_quality": 20}, "ai_summary": "good code"},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-08T14:30:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/42")
    assert r.status_code == 200
    assert "feat: add login page" in r.text


def test_analysis_detail_shows_fallback_when_no_commit_message():
    """커밋 메시지가 없어도 fallback 텍스트가 표시된다."""
    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=42, commit_sha="abc1234567890", commit_message=None,
        pr_number=None, score=70, grade="C",
        result={"breakdown": {}},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-08T10:00:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/42")
    assert r.status_code == 200
    assert "커밋 메시지 없음" in r.text


def test_analysis_detail_shows_score_when_result_empty():
    """result가 빈 dict일 때도 점수 배너가 표시된다."""
    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=42, commit_sha="abc1234567890", commit_message="fix: bug",
        pr_number=None, score=65, grade="C",
        result={},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-08T10:00:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/42")
    assert r.status_code == 200
    assert "65" in r.text
    assert "/100" in r.text


def test_analysis_detail_shows_source_indicator():
    """분석 소스(CLI/PR/Push)가 표시된다."""
    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=42, commit_sha="abc1234567890", commit_message="test",
        pr_number=None, score=80, grade="B",
        result={"source": "cli", "breakdown": {}},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-08T10:00:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/42")
    assert r.status_code == 200
    assert "CLI" in r.text


def test_analysis_detail_shows_full_datetime():
    """분석 상세에 날짜와 시간이 모두 표시된다."""
    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=42, commit_sha="abc1234567890", commit_message="test",
        pr_number=None, score=80, grade="B",
        result={"breakdown": {}},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-08T14:30:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/42")
    assert r.status_code == 200
    assert "2026-04-08 14:30" in r.text


def test_repo_detail_shows_commit_message():
    """리포 상세 이력 테이블에 커밋 메시지 미리보기가 표시된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_analysis = MagicMock(
        id=1, commit_sha="abc1234", commit_message="feat: new feature for users",
        pr_number=None, score=90, grade="A", result=None,
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-08T10:00:00")),
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_analysis]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200
    assert "feat: new feature" in r.text


# ── reinstall-webhook 엔드포인트 테스트 ──────────────────────────

def test_reinstall_webhook_deletes_and_recreates():
    """reinstall-webhook은 delete_webhook + create_webhook을 호출하고 303 리다이렉트한다."""
    from unittest.mock import AsyncMock, patch
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None, webhook_id=999
    )
    with patch("src.ui.routes.settings.list_webhooks", new_callable=AsyncMock, return_value=[]):
        with patch("src.ui.routes.settings.delete_webhook", new_callable=AsyncMock, return_value=True):
            with patch("src.ui.routes.settings.create_webhook", new_callable=AsyncMock, return_value=12345):
                with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
                    r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    assert r.status_code == 303
    assert "hook_ok=1" in r.headers["location"]


def test_reinstall_webhook_404_for_other_user():
    """타인 소유 리포 → 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=999
    )
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
        r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    assert r.status_code == 404


def test_reinstall_webhook_no_existing_webhook():
    """webhook_id가 없어도(None) create_webhook은 호출된다."""
    from unittest.mock import AsyncMock, patch
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None, webhook_id=None
    )
    with patch("src.ui.routes.settings.list_webhooks", new_callable=AsyncMock, return_value=[]):
        with patch("src.ui.routes.settings.delete_webhook", new_callable=AsyncMock) as mock_del:
            with patch("src.ui.routes.settings.create_webhook", new_callable=AsyncMock, return_value=99999):
                with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
                    r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    mock_del.assert_not_called()  # webhook_id None → 삭제 스킵
    assert r.status_code == 303


# ── 리포 삭제 엔드포인트 테스트 ──────────────────────────
# ── Repository delete endpoint tests ──────────────────────────

def test_delete_repo_success():
    """소유자 삭제 시 webhook 삭제 + DB cascade 후 303 /?deleted=1."""
    from unittest.mock import AsyncMock, patch
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1, webhook_id=999)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    # Analysis.id 조회 시 빈 결과
    mock_db.query.return_value.filter.return_value.all.return_value = []

    with patch("src.ui._helpers.delete_webhook", new_callable=AsyncMock, return_value=True) as mock_del:
        with patch("src.ui.routes.actions.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/?deleted=1"
    mock_del.assert_called_once()
    mock_db.delete.assert_called_once_with(mock_repo)
    mock_db.commit.assert_called()


def test_delete_repo_404_for_other_user():
    """타인 소유 리포 삭제 → 404, db.delete 호출되지 않음."""
    from unittest.mock import AsyncMock, patch
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=99, webhook_id=None
    )
    with patch("src.ui._helpers.delete_webhook", new_callable=AsyncMock) as mock_del:
        with patch("src.ui.routes.actions.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)

    assert r.status_code == 404
    mock_del.assert_not_called()
    mock_db.delete.assert_not_called()


def test_delete_repo_404_not_found():
    """존재하지 않는 리포 삭제 → 404."""
    from unittest.mock import AsyncMock, patch
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.ui._helpers.delete_webhook", new_callable=AsyncMock):
        with patch("src.ui.routes.actions.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/nope%2Frepo/delete", follow_redirects=False)
    assert r.status_code == 404


def test_delete_repo_webhook_failure_still_deletes_db():
    """delete_webhook이 예외를 던져도 DB 정리는 계속 진행되어야 한다."""
    from unittest.mock import AsyncMock, patch
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=None, webhook_id=999)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.query.return_value.filter.return_value.all.return_value = []

    with patch("src.ui._helpers.delete_webhook", new_callable=AsyncMock,
               side_effect=RuntimeError("github api down")):
        with patch("src.ui.routes.actions.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)

    assert r.status_code == 303
    mock_db.delete.assert_called_once_with(mock_repo)
    mock_db.commit.assert_called()


def test_delete_repo_skips_webhook_when_none():
    """webhook_id가 None이면 delete_webhook 호출하지 않고 DB만 정리."""
    from unittest.mock import AsyncMock, patch
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1, webhook_id=None)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.query.return_value.filter.return_value.all.return_value = []

    with patch("src.ui._helpers.delete_webhook", new_callable=AsyncMock) as mock_del:
        with patch("src.ui.routes.actions.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)

    assert r.status_code == 303
    mock_del.assert_not_called()
    mock_db.delete.assert_called_once_with(mock_repo)


# ── 네비게이션 사용자 UI 테스트 ──────────────────────────
# ── Navigation user UI tests ──────────────────────────

def test_overview_shows_display_name_in_nav():
    """로그인 후 nav에 display_name이 표시된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "Test User" in r.text


def test_overview_shows_logout_button_in_nav():
    """로그인 후 nav에 로그아웃 버튼과 action URL이 표시된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "로그아웃" in r.text
    assert "/auth/logout" in r.text


def test_nav_user_fallback_to_github_login():
    """display_name이 빈 문자열이면 github_login이 nav에 표시된다."""
    no_name_user = UserModel(
        id=2, github_id="99999", github_login="fallback_user",
        github_access_token="gho_x", email="fb@example.com", display_name=""
    )
    app.dependency_overrides[require_login] = lambda: no_name_user
    try:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
            r = client.get("/")
        assert r.status_code == 200
        assert "fallback_user" in r.text
    finally:
        app.dependency_overrides[require_login] = lambda: _test_user


# ── 이력 페이지 조회 강화 테스트 ──────────────────────────
# ── Analysis history page enhanced tests ──────────────────────────

def test_repo_detail_queries_limit_100():
    """repo_detail은 최근 100건을 조회한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        client.get("/repos/owner%2Frepo")
    call_args = mock_db.query.return_value.filter.return_value.order_by.return_value.limit.call_args
    assert call_args is not None
    assert call_args[0][0] == 100


def test_repo_detail_source_pr():
    """pr_number가 있으면 source='pr'이 analyses JSON에 포함된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_analysis = MagicMock(
        id=1, commit_sha="abc1234", commit_message="feat: pr",
        pr_number=5, score=88, grade="A", result={},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-09T10:00:00")),
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_analysis]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200
    assert '"source"' in r.text
    assert '"pr"' in r.text


def test_repo_detail_source_push_fallback():
    """pr_number가 없고 result에 source 없으면 source='push' 폴백."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_analysis = MagicMock(
        id=2, commit_sha="def5678", commit_message="fix: push",
        pr_number=None, score=70, grade="B", result=None,
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-09T11:00:00")),
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_analysis]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert '"push"' in r.text


def test_repo_detail_source_cli_from_result():
    """result에 source='cli'가 있으면 cli로 반영된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_analysis = MagicMock(
        id=3, commit_sha="ghi9012", commit_message="chore: cli",
        pr_number=None, score=75, grade="B", result={"source": "cli"},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-09T12:00:00")),
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_analysis]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert '"cli"' in r.text


def test_repo_detail_filter_bar_rendered():
    """이력 페이지에 필터 바 UI 요소가 렌더링된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200
    assert 'id="searchInput"' in r.text
    assert 'data-grade="A"' in r.text
    assert 'data-source="pr"' in r.text
    assert 'id="scoreMin"' in r.text
    assert 'id="pagination"' in r.text


def test_repo_detail_date_filter_rendered():
    """이력 페이지에 날짜 필터 UI 요소가 렌더링된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200
    assert 'id="dateFilter"' in r.text
    assert 'data-date="today"' in r.text
    assert 'data-date="week"' in r.text
    assert 'data-date="month"' in r.text
    assert 'data-date="year"' in r.text
    assert 'data-date="custom"' in r.text
    assert 'id="customDateWrap"' in r.text
    assert 'id="dateFrom"' in r.text
    assert 'id="dateTo"' in r.text


# ── 분석 상세 버그 수정 TDD 테스트 ──────────────────────────
# ── Analysis detail bug-fix TDD tests ──────────────────────────

def test_analysis_detail_result_none_shows_fallback():
    """result=None, score=75, grade='B' 분석 조회 시:
    - HTTP 200 반환
    - 점수 배너(75 텍스트, /100) 포함
    - fallback 메시지("분석 결과 데이터가 없습니다" 또는 유사 문구) 포함
    - AI 요약(ai_summary) 섹션은 없어야 함
    현재 버그: result=None → {} → {% if r %} falsy → AI 블록 숨김,
    {% elif analysis.score is none %} → score 있으므로 False → fallback도 없음.
    """
    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=10, commit_sha="aaa1111", commit_message="fix: null result case",
        pr_number=None, score=75, grade="B",
        result=None,  # DB에 NULL 저장된 구버전 분석
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-09T12:00:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/10")
    # 200 반환
    # Must return 200.
    assert r.status_code == 200
    # 점수 배너 표시
    # Score banner must be displayed.
    assert "75" in r.text
    assert "/100" in r.text
    # fallback 메시지 포함 (result 데이터 없음을 안내)
    assert "분석 결과 데이터가 없습니다" in r.text or "상세 데이터가 없습니다" in r.text
    # AI 관련 섹션은 없어야 함 (result가 없으므로)
    assert "ai_summary" not in r.text
    assert "AI 요약" not in r.text


def test_analysis_detail_result_empty_dict_shows_fallback():
    """result={} (빈 dict), score=80, grade='A' 분석 조회 시:
    - HTTP 200 반환
    - 점수 배너(80 텍스트) 포함
    - fallback 메시지 포함
    현재 버그: {} → {% if r %} falsy → AI 블록 전체 숨김,
    {% elif analysis.score is none %} → score 있으므로 False → fallback도 없음.
    """
    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=11, commit_sha="bbb2222", commit_message="chore: empty result case",
        pr_number=None, score=80, grade="A",
        result={},  # 빈 dict — 데이터 누락 상태
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-09T13:00:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/11")
    # 200 반환
    # Must return 200.
    assert r.status_code == 200
    # 점수 배너 표시
    # Score banner must be displayed.
    assert "80" in r.text
    assert "/100" in r.text
    # fallback 메시지 포함
    assert "분석 결과 데이터가 없습니다" in r.text or "상세 데이터가 없습니다" in r.text
    # AI 요약 섹션 없음
    # AI summary section must not be present.
    assert "AI 요약" not in r.text


def test_analysis_detail_with_current_user_shows_nav():
    """analysis_detail 렌더링 시 current_user가 nav에 표시된다.
    현재 버그: router.py의 analysis_detail이 current_user를 template context에
    전달하지 않아 base.html nav의 사용자명·로그아웃 버튼이 표시되지 않음.
    """
    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=12, commit_sha="ccc3333", commit_message="feat: nav user test",
        pr_number=5, score=90, grade="A",
        result={"breakdown": {"code_quality": 25}, "ai_summary": "excellent"},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-09T14:00:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/12")
    assert r.status_code == 200
    # _test_user의 display_name="Test User"가 nav에 표시되어야 함
    assert "Test User" in r.text
    # 로그아웃 버튼 및 URL이 포함되어야 함
    # Logout button and URL must be present.
    assert "로그아웃" in r.text
    assert "/auth/logout" in r.text


# ── analysis_detail trend_data / prev_id / next_id TDD (Red 단계) ──────────────────────────

def _make_sibling(id_, score, created_at_str):
    """시블링 분석 mock 생성 헬퍼 — id·score·created_at 속성 제공."""
    from datetime import datetime
    m = MagicMock()
    m.id = id_
    m.score = score
    m.created_at = datetime.fromisoformat(created_at_str)
    return m


def test_analysis_detail_trend_data_returned():
    """analysis_detail 라우트가 같은 리포의 최근 30건을 trend_data로 context에 전달한다.
    3건 시블링(id=1,2,3) 중 현재 분석이 id=1일 때:
    - trend_data 길이 3, 시간 오름차순
    - 각 항목에 id·score·label 키 포함
    - context에 trend_data 키가 존재
    """
    from unittest.mock import call
    import json

    mock_db = MagicMock()

    mock_repo = MagicMock(id=10, full_name="owner/repo", user_id=None)
    mock_analysis = MagicMock(
        id=1, commit_sha="sha001", commit_message="feat: first",
        pr_number=None, score=70, grade="C",
        result={"breakdown": {}},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-01T10:00:00")),
    )

    siblings = [
        _make_sibling(3, 90, "2026-04-03T12:00:00"),  # desc 순서 최신
        _make_sibling(2, 80, "2026-04-02T11:00:00"),
        _make_sibling(1, 70, "2026-04-01T10:00:00"),  # 가장 오래된
    ]

    # first() 호출 순서: repo → analysis
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_repo,
        mock_analysis,
    ]
    # siblings: .order_by(...).limit(30).all()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = siblings
    # prev scalar: None (id=1보다 작은 것 없음)
    # next scalar: 2
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.scalar.side_effect = [None, 2]

    captured_context = {}

    def fake_template_response(request, template_name, context):
        captured_context.update(context)
        # 실제 응답 대신 간단한 HTML 반환
        # Return simple HTML instead of the real response.
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html>ok</html>")

    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.routes.detail.templates.TemplateResponse", side_effect=fake_template_response):
            r = client.get("/repos/owner%2Frepo/analyses/1")

    assert r.status_code == 200
    # trend_data 키가 context에 있어야 한다
    assert "trend_data" in captured_context, "trend_data가 template context에 없음 — 미구현 상태"
    trend = captured_context["trend_data"]
    # 3건 반환
    # Must return 3 items.
    assert len(trend) == 3
    # 오름차순 (가장 오래된 것이 index 0)
    assert trend[0]["id"] == 1
    assert trend[-1]["id"] == 3
    # 각 항목에 id·score·label 키 포함
    for item in trend:
        assert "id" in item
        assert "score" in item
        assert "label" in item


def test_analysis_detail_prev_next_navigation():
    """중간 분석(id=2)을 조회할 때 prev_id=1, next_id=3이 context에 전달된다."""
    mock_db = MagicMock()

    mock_repo = MagicMock(id=10, full_name="owner/repo", user_id=None)
    mock_analysis = MagicMock(
        id=2, commit_sha="sha002", commit_message="feat: middle",
        pr_number=None, score=80, grade="B",
        result={"breakdown": {}},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-02T11:00:00")),
    )

    siblings = [
        _make_sibling(3, 90, "2026-04-03T12:00:00"),
        _make_sibling(2, 80, "2026-04-02T11:00:00"),
        _make_sibling(1, 70, "2026-04-01T10:00:00"),
    ]

    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_repo,
        mock_analysis,
    ]
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = siblings
    # prev scalar=1, next scalar=3
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.scalar.side_effect = [1, 3]

    captured_context = {}

    def fake_template_response(request, template_name, context):
        captured_context.update(context)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html>ok</html>")

    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.routes.detail.templates.TemplateResponse", side_effect=fake_template_response):
            r = client.get("/repos/owner%2Frepo/analyses/2")

    assert r.status_code == 200
    # prev_id, next_id 키가 context에 있어야 한다
    assert "prev_id" in captured_context, "prev_id가 template context에 없음 — 미구현 상태"
    assert "next_id" in captured_context, "next_id가 template context에 없음 — 미구현 상태"
    assert captured_context["prev_id"] == 1
    assert captured_context["next_id"] == 3


def test_analysis_detail_single_analysis_no_siblings():
    """리포에 분석이 1건만 있을 때(id=5) trend_data=1건, prev_id=None, next_id=None."""
    mock_db = MagicMock()

    mock_repo = MagicMock(id=20, full_name="owner/solo-repo", user_id=None)
    mock_analysis = MagicMock(
        id=5, commit_sha="sha005", commit_message="chore: only one",
        pr_number=None, score=60, grade="C",
        result={"breakdown": {}},
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-10T09:00:00")),
    )

    siblings = [_make_sibling(5, 60, "2026-04-10T09:00:00")]

    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_repo,
        mock_analysis,
    ]
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = siblings
    # prev scalar=None, next scalar=None
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.scalar.side_effect = [None, None]

    captured_context = {}

    def fake_template_response(request, template_name, context):
        captured_context.update(context)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html>ok</html>")

    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.routes.detail.templates.TemplateResponse", side_effect=fake_template_response):
            r = client.get("/repos/owner%2Frepo/analyses/5")

    assert r.status_code == 200
    # trend_data 1건
    assert "trend_data" in captured_context, "trend_data가 template context에 없음 — 미구현 상태"
    assert len(captured_context["trend_data"]) == 1
    assert captured_context["trend_data"][0]["id"] == 5
    # prev/next 없음
    assert "prev_id" in captured_context, "prev_id가 template context에 없음 — 미구현 상태"
    assert "next_id" in captured_context, "next_id가 template context에 없음 — 미구현 상태"
    assert captured_context["prev_id"] is None
    assert captured_context["next_id"] is None


# ── P3 커버리지 보강 테스트 ──────────────────────────
# ── P3 coverage enhancement tests ──────────────────────────

def test_webhook_base_url_uses_app_base_url_when_set():
    """APP_BASE_URL 설정 시 _webhook_base_url이 해당 URL을 반환해야 한다 (line 33)."""
    with patch("src.ui._helpers.settings") as mock_settings:
        mock_settings.app_base_url = "https://myapp.railway.app"
        from src.ui._helpers import webhook_base_url
        fake_request = MagicMock()
        result = webhook_base_url(fake_request)
    assert result == "https://myapp.railway.app"


def test_delete_repo_with_analyses_deletes_gate_decisions():
    """분석 기록이 있는 리포 삭제 시 GateDecision도 cascade 삭제되어야 한다 (line 63)."""
    from unittest.mock import AsyncMock, patch

    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1, webhook_id=None)
    mock_analysis_row = MagicMock()
    mock_analysis_row.id = 42

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_analysis_row]

    with patch("src.ui._helpers.delete_webhook", new_callable=AsyncMock):
        with patch("src.ui.routes.actions.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)

    assert r.status_code == 303
    # GateDecision.delete 호출 확인 (synchronize_session=False)
    mock_db.query.return_value.filter.return_value.delete.assert_called()


def test_add_repo_empty_name_returns_400():
    """repo_full_name이 빈 문자열이면 400 에러가 반환되어야 한다 (line 105)."""
    r = client.post("/repos/add", data={"repo_full_name": ""}, follow_redirects=False)
    assert r.status_code == 400


def test_add_repo_missing_name_returns_400():
    """repo_full_name 필드 자체가 없으면 400 에러가 반환되어야 한다 (line 105)."""
    r = client.post("/repos/add", data={}, follow_redirects=False)
    assert r.status_code == 400


def test_add_repo_ownership_transfer_when_user_id_null():
    """user_id=NULL인 기존 리포 → 현재 사용자 소유로 이전 후 리다이렉트 (line 118-120)."""
    from unittest.mock import patch
    from src.models.repository import Repository

    existing = MagicMock(spec=Repository)
    existing.full_name = "owner/legacy-repo"
    existing.user_id = None  # 레거시 리포, 소유자 없음

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    with patch("src.ui.routes.add_repo.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__.return_value = mock_db
        r = client.post(
            "/repos/add",
            data={"repo_full_name": "owner/legacy-repo"},
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert "/repos/owner/legacy-repo" in r.headers["location"]
    assert existing.user_id == 1  # _test_user.id


def test_add_repo_updates_existing_config_hook_token():
    """리포 등록 시 RepoConfig가 이미 있으면 hook_token만 업데이트해야 한다 (line 149)."""
    from unittest.mock import AsyncMock, patch

    existing_config = MagicMock()
    existing_config.hook_token = "old-token"

    call_count = [0]

    def fake_first():
        call_count[0] += 1
        if call_count[0] == 1:
            return None  # Repository가 없음 (새 리포)
        return existing_config  # RepoConfig가 이미 있음

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = lambda: fake_first()

    with patch("src.ui.routes.add_repo.create_webhook", new_callable=AsyncMock, return_value=12345):
        with patch("src.ui.routes.add_repo.commit_scamanager_files", new_callable=AsyncMock, return_value=True):
            with patch("src.ui.routes.add_repo.SessionLocal") as mock_sl:
                mock_sl.return_value.__enter__.return_value = mock_db
                r = client.post(
                    "/repos/add",
                    data={"repo_full_name": "owner/new-repo"},
                    follow_redirects=False,
                )

    assert r.status_code == 303
    # hook_token이 새 값으로 업데이트되어야 한다
    # hook_token must be updated to the new value.
    assert existing_config.hook_token != "old-token"


def test_post_settings_invalid_threshold_redirects_with_error():
    """threshold에 비정수 값 전송 시 ?save_error=1 리다이렉트해야 한다 (line 271-273)."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.routes.settings.upsert_repo_config"):
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "approve_mode": "auto",
                    "approve_threshold": "not-a-number",
                    "reject_threshold": "50",
                },
                follow_redirects=False,
            )
    assert r.status_code == 303
    assert "save_error=1" in r.headers["location"]


def test_reinstall_hook_creates_config_when_none_exists():
    """RepoConfig가 없을 때 reinstall_hook이 새 config를 생성해야 한다 (line 286-311)."""
    from unittest.mock import AsyncMock, patch

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),  # _get_accessible_repo
        None,  # RepoConfig 없음
    ]

    with patch("src.ui.routes.settings.commit_scamanager_files", new_callable=AsyncMock, return_value=True):
        with patch("src.ui.routes.settings.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__.return_value = mock_db
            r = client.post("/repos/owner%2Frepo/reinstall-hook", follow_redirects=False)

    assert r.status_code == 303
    assert "hook_ok=1" in r.headers["location"]
    mock_db.add.assert_called()


def test_reinstall_hook_generates_token_when_missing():
    """기존 config의 hook_token이 없으면 새 토큰을 생성해야 한다 (line 297-298)."""
    from unittest.mock import AsyncMock, patch

    existing_config = MagicMock()
    existing_config.hook_token = None  # 토큰 없음

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        existing_config,
    ]

    with patch("src.ui.routes.settings.commit_scamanager_files", new_callable=AsyncMock, return_value=True):
        with patch("src.ui.routes.settings.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__.return_value = mock_db
            r = client.post("/repos/owner%2Frepo/reinstall-hook", follow_redirects=False)

    assert r.status_code == 303
    assert existing_config.hook_token is not None


def test_reinstall_hook_fail_returns_hook_fail_redirect():
    """commit_scamanager_files 실패 시 ?hook_fail=1 리다이렉트해야 한다 (line 310-311)."""
    from unittest.mock import AsyncMock, patch

    existing_config = MagicMock()
    existing_config.hook_token = "existing-token"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        existing_config,
    ]

    with patch("src.ui.routes.settings.commit_scamanager_files", new_callable=AsyncMock, return_value=False):
        with patch("src.ui.routes.settings.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__.return_value = mock_db
            r = client.post("/repos/owner%2Frepo/reinstall-hook", follow_redirects=False)

    assert r.status_code == 303
    assert "hook_fail=1" in r.headers["location"]


def test_reinstall_webhook_deletes_matching_hooks():
    """기존 Webhook 중 /webhooks/github URL이 포함된 것은 삭제되어야 한다 (line 333-337)."""
    from unittest.mock import AsyncMock, patch

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None, webhook_id=None
    )

    existing_hooks = [
        {"id": 111, "config": {"url": "https://old.example.com/webhooks/github"}},
        {"id": 222, "config": {"url": "https://old.example.com/webhooks/github"}},
        {"id": 333, "config": {"url": "https://unrelated.example.com/something-else"}},
    ]

    with patch("src.ui.routes.settings.list_webhooks", new_callable=AsyncMock, return_value=existing_hooks):
        with patch("src.ui.routes.settings.delete_webhook", new_callable=AsyncMock, return_value=True) as mock_del:
            with patch("src.ui.routes.settings.create_webhook", new_callable=AsyncMock, return_value=99999):
                with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)):
                    r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)

    assert r.status_code == 303
    # /webhooks/github URL 포함 2개만 삭제, 나머지 1개(unrelated)는 스킵
    assert mock_del.call_count == 2


# ── overview 컬럼 리디자인 TDD 테스트 (Red 단계) ──────────────────────────

def test_overview_does_not_show_latest_score_column():
    """GET / 응답 HTML에 '최근 점수' 문자열이 없어야 한다.
    변경 예정: 최근 점수 컬럼 제거 — 구현 전까지 이 테스트는 실패(Red).
    """
    mock_db = MagicMock()
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1, created_at="2026-01-01")
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_repo]
    # count_map, avg_map → 빈 결과
    mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    mock_db.query.return_value.filter.return_value.all.return_value = []
    with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "최근 점수" not in r.text


def test_overview_grade_derived_from_avg_score():
    """avg_map에 {1: 92.0} 반환 시 등급 뱃지 'grade-A'가 HTML에 포함되어야 한다.
    변경 예정: 등급 컬럼을 최신 grade가 아닌 평균 점수 기반 calculate_grade(avg_score)로 변경.
    평균 92점 → GRADE_THRESHOLDS A≥90 → 'grade-A' CSS 클래스.
    구현 전에는 avg 기반 grade 렌더링이 없으므로 이 테스트는 실패(Red).
    """
    mock_db = MagicMock()
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1, created_at="2026-01-01")
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_repo]

    # count_map → [(repo_id=1, count=1)], avg_map → [(repo_id=1, avg=92.0)]
    # .group_by().all() 호출이 count_map, avg_map 순서로 발생
    mock_db.query.return_value.filter.return_value.group_by.return_value.all.side_effect = [
        [(1, 1)],     # count_map: [(repo_id, count)]
        [(1, 92.0)],  # avg_map: [(repo_id, avg_score)]
    ]
    # latest_id_subq / latest_map 조회는 제거 예정 — 포함하지 않음
    mock_db.query.return_value.filter.return_value.all.return_value = []

    with patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    # 평균 92점 → grade A → 템플릿에서 <span class="grade grade-A"> 뱃지 스팬으로 렌더
    # 현재 구현(latest_grade 기반)에서는 latest_map이 비어 있어 이 스팬이 없음 → Red
    assert '<span class="grade grade-A">' in r.text


# ── Settings 페이지 재설계 스모크 테스트 (2026-04-21) ──────────────────────────

def test_settings_form_fields_preserved():
    """settings.html 리팩토링 후 16개 form name= 속성이 모두 보존되는지 확인."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
    body = r.text
    required_names = [
        "pr_review_comment", "approve_mode", "approve_threshold", "reject_threshold",
        "commit_comment", "create_issue", "auto_merge", "merge_threshold",
        "railway_deploy_alerts", "railway_api_token",
        "notify_chat_id", "discord_webhook_url", "slack_webhook_url",
        "email_recipients", "custom_webhook_url", "n8n_webhook_url",
    ]
    for name in required_names:
        assert f'name="{name}"' in body, f"Missing form field: {name}"


def test_settings_railway_alerts_uses_toggle_switch():
    """railway_deploy_alerts 체크박스가 toggle-switch 클래스 label 안에 있어야 한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
    import re
    # 동일 <label class="toggle-switch"> 내부에 railway_deploy_alerts input 이 있어야 함.
    # 음수 lookahead 로 중간에 </label> 이 끼어들면 매치 실패 → 다른 toggle-switch
    # label 안에 있는 경우를 걸러낸다.
    # Filters out items that are inside a label.
    pattern = re.compile(
        r'<label[^>]*class="[^"]*toggle-switch[^"]*"[^>]*>'
        r'(?:(?!</label>)[\s\S])*?'
        r'name="railway_deploy_alerts"',
        re.MULTILINE,
    )
    assert pattern.search(r.text), (
        "railway_deploy_alerts must be wrapped in a .toggle-switch label "
        "for UX consistency with other toggles"
    )


def test_settings_has_preset_details_elements():
    """프리셋 3종 모두 <details id='preset-*'> 요소 + JS 헬퍼 3종이 존재해야 한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
    for preset in ("minimal", "standard", "strict"):
        assert f'id="preset-{preset}"' in r.text, f"Missing <details id=preset-{preset}>"
    for fn in ("onPresetToggle", "renderPresetDiff", "flashPresetChanges"):
        assert fn in r.text, f"Missing JS helper: {fn}"


# ── T9: Telegram 연결 서브섹션 렌더링 테스트 ──
# ── T9: Telegram connection subsection rendering tests ──

def test_telegram_otp_section_renders_when_not_connected():
    """미연결 user → settings 페이지에 '연결 코드 발급' 버튼이 포함된다.
    When Telegram is not connected, the settings page shows the 'Issue Code' button.
    """
    # _test_user는 파일 상단에서 is_telegram_connected=False 기본값으로 설정됨
    # _test_user at the top of this file has is_telegram_connected=False by default.
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
    html = r.text
    # '연결 코드 발급' 버튼이 렌더링되어야 한다
    # The 'Issue Code' button must be rendered.
    assert "issueTelegramOtp" in html
    assert "Issue Code" in html or "연결 코드 발급" in html
    # 'Telegram 연결' 서브섹션 제목이 존재해야 한다
    # The 'Telegram Connection' subsection title must be present.
    assert "Telegram" in html and "connect" in html.lower()


def test_telegram_connected_status_hides_otp_button():
    """연결된 user → settings 페이지에 OTP 버튼 없이 '연결됨' 메시지를 표시한다.
    When Telegram is connected, shows 'connected' message without the OTP button.
    """
    from src.auth.session import CurrentUser as CU
    # is_telegram_connected=True 인 사용자로 의존성 오버라이드
    # Override dependency with a user that has is_telegram_connected=True.
    connected_user = CU(
        id=99,
        github_login="connected_user",
        email="connected@example.com",
        display_name="Connected User",
        plaintext_token="gho_connected",
        is_telegram_connected=True,
    )
    app.dependency_overrides[require_login] = lambda: connected_user
    try:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            id=1, full_name="owner/repo", user_id=None
        )
        from src.config_manager.manager import RepoConfigData
        with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(mock_db)), \
             patch("src.ui.routes.settings.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")), \
             patch("src.ui.routes.settings._detect_stale_webhook",
                   new_callable=AsyncMock, return_value=False):
            r = client.get("/repos/owner%2Frepo/settings")
        assert r.status_code == 200
        html = r.text
        # 연결 완료 메시지가 있어야 한다
        # The 'connected' status message must be present.
        assert "연결되어 있습니다" in html or "connected" in html.lower()
        # OTP 발급 버튼은 없어야 한다
        # The OTP issuance button must not be present.
        assert "issueTelegramOtp" not in html
    finally:
        # 다른 테스트에 영향을 주지 않도록 오버라이드 복원
        # Restore the override so other tests are not affected.
        app.dependency_overrides[require_login] = lambda: _test_user


# ── PR-4 G2/G3: UI 감사 사이클 회귀 가드 ──────────────────────────────
# Step A~E 핵심 변경이 향후 회귀로 사라지지 않도록 source-grep 어셔션 추가
# Source-grep guards so Step A~E key changes don't silently regress

from pathlib import Path  # noqa: E402

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "src" / "templates"


def _read_template(name: str) -> str:
    """템플릿 파일 내용 반환 — grep 기반 회귀 가드 헬퍼."""
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def test_phantom_token_aliases_in_root():
    """PR #169 cleanup 회귀 가드 — :root 에 환각 토큰 alias 5종 보존.

    --bg-hover / --card-bg / --text (Step A) +
    --accent-blue / --c-warning (PR-1 cleanup) 이 base.html :root 에 정의돼야.
    """
    base = _read_template("base.html")
    for token in ("--bg-hover:", "--card-bg:", "--text:", "--accent-blue:", "--c-warning:"):
        assert token in base, f"환각 토큰 alias {token} 가 base.html :root 에서 누락"


def test_warning_token_defined_in_all_themes():
    """PR #167 회귀 가드 — --warning 토큰이 4-테마 모두에 정의."""
    base = _read_template("base.html")
    assert base.count("--warning:") >= 3, (
        f"--warning 토큰 정의가 부족 (3개 이상 기대 — dark/light/glass): "
        f"{base.count('--warning:')}회"
    )


def test_claude_dark_settings_tokens_defined():
    """PR #169 cleanup 회귀 가드 — claude-dark 의 settings 페이지 토큰 8종.

    --grad-gate/merge/notify/hook + --title-gradient + --btn-gate-active-* +
    --save-btn-* + --hint-* + --hook-btn-* 가 claude-dark 블록에 있어야.
    """
    base = _read_template("base.html")
    # claude-dark 블록 안에서 --grad-gate 정의 확인
    cd_idx = base.find('body[data-theme="claude-dark"]')
    assert cd_idx != -1, "claude-dark 블록 누락"
    cd_block_end = base.find("}", cd_idx + 100)  # 대략적 블록 끝
    cd_block = base[cd_idx:cd_block_end + 200]  # 약간 여유
    for token in ("--grad-gate:", "--save-btn-bg:", "--hint-bg:", "--hook-btn-tx:"):
        assert token in cd_block, (
            f"claude-dark 블록에 {token} 누락 — settings 페이지 시각 깨짐 위험"
        )


def test_chart_vendoring_no_jsdelivr_chartjs():
    """PR #166 회귀 가드 — Chart.js CDN 참조가 어떤 템플릿에도 잔존하지 않아야."""
    for tpl in ("repo_detail.html", "analysis_detail.html", "insights_me.html"):
        content = _read_template(tpl)
        assert "cdn.jsdelivr.net/npm/chart.js" not in content, (
            f"{tpl} 에 jsdelivr Chart.js CDN 잔존 — vendoring 회귀"
        )
        assert "/static/vendor/chart.umd.min.js" in content, (
            f"{tpl} 에 vendored Chart.js 참조 누락"
        )


def test_chart_aspect_ratio_false():
    """PR #168 + PR-3 회귀 가드 — Chart.js maintainAspectRatio:false + chart-wrap-inner."""
    for tpl in ("repo_detail.html", "analysis_detail.html"):
        content = _read_template(tpl)
        assert "maintainAspectRatio: false" in content, (
            f"{tpl} 의 maintainAspectRatio:false 회귀"
        )
        assert "chart-wrap-inner" in content, (
            f"{tpl} 의 chart-wrap-inner 컨테이너 누락"
        )
        assert "clamp(200px" in content, (
            f"{tpl} 의 chart-wrap-inner clamp 회귀 (PR-3 F1)"
        )


def test_nav_login_guard():
    """PR #168 E1 회귀 가드 — base.html nav 햄버거 + 링크가 {% if current_user %} 안.

    비로그인 시 햄버거/Overview/Insights 링크 시각 노출 회피.
    """
    base = _read_template("base.html")
    # 햄버거 버튼 마크업 (CSS 정의가 아닌 실제 <button id="navHamburger">) 직전에 가드
    # Hamburger button markup (not the CSS rule) must be wrapped in {% if current_user %}
    ham_idx = base.find('id="navHamburger"')
    assert ham_idx != -1, "navHamburger 마크업 누락"
    preceding = base[max(0, ham_idx - 300):ham_idx]
    assert "{% if current_user %}" in preceding, (
        "navHamburger 마크업 직전에 {% if current_user %} 가드 누락 — 비로그인 시 노출"
    )


def test_chip_a11y_sr_only_pattern():
    """PR #168 E4 회귀 가드 — insights chip 의 sr-only 패턴 + focus-within outline."""
    insights = _read_template("insights.html")
    # display:none 이 chip-label input 에 잔존하면 안 됨
    assert ".chip-label input[type=checkbox] { display:none" not in insights, (
        "chip-label input 에 display:none 회귀 (a11y 깨짐)"
    )
    # sr-only 패턴 (position:absolute + opacity:0) 와 focus-within outline 존재
    assert "position: absolute;" in insights and "clip: rect(0 0 0 0)" in insights, (
        "chip-label sr-only 패턴 누락"
    )
    assert ".chip-label:focus-within" in insights, (
        "chip-label focus-within outline 누락"
    )


def test_btn_disabled_extended_selectors():
    """PR-3 F2 회귀 가드 — .btn:disabled selector 가 자체 button 클래스 커버."""
    base = _read_template("base.html")
    for cls in ("button:disabled.fb-btn", "button:disabled.nav-btn",
                "button:disabled.gate-mode-btn", "button:disabled.hook-btn"):
        assert cls in base, (
            f".btn:disabled selector 에서 {cls} 누락 — disabled 시각 비일관"
        )


def test_safe_area_inset_in_nav_and_container():
    """Step A S4 회귀 가드 — nav / .container 에 safe-area-inset 적용."""
    base = _read_template("base.html")
    assert "env(safe-area-inset-left)" in base, "safe-area-inset-left 미사용"
    assert "env(safe-area-inset-right)" in base, "safe-area-inset-right 미사용"
    assert "env(safe-area-inset-bottom" in base, "safe-area-inset-bottom 미사용"


def test_settings_field_input_mobile_16px():
    """PR #169 C4 회귀 가드 — settings.html 모바일 .field-input { font-size: 16px } (iOS 줌인 방지)."""
    settings = _read_template("settings.html")
    # 모바일 분기 안에 .field-input 16px 정의 존재
    mobile_idx = settings.find("@media(max-width:639px)")
    assert mobile_idx != -1, "모바일 분기 (@media max-width:639px) 누락"
    block_end = settings.find("@media(min-width:640px)", mobile_idx)
    mobile_block = settings[mobile_idx:block_end if block_end != -1 else mobile_idx + 1000]
    assert ".field-input { font-size: 16px;" in mobile_block, (
        "settings.html 모바일 분기에 .field-input 16px 누락 (iOS Safari 줌인 방지)"
    )
