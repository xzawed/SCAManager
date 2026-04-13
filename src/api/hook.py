"""Hook API — pre-push 훅 인증 및 결과 저장 엔드포인트.

X-API-Key 없이 hook_token으로 인증 (훅은 일반 개발자 터미널에서 실행됨).
"""
import hmac
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.database import SessionLocal
from src.models.analysis import Analysis
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.analyzer.ai_review import AiReviewResult
from src.scorer.calculator import calculate_score
from src.worker.pipeline import _build_result_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hook")


# ---------------------------------------------------------------------------
# GET /api/hook/verify
# ---------------------------------------------------------------------------

@router.get("/verify")
def verify_hook(repo: str, token: str):
    """pre-push 훅이 Repo 등록 여부를 확인하는 엔드포인트.

    hook_token 일치 → 200 {"status": "active"}
    불일치 또는 미등록 → 404
    """
    with SessionLocal() as db:
        config = db.query(RepoConfig).filter(
            RepoConfig.repo_full_name == repo
        ).first()

    if config is None or not hmac.compare_digest(config.hook_token or "", token):
        raise HTTPException(status_code=404, detail="등록되지 않은 리포 또는 유효하지 않은 토큰")

    return {"status": "active"}


# ---------------------------------------------------------------------------
# POST /api/hook/result
# ---------------------------------------------------------------------------

class HookResultRequest(BaseModel):
    repo: str
    token: str
    commit_sha: str
    commit_message: str = ""
    ai_result: dict[str, Any]


@router.post("/result")
def save_hook_result(body: HookResultRequest):
    """pre-push 훅이 코드리뷰 결과를 전송하는 엔드포인트.

    토큰 검증 후 Analysis 레코드를 저장하고 점수를 반환한다.
    """
    with SessionLocal() as db:
        config = db.query(RepoConfig).filter(
            RepoConfig.repo_full_name == body.repo
        ).first()

        if config is None or not hmac.compare_digest(config.hook_token or "", body.token):
            raise HTTPException(status_code=403, detail="유효하지 않은 토큰")

        repo = db.query(Repository).filter(
            Repository.full_name == body.repo
        ).first()

        if repo is None:
            raise HTTPException(status_code=404, detail="리포지토리를 찾을 수 없습니다")

        existing = db.query(Analysis).filter_by(
            commit_sha=body.commit_sha, repo_id=repo.id
        ).first()
        if existing:
            return {
                "status": "duplicate",
                "score": existing.score,
                "grade": existing.grade,
                "analysis_id": existing.id,
            }

        # ai_result → AiReviewResult 변환
        # 필수 score 필드 누락 시 status="parse_error"로 표시 (대시보드 fallback 배너 노출)
        ar = body.ai_result
        required_keys = ("commit_message_score", "direction_score", "test_score")
        ai_status = "success" if all(k in ar for k in required_keys) else "parse_error"
        ai_review = AiReviewResult(
            commit_score=int(ar.get("commit_message_score", 13)),
            ai_score=int(ar.get("direction_score", 17)),
            test_score=int(ar.get("test_score", 7)),
            summary=ar.get("summary", ""),
            suggestions=ar.get("suggestions", []),
            commit_message_feedback=ar.get("commit_message_feedback", ""),
            code_quality_feedback=ar.get("code_quality_feedback", ""),
            security_feedback=ar.get("security_feedback", ""),
            direction_feedback=ar.get("direction_feedback", ""),
            test_feedback=ar.get("test_feedback", ""),
            file_feedbacks=ar.get("file_feedbacks", []),
            status=ai_status,
        )

        # CLI 훅은 정적 분석 없음 → 빈 리스트 (code_quality=25, security=20 만점)
        score_result = calculate_score([], ai_review=ai_review)

        analysis = Analysis(
            repo_id=repo.id,
            commit_sha=body.commit_sha,
            commit_message=body.commit_message,
            pr_number=None,
            score=score_result.total,
            grade=score_result.grade,
            result=_build_result_dict(ai_review, score_result, [], "cli"),
        )

        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        logger.info("CLI hook result saved: repo=%s sha=%s score=%d",
                    body.repo, body.commit_sha, score_result.total)

        return {
            "status": "saved",
            "score": score_result.total,
            "grade": score_result.grade,
            "analysis_id": analysis.id,
        }
