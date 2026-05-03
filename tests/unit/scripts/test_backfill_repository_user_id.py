"""scripts/backfill_repository_user_id.py `_resolve_user_id_for_repo` 단위 테스트
— Phase 3 backfill (TDD Red).

scripts/backfill_repository_user_id.py `_resolve_user_id_for_repo` unit tests
— Phase 3 backfill (TDD Red).

본 PR 의 신규 함수 (구현 미존재 — Red 단계):
The new function this PR introduces (implementation pending — Red phase):

    def _resolve_user_id_for_repo(db, repo) -> int | None:
        # 주어진 repository 의 첫 Analysis 의 author_login 으로 user_id 매칭.
        # 1. Analysis (repo_id == repo.id) 중 created_at asc 의 첫 row 의
        #    author_login 가져옴
        # 2. users.github_login = author_login 매칭
        # 3. 매칭되면 user.id 반환 / 없으면 None
        #
        # Resolves user_id for a repository by joining the chronologically first
        # Analysis.author_login against users.github_login.

사용자 결정 옵션 🅐-2 (author_login JOIN — Claude 권장 default).
User decision option 🅐-2 (author_login JOIN — Claude recommended default).

ORM import 모듈 최상단 의무 — auto-memory pytest-fixture-lazy-orm-import-trap.md
참조 (Phase 3 PR 4 CI #428 사고). lazy import 는 tests/ 전체 실행 시 metadata 누락.
ORM imports MUST be at module top — see auto-memory pytest-fixture-lazy-orm-import-trap.md
(Phase 3 PR 4 CI #428 incident). Lazy imports inside fixtures cause metadata gaps.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# ORM 모델 import 는 모듈 최상단 — Base.metadata 등록 (lazy import 금지)
# Top-level ORM imports register Base.metadata (no lazy imports allowed)
from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User

# 구현 대상 함수 — Red 단계에서는 ModuleNotFoundError 발생 의도.
# collection error 가 아닌 per-test fail 로 집계되도록 try/except 로 감싼다.
# Function under test — ModuleNotFoundError expected during Red phase.
# Wrapped in try/except so failures count per-test instead of as collection error.
try:
    from scripts.backfill_repository_user_id import (  # type: ignore[import-not-found]
        _resolve_user_id_for_repo,
    )
except ModuleNotFoundError:  # pragma: no cover — Red 단계 전용 분기
    _resolve_user_id_for_repo = None  # type: ignore[assignment]


@pytest.fixture
def db():
    """in-memory SQLite + ORM 메타데이터 — 테스트 간 완전 격리.
    in-memory SQLite + ORM metadata — full isolation between tests.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _make_user(db, *, github_login: str, user_id: int) -> User:
    """User seed 헬퍼 — email/display_name nullable=False 충족.
    User seed helper — satisfies nullable=False constraints on email/display_name.
    """
    user = User(
        id=user_id,
        github_id=f"gh-{user_id}",
        github_login=github_login,
        email=f"{github_login}@example.com",
        display_name=github_login,
    )
    db.add(user)
    db.commit()
    return user


def _make_repo(db, *, full_name: str = "owner/repo") -> Repository:
    """Repository seed 헬퍼 — user_id NULL (legacy 시뮬레이션).
    Repository seed helper — user_id NULL (legacy simulation).
    """
    repo = Repository(full_name=full_name, user_id=None)
    db.add(repo)
    db.commit()
    return repo


def _make_analysis(
    db,
    *,
    repo_id: int,
    author_login: str | None,
    commit_sha: str,
    created_at: datetime | None = None,
) -> Analysis:
    """Analysis seed 헬퍼 — repo_id + author_login + 명시적 created_at 지원.
    Analysis seed helper — supports explicit created_at for chronological ordering.
    """
    analysis = Analysis(
        repo_id=repo_id,
        commit_sha=commit_sha,
        author_login=author_login,
        score=80,
        grade="B",
    )
    if created_at is not None:
        analysis.created_at = created_at
    db.add(analysis)
    db.commit()
    return analysis


# ───────────────────────── 테스트 5건 / 5 tests ─────────────────────────


def test_resolve_returns_user_id_when_author_login_matches(db):
    """첫 Analysis.author_login 이 users.github_login 매칭 시 user.id 반환.
    Returns user.id when first Analysis.author_login matches users.github_login.
    """
    _make_user(db, github_login="alice", user_id=42)
    repo = _make_repo(db, full_name="alice/repo")
    _make_analysis(db, repo_id=repo.id, author_login="alice", commit_sha="sha1")

    result = _resolve_user_id_for_repo(db, repo)

    assert result == 42


def test_resolve_returns_none_when_no_analysis(db):
    """repo 에 Analysis 0건 시 None 반환.
    Returns None when the repo has no Analysis rows.
    """
    repo = _make_repo(db, full_name="orphan/repo")

    result = _resolve_user_id_for_repo(db, repo)

    assert result is None


def test_resolve_returns_none_when_author_login_null(db):
    """첫 Analysis.author_login 이 NULL 인 경우 None 반환.
    Returns None when first Analysis.author_login is NULL.
    """
    _make_user(db, github_login="alice", user_id=42)
    repo = _make_repo(db, full_name="legacy/repo")
    _make_analysis(db, repo_id=repo.id, author_login=None, commit_sha="sha1")

    result = _resolve_user_id_for_repo(db, repo)

    assert result is None


def test_resolve_returns_none_when_no_matching_user(db):
    """Analysis.author_login 에 매칭되는 users.github_login 없을 때 None.
    Returns None when no user matches Analysis.author_login.
    """
    # alice 만 존재 — bob 미존재
    # only alice exists — bob is absent
    _make_user(db, github_login="alice", user_id=42)
    repo = _make_repo(db, full_name="bob/repo")
    _make_analysis(db, repo_id=repo.id, author_login="bob", commit_sha="sha1")

    result = _resolve_user_id_for_repo(db, repo)

    assert result is None


def test_resolve_uses_first_analysis_chronologically(db):
    """3 Analysis 시드 시 created_at asc 의 첫 row 의 author_login 사용.
    Uses author_login of the chronologically first Analysis when 3 rows exist.
    """
    # User seed — first_user(99), second_user(88) 모두 존재
    # User seed — first_user(99) and second_user(88) both exist
    _make_user(db, github_login="first_user", user_id=99)
    _make_user(db, github_login="second_user", user_id=88)
    repo = _make_repo(db, full_name="multi/repo")

    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    # 명시적 created_at 으로 순서 강제 (asc: first → second → third)
    # Force ordering via explicit created_at (asc: first → second → third)
    _make_analysis(
        db,
        repo_id=repo.id,
        author_login="first_user",
        commit_sha="sha-first",
        created_at=base,
    )
    _make_analysis(
        db,
        repo_id=repo.id,
        author_login="second_user",
        commit_sha="sha-second",
        created_at=base + timedelta(hours=1),
    )
    _make_analysis(
        db,
        repo_id=repo.id,
        author_login="third_user",
        commit_sha="sha-third",
        created_at=base + timedelta(hours=2),
    )

    result = _resolve_user_id_for_repo(db, repo)

    # first_user.id == 99 사용 (가장 오래된 Analysis 기준)
    # Uses first_user.id == 99 (oldest Analysis takes precedence)
    assert result == 99
