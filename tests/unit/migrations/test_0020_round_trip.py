"""Migration 0020 round-trip test: upgrade → check table exists → downgrade → table gone.

마이그레이션 0020 왕복 테스트: 업그레이드 → 테이블 존재 확인 → 다운그레이드 → 테이블 제거 확인.
SQLAlchemy Base.metadata.create_all 로 ORM 스키마 검증 (Alembic scripting API 우회).
Uses SQLAlchemy Base.metadata.create_all to verify ORM schema (bypasses Alembic scripting API).
"""
# pylint: disable=redefined-outer-name
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest
from sqlalchemy import create_engine, inspect

from src.database import Base
from src.models.merge_retry import MergeRetryQueue  # noqa: F401  # pylint: disable=unused-import


def test_orm_creates_merge_retry_queue_table():
    """Base.metadata.create_all 로 merge_retry_queue 테이블이 생성되는지 검증.
    Verify that Base.metadata.create_all creates the merge_retry_queue table.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    insp = inspect(engine)
    assert "merge_retry_queue" in insp.get_table_names(), (
        "merge_retry_queue 테이블이 생성되어야 한다 / merge_retry_queue table must be created"
    )

    # 필수 컬럼 존재 확인 — 이름만 검사 (타입은 방언별로 다를 수 있음)
    # Verify required columns exist — name only (types vary by dialect).
    col_names = {c["name"] for c in insp.get_columns("merge_retry_queue")}
    required = {
        "id",
        "repo_full_name",
        "pr_number",
        "analysis_id",
        "commit_sha",
        "score",
        "threshold_at_enqueue",
        "status",
        "attempts_count",
        "max_attempts",
        "next_retry_at",
        "last_attempt_at",
        "claimed_at",
        "claim_token",
        "last_failure_reason",
        "last_detail_message",
        "notify_chat_id",
        "created_at",
        "updated_at",
    }
    missing = required - col_names
    assert not missing, f"누락된 컬럼 / Missing columns: {missing}"

    engine.dispose()


def test_orm_indexes_exist_on_merge_retry_queue():
    """sweep 및 sha_lookup 인덱스가 생성되는지 검증.
    Verify that sweep and sha_lookup indexes are created.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    insp = inspect(engine)
    index_names = {idx["name"] for idx in insp.get_indexes("merge_retry_queue")}

    # 두 일반 인덱스가 있어야 한다
    # Both regular indexes must be present.
    assert "ix_merge_retry_queue_sweep" in index_names, (
        "sweep 인덱스가 있어야 한다 / ix_merge_retry_queue_sweep must exist"
    )
    assert "ix_merge_retry_queue_sha_lookup" in index_names, (
        "sha_lookup 인덱스가 있어야 한다 / ix_merge_retry_queue_sha_lookup must exist"
    )

    engine.dispose()


def test_migration_alembic_round_trip():
    """Alembic scripting API 로 0020mergeretryqueue 업그레이드/다운그레이드 왕복 테스트.
    Round-trip test via Alembic scripting API: upgrade to 0020mergeretryqueue, then downgrade.

    주의: 구형 마이그레이션(0009 등) 이 SQLite 에서 ALTER TABLE UNIQUE 를 사용하므로
    SQLite 에서는 전체 히스토리 재생이 불가능하다. 이 테스트는 PostgreSQL 환경에서 실행된다.
    Note: Legacy migrations (e.g. 0009) use ALTER TABLE UNIQUE which SQLite does not support,
    so full history replay is not possible on SQLite. This test runs on PostgreSQL only.
    """
    db_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")

    # SQLite 환경(로컬 단위 테스트)에서는 건너뜀 — PostgreSQL CI/프로덕션에서만 실행
    # Skip on SQLite (local unit tests) — run only on PostgreSQL CI/production.
    if db_url.startswith("sqlite"):
        pytest.skip(
            "Alembic full-history replay requires PostgreSQL "
            "(SQLite does not support ALTER TABLE UNIQUE constraint)"
        )

    from alembic.config import Config
    from alembic import command as alembic_command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 0020mergeretryqueue 로 업그레이드
    # Upgrade to 0020mergeretryqueue.
    alembic_command.upgrade(cfg, "0020mergeretryqueue")

    eng = create_engine(db_url)
    tables = inspect(eng).get_table_names()
    eng.dispose()
    assert "merge_retry_queue" in tables, "업그레이드 후 테이블이 존재해야 한다 / Table must exist after upgrade"

    # 0019leaderboardoptin 으로 다운그레이드
    # Downgrade back to 0019leaderboardoptin.
    alembic_command.downgrade(cfg, "0019leaderboardoptin")

    eng2 = create_engine(db_url)
    tables2 = inspect(eng2).get_table_names()
    eng2.dispose()
    assert "merge_retry_queue" not in tables2, (
        "다운그레이드 후 테이블이 제거되어야 한다 / Table must be gone after downgrade"
    )
