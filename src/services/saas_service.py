"""saas_service — SaaS Phase 1 MVP read-only 집계 (Cycle 79 PR 3a 신설).

5+1 cross-verify (Cycle 78 NEW-P0-1) 결과 = 영역 🅐 SaaS 멀티 테넌트 진입 의무.

Phase 1 = read-only (자동 처리 X — 사용자 1-click confirm 의무).
Phase 1 = read-only (no auto action — user 1-click confirm required).

함수:
- tenant_inventory(db) — 사용자별 (id, github_login, email, repo_count, analysis_count, last_active_at)
- rls_audit_matrix() — 정적 RLS policy 적용 매트릭스 (alembic 0026 + 0027 + 0028 + 0029 + 0037 영역)

Phase 2 영역 (본 PR X): 결제 / 사용량 cap / API key per-tenant — 별도 PR 진입 의무 (High tier).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.orm import Session

from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.shared.alembic_dialect import is_postgresql


def tenant_inventory(db: Session) -> list[dict[str, Any]]:
    """사용자별 인벤토리 — repo_count + analysis_count + last_active_at.

    User-level inventory — repo count + analysis count + last active timestamp.
    """
    stmt = (
        select(
            User.id,
            User.github_login,
            User.email,
            User.display_name,
            User.created_at,
            func.count(Repository.id.distinct()).label("repo_count"),  # pylint: disable=not-callable
            func.count(Analysis.id.distinct()).label("analysis_count"),  # pylint: disable=not-callable
            func.max(Analysis.created_at).label("last_analysis_at"),
        )
        .select_from(User)
        .outerjoin(Repository, Repository.user_id == User.id)
        .outerjoin(Analysis, Analysis.repo_id == Repository.id)
        .group_by(User.id, User.github_login, User.email, User.display_name, User.created_at)
        .order_by(User.id)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "id": row.id,
            "github_login": row.github_login,
            "email": row.email,
            "display_name": row.display_name,
            "created_at": row.created_at,
            "repo_count": int(row.repo_count or 0),
            "analysis_count": int(row.analysis_count or 0),
            "last_analysis_at": row.last_analysis_at,
        }
        for row in rows
    ]


# ─── RLS audit matrix (정적 — alembic 마이그레이션 결과) ─────────────────


# RLS policy 적용 매트릭스 — alembic 0026/0027/0028/0029/0037 누적 결과
# RLS policy matrix — cumulative result of alembic 0026/0027/0028/0029/0037
# 각 항목 = (table, isolation_pattern, since_alembic, status)
# 🔴 신규 RLS 테이블 추가 시 본 매트릭스 동기화 의무 — tests/unit/test_rls_matrix_completeness.py 가드
# When a new table gets RLS, this matrix MUST be updated — guarded by test_rls_matrix_completeness.py
_RLS_MATRIX: tuple[dict[str, str], ...] = (
    {
        "table": "repositories",
        "pattern": "user_id 직접 (legacy NULL 호환)",
        "since": "0026",
        "status": "applied",
    },
    {
        "table": "analyses",
        "pattern": "repo_id 간접 (repositories 페어)",
        "since": "0026",
        "status": "applied",
    },
    {
        "table": "merge_attempts",
        "pattern": "repo_name 간접 (repositories.full_name 페어)",
        "since": "0026",
        "status": "applied",
    },
    {
        "table": "security_alert_process_logs",
        "pattern": "repo_id 간접 (analyses 패턴)",
        "since": "0027",
        "status": "applied",
    },
    {
        "table": "insight_narrative_cache",
        "pattern": "user_id 직접 (NULL 허용 X)",
        "since": "0028",
        "status": "applied",
    },
    {
        "table": "users",
        "pattern": "self-RLS (id 직접 비교)",
        "since": "0029",
        "status": "applied",
    },
    {
        "table": "repo_configs",
        "pattern": "repo_full_name 간접 (repositories 페어)",
        "since": "0029",
        "status": "applied",
    },
    {
        "table": "gate_decisions",
        "pattern": "analysis_id 간접 2-hop (analyses → repositories)",
        "since": "0029",
        "status": "applied",
    },
    {
        "table": "merge_retry_queue",
        "pattern": "repo_full_name 간접 (repositories 페어)",
        "since": "0029",
        "status": "applied",
    },
    {
        "table": "analysis_feedbacks",
        "pattern": "user_id 직접 (NULL 허용 X — FK NOT NULL)",
        "since": "0029",
        "status": "applied",
    },
    {
        "table": "issue_registrations",
        "pattern": "repo_id 간접 1-hop (repositories.user_id 페어, legacy NULL 호환)",
        "since": "0037",
        "status": "applied",
    },
)


def rls_audit_matrix() -> list[dict[str, str]]:
    """RLS policy 적용 매트릭스 (정적 — 운영 SQL injection 회피).

    RLS policy matrix (static — avoids runtime SQL injection risk).
    """
    return list(_RLS_MATRIX)


# FORCE 실측 쿼리 — 테이블명은 bound parameter 로만 전달 (f-string SQL 조립 금지,
# PR #516 RLS f-string SQL injection 사고 전례). expanding=True 가 IN 절 리스트 확장.
# FORCE live-check query — table names travel only as bound parameters (no f-string
# SQL assembly; PR #516 RLS injection precedent). expanding=True expands the IN list.
_FORCE_COUNT_SQL = text(
    "SELECT count(*) FROM pg_class c "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = 'public' AND c.relkind = 'r' "
    "AND c.relforcerowsecurity AND c.relname IN :tbl_list"
).bindparams(bindparam("tbl_list", expanding=True))


# 접속 role 의 RLS 우회 여부 실측 — BYPASSRLS 속성 + superuser(암묵 우회) 양쪽 검사.
# Live-check whether the connection role bypasses RLS — BYPASSRLS attribute plus
# superuser (which implicitly bypasses RLS).
_BYPASS_ROLE_SQL = text(
    "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user"
)


def _measure_connection_bypasses_rls(db: Session) -> bool:
    """접속 role 이 RLS 를 우회하는지 실측 (rolbypassrls OR rolsuper, PG 전용).

    FORCE 가 전부 적용돼도 BYPASSRLS/superuser 접속은 RLS 를 항상 우회한다 —
    Phase 3(0041) 반영 후 Phase 4(role 전환) 전 구간의 거짓 안심(false confidence)
    창을 admin 화면에서 가시화하기 위한 실측 (db.md 'rolbypassrls 실측 의무' 정합).
    비-PostgreSQL 은 RLS 개념이 없으므로 False.

    Live-check whether the connection role bypasses RLS (rolbypassrls OR rolsuper,
    PG only). Even with FORCE everywhere, a BYPASSRLS/superuser connection always
    bypasses RLS — this surfaces the false-confidence window between Phase 3 (0041)
    and Phase 4 (role switch) on the admin page. Non-PostgreSQL returns False.
    """
    if not is_postgresql(db.get_bind()):
        return False
    return bool(db.execute(_BYPASS_ROLE_SQL).scalar())


def _measure_force_applied(db: Session) -> bool:
    """pg_class.relforcerowsecurity 실측 — _RLS_MATRIX 전 테이블 FORCE 여부 (PG 전용).

    비-PostgreSQL(SQLite 단위 테스트/로컬 dev)은 RLS 미지원이므로 False 고정.
    PostgreSQL 은 alembic 0041 적용 여부를 카탈로그에서 직접 읽는다 — 정적 선언 대신
    실측이므로 마이그레이션 미적용 운영 DB 에서 거짓 안심(false confidence)이 없다.

    Live-check pg_class.relforcerowsecurity for every _RLS_MATRIX table (PG only).
    Non-PostgreSQL (SQLite unit tests / local dev) has no RLS, so always False.
    Reads the catalog directly instead of a static flag — no false confidence on an
    operational DB where alembic 0041 has not run yet.
    """
    if not is_postgresql(db.get_bind()):
        return False
    forced = db.execute(
        _FORCE_COUNT_SQL, {"tbl_list": [m["table"] for m in _RLS_MATRIX]}
    ).scalar()
    return int(forced or 0) == len(_RLS_MATRIX)


def rls_coverage_summary(db: Session | None = None) -> dict[str, int | bool]:
    """RLS 적용 vs 미적용 카운트 요약 + FORCE 실측 플래그.
    RLS applied vs missing summary, plus a live FORCE-status flag.

    force_applied (RLS Phase 3, alembic 0041): db 전달 + PostgreSQL 이면
    pg_class.relforcerowsecurity 실측 — _RLS_MATRIX 11 테이블 전부 FORCE 일 때만 True.
    db 미전달 또는 비-PG 는 False (하위 호환 + SQLite 단위 테스트 안전).
    connection_bypasses_rls: 접속 role 의 rolbypassrls OR rolsuper 실측 — True 면
    FORCE 가 전부 적용돼도 2차 안전망이 미실효 (Phase 3~4 사이 거짓 안심 창 가시화).
    🔴 FORCE 는 owner-bypass 만 막는다 — 실효는 비-BYPASSRLS 앱 role 전환(Phase 4)과
    페어 (docs/runbooks/rls-role-separation.md).
    force_applied (RLS Phase 3, alembic 0041): with a db on PostgreSQL this live-checks
    pg_class.relforcerowsecurity — True only when all 11 _RLS_MATRIX tables are FORCEd.
    Without a db, or on non-PG, it stays False (backward compatible + SQLite-safe).
    connection_bypasses_rls: live rolbypassrls OR rolsuper of the connection role —
    when True the 2nd safety layer stays ineffective even with FORCE everywhere
    (surfaces the Phase 3~4 false-confidence window). FORCE only blocks owner-bypass;
    the real effect pairs with the Phase 4 app-role switch.
    """
    matrix = rls_audit_matrix()
    applied = sum(1 for m in matrix if m["status"] == "applied")
    return {
        "total": len(matrix),
        "applied": applied,
        "missing": len(matrix) - applied,
        "force_applied": _measure_force_applied(db) if db is not None else False,
        "connection_bypasses_rls": (
            _measure_connection_bypasses_rls(db) if db is not None else False
        ),
    }
