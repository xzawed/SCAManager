"""전역 ORM ↔ alembic 마이그레이션 메타데이터 정합 가드 (#18, PostgreSQL 전용).

Global ORM ↔ alembic migration metadata parity guard (#18, PostgreSQL-only).

정합성 감사 full(2026-06-08) P2 #18 — ORM 모델(Base.metadata)과 alembic 마이그레이션 체인이
drift 해도 자동 검출하는 전역 가드 부재. #14(FK ondelete)·#15/#16/#17(인덱스 ORM↔alembic) 같은
누적 drift 의 근본 원인. 본 테스트는 실 PG 에 `alembic upgrade head` 적용한 스키마 ↔ Base.metadata 를
`alembic.autogenerate.compare_metadata` 로 대조해 **구조적 diff(테이블/컬럼/인덱스/제약/FK 누락·잉여)**
가 0 임을 단언한다.

This guard applies the full alembic chain to a real Postgres DB, then compares the resulting schema
against the ORM Base.metadata via compare_metadata, asserting zero structural drift.

🔴 PG 전용 — conftest 가 DATABASE_URL 을 sqlite 로 강제하므로 `DATABASE_URL_TEST_POSTGRES` 를 읽는다
(pg-concurrency CI job 에서 실행, `ci.yml` node-id 핀 등재 의무 — 핀 미등재 시 자동 미수집).
SQLite 는 RLS·부분 인덱스·일부 ALTER constraint 미지원으로 전체 체인 재생 불가 → skip.

🔴 FP 제거: `compare_type`/`compare_server_default` 비활성(방언 텍스트 정규화 차이) + `modify_*`(nullable
표현 차이) 필터. 방언 정규화로 불가피한 구조 FP 는 `_ALLOWLIST_NAMES` 에 사유와 함께만 등재한다.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
import pytest
from sqlalchemy import create_engine, text

from src.database import Base

# 🔴 Base.metadata 완성을 위해 전 ORM 모델(11종) 명시 import (empty __init__ 규칙, testing.md).
# Explicitly import every ORM model so Base.metadata is complete before the comparison.
import src.models.analysis  # noqa: F401  pylint: disable=unused-import
import src.models.analysis_feedback  # noqa: F401  pylint: disable=unused-import
import src.models.gate_decision  # noqa: F401  pylint: disable=unused-import
import src.models.insight_narrative_cache  # noqa: F401  pylint: disable=unused-import
import src.models.issue_registration  # noqa: F401  pylint: disable=unused-import
import src.models.merge_attempt  # noqa: F401  pylint: disable=unused-import
import src.models.merge_retry  # noqa: F401  pylint: disable=unused-import
import src.models.repo_config  # noqa: F401  pylint: disable=unused-import
import src.models.repository  # noqa: F401  pylint: disable=unused-import
import src.models.security_alert_log  # noqa: F401  pylint: disable=unused-import
import src.models.user  # noqa: F401  pylint: disable=unused-import


# 방언 정규화 차이로 FP 인 attribute-level diff op (type/default 은 opts 로 이미 미생성).
# Attribute-level diff ops that are dialect-normalization FPs (type/default already disabled via opts).
_IGNORED_OPS = frozenset({
    "modify_nullable", "modify_default", "modify_type", "modify_comment",
})

# 방언 정규화로 불가피한 구조 FP 이름 — CI 실측 사유와 함께만 등재 (현재 없음).
# Structural-diff object names that are unavoidable dialect FPs — add ONLY with a CI-verified reason.
_ALLOWLIST_NAMES: "frozenset[str]" = frozenset()


def _structural_diffs(raw_diff: list) -> list:
    """compare_metadata 결과에서 구조적(테이블/컬럼/인덱스/제약/FK) diff 만 추출.

    Flatten compare_metadata output and keep only structural diffs (drop attribute-level
    modify_* and allowlisted FP names). compare_metadata 는 컬럼 단위 diff 를 sublist 로 묶어 반환.
    """
    out = []
    for item in raw_diff:
        entries = item if isinstance(item, list) else [item]
        for entry in entries:
            if not (isinstance(entry, tuple) and entry):
                continue
            if entry[0] in _IGNORED_OPS:
                continue
            if any(name in repr(entry) for name in _ALLOWLIST_NAMES):
                continue
            out.append(entry)
    return out


def test_orm_metadata_matches_migrations():
    """ORM Base.metadata 가 `alembic upgrade head` 스키마와 구조적으로 일치 (#18).

    drift(누락·잉여 테이블/컬럼/인덱스/제약/FK) 시 fail → ORM(`__table_args__`/`Column`)과
    alembic 마이그레이션 양쪽 동기화 의무 환기. #14/#15/#16/#17 류 drift 자동 검출.
    """
    db_url = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
    if not db_url:
        pytest.skip(
            "ORM↔alembic compare_metadata 가드는 PostgreSQL 필요 — "
            "DATABASE_URL_TEST_POSTGRES 설정 시 pg-concurrency CI job 에서 실행"
        )

    from unittest.mock import patch  # pylint: disable=import-outside-toplevel

    from alembic.config import Config  # pylint: disable=import-outside-toplevel
    from alembic import command as alembic_command  # pylint: disable=import-outside-toplevel
    from alembic.migration import MigrationContext  # pylint: disable=import-outside-toplevel
    from alembic.autogenerate import compare_metadata  # pylint: disable=import-outside-toplevel
    from src.config import settings as app_settings  # pylint: disable=import-outside-toplevel

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    # env.py:30 이 cfg URL 을 settings.database_url 로 덮어쓰므로 싱글톤 patch (db.md 규칙, 사이클 157 #8).
    with patch.object(app_settings, "database_url", db_url):
        # clean-base 리셋 — 동일 PG job 선행 테스트 잔여 격리 (round-trip 패턴, 사이클 159).
        reset_eng = create_engine(db_url)
        with reset_eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        reset_eng.dispose()

        alembic_command.upgrade(cfg, "head")

        eng = create_engine(db_url)
        try:
            with eng.connect() as conn:
                # type/server_default 비교 비활성 — 방언 텍스트 정규화 FP 제거 (구조 drift 만 본다).
                ctx = MigrationContext.configure(
                    conn,
                    opts={"compare_type": False, "compare_server_default": False},
                )
                raw_diff = compare_metadata(ctx, Base.metadata)
        finally:
            eng.dispose()

    structural = _structural_diffs(raw_diff)
    assert not structural, (
        "🔴 ORM Base.metadata ↔ alembic 마이그레이션 구조적 drift 검출 — "
        "ORM __table_args__/Column 또는 alembic 마이그레이션 한쪽 누락 동기화 필요:\n"
        + "\n".join(f"  - {d!r}" for d in structural)
    )
