"""리포 분석 이력 + 분석 상세 페이지 — catch-all `/repos/{name}` 는 마지막에 include."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser, require_login
from src.constants import CLAUDE_MODEL_PRICING, CLAUDE_PRICING_FALLBACK
from src.database import SessionLocal
from src.models.analysis import Analysis
from src.repositories import analysis_feedback_repo
from src.ui._helpers import get_accessible_repo, get_locale, templates

router = APIRouter()


def _calc_monthly_cost(rows: list) -> float:
    """분석 행 목록에서 Anthropic API 예상 비용(USD)을 계산한다.

    Calculate estimated Anthropic API cost (USD) from a list of analysis rows.
    입력: (review_model, input_tokens, output_tokens) 튜플 목록
    Input: list of (review_model, input_tokens, output_tokens) tuples.
    """
    total = 0.0
    for row in rows:
        pricing = CLAUDE_MODEL_PRICING.get(row.review_model or "", CLAUDE_PRICING_FALLBACK)
        inp = (row.input_tokens or 0) / 1_000_000
        out = (row.output_tokens or 0) / 1_000_000
        total += inp * pricing["input"] + out * pricing["output"]
    return round(total, 4)


class FeedbackRequest(BaseModel):
    """Phase E.3 — 피드백 upsert 본문.

    comment 최대 길이 2000자 — DB 행 크기 폭주/거대 payload 방어.
    """
    thumbs: Literal[1, -1] = Field(..., description="+1=up, -1=down")
    comment: str | None = Field(default=None, max_length=2000)


def _serialize_feedback(fb: object | None) -> dict:
    """Feedback ORM → JSON 직렬화 헬퍼."""
    if fb is None:
        return {"thumbs": None, "comment": None, "updated_at": None}
    updated_at = getattr(fb, "updated_at", None)
    return {
        "thumbs": getattr(fb, "thumbs", None),
        "comment": getattr(fb, "comment", None),
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _load_analysis_or_404(db: Session, repo_id: int, analysis_id: int) -> Analysis:
    """repo_id + analysis_id 로 Analysis 조회, 없으면 404 (3 라우트 공통 — S1192 중복 가드 추출).

    Load an Analysis by repo_id + analysis_id, or raise 404 (shared by 3 routes).
    """
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id, Analysis.repo_id == repo_id,
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.get("/repos/{repo_name:path}/analyses/{analysis_id}", response_class=HTMLResponse)
def analysis_detail(
    request: Request, repo_name: str, analysis_id: int,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """분석 상세 페이지(AI 리뷰·점수·피드백)를 렌더링한다."""
    with SessionLocal() as db:
        repo = get_accessible_repo(db, repo_name, current_user)
        analysis = _load_analysis_or_404(db, repo.id, analysis_id)
        result = analysis.result or {}
        source = result.get("source") or ("pr" if analysis.pr_number else "push")
        data = {
            "id": analysis.id,
            "commit_sha": analysis.commit_sha,
            "commit_message": analysis.commit_message,
            "pr_number": analysis.pr_number,
            "score": analysis.score,
            "grade": analysis.grade,
            "result": result,
            "source": source,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }
        siblings = (db.query(Analysis.id, Analysis.score, Analysis.created_at)
                    .filter(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.desc()).limit(30).all())
        trend_data = [
            {"id": s.id, "score": s.score,
             "label": s.created_at.strftime("%m/%d") if s.created_at else ""}
            for s in reversed(siblings)
        ]
        prev_id = (db.query(Analysis.id)
                   .filter(Analysis.repo_id == repo.id, Analysis.id < analysis_id)
                   .order_by(Analysis.id.desc()).limit(1).scalar())
        next_id = (db.query(Analysis.id)
                   .filter(Analysis.repo_id == repo.id, Analysis.id > analysis_id)
                   .order_by(Analysis.id.asc()).limit(1).scalar())
        user_feedback = analysis_feedback_repo.find_by_analysis_and_user(
            db, analysis_id=analysis_id, user_id=current_user.id,
        )
    return templates.TemplateResponse(request, "analysis_detail.html", {
        "repo_name": repo_name, "analysis": data, "current_user": current_user,
        "trend_data": trend_data, "prev_id": prev_id, "next_id": next_id,
        "user_feedback": _serialize_feedback(user_feedback),
        "locale": get_locale(request),
    })


@router.post("/repos/{repo_name:path}/analyses/{analysis_id}/feedback")
def post_analysis_feedback(
    request: Request,
    repo_name: str,
    analysis_id: int,
    body: FeedbackRequest,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """분석에 thumbs up/down 피드백을 upsert — Phase E.3."""
    with SessionLocal() as db:
        repo = get_accessible_repo(
            db, repo_name, current_user, require_write=True, locale=get_locale(request),
        )
        _load_analysis_or_404(db, repo.id, analysis_id)
        fb = analysis_feedback_repo.upsert_feedback(
            db,
            analysis_id=analysis_id,
            user_id=current_user.id,
            thumbs=body.thumbs,
            comment=body.comment,
        )
    return _serialize_feedback(fb)


@router.get("/repos/{repo_name:path}/analyses/{analysis_id}/feedback")
def get_analysis_feedback(
    repo_name: str,
    analysis_id: int,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """현재 사용자의 분석 피드백 조회 — UI 상태 복원용."""
    with SessionLocal() as db:
        repo = get_accessible_repo(db, repo_name, current_user)
        _load_analysis_or_404(db, repo.id, analysis_id)
        fb = analysis_feedback_repo.find_by_analysis_and_user(
            db, analysis_id=analysis_id, user_id=current_user.id,
        )
    return _serialize_feedback(fb)


@router.get("/repos/{repo_name:path}", response_class=HTMLResponse)
def repo_detail(  # pylint: disable=too-many-positional-arguments
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    hook_installed: int = 0,
):
    """리포 분석 이력 및 점수 차트 페이지를 렌더링한다."""
    with SessionLocal() as db:
        repo = get_accessible_repo(db, repo_name, current_user)
        analyses = (db.query(Analysis).filter(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.desc()).limit(100).all())
        analyses_data = [
            {"id": a.id, "commit_sha": a.commit_sha, "pr_number": a.pr_number,
             "commit_message": a.commit_message,
             "score": a.score, "grade": a.grade,
             "source": (a.result or {}).get("source") or ("pr" if a.pr_number else "push"),
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in analyses
        ]
        rev = list(reversed(analyses_data))

        # 이번 달 비용 계산 (매월 1일 00:00 UTC ~ 말일 23:59 UTC 기준)
        # Monthly cost calculation (1st 00:00 UTC to last day of month)
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_analyses = (
            db.query(Analysis.review_model, Analysis.input_tokens, Analysis.output_tokens)
            .filter(
                Analysis.repo_id == repo.id,
                Analysis.created_at >= month_start,
                Analysis.input_tokens.isnot(None),
            )
            .all()
        )
        monthly_cost_usd = _calc_monthly_cost(monthly_analyses)
        monthly_token_count = sum(
            (row.input_tokens or 0) + (row.output_tokens or 0)
            for row in monthly_analyses
        )

    return templates.TemplateResponse(request, "repo_detail.html", {
        "repo_name": repo_name, "repo_id": repo.id, "analyses": analyses_data,
        "chart_labels": [a["created_at"][:10] if a["created_at"] else "" for a in rev],
        "chart_scores": [a["score"] for a in rev],
        "hook_installed": bool(hook_installed),
        "current_user": current_user,
        "locale": get_locale(request),
        "monthly_cost_usd": monthly_cost_usd,
        "monthly_token_count": monthly_token_count,
        "monthly_cost_month": now.strftime("%Y-%m"),
    })
