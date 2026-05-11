"""repo_insights 라우트 단위 테스트 — 200/404/권한 격리.

repo_insights route unit tests — 200/404/permission isolation.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import src.models.insight_narrative_cache  # noqa: F401  (register table on Base.metadata for create_all)
from src.auth.session import CurrentUser, require_login
from src.database import Base
from src.main import app
from src.models.repository import Repository
from src.models.user import User


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
def test_user(db_session):
    u = User(github_id=1, github_login="owner", email="owner@x.com", display_name="O")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture()
def other_user(db_session):
    u = User(github_id=2, github_login="other", email="other@x.com", display_name="X")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture()
def repo(db_session, test_user):
    r = Repository(full_name="owner/myrepo", user_id=test_user.id)
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


def _make_client(db_session, user):
    current = CurrentUser(
        id=user.id,
        github_login=user.github_login,
        email=user.email or "",
        display_name=user.display_name or "",
        plaintext_token="ghp_test",
    )
    from src.ui.routes.repo_insights import _get_db

    # 기존 override 저장 후 복원 — 모듈 레벨 override 오염 방지
    # Save existing overrides and restore after test — prevents module-level override pollution.
    prev_require_login = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: current
    app.dependency_overrides[_get_db] = lambda: db_session
    client = TestClient(app)
    yield client
    if prev_require_login is None:
        app.dependency_overrides.pop(require_login, None)
    else:
        app.dependency_overrides[require_login] = prev_require_login
    app.dependency_overrides.pop(_get_db, None)


@pytest.fixture()
def client(db_session, test_user):
    yield from _make_client(db_session, test_user)


@pytest.fixture()
def other_client(db_session, other_user):
    yield from _make_client(db_session, other_user)


def test_insights_page_returns_200(client, repo):
    """GET /repos/owner/myrepo/insights → 200."""
    response = client.get("/repos/owner/myrepo/insights")
    assert response.status_code == 200


def test_insights_page_contains_repo_name(client, repo):
    """인사이트 페이지 HTML에 리포명이 포함된다."""
    response = client.get("/repos/owner/myrepo/insights")
    assert "owner/myrepo" in response.text


def test_unknown_repo_returns_404(client):
    """존재하지 않는 리포 → 404."""
    response = client.get("/repos/nobody/unknown/insights")
    assert response.status_code == 404


def test_other_user_cannot_access_repo(other_client, repo):
    """다른 사용자의 리포 → 404 (권한 격리)."""
    response = other_client.get("/repos/owner/myrepo/insights")
    assert response.status_code == 404


def test_days_parameter_accepted(client, repo):
    """?days=7, ?days=90 모두 200 반환."""
    for days in (7, 90):
        response = client.get(f"/repos/owner/myrepo/insights?days={days}")
        assert response.status_code == 200
