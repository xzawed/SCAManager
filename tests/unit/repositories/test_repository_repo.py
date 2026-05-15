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


# ──────────────────────────────────────────────────────────────────────────
# find_all_by_user — 사용자 소유 + 공유(user_id=NULL) 리포 조회
# find_all_by_user — returns repos owned by user plus shared (user_id=NULL)
# ──────────────────────────────────────────────────────────────────────────


def _seed_user(db_session, github_id: str, login: str) -> User:
    """테스트용 User 레코드 생성 헬퍼.
    Helper to create a User record for tests.
    """
    user = User(
        github_id=github_id,
        github_login=login,
        display_name=login,
        email=f"{login}@example.com",
        github_access_token=f"ghp_{login}",
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_find_all_by_user_returns_owned_repos(db_session):
    """사용자 소유 리포 2건이 모두 반환된다.
    Both repos owned by the user are returned.
    """
    user = _seed_user(db_session, "1", "alice")
    db_session.add_all([
        Repository(full_name="alice/repo1", user_id=user.id),
        Repository(full_name="alice/repo2", user_id=user.id),
    ])
    db_session.commit()

    result = repository_repo.find_all_by_user(db_session, user.id)
    full_names = {r.full_name for r in result}
    assert full_names == {"alice/repo1", "alice/repo2"}


def test_find_all_by_user_returns_shared_repos(db_session):
    """user_id=NULL 공유 리포가 포함된다.
    Repos with user_id=NULL (shared) are included.
    """
    user = _seed_user(db_session, "2", "bob")
    db_session.add(Repository(full_name="shared/repo", user_id=None))
    db_session.commit()

    result = repository_repo.find_all_by_user(db_session, user.id)
    assert any(r.full_name == "shared/repo" for r in result)


def test_find_all_by_user_excludes_other_user_repos(db_session):
    """다른 사용자 소유 리포는 제외된다.
    Repos owned by a different user are excluded.
    """
    user_a = _seed_user(db_session, "3", "carol")
    user_b = _seed_user(db_session, "4", "dave")
    db_session.add_all([
        Repository(full_name="carol/repo", user_id=user_a.id),
        Repository(full_name="dave/repo", user_id=user_b.id),
    ])
    db_session.commit()

    result = repository_repo.find_all_by_user(db_session, user_a.id)
    full_names = {r.full_name for r in result}
    assert "carol/repo" in full_names
    assert "dave/repo" not in full_names


def test_find_all_by_user_ordered_by_created_at_desc(db_session):
    """반환 순서가 created_at 내림차순 (최신 리포가 첫 번째).
    Results are ordered by created_at descending (newest first).
    """
    from datetime import datetime, timedelta, timezone

    user = _seed_user(db_session, "5", "eve")
    now = datetime.now(timezone.utc)
    older = Repository(
        full_name="eve/older",
        user_id=user.id,
        created_at=now - timedelta(days=2),
    )
    newer = Repository(
        full_name="eve/newer",
        user_id=user.id,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([older, newer])
    db_session.commit()

    result = repository_repo.find_all_by_user(db_session, user.id)
    assert result[0].full_name == "eve/newer"
    assert result[1].full_name == "eve/older"
