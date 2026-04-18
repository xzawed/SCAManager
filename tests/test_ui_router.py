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

from unittest.mock import MagicMock, patch
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

def test_overview_returns_html():
    """로그인 후 / 는 200 HTML을 반환한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200


def test_repo_detail_404():
    """존재하지 않는 리포 접근 시 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/nope%2Frepo")
    assert r.status_code == 404


def test_repo_detail_404_for_other_users_repo():
    """타인 소유 리포(user_id=2) 접근 시 404. 현재 사용자는 user_id=1."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=2
    )
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 404


def test_settings_returns_html():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200


def test_post_settings_redirects():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
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
    """설정 페이지 HTML을 렌더링해 반환하는 헬퍼."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    cfg = config or RepoConfigData(repo_full_name="owner/repo")
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config", return_value=cfg):
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


def test_semi_auto_hint_in_pr_card():
    """semi-auto 모드에서 ① PR 동작 카드에 hint 텍스트가 노출되어야 한다."""
    from src.config_manager.manager import RepoConfigData
    cfg = RepoConfigData(repo_full_name="owner/repo", approve_mode="semi-auto")
    html = _render_settings(cfg)
    assert "semiAutoHint" in html, "semiAutoHint 엘리먼트가 없음"
    # PR 동작 카드(s-card-hdr hdr-gate div) 이후, Push 동작 카드(s-card-hdr hdr-merge) 이전에 hint가 있어야 함
    gate_card_idx = html.find('s-card-hdr hdr-gate')
    merge_card_idx = html.find('s-card-hdr hdr-merge')
    hint_idx = html.find("semiAutoHint")
    assert gate_card_idx != -1, "s-card-hdr hdr-gate 카드 헤더가 없음"
    assert merge_card_idx != -1, "s-card-hdr hdr-merge 카드 헤더가 없음"
    assert gate_card_idx < hint_idx < merge_card_idx, (
        "semiAutoHint가 ① PR 동작 카드 안에 없음"
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

    with patch("src.ui.router.list_user_repos", new_callable=AsyncMock, return_value=mock_repos):
        with patch("src.ui.router.SessionLocal") as mock_sl:
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

    with patch("src.ui.router.list_user_repos", new_callable=AsyncMock, return_value=mock_repos):
        with patch("src.ui.router.SessionLocal") as mock_sl:
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

    with patch("src.ui.router.create_webhook", new_callable=AsyncMock, return_value=77777):
        with patch("src.ui.router.SessionLocal") as mock_sl:
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

    with patch("src.ui.router.SessionLocal") as mock_sl:
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/999")
    assert r.status_code == 404


def test_analysis_detail_404_for_other_users_repo():
    """타인 리포의 분석 → 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=999  # 다른 사용자
    )
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.delete_webhook", new_callable=AsyncMock, return_value=True):
        with patch("src.ui.router.create_webhook", new_callable=AsyncMock, return_value=12345):
            with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
                r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    assert r.status_code == 303
    assert "hook_ok=1" in r.headers["location"]


def test_reinstall_webhook_404_for_other_user():
    """타인 소유 리포 → 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=999
    )
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    assert r.status_code == 404


def test_reinstall_webhook_no_existing_webhook():
    """webhook_id가 없어도(None) create_webhook은 호출된다."""
    from unittest.mock import AsyncMock, patch
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None, webhook_id=None
    )
    with patch("src.ui.router.delete_webhook", new_callable=AsyncMock) as mock_del:
        with patch("src.ui.router.create_webhook", new_callable=AsyncMock, return_value=99999):
            with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
                r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    mock_del.assert_not_called()  # webhook_id None → 삭제 스킵
    assert r.status_code == 303


# ── 리포 삭제 엔드포인트 테스트 ──────────────────────────

def test_delete_repo_success():
    """소유자 삭제 시 webhook 삭제 + DB cascade 후 303 /?deleted=1."""
    from unittest.mock import AsyncMock, patch
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1, webhook_id=999)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    # Analysis.id 조회 시 빈 결과
    mock_db.query.return_value.filter.return_value.all.return_value = []

    with patch("src.ui.router.delete_webhook", new_callable=AsyncMock, return_value=True) as mock_del:
        with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.delete_webhook", new_callable=AsyncMock) as mock_del:
        with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)

    assert r.status_code == 404
    mock_del.assert_not_called()
    mock_db.delete.assert_not_called()


def test_delete_repo_404_not_found():
    """존재하지 않는 리포 삭제 → 404."""
    from unittest.mock import AsyncMock, patch
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.ui.router.delete_webhook", new_callable=AsyncMock):
        with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/nope%2Frepo/delete", follow_redirects=False)
    assert r.status_code == 404


def test_delete_repo_webhook_failure_still_deletes_db():
    """delete_webhook이 예외를 던져도 DB 정리는 계속 진행되어야 한다."""
    from unittest.mock import AsyncMock, patch
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=None, webhook_id=999)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.query.return_value.filter.return_value.all.return_value = []

    with patch("src.ui.router.delete_webhook", new_callable=AsyncMock,
               side_effect=RuntimeError("github api down")):
        with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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

    with patch("src.ui.router.delete_webhook", new_callable=AsyncMock) as mock_del:
        with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
            r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)

    assert r.status_code == 303
    mock_del.assert_not_called()
    mock_db.delete.assert_called_once_with(mock_repo)


# ── 네비게이션 사용자 UI 테스트 ──────────────────────────

def test_overview_shows_display_name_in_nav():
    """로그인 후 nav에 display_name이 표시된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "Test User" in r.text


def test_overview_shows_logout_button_in_nav():
    """로그인 후 nav에 로그아웃 버튼과 action URL이 표시된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
        with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
            r = client.get("/")
        assert r.status_code == 200
        assert "fallback_user" in r.text
    finally:
        app.dependency_overrides[require_login] = lambda: _test_user


# ── 이력 페이지 조회 강화 테스트 ──────────────────────────

def test_repo_detail_queries_limit_100():
    """repo_detail은 최근 100건을 조회한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert '"cli"' in r.text


def test_repo_detail_filter_bar_rendered():
    """이력 페이지에 필터 바 UI 요소가 렌더링된다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/10")
    # 200 반환
    assert r.status_code == 200
    # 점수 배너 표시
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/11")
    # 200 반환
    assert r.status_code == 200
    # 점수 배너 표시
    assert "80" in r.text
    assert "/100" in r.text
    # fallback 메시지 포함
    assert "분석 결과 데이터가 없습니다" in r.text or "상세 데이터가 없습니다" in r.text
    # AI 요약 섹션 없음
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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo/analyses/12")
    assert r.status_code == 200
    # _test_user의 display_name="Test User"가 nav에 표시되어야 함
    assert "Test User" in r.text
    # 로그아웃 버튼 및 URL이 포함되어야 함
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
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html>ok</html>")

    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.templates.TemplateResponse", side_effect=fake_template_response):
            r = client.get("/repos/owner%2Frepo/analyses/1")

    assert r.status_code == 200
    # trend_data 키가 context에 있어야 한다
    assert "trend_data" in captured_context, "trend_data가 template context에 없음 — 미구현 상태"
    trend = captured_context["trend_data"]
    # 3건 반환
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

    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.templates.TemplateResponse", side_effect=fake_template_response):
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

    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.templates.TemplateResponse", side_effect=fake_template_response):
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
