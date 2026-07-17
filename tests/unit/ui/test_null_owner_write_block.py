"""NULL-owner 저장소 쓰기 차단 (IDOR) — UI 라우트 3축 대칭 가드.

NULL-owner repository write block (IDOR) — 3-axis symmetric guard for UI routes.

배경 / Background:
    `src/ui/_helpers.py::get_accessible_repo` 는 `repo.user_id is not None` 일 때만
    소유권을 검사한다 → `user_id IS NULL` 저장소는 **모든 인증 세션**을 통과한다.
    NULL-owner 행은 `src/worker/pipeline.py:425` 가 미등록 저장소 웹훅마다 계속 생성한다.

    get_accessible_repo only checks ownership when `repo.user_id is not None`, so
    NULL-owner repos pass for *any* authenticated session. Such rows keep being
    created by the webhook path for unregistered repositories.

승인된 계약 / Approved contract:
    - 쓰기 = 403 차단 (`require_write=True`)
    - 조회 = 현행 유지 (0039 마이그레이션이 의도적으로 택한 읽기 노출 설계)
    - write = blocked with 403; read = unchanged by design.

🔴 부수효과 단언 의무 / Side-effect assertions are mandatory:
    상태 코드만 검사하면 `src/ui/routes/settings.py:263` 처럼 `db.commit()` 이
    GitHub 호출보다 **앞선** 순서 결함을 놓친다. 각 축 1 테스트는 403 과 함께
    "부수효과 미발생"을 반드시 단언한다.
    Status-code-only assertions would miss ordering defects where db.commit()
    precedes the GitHub call. Every axis-1 test asserts no side effect occurred.
"""
from __future__ import annotations

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

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.auth.session import require_login  # noqa: E402
from src.i18n.loader import get_text  # noqa: E402
from src.main import app  # noqa: E402
from src.models.user import User as UserModel  # noqa: E402

_test_user = UserModel(
    id=1, github_id="12345", github_login="testuser",
    github_access_token="gho_test", email="test@example.com", display_name="Test User",
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _login_as_test_user():
    """require_login 을 **테스트 시점**에 override 하고 복원한다.

    Override require_login at *test time* and restore afterwards.

    🔴 모듈 레벨 `app.dependency_overrides[...] = ...` 대입 금지 — `app` 은 전 테스트가
    공유하는 전역이라 import 순서에 따라 다른 모듈이 덮어쓴다
    (`tests/unit/api/test_users_api.py:37` 이 id=42 로 덮어써 `test_feedback_routes.py`
    5건을 오염시키는 기존 사례). 픽스처는 순서와 무관하게 격리를 보장한다.
    Module-level assignment is import-order dependent; a fixture is order-independent.
    """
    prev = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _test_user
    yield
    if prev is None:
        app.dependency_overrides.pop(require_login, None)
    else:
        app.dependency_overrides[require_login] = prev


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _repo(user_id):
    """저장소 mock — user_id=None 이면 미청구(NULL-owner) 저장소.

    Repository mock — user_id=None means an unclaimed (NULL-owner) repository.
    """
    return MagicMock(id=1, full_name="owner/repo", user_id=user_id, webhook_id=999)


def _db_with_repo(user_id):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _repo(user_id)
    db.query.return_value.filter.return_value.all.return_value = []
    return db


_SETTINGS_FORM = {
    "approve_mode": "auto",
    "approve_threshold": "85",
    "reject_threshold": "55",
    "notify_chat_id": "-123",
}

_FEEDBACK_BODY = {"thumbs": 1, "comment": "nice"}


# ══════════════════════════════════════════════════════════════════════
# 축 1 — 쓰기 차단 (403) + 부수효과 미발생
# Axis 1 — writes blocked (403) with no side effects
# ══════════════════════════════════════════════════════════════════════


def test_post_settings_null_owner_returns_403_and_does_not_save():
    """NULL-owner 리포 설정 저장 → 403, upsert/commit 모두 미발생."""
    db = _db_with_repo(None)
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)), \
         patch("src.ui.routes.settings.upsert_repo_config") as mock_upsert:
        r = client.post(
            "/repos/owner%2Frepo/settings", data=_SETTINGS_FORM, follow_redirects=False,
        )
    assert r.status_code == 403
    mock_upsert.assert_not_called()
    db.commit.assert_not_called()


def test_post_settings_null_owner_403_detail_is_localized_to_request_locale():
    """403 detail 은 `errors.repo_unclaimed` 를 **요청 locale** 로 현지화한다.

    🔴 쿠키로 ko 를 강제해 `locale=get_locale(request)` 배선까지 검증한다 —
    배선이 빠지면 `settings.default_locale`('en') 영문이 반환돼 이 테스트가 실패한다.
    (단순히 `get_text(...)` 끼리 비교하면 키 미등재 시 양변이 같아져 공허하게 통과하므로
    `!= 키 자체` 단언을 함께 둔다.)
    """
    db = _db_with_repo(None)
    client.cookies.set("preferred_language", "ko")
    try:
        with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)), \
             patch("src.ui.routes.settings.upsert_repo_config"):
            r = client.post(
                "/repos/owner%2Frepo/settings", data=_SETTINGS_FORM, follow_redirects=False,
            )
    finally:
        client.cookies.clear()
    assert r.status_code == 403
    expected_ko = get_text("errors.repo_unclaimed", "ko")
    assert expected_ko != "errors.repo_unclaimed", "i18n 키 미등재 — 키 문자열이 사용자에게 노출된다"
    assert r.json()["detail"] == expected_ko
    assert r.json()["detail"] != get_text("errors.repo_unclaimed", "en")


def test_reinstall_hook_null_owner_returns_403_and_does_not_commit():
    """NULL-owner 리포 hook 재커밋 → 403, commit + GitHub 호출 모두 미발생.

    🔴 `settings.py:263` 은 `commit_scamanager_files` **앞에서** `db.commit()` 한다 —
    상태 코드만 보면 hook_token 이 이미 DB 에 쓰인 뒤 403 이 나도 통과한다.
    settings.py:263 commits BEFORE the GitHub call, so the commit assertion is
    what actually pins the guard's position.
    """
    db = _db_with_repo(None)
    with patch("src.ui.routes.settings.commit_scamanager_files",
               new_callable=AsyncMock) as mock_commit_files, \
         patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)):
        r = client.post("/repos/owner%2Frepo/reinstall-hook", follow_redirects=False)
    assert r.status_code == 403
    db.commit.assert_not_called()
    db.add.assert_not_called()
    mock_commit_files.assert_not_called()


def test_reinstall_webhook_null_owner_returns_403_and_does_not_touch_github():
    """NULL-owner 리포 webhook 재등록 → 403, delete/create webhook + commit 미발생."""
    db = _db_with_repo(None)
    with patch("src.ui.routes.settings.list_webhooks",
               new_callable=AsyncMock, return_value=[]) as mock_list, \
         patch("src.ui.routes.settings.delete_webhook", new_callable=AsyncMock) as mock_del, \
         patch("src.ui.routes.settings.create_webhook", new_callable=AsyncMock) as mock_create, \
         patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)):
        r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    assert r.status_code == 403
    mock_list.assert_not_called()
    mock_del.assert_not_called()
    mock_create.assert_not_called()
    db.commit.assert_not_called()


def test_delete_repo_null_owner_returns_403_and_does_not_delete():
    """NULL-owner 리포 삭제 → 403, webhook 삭제 + DB cascade 모두 미발생."""
    db = _db_with_repo(None)
    with patch("src.ui._helpers.delete_webhook", new_callable=AsyncMock) as mock_del, \
         patch("src.ui.routes.actions.SessionLocal", return_value=_ctx(db)):
        r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)
    assert r.status_code == 403
    mock_del.assert_not_called()
    db.delete.assert_not_called()
    db.commit.assert_not_called()


def test_post_feedback_null_owner_returns_403_and_does_not_upsert():
    """NULL-owner 리포 분석 피드백 POST → 403, upsert_feedback 미발생."""
    db = _db_with_repo(None)
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(db)), \
         patch("src.ui.routes.detail.analysis_feedback_repo") as mock_repo_mod:
        r = client.post(
            "/repos/owner%2Frepo/analyses/1/feedback", json=_FEEDBACK_BODY,
        )
    assert r.status_code == 403
    mock_repo_mod.upsert_feedback.assert_not_called()
    db.commit.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# 축 2 — 읽기 비회귀 (200) — NULL-owner 로 여전히 통과
# Axis 2 — reads must NOT regress (200) with a NULL-owner repo
#
# 🔴 이 축이 "조회는 현행 유지" 의 **유일한 성문 계약**이다. 과잉 차단 회귀를 잡는다.
# This axis is the only written contract for "reads stay open"; it catches
# over-blocking regressions.
# ══════════════════════════════════════════════════════════════════════


def test_get_settings_null_owner_still_returns_200():
    """NULL-owner 리포 설정 페이지 조회 → 200 (읽기 비회귀)."""
    from src.config_manager.manager import RepoConfigData

    db = _db_with_repo(None)
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200


def test_repo_detail_null_owner_still_returns_200():
    """NULL-owner 리포 상세 페이지 조회 → 200 (읽기 비회귀)."""
    db = _db_with_repo(None)
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200


def test_analysis_detail_null_owner_still_returns_200():
    """NULL-owner 리포 분석 상세 페이지 조회 → 200 (읽기 비회귀)."""
    db = _db_with_repo(None)
    analysis = MagicMock(
        id=1, commit_sha="abc1234", commit_message="feat: x", pr_number=None,
        score=90, grade="A", result=None,
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-04-08T10:00:00")),
    )
    db.query.return_value.filter.return_value.first.side_effect = [_repo(None), analysis]
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.scalar.return_value = None
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(db)):
        r = client.get("/repos/owner%2Frepo/analyses/1")
    assert r.status_code == 200


def test_get_feedback_null_owner_still_returns_200():
    """NULL-owner 리포 피드백 조회(GET) → 200 (읽기 비회귀 — 쓰기만 차단)."""
    db = _db_with_repo(None)
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(db)), \
         patch("src.ui.routes.detail.analysis_feedback_repo") as mock_repo_mod:
        mock_repo_mod.find_by_analysis_and_user.return_value = None
        r = client.get("/repos/owner%2Frepo/analyses/1/feedback")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════
# 축 3 — 소유자 정상 통과 (기존 계약 불변)
# Axis 3 — owner (user_id=1) still passes every write route
# ══════════════════════════════════════════════════════════════════════


def test_post_settings_owner_still_saves():
    """소유자 설정 저장 → 303 + upsert 발생 (기존 계약 불변)."""
    db = _db_with_repo(1)
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)), \
         patch("src.ui.routes.settings.upsert_repo_config") as mock_upsert:
        r = client.post(
            "/repos/owner%2Frepo/settings", data=_SETTINGS_FORM, follow_redirects=False,
        )
    assert r.status_code == 303
    mock_upsert.assert_called_once()


def test_reinstall_hook_owner_still_succeeds():
    """소유자 hook 재커밋 → 303 hook_ok (기존 계약 불변)."""
    db = MagicMock()
    config = MagicMock(hook_token="existing-token")
    db.query.return_value.filter.return_value.first.side_effect = [_repo(1), config]
    with patch("src.ui.routes.settings.commit_scamanager_files",
               new_callable=AsyncMock, return_value=True) as mock_commit_files, \
         patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)):
        r = client.post("/repos/owner%2Frepo/reinstall-hook", follow_redirects=False)
    assert r.status_code == 303
    assert "hook_ok=1" in r.headers["location"]
    mock_commit_files.assert_called_once()


def test_reinstall_webhook_owner_still_succeeds():
    """소유자 webhook 재등록 → 303 hook_ok + create_webhook 발생 (기존 계약 불변)."""
    db = _db_with_repo(1)
    with patch("src.ui.routes.settings.list_webhooks", new_callable=AsyncMock, return_value=[]), \
         patch("src.ui.routes.settings.delete_webhook", new_callable=AsyncMock), \
         patch("src.ui.routes.settings.create_webhook",
               new_callable=AsyncMock, return_value=12345) as mock_create, \
         patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)):
        r = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    assert r.status_code == 303
    assert "hook_ok=1" in r.headers["location"]
    mock_create.assert_called_once()


def test_delete_repo_owner_still_deletes():
    """소유자 리포 삭제 → 303 + DB cascade 발생 (기존 계약 불변)."""
    db = _db_with_repo(1)
    repo_obj = db.query.return_value.filter.return_value.first.return_value
    with patch("src.ui._helpers.delete_webhook", new_callable=AsyncMock, return_value=True), \
         patch("src.ui.routes.actions.SessionLocal", return_value=_ctx(db)):
        r = client.post("/repos/owner%2Frepo/delete", follow_redirects=False)
    assert r.status_code == 303
    db.delete.assert_called_once_with(repo_obj)


def test_post_feedback_owner_still_upserts():
    """소유자 분석 피드백 POST → 200 + upsert_feedback 발생 (기존 계약 불변)."""
    db = _db_with_repo(1)
    with patch("src.ui.routes.detail.SessionLocal", return_value=_ctx(db)), \
         patch("src.ui.routes.detail.analysis_feedback_repo") as mock_repo_mod:
        mock_repo_mod.upsert_feedback.return_value = MagicMock(
            thumbs=1, comment="nice", updated_at=None,
        )
        r = client.post("/repos/owner%2Frepo/analyses/1/feedback", json=_FEEDBACK_BODY)
    assert r.status_code == 200
    mock_repo_mod.upsert_feedback.assert_called_once()
