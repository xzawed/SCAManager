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

# 🔴 사전 존재(pre-existing) ORM↔alembic 구조 차이 — 본 가드(#18) 도입 전부터 존재하는 legacy/표현 차이.
# 전부 운영 무해(앱 정상 동작)하며 별도 fix 후보다. 본 가드 목적은 '신규 drift 차단'이므로 사전 존재 항목만
# allowlist 한다(allowlist 밖 신규 항목은 자동 fail). repr 부분문자열(전부 포함) 매칭 — 인덱스/객체명은 repr 안정.
# Pre-existing ORM↔alembic structural diffs (legacy/representation), harmless and tracked as separate
# fix candidates. This guard blocks NEW drift; pre-existing items below are allowlisted by repr substrings.
_ALLOWLIST_PATTERNS = (
    # ① users 인덱스 legacy 명 — 0005 가 google_id 컬럼에 ix_users_google_id 생성, 이후 컬럼이 github_id 로
    #    리네임됐으나 인덱스명 미반영. ORM 은 ix_users_github_id 선언. (인덱스 리네임 마이그레이션 차기 후보)
    ("remove_index", "ix_users_google_id"),
    ("add_index", "ix_users_github_id"),
    # ② email 유일성 표현 차이 — ORM unique=True(UniqueConstraint) ↔ DB unique INDEX ix_users_email(0005).
    #    기능 동등(둘 다 email 유일성) — 표현 FP. (ORM/마이그레이션 표현 통일 차기 후보)
    ("remove_index", "ix_users_email"),
    ("add_constraint", "users", "email"),
    # ③ analyses 보조 복합 인덱스 — 0032 가 ix_analyses_repo_id_created_at_tokens 생성, ORM __table_args__ 미선언
    #    (#15-class, alembic 전용). (ORM 선언 차기 후보)
    ("remove_index", "ix_analyses_repo_id_created_at_tokens"),
    # ④ insight_narrative_cache 부분 유일 인덱스 — 0031 raw DDL(WHERE 절), ORM 미선언 (#16-class).
    #    (ORM postgresql_where 선언 차기 후보 — WHERE 정규화 FP 주의)
    ("remove_index", "uq_insight_cache_global"),
    ("remove_index", "uq_insight_cache_repo"),
    # ⑤ repositories.user_id FK — **해소(alembic 0039, ondelete=SET NULL)**: 0005 가 컬럼만 추가했던
    #    DB FK 부재를 0039 가 추가(고아 정리 선행). ORM↔DB 정합 → allowlist 불요(제거). 잔존 시 가드가
    #    실제 FK 누락(회귀)을 잡도록 의도적 미등재. (#14-class 중 데이터 무결성 영향분 — drift ①③④ 는 잔존)
)


def _is_pk_redundant_index(op: str, obj) -> bool:
    """단일 PK 컬럼 인덱스 = PK 중복 FP — PG 는 PK 자동 인덱스 생성, ORM `index=True` 가 ix_<table>_id 추가 선언.

    Single-column index on the primary key is a redundancy FP (PG auto-creates the PK index; the ORM's
    `index=True` on the PK column additionally declares ix_<table>_id which has no separate DB index).
    """
    if op not in ("add_index", "remove_index"):
        return False
    try:
        cols = list(obj.columns)
    except (AttributeError, TypeError):
        return False
    return len(cols) == 1 and bool(getattr(cols[0], "primary_key", False))


def _structural_diffs(raw_diff: list) -> list:
    """compare_metadata 결과에서 신규(non-allowlisted, non-FP) 구조적 diff 만 추출.

    compare_metadata 는 컬럼 단위 diff 를 sublist 로 묶어 반환. attribute-level(modify_*),
    PK 중복 인덱스 FP, 사전 존재 allowlist 항목을 제외한 신규 구조 drift 만 남긴다.
    """
    out = []
    for item in raw_diff:
        entries = item if isinstance(item, list) else [item]
        for entry in entries:
            if not (isinstance(entry, tuple) and len(entry) >= 2):
                continue
            op = entry[0]
            if op in _IGNORED_OPS:
                continue
            if _is_pk_redundant_index(op, entry[-1]):
                continue
            entry_repr = repr(entry)
            if any(all(n in entry_repr for n in pat) for pat in _ALLOWLIST_PATTERNS):
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


def test_structural_diffs_filter_logic():
    """_structural_diffs 필터 로직 검증 — 로컬(PG 불필요). PK FP·allowlist 제외, 신규 drift 포착, modify_* 제외.

    Local guard for the filter logic (no PG needed): PK-redundant index FP and allowlisted pre-existing
    diffs are dropped, NEW structural drift is caught, attribute-level modify_* is ignored.
    """
    from sqlalchemy import Column, Integer, MetaData, Table, Index  # pylint: disable=import-outside-toplevel

    md = MetaData()
    # 1) 단일 PK 컬럼 인덱스 → PK 중복 FP 제외
    t_pk = Table("merge_attempts", md, Column("id", Integer, primary_key=True))
    assert _structural_diffs([("add_index", Index("ix_merge_attempts_id", t_pk.c.id))]) == []

    # 2) allowlist 사전 존재 항목(인덱스명 repr) 제외
    t_users = Table("users", md, Column("github_id", Integer))
    assert _structural_diffs([("add_index", Index("ix_users_github_id", t_users.c.github_id))]) == []

    # 3) 신규(non-allowlisted, non-PK) 인덱스 drift 는 포착 → fail 신호
    t_an = Table("analyses", md, Column("score", Integer))
    caught = _structural_diffs([("add_index", Index("ix_analyses_score_brand_new", t_an.c.score))])
    assert len(caught) == 1 and caught[0][0] == "add_index"

    # 4) attribute-level modify_* 는 제외 (방언 정규화 FP)
    assert _structural_diffs([("modify_nullable", None, "users", None, {}, True, False)]) == []

    # 5) sublist(컬럼 단위 diff 묶음) flatten 처리 — 신규 add_column 포착
    nested = [[("modify_default", None, "users", None, {}, "a", "b"),
               ("add_column", None, "users", Column("brand_new_col", Integer))]]
    flat = _structural_diffs(nested)
    assert len(flat) == 1 and flat[0][0] == "add_column"
