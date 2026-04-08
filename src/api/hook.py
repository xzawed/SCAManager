"""Hook API — pre-push 훅 인증 및 결과 저장 엔드포인트.

X-API-Key 없이 hook_token으로 인증 (훅은 일반 개발자 터미널에서 실행됨).
"""
import json
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

    if config is None or config.hook_token != token:
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

        if config is None or config.hook_token != body.token:
            raise HTTPException(status_code=403, detail="유효하지 않은 토큰")

        repo = db.query(Repository).filter(
            Repository.full_name == body.repo
        ).first()

        if repo is None:
            raise HTTPException(status_code=404, detail="리포지토리를 찾을 수 없습니다")

        # ai_result → AiReviewResult 변환
        ar = body.ai_result
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
            result=json.dumps({
                "breakdown": score_result.breakdown,
                "ai_summary": ai_review.summary,
                "ai_suggestions": ai_review.suggestions,
                "commit_message_feedback": ai_review.commit_message_feedback,
                "code_quality_feedback": ai_review.code_quality_feedback,
                "security_feedback": ai_review.security_feedback,
                "direction_feedback": ai_review.direction_feedback,
                "test_feedback": ai_review.test_feedback,
                "file_feedbacks": ai_review.file_feedbacks,
                "issues": [],
                "source": "cli",
            }, ensure_ascii=False),
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
