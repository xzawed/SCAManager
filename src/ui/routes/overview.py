"""Overview 페이지 — `GET /` 전체 리포 현황 대시보드.
Overview page — `GET /` full repo status dashboard.

비인증 사용자에게는 랜딩 페이지를 보여준다.
Shows landing page to unauthenticated visitors.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func

from src.auth.session import CurrentUser, get_current_user
from src.database import SessionLocal
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.repositories import analysis_feedback_repo
from src.scorer.calculator import calculate_grade
from src.ui._helpers import get_locale, templates

router = APIRouter()


# 허용된 error 파라미터 값 — 미등록 값은 None 으로 치환해 임의 문자열 렌더링 방지
# Allowlisted error param values — unrecognised values replaced with None to prevent arbitrary string rendering
_ALLOWED_ERRORS = {"oauth_failed", "auth_failed"}


@router.get("/", response_class=HTMLResponse)
def overview(
    request: Request,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user)],
    error: str | None = None,
):
    """전체 리포 현황 대시보드를 렌더링한다. 미인증 시 랜딩 페이지 반환.
    Renders repo dashboard. Returns landing page for unauthenticated visitors.
    """
    if current_user is None:
        return templates.TemplateResponse(request, "landing.html", {
            "locale": get_locale(request),
            # OAuth 오류 메시지 표시용 (auth_callback 에서 /?error=<type> 전달)
            # Used to display OAuth error banner (passed from auth_callback via /?error=<type>)
            "error": error if error in _ALLOWED_ERRORS else None,
        })
    with SessionLocal() as db:
        repos = db.query(Repository).filter(
            (Repository.user_id == current_user.id) | (Repository.user_id.is_(None))
        ).order_by(Repository.created_at.desc()).all()
        # 🔴 소유자 미등록 저장소 카운트 — 이미 조회한 목록에서 세므로 추가 쿼리 0.
        # 이 저장소들은 조회는 되지만 설정 변경·삭제가 403 이다(#1062). 운영자가 403 을
        # 만나기 전에 인지하도록 배너로 표면화한다 (막지 않고 탐지 — #1060 과 같은 철학).
        # 🔴 Count unclaimed repos from the already-fetched list (zero extra queries). They are
        # readable but 403 on writes (#1062); surface them before the operator hits that 403.
        unclaimed_count = sum(1 for r in repos if r.user_id is None)
        repo_data = []
        if repos:
            repo_ids = [r.id for r in repos]

            count_map = dict(
                db.query(Analysis.repo_id, func.count(Analysis.id))  # pylint: disable=not-callable
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .all()
            )
            avg_map = dict(
                db.query(Analysis.repo_id, func.avg(Analysis.score))  # pylint: disable=not-callable
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .all()
            )

            for r in repos:
                count = count_map.get(r.id, 0)
                # 🔴 #25: avg_map 은 func.avg(Analysis.score) — SQL AVG 가 NULL(parse_error) 을 자동
                # 제외하므로 score 가 전부 NULL 인 리포는 avg=None. 반면 count 는 parse_error 를 포함한다.
                # grade 를 count(>0) 가 아닌 '실제 평균 존재(avg_raw is not None)' 기준으로 판정해야
                # parse_error-only 리포가 calculate_grade(0)=F 로 오분류되지 않는다(#25 NULL 저장 회귀 차단).
                # avg_map is func.avg (auto-excludes NULL); a parse_error-only repo yields None while count
                # still includes it. Gate the grade on an actual average, not the count, to avoid an F.
                avg_raw = avg_map.get(r.id)
                avg = round(avg_raw) if avg_raw is not None else 0
                repo_data.append({
                    "full_name": r.full_name,
                    "analysis_count": count,
                    "avg_score": avg,
                    "avg_grade": calculate_grade(avg) if avg_raw is not None else None,
                })

        # Phase E.3-d — AI 점수 정합도 지표 (전역)
        calibration = analysis_feedback_repo.get_calibration_by_score_range(db)
    return templates.TemplateResponse(request, "overview.html", {
        "repos": repo_data,
        "current_user": current_user,
        "calibration": calibration,
        "unclaimed_count": unclaimed_count,
        "locale": get_locale(request),
    })
