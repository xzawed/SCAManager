"""Repo별 분석 레포트 JSON API.
Per-repository analysis report JSON API endpoints.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query, Request
from src.middleware.rate_limiter import limiter, RATE_LIMIT_API

from src.api.auth import require_api_key
from src.api.deps import get_repo_or_404
# require_api_key 시스템 엔드포인트 — 세션 없는 cross-tenant 조회 → Phase 4 RLS 우회용 worker 세션.
# 미설정 시 WorkerSessionLocal is SessionLocal (현행 동일). 상세: src/api/repos.py 주석.
# Global-API-key system endpoint — sessionless cross-tenant reads → worker (BYPASSRLS) session for
# Phase 4. Unset → WorkerSessionLocal is SessionLocal (unchanged). See src/api/repos.py for detail.
from src.database import WorkerSessionLocal as SessionLocal
from src.repositories import repository_repo
from src.services.repo_insight_service import (
    repo_ai_suggestions,
    repo_category_breakdown,
    repo_kpi,
    repo_recurring_issues,
    repo_score_trend,
)

router = APIRouter(prefix="/api", dependencies=[require_api_key])

# 경고 등급 기준 — D 이하 또는 보안 HIGH 1건 이상
# Warning threshold — grade D/F or any HIGH security issue
_WARNING_GRADES = {"D", "F"}


@router.get("/repos/report")
@limiter.limit(RATE_LIMIT_API)
def list_repos_report(
    request: Request,  # pylint: disable=unused-argument
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """연결된 전체 Repo 요약 반환 (KPI + 등급 + 경고 여부).

    Returns summary for all repos: KPI, grade, warning flag.
    """
    with SessionLocal() as db:
        repos = repository_repo.find_all(db)
        now = datetime.now(timezone.utc)

        repo_rows = []
        grade_dist: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        total_scores: list[float] = []

        # repo당 최대 2 쿼리 (현재+이전 윈도우) — 규모 확장 시 batch로 최적화 고려
        # Up to 2 queries per repo (current + prev window) — consider batching at scale
        for repo in repos:
            kpi = repo_kpi(db, repo.id, days, now=now)
            grade = kpi["grade"]
            warning = (
                grade in _WARNING_GRADES or kpi["high_security_count"] > 0
            )
            if grade in grade_dist:
                grade_dist[grade] += 1

            if kpi["avg_score"] is not None:
                total_scores.append(kpi["avg_score"])

            repo_rows.append(
                {
                    "repo_id": repo.id,
                    "full_name": repo.full_name,
                    "avg_score": kpi["avg_score"],
                    "grade": grade,
                    "score_delta": kpi["score_delta"],
                    "analysis_count": kpi["analysis_count"],
                    "warning": warning,
                    "days": days,
                }
            )

        global_avg = (
            round(sum(total_scores) / len(total_scores), 1)
            if total_scores
            else None
        )
        warning_count = sum(1 for r in repo_rows if r["warning"])

        return {
            "repos": repo_rows,
            "summary": {
                "total_repos": len(repos),
                "avg_score": global_avg,
                "grade_distribution": grade_dist,
                "warning_count": warning_count,
            },
            "generated_at": now.isoformat(),
        }


@router.get("/repos/{repo_name:path}/report")
@limiter.limit(RATE_LIMIT_API)
def get_repo_report(
    request: Request,  # pylint: disable=unused-argument
    repo_name: str,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """개별 Repo 상세 분석 레포트 반환.

    Returns detailed analysis report for a single repo.
    """
    with SessionLocal() as db:
        repo = get_repo_or_404(repo_name, db)
        # API key auth는 전역 — user_id 필터 없음 (기존 /api/repos 패턴 동일)
        # API key auth is global — no user_id filter (matches existing /api/repos pattern)

        now = datetime.now(timezone.utc)

        return {
            "repo_full_name": repo.full_name,
            "days": days,
            "kpi": repo_kpi(db, repo.id, days, now=now),
            "recurring_issues": repo_recurring_issues(db, repo.id, days, now=now),
            "category_breakdown": repo_category_breakdown(db, repo.id, days, now=now),
            "ai_suggestions": repo_ai_suggestions(db, repo.id, days, now=now),
            "score_trend": repo_score_trend(db, repo.id, days, now=now),
            "generated_at": now.isoformat(),
        }
