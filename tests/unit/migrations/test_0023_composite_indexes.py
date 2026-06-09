"""Phase H PR-4A — 복합 인덱스 3종 회귀 가드.

12-에이전트 감사 (2026-04-30) High 성능 — analytics/leaderboard/dashboard 쿼리가
복합 인덱스 부재로 1만 row 시점부터 풀스캔 회귀.

신규 인덱스:
  - ix_analyses_repo_id_created_at — `WHERE repo_id=X ORDER BY created_at DESC LIMIT N`
  - ix_analyses_repo_id_author_login — leaderboard / author_trend
  - ix_merge_attempts_attempted_at — Phase F.4 dashboard 시계열
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
import pytest
from sqlalchemy import create_engine, inspect

from src.database import Base


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _index_columns(engine_, table: str, index_name: str) -> list[str] | None:
    """SQLAlchemy Inspector 로 인덱스의 컬럼 목록 조회. 미존재 시 None."""
    inspector = inspect(engine_)
    for idx in inspector.get_indexes(table):
        if idx["name"] == index_name:
            return idx["column_names"]
    return None


def test_analyses_has_composite_repo_id_created_at_index(engine):
    """ix_analyses_repo_id_created_at 인덱스 존재 + 컬럼 순서."""
    cols = _index_columns(engine, "analyses", "ix_analyses_repo_id_created_at")
    assert cols is not None, "복합 인덱스 ix_analyses_repo_id_created_at 미존재"
    assert cols == ["repo_id", "created_at"], (
        f"인덱스 컬럼 순서 불일치: {cols}"
    )


def test_analyses_has_composite_repo_id_author_login_index(engine):
    """ix_analyses_repo_id_author_login 인덱스 존재 + 컬럼 순서."""
    cols = _index_columns(engine, "analyses", "ix_analyses_repo_id_author_login")
    assert cols is not None, "복합 인덱스 ix_analyses_repo_id_author_login 미존재"
    assert cols == ["repo_id", "author_login"], (
        f"인덱스 컬럼 순서 불일치: {cols}"
    )


def test_merge_attempts_has_attempted_at_index(engine):
    """ix_merge_attempts_attempted_at 인덱스 존재 (시계열 쿼리용)."""
    cols = _index_columns(engine, "merge_attempts", "ix_merge_attempts_attempted_at")
    assert cols is not None, "ix_merge_attempts_attempted_at 미존재"
    assert cols == ["attempted_at"]


def test_merge_attempts_has_state_repo_index(engine):
    """ix_merge_attempts_state_repo 복합 인덱스 ORM↔alembic 정합 (#15).

    alembic 0022 전용이던 인덱스를 ORM __table_args__ 에도 선언 — create_all 정합.
    """
    cols = _index_columns(engine, "merge_attempts", "ix_merge_attempts_state_repo")
    assert cols is not None, (
        "ix_merge_attempts_state_repo 미존재 — ORM __table_args__ 미선언(alembic 0022 drift)"
    )
    assert cols == ["state", "repo_name"], f"인덱스 컬럼 순서 불일치: {cols}"


def test_merge_retry_has_partial_unique_active_index(engine):
    """uq_merge_retry_queue_active 부분 유일 인덱스 ORM↔alembic 정합 (#16).

    status='pending' 활성 행 중복 방지 — ORM __table_args__(sqlite/postgresql_where) + alembic 0020 양쪽 선언.
    """
    inspector = inspect(engine)
    indexes = {ix["name"]: ix for ix in inspector.get_indexes("merge_retry_queue")}
    assert "uq_merge_retry_queue_active" in indexes, (
        "uq_merge_retry_queue_active 미존재 — ORM __table_args__ 미선언(alembic 0020 drift)"
    )
    idx = indexes["uq_merge_retry_queue_active"]
    assert idx["column_names"] == ["repo_full_name", "pr_number", "commit_sha"], (
        f"인덱스 컬럼 불일치: {idx['column_names']}"
    )
    assert idx["unique"], "부분 유일 인덱스는 unique=True 여야 함"


def test_existing_orm_indexes_preserved(engine):
    """기존 ORM 인덱스 회귀 가드 — Phase 2 추가 단일 인덱스 보존.

    Note: 사이클 166 #15/#16 으로 ix_merge_attempts_state_repo(0022)·uq_merge_retry_queue_active(0020)
    도 ORM __table_args__ 에 선언됨 — 각각 위 전용 테스트(state_repo/partial_unique)로 검증. 본 테스트는
    그 외 ORM 측 단일 인덱스만 검증.
    """
    # 0021 — analyses.created_at 단일 인덱스 (ORM index=True 명시)
    assert _index_columns(engine, "analyses", "ix_analyses_created_at") == ["created_at"]
    # author_login 단일 인덱스 (ORM index=True 명시)
    assert _index_columns(engine, "analyses", "ix_analyses_author_login") == ["author_login"]
    # commit_sha 단일 인덱스
    assert _index_columns(engine, "analyses", "ix_analyses_commit_sha") == ["commit_sha"]
