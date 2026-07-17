"""NULL-owner 저장소 쓰기 차단 (IDOR) — API + insights 인라인 가드 3축 대칭.

NULL-owner repository write block (IDOR) — 3-axis guard for API + insights routes.

본 파일이 다루는 2개 라우트는 `get_accessible_repo` 를 **경유하지 않아** 헬퍼 수정만으로는
차단되지 않는다 — 인라인 가드가 필요하다.
These two routes do NOT go through get_accessible_repo, so the helper change alone
does not cover them — they need inline guards.

🔴 가드 배치 제약 / Guard placement constraints:
    1. `src/api/issue_registration.py` — 가드는 `register()` 안, `_check_ownership`
       **직후**. 공용 헬퍼 `_get_analysis_and_repo:59` 내부에 넣으면 읽기 전용
       `GET /status:155` 와 공유되어 이슈 배지가 무음 소실한다.
       Put the guard in register(), NOT in the shared helper (GET /status reuses it).
    2. `src/ui/routes/repo_insights.py` — `refresh=1` 일 때만 403. `_find_repo:54`
       내부 금지 — 반환 규약이 `None`(→404) 이라 다르고, `refresh=0` 조회는 현행 유지.
       Guard only when refresh=1; _find_repo returns None (→404), a different contract.
    3. `_get_repo_or_404:170` (NULL 판정 `:179`) 는 **손대지 않는다** — 유일 호출처가
       `:194` GET /repo-summary = 순수 읽기.
       _get_repo_or_404 is untouched: its only caller is a pure read.

🔴 `_get_analysis_and_repo` 통째 patch 금지 (본 파일 신규 403 테스트) / Do not patch the helper:
    기존 테스트(`test_issue_registration_api.py:51/71/88`)는 `_get_analysis_and_repo` 를
    통째로 patch 한다 → 헬퍼 기반 403 테스트는 가드를 sabotage 해도 green = 무의미.
    아래 403 테스트는 **실 헬퍼를 경유**(SessionLocal mock)해 가드가 실제 발동하게 한다.
    Existing tests patch the helper wholesale; a guard test written that way would pass
    even with the guard removed. These tests route through the real helper instead.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import src.models.insight_narrative_cache  # noqa: F401  (register table for create_all)
from src.auth.session import CurrentUser, require_login
from src.database import Base
from src.i18n.loader import get_text
from src.main import app
from src.models.repository import Repository
from src.models.user import User


def _mock_user():
    return CurrentUser(
        id=1, github_login="user", email="u@example.com",
        display_name="User", plaintext_token="ghp_test",
    )


def _mock_analysis(repo_id=1):
    m = MagicMock()
    m.id = 10
    m.repo_id = repo_id
    return m


def _mock_repo(full_name="owner/repo", user_id=1):
    m = MagicMock()
    m.id = 1
    m.full_name = full_name
    m.user_id = user_id
    return m


def _mock_session_ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


_REGISTER_BODY = {
    "analysis_id": 10, "issue_type": "ai_suggestion",
    "suggestion_text": "cache TTL", "title": "T", "body": "B", "labels": ["bug"],
}

# 성공 응답 형태 — 가드 부재 시 라우트가 **깔끔히 201** 을 반환하게 해서
# RED 실패가 `assert 201 == 403` 로 명확히 드러나게 한다 (직렬화 불가 MagicMock 이
# RecursionError 를 던지면 실패 원인이 가드 부재인지 mock 결함인지 구분 불가).
# Serializable success payload so the un-guarded path returns a clean 201 —
# otherwise a bare MagicMock raises RecursionError and muddies the RED signal.
_REGISTER_RESULT = {
    "github_issue_number": 44,
    "github_issue_url": "https://github.com/owner/repo/issues/44",
    "state": "open",
}


@pytest.fixture
def client():
    return TestClient(app)


# ══════════════════════════════════════════════════════════════════════
# 축 1 — POST /api/issues/register 쓰기 차단 (403)
# Axis 1 — POST /api/issues/register blocked (403)
# ══════════════════════════════════════════════════════════════════════


def test_register_null_owner_returns_403_and_does_not_create_issue(client):
    """NULL-owner 리포 이슈 등록 → 403, register_issue(GitHub 쓰기) 미발생.

    실 헬퍼 경유 — `_get_analysis_and_repo` 를 patch 하지 않는다 (파일 docstring 참조).
    Routes through the real helper — the guard must actually fire.
    """
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.side_effect = [
        _mock_analysis(), _mock_repo(user_id=None),
    ]
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal",
              return_value=_mock_session_ctx(db_mock)),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(return_value=_REGISTER_RESULT)) as mock_register,
    ):
        resp = client.post("/api/issues/register", json=_REGISTER_BODY)
    assert resp.status_code == 403
    mock_register.assert_not_awaited()


def test_register_null_owner_403_detail_is_localized_to_request_locale(client):
    """403 detail 은 `errors.repo_unclaimed` 를 **요청 locale** 로 현지화한다.

    🔴 쿠키로 ko 를 강제해 라우트가 이미 해소해 둔 `locale`(issue_registration.py:96)을
    가드가 실제로 쓰는지 검증한다 — `settings.default_locale`('en') 로 새면 실패.
    `!= 키 자체` 단언은 i18n 미등재 시 공허 통과를 막는다.
    """
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.side_effect = [
        _mock_analysis(), _mock_repo(user_id=None),
    ]
    client.cookies.set("preferred_language", "ko")
    try:
        with (
            patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
            patch("src.api.issue_registration.SessionLocal",
                  return_value=_mock_session_ctx(db_mock)),
            patch("src.api.issue_registration.register_issue",
                  new=AsyncMock(return_value=_REGISTER_RESULT)),
        ):
            resp = client.post("/api/issues/register", json=_REGISTER_BODY)
    finally:
        client.cookies.clear()
    assert resp.status_code == 403
    expected_ko = get_text("errors.repo_unclaimed", "ko")
    assert expected_ko != "errors.repo_unclaimed", "i18n 키 미등재 — 키 문자열이 사용자에게 노출된다"
    assert resp.json()["detail"] == expected_ko
    assert resp.json()["detail"] != get_text("errors.repo_unclaimed", "en")


# ══════════════════════════════════════════════════════════════════════
# 축 2 — 읽기 비회귀 (200) — NULL-owner 로 여전히 통과
# Axis 2 — reads must NOT regress with a NULL-owner repo
#
# 🔴 가드를 공용 헬퍼 `_get_analysis_and_repo` 에 넣으면 아래 status 테스트가 깨진다
# — 이슈 배지 무음 소실의 성문 계약.
# If the guard is (wrongly) placed in the shared helper, the status test below breaks.
# ══════════════════════════════════════════════════════════════════════


def test_status_null_owner_still_returns_200(client):
    """NULL-owner 리포 이슈 상태 조회(GET /status) → 200 (읽기 비회귀).

    가드가 공용 헬퍼에 잘못 배치되면 이 테스트가 실패한다 — 배지 무음 소실 봉인.
    """
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.side_effect = [
        _mock_analysis(), _mock_repo(user_id=None),
    ]
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal",
              return_value=_mock_session_ctx(db_mock)),
        patch("src.api.issue_registration.get_analysis_issue_status",
              new=AsyncMock(return_value=[])),
    ):
        resp = client.get("/api/issues/status?analysis_id=10")
    assert resp.status_code == 200


def test_repo_summary_null_owner_still_returns_200(client):
    """NULL-owner 리포 이슈 요약(GET /repo-summary) → 200 (읽기 비회귀).

    `_get_repo_or_404` 는 순수 읽기 전용이라 가드 대상이 아니다.
    _get_repo_or_404 is read-only and must NOT gain a guard.
    """
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = _mock_repo(user_id=None)
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal",
              return_value=_mock_session_ctx(db_mock)),
        patch("src.api.issue_registration.get_repo_issue_summary",
              new=AsyncMock(return_value=[])),
    ):
        resp = client.get("/api/issues/repo-summary?repo_id=1")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════
# 축 3 — 소유자 정상 통과 (기존 계약 불변)
# Axis 3 — owner (user_id=1) still passes
# ══════════════════════════════════════════════════════════════════════


def test_register_owner_still_creates_issue(client):
    """소유자 이슈 등록 → 201 + register_issue 발생 (기존 계약 불변)."""
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.side_effect = [
        _mock_analysis(), _mock_repo(user_id=1),
    ]
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal",
              return_value=_mock_session_ctx(db_mock)),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(return_value={
                  "github_issue_number": 44,
                  "github_issue_url": "https://github.com/owner/repo/issues/44",
                  "state": "open",
              })) as mock_register,
    ):
        resp = client.post("/api/issues/register", json=_REGISTER_BODY)
    assert resp.status_code == 201
    mock_register.assert_awaited_once()


# ══════════════════════════════════════════════════════════════════════
# repo_insights — refresh=1 만 쓰기 (AI 내러티브 재생성 = 유료 호출)
# repo_insights — only refresh=1 is a write (AI narrative regeneration = paid call)
#
# 실 DB(SQLite in-memory) 사용 — `tests/unit/api/test_repo_insights_route.py` 패턴 재사용.
# Uses a real in-memory DB, reusing the existing insights route test pattern.
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sess = Session(engine)
    yield sess
    sess.close()
    engine.dispose()


@pytest.fixture()
def viewer(db_session):
    u = User(github_id=1, github_login="viewer", email="v@x.com", display_name="V")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture()
def unclaimed_repo(db_session):
    """user_id=None 저장소 — 웹훅이 미등록 리포마다 생성하는 바로 그 행."""
    r = Repository(full_name="owner/unclaimed", user_id=None)
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


@pytest.fixture()
def insights_client(db_session, viewer):
    """require_login + _get_db override — 기존 override 저장 후 복원 (오염 방지)."""
    from src.ui.routes.repo_insights import _get_db

    current = CurrentUser(
        id=viewer.id, github_login=viewer.github_login, email=viewer.email or "",
        display_name=viewer.display_name or "", plaintext_token="ghp_test",
    )
    prev_require_login = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: current
    app.dependency_overrides[_get_db] = lambda: db_session
    yield TestClient(app)
    if prev_require_login is None:
        app.dependency_overrides.pop(require_login, None)
    else:
        app.dependency_overrides[require_login] = prev_require_login
    app.dependency_overrides.pop(_get_db, None)


def test_insights_refresh_null_owner_returns_403_and_skips_narrative(insights_client, unclaimed_repo):
    """NULL-owner 리포 인사이트 강제 갱신(?refresh=1) → 403, AI 내러티브 호출 미발생."""
    # return_value=None → 가드 부재 시 라우트가 **깔끔히 200** 을 반환 (narrative 생략)
    # → RED 실패가 `assert 200 == 403` 로 명확. 직렬화 불가 MagicMock 잡음 회피.
    # Clean 200 when the guard is absent, so the RED signal is unambiguous.
    with patch("src.ui.routes.repo_insights.settings.anthropic_api_key", "sk-test"), \
         patch("src.ui.routes.repo_insights.repo_insight_narrative",
               new_callable=AsyncMock, return_value=None) as mock_narrative:
        r = insights_client.get("/repos/owner/unclaimed/insights?refresh=1")
    assert r.status_code == 403
    mock_narrative.assert_not_awaited()


def test_insights_without_refresh_null_owner_still_returns_200(insights_client, unclaimed_repo):
    """NULL-owner 리포 인사이트 조회(refresh 없음) → 200 (읽기 비회귀).

    🔴 `_find_repo` 내부에 가드를 넣으면 이 테스트가 실패한다 — refresh=0 조회는 현행 유지.
    Placing the guard inside _find_repo would break this — refresh=0 stays open.
    """
    with patch("src.ui.routes.repo_insights.settings.anthropic_api_key", ""):
        r = insights_client.get("/repos/owner/unclaimed/insights")
    assert r.status_code == 200


def test_insights_refresh_owner_still_returns_200(insights_client, db_session, viewer):
    """소유자 리포 강제 갱신(?refresh=1) → 200 (기존 계약 불변)."""
    owned = Repository(full_name="owner/owned", user_id=viewer.id)
    db_session.add(owned)
    db_session.commit()

    with patch("src.ui.routes.repo_insights.settings.anthropic_api_key", ""):
        r = insights_client.get("/repos/owner/owned/insights?refresh=1")
    assert r.status_code == 200
