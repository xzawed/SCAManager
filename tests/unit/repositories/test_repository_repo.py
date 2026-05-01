"""repository_repo 단위 테스트 — Phase H PR-3B joinedload 검증.

12-에이전트 감사 (2026-04-30) 개선 권장 #B3 — `find_by_full_name` 이 owner
relationship 을 lazy-load 하면 호출처마다 추가 SELECT (N+1). joinedload 로
단일 SELECT 보장.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.repository import Repository
from src.models.user import User
from src.repositories import repository_repo


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_repo_with_owner(db_session) -> tuple[User, Repository]:
    user = User(
        github_id="999",
        github_login="alice",
        display_name="Alice",
        email="alice@example.com",
        github_access_token="ghp_user_token",
    )
    db_session.add(user)
    db_session.commit()
    repo = Repository(full_name="owner/repo", user_id=user.id)
    db_session.add(repo)
    db_session.commit()
    return user, repo


# ──────────────────────────────────────────────────────────────────────────
# 기존 동작 회귀 방지
# ──────────────────────────────────────────────────────────────────────────


def test_find_by_full_name_returns_repo(db_session):
    """기본 동작 — full_name 으로 Repository 조회."""
    _seed_repo_with_owner(db_session)
    repo = repository_repo.find_by_full_name(db_session, "owner/repo")
    assert repo is not None
    assert repo.full_name == "owner/repo"


def test_find_by_full_name_returns_none_when_missing(db_session):
    repo = repository_repo.find_by_full_name(db_session, "ghost/repo")
    assert repo is None


# ──────────────────────────────────────────────────────────────────────────
# Phase H PR-3B — joinedload 검증
# ──────────────────────────────────────────────────────────────────────────


def test_find_by_full_name_with_owner_eagerly_loads(db_session):
    """find_by_full_name_with_owner 호출 후 repo.owner 접근 시 추가 SELECT 없음.

    SQLAlchemy event hook 으로 SELECT 횟수를 카운트. lazy-load 면 owner 접근 시
    +1 SELECT 가 발생하지만, joinedload 면 단일 쿼리로 끝.
    """
    _seed_repo_with_owner(db_session)
    db_session.expire_all()  # session cache 초기화 — lazy-load 가 발동되도록 강제

    select_count = [0]

    def _on_select(_conn, _cursor, statement, *_args):
        if statement.strip().upper().startswith("SELECT"):
            select_count[0] += 1

    event.listen(db_session.bind, "before_cursor_execute", _on_select)
    try:
        repo = repository_repo.find_by_full_name_with_owner(db_session, "owner/repo")
        # owner 접근 — joinedload 면 SELECT 추가 없음
        baseline_after_lookup = select_count[0]
        owner = repo.owner
        assert owner is not None
        # owner 접근으로 인한 SELECT 추가 횟수 = 0 이어야 joinedload 검증
        assert select_count[0] == baseline_after_lookup, (
            f"owner lazy-load 발생 — joinedload 미적용. "
            f"lookup 후 {baseline_after_lookup} → 접근 후 {select_count[0]}"
        )
    finally:
        event.remove(db_session.bind, "before_cursor_execute", _on_select)


def test_find_by_full_name_with_owner_returns_none_when_missing(db_session):
    """존재하지 않는 리포 → None."""
    result = repository_repo.find_by_full_name_with_owner(db_session, "ghost/repo")
    assert result is None


def test_find_by_full_name_with_owner_handles_repo_without_owner(db_session):
    """user_id=None 레거시 리포도 정상 — owner 는 None."""
    repo = Repository(full_name="legacy/repo", user_id=None)
    db_session.add(repo)
    db_session.commit()
    found = repository_repo.find_by_full_name_with_owner(db_session, "legacy/repo")
    assert found is not None
    assert found.owner is None


def test_find_by_full_name_handles_repo_without_owner(db_session):
    """user_id=None 인 레거시 리포 (Phase 8 OAuth 이전) 도 정상 처리."""
    repo = Repository(full_name="legacy/repo", user_id=None)
    db_session.add(repo)
    db_session.commit()

    found = repository_repo.find_by_full_name(db_session, "legacy/repo")
    assert found is not None
    assert found.user_id is None
    assert found.owner is None
