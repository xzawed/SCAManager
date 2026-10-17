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
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.repositories import analysis_feedback_repo
from src.scorer.calculator import calculate_grade
from src.shared.feature_kill_switch import is_disabled
from src.ui._helpers import get_locale, templates

router = APIRouter()


# 허용된 error 파라미터 값 — 미등록 값은 None 으로 치환해 임의 문자열 렌더링 방지
# Allowlisted error param values — unrecognised values replaced with None to prevent arbitrary string rendering
_ALLOWED_ERRORS = {"oauth_failed", "auth_failed"}


def recorded_score_summary(db, repo_ids: list[int]) -> dict[int, tuple[float, int]]:
    """리포별 (기록된 점수 평균, 그중 미검증 행 수) — 점수가 NULL 인 분석만 빠진다.

    🔴 첫 화면 평균은 검증 여부와 상관없이 **점수가 저장된 분석 전부**다(사용자 결정
    2026-10-17). 미검증(`score_unreliable`)은 평균에서 빼지 않고 개수만 세어 카드에
    «미검증 포함» 으로 알린다. 점수가 NULL 인 것은 진짜 AI 실패뿐이다
    (`src/scorer/reliability.py::def should_null_persist_score`).

    `result` 블롭은 읽지 않는다 — 미검증 판정은 쓰기 시점에 채운 캐시 컬럼이다(0046).
    🔴 행은 `count(*)` 로 센다 — 이 집계가 읽는 열이 전부 `ix_analyses_repo_scores`(0048) 안에
    있어야 PostgreSQL 이 인덱스만으로 답한다. `count(Analysis.id)` 는 id 가 인덱스 밖이라 힙을
    통째로 읽는다(운영 2026-10-17: 버퍼 1,185 · 5.8 ms). 가드 =
    `tests/unit/ui/test_overview_payload_bounded.py` · PG 계획은 `tests/integration/`.

    Per repo: (average of every stored score, how many of those rows are unverified).
    Unverified rows stay in the average; the card only marks them. Rows are counted with count(*)
    so the aggregate is answered from the index alone.
    """
    rows = (
        db.query(
            Analysis.repo_id,
            func.avg(Analysis.score),
            func.count().filter(  # pylint: disable=not-callable
                Analysis.score_unreliable.is_(True)),
        )
        .filter(Analysis.repo_id.in_(repo_ids), Analysis.score.isnot(None))
        .group_by(Analysis.repo_id)
        .all()
    )
    return {repo_id: (avg, unverified) for repo_id, avg, unverified in rows}


def _ai_review_off(db, names: list[str]) -> set[str]:
    """`names` 중 AI 리뷰가 지금 꺼진 리포 — 비어 있으면 조회하지 않는다.

    기준은 파이프라인이 AI 를 끄는 두 스위치(리포 토글 `ai_review_enabled=False` · 전역
    `AI_REVIEW_DISABLED`)와 같다. 설정 행이 없는 리포는 기본값(켜짐)이다.
    Repos among `names` whose AI review is off now, by the pipeline's two switches.
    """
    if not names:
        return set()
    if is_disabled("AI_REVIEW"):
        return set(names)
    return {name for (name,) in
            db.query(RepoConfig.repo_full_name)
            .filter(RepoConfig.repo_full_name.in_(names),
                    RepoConfig.ai_review_enabled.is_(False))
            .all()}


def _repo_cards(db, repos) -> list[dict]:
    """리포 카드 데이터 — 분석 수 · 기록된 점수 평균과 등급 · «미검증 포함» · «AI 리뷰 꺼짐».

    Card data per repo: analysis count, recorded average and grade, and the two markers.
    """
    repo_ids = [r.id for r in repos]
    # 분석 수도 `count(*)` — repo_id 를 앞에 둔 인덱스만으로 센다(`recorded_score_summary` 참조).
    # Count with count(*) so a repo_id-leading index answers it without touching the heap.
    count_map = dict(
        db.query(Analysis.repo_id, func.count())  # pylint: disable=not-callable
        .filter(Analysis.repo_id.in_(repo_ids))
        .group_by(Analysis.repo_id)
        .all()
    )
    # 🔴 평균 = 기록된 점수 전부(검증 여부 무관) — `recorded_score_summary` 참조.
    # Average = every stored score, verified or not.
    summary = recorded_score_summary(db, repo_ids)
    # 미검증 점수가 섞인 리포는 AI 리뷰가 지금 꺼져 있는지도 카드에 적는다.
    # Repos with unverified rows also say whether AI review is off now.
    ai_off = _ai_review_off(db, [r.full_name for r in repos if summary.get(r.id, (None, 0))[1]])

    cards = []
    for r in repos:
        # 🔴 #25: 점수가 전부 NULL(진짜 AI 실패)인 리포는 summary 에 없다 — count 는 그 분석도
        #    센다. 등급은 count(>0) 가 아니라 «실제 평균이 있는가» 로 판정해야 F 로 오분류되지 않는다.
        # A repo whose scores are all NULL is absent from the summary while count still includes
        # it; gate the grade on an actual average, not the count, to avoid an F.
        avg_raw, unverified = summary.get(r.id, (None, 0))
        # 🔴 평균이 없으면 0 이 아니라 None 이다 — 템플릿이 0 을 «없음» 으로 읽지 않게.
        # No average is None, not 0: the template must not read 0 as «missing».
        avg = round(avg_raw) if avg_raw is not None else None
        cards.append({
            "full_name": r.full_name,
            "analysis_count": count_map.get(r.id, 0),
            "avg_score": avg,
            "avg_grade": calculate_grade(avg) if avg is not None else None,
            "includes_unverified": bool(unverified),
            "ai_review_off": r.full_name in ai_off,
        })
    return cards


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
        repo_data = _repo_cards(db, repos) if repos else []

        # Phase E.3-d — AI 점수 정합도 지표 (전역)
        calibration = analysis_feedback_repo.get_calibration_by_score_range(db)
    return templates.TemplateResponse(request, "overview.html", {
        "repos": repo_data,
        "current_user": current_user,
        "calibration": calibration,
        "unclaimed_count": unclaimed_count,
        "locale": get_locale(request),
    })
