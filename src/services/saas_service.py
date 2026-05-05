"""saas_service — SaaS Phase 1 MVP read-only 집계 (Cycle 79 PR 3a 신설).

5+1 cross-verify (Cycle 78 NEW-P0-1) 결과 = 영역 🅐 SaaS 멀티 테넌트 진입 의무.

Phase 1 = read-only (자동 처리 X — 사용자 1-click confirm 의무).
Phase 1 = read-only (no auto action — user 1-click confirm required).

함수:
- tenant_inventory(db) — 사용자별 (id, github_login, email, repo_count, analysis_count, last_active_at)
- rls_audit_matrix() — 정적 RLS policy 적용 매트릭스 (alembic 0026 + 0027 + 0028 + 0029 영역)

Phase 2 영역 (본 PR X): 결제 / 사용량 cap / API key per-tenant — 별도 PR 진입 의무 (High tier).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User


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


# RLS policy 적용 매트릭스 — alembic 0026/0027/0028/0029 누적 결과
# RLS policy matrix — cumulative result of alembic 0026/0027/0028/0029
# 각 항목 = (table, isolation_pattern, since_alembic, status)
_RLS_MATRIX: tuple[dict[str, str], ...] = (
    {"table": "repositories", "pattern": "user_id 직접 (legacy NULL 호환)", "since": "0026", "status": "applied"},
    {"table": "analyses", "pattern": "repo_id 간접 (repositories 페어)", "since": "0026", "status": "applied"},
    {"table": "merge_attempts", "pattern": "repo_name 간접 (repositories.full_name 페어)", "since": "0026", "status": "applied"},
    {"table": "security_alert_process_logs", "pattern": "repo_id 간접 (analyses 패턴)", "since": "0027", "status": "applied"},
    {"table": "insight_narrative_cache", "pattern": "user_id 직접 (NULL 허용 X)", "since": "0028", "status": "applied"},
    {"table": "users", "pattern": "self-RLS (id 직접 비교)", "since": "0029", "status": "applied"},
    {"table": "repo_configs", "pattern": "repo_full_name 간접 (repositories 페어)", "since": "0029", "status": "applied"},
    {"table": "gate_decisions", "pattern": "analysis_id 간접 2-hop (analyses → repositories)", "since": "0029", "status": "applied"},
    {"table": "merge_retry_queue", "pattern": "repo_full_name 간접 (repositories 페어)", "since": "0029", "status": "applied"},
    {"table": "analysis_feedbacks", "pattern": "user_id 직접 (NULL 허용 X — FK NOT NULL)", "since": "0029", "status": "applied"},
)


def rls_audit_matrix() -> list[dict[str, str]]:
    """RLS policy 적용 매트릭스 (정적 — 운영 SQL injection 회피).

    RLS policy matrix (static — avoids runtime SQL injection risk).
    """
    return list(_RLS_MATRIX)


def rls_coverage_summary() -> dict[str, int]:
    """RLS 적용 vs 미적용 카운트 요약.

    RLS applied vs missing summary.
    """
    matrix = rls_audit_matrix()
    applied = sum(1 for m in matrix if m["status"] == "applied")
    return {
        "total": len(matrix),
        "applied": applied,
        "missing": len(matrix) - applied,
    }
