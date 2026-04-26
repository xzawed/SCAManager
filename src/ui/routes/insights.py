"""Team/Multi-repo Insights UI 라우트 — 멀티 리포 비교 및 개인 추세 대시보드.
Team/multi-repo insights UI routes — multi-repo comparison and personal trend dashboard.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.auth.session import CurrentUser, require_login
from src.database import SessionLocal
from src.models.repository import Repository
from src.scorer.calculator import calculate_grade
from src.services import analytics_service
from src.ui._helpers import templates

router = APIRouter()


def _compute_kpi(trend: list[dict[str, Any]]) -> dict[str, Any]:
    """추세 데이터에서 KPI (평균·등급·델타) 를 계산한다.
    Compute KPI (avg, grade, delta) from trend data.

    delta는 앞 절반과 뒷 절반의 평균 차이 — 양수면 개선, 음수면 하락.
    delta is the difference between the second and first halves of the period.
    """
    if not trend:
        return {"avg": None, "grade": None, "delta": None, "count": 0}

    scores = [item["avg_score"] for item in trend]
    avg = round(sum(scores) / len(scores), 1)
    grade = calculate_grade(int(avg))

    # delta: 뒷 절반 평균 - 앞 절반 평균 (최소 2개 데이터 필요)
    # delta: second-half avg minus first-half avg (need at least 2 data points)
    delta: float | None = None
    if len(scores) >= 2:
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        delta = round(
            sum(second_half) / len(second_half) - sum(first_half) / len(first_half),
            1,
        )

    total_count = sum(item["count"] for item in trend)
    return {"avg": avg, "grade": grade, "delta": delta, "count": total_count}


@router.get("/insights", response_class=HTMLResponse)
def insights_comparison(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    repos: str = "",
    days: int = 30,
):
    """멀티 리포 평균 점수 비교 페이지.
    Multi-repo average score comparison page.
    """
    full_names = [r.strip() for r in repos.split(",") if r.strip()] if repos else []

    with SessionLocal() as db:
        # 사용자 접근 가능한 모든 리포 목록 (리포 셀렉터 용도)
        # All accessible repos for the repo selector
        all_repos = (
            db.query(Repository)
            .filter(
                (Repository.user_id == current_user.id) | (Repository.user_id.is_(None))
            )
            .order_by(Repository.full_name.asc())
            .all()
        )

        # 선택된 리포의 full_name → repo_id 매핑
        # Resolve selected full_names to repo_ids
        comparison: list[dict] = []
        if full_names:
            selected_repos = (
                db.query(Repository)
                .filter(Repository.full_name.in_(full_names))
                .all()
            )
            id_to_name = {r.id: r.full_name for r in selected_repos}
            repo_ids = list(id_to_name.keys())
            raw = analytics_service.repo_comparison(db, repo_ids, days)
            comparison = [
                {
                    "repo_id": item["repo_id"],
                    "full_name": id_to_name.get(item["repo_id"], ""),
                    "avg_score": item["avg_score"],
                    "count": item["count"],
                    "min_score": item.get("min_score"),
                    "max_score": item.get("max_score"),
                }
                for item in raw
            ]

        # 옵트인 리포의 리더보드 — leaderboard_opt_in=True 리포 ID 수집
        # Leaderboard for opted-in repos — collect repo IDs with leaderboard_opt_in=True
        opted_in_repos = (
            db.query(Repository)
            .filter(
                (Repository.user_id == current_user.id) | (Repository.user_id.is_(None))
            )
            .all()
        )
        # repo_config 에서 opt-in 여부 확인 — 설정이 없으면 False (기본 비활성)
        # Check opt-in via repo_config — default False if no config
        opted_in_ids = [
            r.id for r in opted_in_repos
            if r.config and getattr(r.config, "leaderboard_opt_in", False)
        ]
        lb = analytics_service.leaderboard(db, days=days, opted_in_repo_ids=opted_in_ids)

    return templates.TemplateResponse(
        request,
        "insights.html",
        {
            "current_user": current_user,
            "comparison": comparison,
            "repos": full_names,
            "days": days,
            "all_repos": all_repos,
            "leaderboard": lb,
        },
    )


@router.get("/insights/me", response_class=HTMLResponse)
def insights_me(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    days: int = 30,
):
    """개인 개발자 점수 추세 페이지.
    Personal developer score trend page.
    """
    with SessionLocal() as db:
        trend = analytics_service.author_trend(db, current_user.github_login, days)

        # top_issues: 사용자가 기여한 리포들을 대상으로 집계
        # top_issues: aggregate across repos where the user has contributions
        user_repos = (
            db.query(Repository)
            .filter(Repository.user_id == current_user.id)
            .all()
        )
        # 리포별 top_issues를 모두 합산하여 상위 5개 추출
        # Merge top_issues across all user repos and return top 5
        issue_counter: dict[str, int] = {}
        for repo in user_repos:
            for issue in analytics_service.top_issues(db, repo.id, days=days, n=20):
                key = issue["message"]
                issue_counter[key] = issue_counter.get(key, 0) + issue["count"]
        top = sorted(issue_counter.items(), key=lambda x: x[1], reverse=True)
        top_issues_merged = [{"message": msg, "count": cnt} for msg, cnt in top[:5]]

    kpi = _compute_kpi(trend)

    return templates.TemplateResponse(
        request,
        "insights_me.html",
        {
            "current_user": current_user,
            "trend": trend,
            "days": days,
            "top_issues": top_issues_merged,
            "kpi": kpi,
        },
    )
