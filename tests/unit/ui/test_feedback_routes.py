"""Phase E.3-b — 피드백 엔드포인트 (POST/GET /repos/{name}/analyses/{id}/feedback) 테스트.

TDD Red: 엔드포인트 아직 없음 (405/404 로 실패 예상).
"""
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

from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402
from src.auth.session import require_login  # noqa: E402
from src.models.user import User as UserModel  # noqa: E402

_test_user = UserModel(
    id=1, github_id="12345", github_login="testuser",
    github_access_token="gho_test", email="test@example.com", display_name="Test User",
)
app.dependency_overrides[require_login] = lambda: _test_user

client = TestClient(app)


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _setup_repo_and_analysis(mock_db, repo_user_id=1):
    """Helper: repo (access OK) + analysis 를 mock_db 에 세팅."""
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=repo_user_id)
    mock_analysis = MagicMock(id=42, repo_id=1, score=82)
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_repo, mock_analysis,
    ]
    return mock_repo, mock_analysis


# ── POST /feedback ─────────────────────────────────────────

def test_post_feedback_upsert_success():
    """정상 본문 → upsert_feedback 호출 후 200 + feedback JSON 반환."""
    mock_db = MagicMock()
    _setup_repo_and_analysis(mock_db)
    mock_fb = MagicMock(
        thumbs=1, comment="좋음",
        updated_at=MagicMock(isoformat=MagicMock(return_value="2026-04-23T12:00:00")),
    )
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.detail.analysis_feedback_repo.upsert_feedback",
               return_value=mock_fb) as mock_upsert:
        r = client.post(
            "/repos/owner%2Frepo/analyses/42/feedback",
            json={"thumbs": 1, "comment": "좋음"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["thumbs"] == 1
    assert body["comment"] == "좋음"
    # upsert 호출 검증
    mock_upsert.assert_called_once()
    kwargs = mock_upsert.call_args.kwargs
    assert kwargs["analysis_id"] == 42
    assert kwargs["user_id"] == 1
    assert kwargs["thumbs"] == 1
    assert kwargs["comment"] == "좋음"


def test_post_feedback_rejects_invalid_thumbs():
    """thumbs 가 +1/-1 이 아니면 400."""
    mock_db = MagicMock()
    _setup_repo_and_analysis(mock_db)
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.post(
            "/repos/owner%2Frepo/analyses/42/feedback",
            json={"thumbs": 0},
        )
    assert r.status_code == 422  # Pydantic validation


def test_post_feedback_404_when_analysis_not_found():
    """존재하지 않는 분석 → 404."""
    mock_db = MagicMock()
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_repo, None,  # analysis not found
    ]
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.post(
            "/repos/owner%2Frepo/analyses/999/feedback",
            json={"thumbs": 1},
        )
    assert r.status_code == 404


def test_post_feedback_404_for_other_users_repo():
    """타인 리포의 분석 → 404 (access check)."""
    mock_db = MagicMock()
    # repo.user_id != current_user.id
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=999,
    )
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)):
        r = client.post(
            "/repos/owner%2Frepo/analyses/42/feedback",
            json={"thumbs": 1},
        )
    assert r.status_code == 404


def test_post_feedback_comment_optional():
    """comment 없이도 정상 (comment=None)."""
    mock_db = MagicMock()
    _setup_repo_and_analysis(mock_db)
    mock_fb = MagicMock(
        thumbs=-1, comment=None,
        updated_at=MagicMock(isoformat=MagicMock(return_value="2026-04-23T12:00:00")),
    )
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.detail.analysis_feedback_repo.upsert_feedback",
               return_value=mock_fb):
        r = client.post(
            "/repos/owner%2Frepo/analyses/42/feedback",
            json={"thumbs": -1},
        )
    assert r.status_code == 200
    assert r.json()["comment"] is None


# ── GET /feedback ─────────────────────────────────────────

def test_get_feedback_returns_existing():
    """기존 피드백이 있으면 JSON 으로 반환."""
    mock_db = MagicMock()
    _setup_repo_and_analysis(mock_db)
    mock_fb = MagicMock(
        thumbs=1, comment="test",
        updated_at=MagicMock(isoformat=MagicMock(return_value="2026-04-23T12:00:00")),
    )
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)), \
         patch(
             "src.ui.routes.detail.analysis_feedback_repo.find_by_analysis_and_user",
             return_value=mock_fb,
         ):
        r = client.get("/repos/owner%2Frepo/analyses/42/feedback")
    assert r.status_code == 200
    assert r.json()["thumbs"] == 1
    assert r.json()["comment"] == "test"


def test_get_feedback_returns_null_when_none():
    """피드백 없을 때 {thumbs: null, comment: null} 반환."""
    mock_db = MagicMock()
    _setup_repo_and_analysis(mock_db)
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(mock_db)), \
         patch(
             "src.ui.routes.detail.analysis_feedback_repo.find_by_analysis_and_user",
             return_value=None,
         ):
        r = client.get("/repos/owner%2Frepo/analyses/42/feedback")
    assert r.status_code == 200
    body = r.json()
    assert body["thumbs"] is None
    assert body["comment"] is None
