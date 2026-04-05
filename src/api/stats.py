from fastapi import APIRouter, HTTPException
from src.api.auth import require_api_key
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis

router = APIRouter(prefix="/api", dependencies=[require_api_key])


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: int):
    with SessionLocal() as db:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return {
            "id": analysis.id, "commit_sha": analysis.commit_sha,
            "pr_number": analysis.pr_number, "score": analysis.score,
            "grade": analysis.grade, "result": analysis.result,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }


@router.get("/repos/{repo_name:path}/stats")
def get_repo_stats(repo_name: str, limit: int = 30):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
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
