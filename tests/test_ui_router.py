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
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "85",
                    "auto_reject_threshold": "55",
                    "notify_chat_id": "-123",
                    "n8n_webhook_url": "http://n8n.local/webhook/abc",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.n8n_webhook_url == "http://n8n.local/webhook/abc"
    assert r.status_code == 303


def test_post_settings_empty_n8n_url():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "disabled",
                    "auto_approve_threshold": "75",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.n8n_webhook_url == ""


def test_post_settings_with_auto_merge_checked():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "80",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                    "auto_merge": "on",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.auto_merge is True
    assert r.status_code == 303


def test_post_settings_without_auto_merge_checkbox():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "80",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.auto_merge is False
    assert r.status_code == 303


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
