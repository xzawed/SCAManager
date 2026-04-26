"""Team/Multi-repo Insights REST API — 개발자별 추세, 멀티 리포 비교, 리더보드.
Team/multi-repo insights API — author trend, repo comparison, leaderboard.
"""
from fastapi import APIRouter
from src.api.auth import require_api_key
from src.database import SessionLocal
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.services import analytics_service

router = APIRouter(prefix="/api/insights", dependencies=[require_api_key])


@router.get("/authors/{login}/trend")
def get_author_trend(login: str, days: int = 30):
    """개발자별 일별 평균 점수 추세를 반환한다.
    Return the per-day average score trend for a GitHub login.
    """
    with SessionLocal() as db:
        trend = analytics_service.author_trend(db, login, days)
    return {"login": login, "days": days, "trend": trend}


@router.get("/repos/compare")
def get_repo_comparison(repos: str = "", days: int = 30):
    """멀티 리포 평균 점수를 비교하여 반환한다.
    Return average score comparison across comma-separated repo full_names.
    """
    # 빈 파라미터이면 즉시 빈 응답 반환 (불필요한 쿼리 방지)
    # Return early on empty param to avoid unnecessary queries
    if not repos or not repos.strip():
        return {"repos": [], "days": days, "comparison": []}

    full_names = [r.strip() for r in repos.split(",") if r.strip()]
    if not full_names:
        return {"repos": [], "days": days, "comparison": []}

    with SessionLocal() as db:
        # full_name → repo_id 매핑 조회
        # Resolve full_names to repo_ids via DB lookup
        repo_objs = (
            db.query(Repository)
            .filter(Repository.full_name.in_(full_names))
            .all()
        )
        id_to_name = {r.id: r.full_name for r in repo_objs}
        repo_ids = list(id_to_name.keys())
        comparison_raw = analytics_service.repo_comparison(db, repo_ids, days)

    # repo_id → full_name 으로 변환하여 응답에 포함, min/max 도 전달
    # Enrich comparison items with full_name and pass through min/max
    comparison = [
        {
            "repo_id": item["repo_id"],
            "full_name": id_to_name.get(item["repo_id"], ""),
            "avg_score": item["avg_score"],
            "count": item["count"],
            "min_score": item.get("min_score"),
            "max_score": item.get("max_score"),
        }
        for item in comparison_raw
    ]

    return {"repos": full_names, "days": days, "comparison": comparison}


@router.get("/leaderboard")
def get_leaderboard(days: int = 30):
    """옵트인 리포의 개발자별 점수 리더보드를 반환한다.
    Return per-author leaderboard for repositories that opted in.
    """
    with SessionLocal() as db:
        # leaderboard_opt_in=True 인 RepoConfig의 repo_full_name 수집 후 Repository.id 조회
        # Collect repo_full_names from opted-in RepoConfigs, then resolve to Repository.id
        opted_in_configs = (
            db.query(RepoConfig)
            .filter(RepoConfig.leaderboard_opt_in.is_(True))
            .all()
        )
        opted_in_names = [c.repo_full_name for c in opted_in_configs]
        opted_in_repos = (
            db.query(Repository)
            .filter(Repository.full_name.in_(opted_in_names))
            .all()
        ) if opted_in_names else []
        opted_in_ids = [r.id for r in opted_in_repos]

        if not opted_in_ids:
            return {"days": days, "leaderboard": []}

        lb = analytics_service.leaderboard(db, days, opted_in_ids)

    return {"days": days, "leaderboard": lb}
