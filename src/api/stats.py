"""Statistics API — analysis detail and per-repo score statistics endpoints."""
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Request
from src.api.auth import require_api_key
from src.api.deps import get_repo_or_404
# require_api_key 시스템 엔드포인트 — 세션 없는 cross-tenant 조회 → Phase 4 RLS 우회용 worker 세션.
# 미설정 시 WorkerSessionLocal is SessionLocal (현행 동일). 상세: src/api/repos.py 주석.
# Global-API-key system endpoint — sessionless cross-tenant reads → worker (BYPASSRLS) session for
# Phase 4. Unset → WorkerSessionLocal is SessionLocal (unchanged). See src/api/repos.py for detail.
from src.database import WorkerSessionLocal as SessionLocal
from src.middleware.rate_limiter import limiter, RATE_LIMIT_API
from src.models.analysis import Analysis

router = APIRouter(prefix="/api", dependencies=[require_api_key])


@router.get("/analyses/{analysis_id}")
@limiter.limit(RATE_LIMIT_API)
def get_analysis(request: Request, analysis_id: int):  # pylint: disable=unused-argument
    """단일 분석 상세 정보를 반환한다."""
    with SessionLocal() as db:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return {
            "id": analysis.id, "commit_sha": analysis.commit_sha,
            "commit_message": analysis.commit_message,
            "pr_number": analysis.pr_number, "score": analysis.score,
            "grade": analysis.grade, "result": analysis.result,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }


@router.get("/repos/{repo_name:path}/stats")
@limiter.limit(RATE_LIMIT_API)
def get_repo_stats(
    request: Request,
    repo_name: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
):  # pylint: disable=unused-argument
    """리포지토리 점수 통계(평균·트렌드)를 반환한다."""
    with SessionLocal() as db:
        repo = get_repo_or_404(repo_name, db)
        analyses = (
            db.query(Analysis).filter(Analysis.repo_id == repo.id)
            .order_by(Analysis.created_at.asc()).limit(limit).all()
        )
        if not analyses:
            return {"total_analyses": 0, "average_score": 0, "trend": []}
        scores = [a.score for a in analyses if a.score is not None]
        average = sum(scores) / len(scores) if scores else 0
        return {
            "total_analyses": len(analyses),
            "average_score": round(average, 1),
            "trend": [
                {"date": a.created_at.isoformat() if a.created_at else None,
                 "score": a.score, "grade": a.grade}
                for a in analyses
            ],
        }
