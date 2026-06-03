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
from sqlalchemy import create_engine, inspect, text

from src.database import Base
import src.models.merge_retry  # ensure model is registered on Base.metadata


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
    # PG 전용 — DATABASE_URL_TEST_POSTGRES 설정 시에만 실행 (사이클 157 #8: CI 활성화).
    # conftest.py 가 DATABASE_URL 을 sqlite 로 강제하므로 별도 PG 전용 env 를 읽는다
    # (S3 의 test_retry_concurrency_postgres 와 동일 패턴 — pg-concurrency CI job 에서 실행).
    # PG-only — runs only when DATABASE_URL_TEST_POSTGRES is set (Cycle 157 #8: CI activation).
    # conftest forces DATABASE_URL to sqlite, so we read a dedicated PG env (same pattern as S3).
    db_url = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
    if not db_url:
        pytest.skip(
            "Alembic full-history replay requires PostgreSQL — set DATABASE_URL_TEST_POSTGRES "
            "(SQLite does not support ALTER TABLE UNIQUE constraint)"
        )

    from unittest.mock import patch

    from alembic.config import Config
    from alembic import command as alembic_command
    from src.config import settings as app_settings

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 🔴 alembic/env.py:30 이 cfg URL 을 settings.database_url 로 덮어씀 (싱글톤, import 시 sqlite 고정).
    # → cfg.set_main_option 만으로는 SQLiteImpl 로 실행돼 0009 의 ALTER constraint 에서 실패.
    # settings 싱글톤 속성을 PG URL 로 patch (monkeypatch.setenv 무효 — testing.md 규칙). (사이클 157 #8 fix-up)
    # env.py overrides cfg URL with settings.database_url (singleton fixed to sqlite at import),
    # so patch the singleton attribute to the PG URL; patch.object restores it automatically.
    with patch.object(app_settings, "database_url", db_url):
        # 🔴 clean-base 보장 (사이클 159 — 158 회고 P2): 동일 pg-concurrency job 의 선행 테스트가
        # Base.metadata.create_all 로 만든 잔여 테이블이 비정상 종료(barrier timeout 등)로 남으면
        # from-base upgrade 가 DuplicateTable 로 spurious-fail — 격리를 CI 실행 순서에만 의존하지
        # 않도록 스키마를 명시적으로 리셋해 round-trip 을 self-isolating 으로 만든다.
        # Reset schema to guarantee a clean base — prior tests in the same PG job may leave residual
        # tables on abnormal exit, which would make the from-base upgrade fail with DuplicateTable.
        reset_eng = create_engine(db_url)
        with reset_eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        reset_eng.dispose()

        # 0020mergeretryqueue 로 업그레이드 / Upgrade to 0020mergeretryqueue.
        alembic_command.upgrade(cfg, "0020mergeretryqueue")

        eng = create_engine(db_url)
        tables = inspect(eng).get_table_names()
        eng.dispose()
        assert "merge_retry_queue" in tables, "업그레이드 후 테이블이 존재해야 한다 / Table must exist after upgrade"

        # 0019leaderboardoptin 으로 다운그레이드 / Downgrade back to 0019leaderboardoptin.
        alembic_command.downgrade(cfg, "0019leaderboardoptin")

        eng2 = create_engine(db_url)
        tables2 = inspect(eng2).get_table_names()
        eng2.dispose()
        assert "merge_retry_queue" not in tables2, (
            "다운그레이드 후 테이블이 제거되어야 한다 / Table must be gone after downgrade"
        )
