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


def test_migration_0041_force_round_trip_postgres():
    """0041 FORCE 실 PG 왕복 + force_applied/connection_bypasses_rls 실측 양성 경로 검증.

    Mock 가드(test_0041_rls_force.py)가 못 덮는 3가지를 실 PostgreSQL 로 봉인한다:
    (a) 0041 upgrade 멀티 스테이트먼트가 실 PG 에서 11/11 FORCE 를 만드는지
    (b) downgrade(NO FORCE) 가 실 PG 에서 실행되는지 (mock SQL 캡처만으로는 미검증)
    (c) `_measure_force_applied` 의 expanding bindparam 쿼리가 실 PG 에서 True 를
        반환하는지 + CI 'scatest'(superuser) 접속에서 connection_bypasses_rls=True 실측.

    Live-PG seal for three gaps the mock guards cannot cover: (a) 0041 upgrade really
    FORCEs 11/11 tables, (b) the downgrade (NO FORCE) actually runs on PG, and
    (c) `_measure_force_applied`'s expanding-bindparam query returns True on real PG,
    with connection_bypasses_rls=True for the superuser 'scatest' CI role.

    🔴 ci.yml pg-concurrency job 의 ::node-id 핀에 등재됨 — 핀 미등재 시 자동 미수집.
    🔴 Pinned by ::node-id in the ci.yml pg-concurrency job — unpinned tests are not collected.
    """
    db_url = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
    if not db_url:
        pytest.skip(
            "0041 FORCE round-trip requires PostgreSQL — set DATABASE_URL_TEST_POSTGRES"
        )

    from unittest.mock import patch

    from alembic.config import Config
    from alembic import command as alembic_command
    from sqlalchemy.orm import sessionmaker

    from src.config import settings as app_settings
    from src.services.saas_service import _RLS_MATRIX, rls_coverage_summary

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    # env.py 가 cfg URL 을 settings.database_url 로 덮어씀 — 싱글톤 patch 의무 (db.md 규칙)
    # env.py overrides the cfg URL with settings.database_url — must patch the singleton
    with patch.object(app_settings, "database_url", db_url):
        # clean-base self-isolating (사이클 159 round-trip 패턴 미러)
        # Clean-base self-isolating (mirrors the Cycle 159 round-trip pattern)
        reset_eng = create_engine(db_url)
        with reset_eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        reset_eng.dispose()

        alembic_command.upgrade(cfg, "head")

        eng = create_engine(db_url)
        try:
            session_factory = sessionmaker(bind=eng)
            with session_factory() as session:
                summary = rls_coverage_summary(session)
                assert summary["force_applied"] is True, (
                    "upgrade head 후 실 PG 실측 force_applied=True 여야 한다 / "
                    "force_applied must be True on real PG after upgrade head"
                )
                # CI 'scatest' 는 superuser — 우회 실측 양성 경로 동시 검증
                # CI 'scatest' is a superuser — also validates the bypass-positive path
                assert summary["connection_bypasses_rls"] is True, (
                    "superuser 접속의 connection_bypasses_rls=True 실측 실패 / "
                    "superuser connection must report connection_bypasses_rls=True"
                )
            # 카탈로그 직접 대조 (서비스 쿼리와 독립적인 이중 검증)
            # Direct catalog cross-check, independent of the service query
            with eng.connect() as conn:
                forced = conn.execute(text(
                    "SELECT count(*) FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                    "AND c.relforcerowsecurity"
                )).scalar()
            assert forced == len(_RLS_MATRIX), (
                f"FORCE 테이블 {forced}/{len(_RLS_MATRIX)} — 0041 부분 적용 / "
                "0041 applied only partially on real PG"
            )
        finally:
            eng.dispose()

        # downgrade — NO FORCE 가 실 PG 에서 실행되는지 검증 후 head 복원
        # Downgrade to verify NO FORCE runs on real PG, then restore head
        alembic_command.downgrade(cfg, "0040")
        eng2 = create_engine(db_url)
        try:
            session_factory2 = sessionmaker(bind=eng2)
            with session_factory2() as session:
                assert rls_coverage_summary(session)["force_applied"] is False, (
                    "downgrade 0040 후 force_applied=False 여야 한다 / "
                    "force_applied must be False after downgrade to 0040"
                )
        finally:
            eng2.dispose()

        # 후속 테스트(orm parity 등)가 head 를 기대 — job 내 실행 순서 무관성 보존
        # Later tests (orm parity, etc.) expect head — keep the job order-independent
        alembic_command.upgrade(cfg, "head")


def test_migrations_idempotent_over_prod_drift_postgres():
    """0039/0040 가 운영 drift(사전 존재 NO ACTION FK)에서도 head 까지 적용되는지 실 PG 검증.

    2026-06-15 운영 사고 재현 — alembic 0038 + `repositories_user_id_fkey`(NO ACTION) 가
    사전 존재한 상태에서 (수정 전) 0039 의 무조건 `create_foreign_key` 가 "already exists" 로
    실패해 0038 고착(0040/0041 FORCE 전부 미적용)했다. 본 테스트는 drift 를 인위 주입한 뒤
    `upgrade head` 가 성공 + FK 가 SET NULL 로 교정 + 인덱스 rename + FORCE 적용까지 도달함을
    봉인한다. 정적 가드(test_0039/0040)가 못 덮는 실행 멱등 경로.

    Reproduces the 2026-06-15 prod incident (pre-existing NO ACTION FK at 0038 stuck alembic
    because the unguarded create_foreign_key failed) and seals that the idempotent 0039/0040
    apply head cleanly over the drift.

    🔴 ci.yml pg-concurrency job 의 ::node-id 핀에 등재됨 — 핀 미등재 시 자동 미수집.
    🔴 Pinned by ::node-id in the ci.yml pg-concurrency job — unpinned tests are not collected.
    """
    db_url = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
    if not db_url:
        pytest.skip(
            "prod-drift idempotency replay requires PostgreSQL — set DATABASE_URL_TEST_POSTGRES"
        )

    from unittest.mock import patch

    from alembic.config import Config
    from alembic import command as alembic_command
    from sqlalchemy.orm import sessionmaker

    from src.config import settings as app_settings
    from src.services.saas_service import rls_coverage_summary

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    # env.py 가 cfg URL 을 settings.database_url 로 덮어씀 — 싱글톤 patch 의무 (db.md 규칙)
    with patch.object(app_settings, "database_url", db_url):
        # clean-base self-isolating (round-trip 패턴 미러)
        reset_eng = create_engine(db_url)
        with reset_eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        reset_eng.dispose()

        # 0039 직전(0038)까지 적용
        alembic_command.upgrade(cfg, "0038")

        # 운영 drift 인위 주입: NO ACTION FK 사전 생성 (0039 가 만들 SET NULL 과 불일치, 동일 이름)
        drift_eng = create_engine(db_url)
        with drift_eng.begin() as conn:
            conn.execute(text(
                "ALTER TABLE repositories ADD CONSTRAINT repositories_user_id_fkey "
                "FOREIGN KEY (user_id) REFERENCES users (id)"
            ))
        drift_eng.dispose()

        # 멱등 0039(DROP IF EXISTS) → 0040(DO block) → 0041 가 drift 위에서 성공해야 한다
        alembic_command.upgrade(cfg, "head")

        eng = create_engine(db_url)
        try:
            with eng.connect() as conn:
                ondelete = conn.execute(text(
                    "SELECT confdeltype FROM pg_constraint "
                    "WHERE conname = 'repositories_user_id_fkey' AND contype = 'f'"
                )).scalar()
                github_idx = conn.execute(text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = 'ix_users_github_id'"
                )).scalar()
            # confdeltype 'n' = SET NULL — 사전 NO ACTION FK 가 교정됐는지
            assert ondelete == "n", (
                f"0039 후 repositories_user_id_fkey ondelete='{ondelete}' — SET NULL('n') 여야 한다 "
                "(사전 NO ACTION FK 교정 실패 — 멱등 DROP+recreate 회귀)"
            )
            assert github_idx == 1, "0040 후 ix_users_github_id 인덱스가 존재해야 한다 (rename 회귀)"
            session_factory = sessionmaker(bind=eng)
            with session_factory() as session:
                assert rls_coverage_summary(session)["force_applied"] is True, (
                    "drift 위 upgrade head 후 force_applied=True 여야 한다 (0041 미도달)"
                )
        finally:
            eng.dispose()
