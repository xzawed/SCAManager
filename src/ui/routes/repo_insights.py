"""리포별 코드 인사이트 라우트 — GET /repos/{name}/insights.

Repository code insights route — GET /repos/{name}/insights.
"""
from __future__ import annotations

import logging
from typing import Annotated, Generator
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from src import constants
from src.auth.session import CurrentUser, require_login
from src.config import settings
from src.database import SessionLocal
from src.i18n.loader import get_text
from src.models.repository import Repository
from src.services.repo_insight_service import (
    invalidate_repo_insight_narrative,
    issue_basis,
    repo_ai_suggestions,
    repo_category_breakdown,
    repo_insight_narrative,
    repo_kpi,
    repo_problem_files,
    repo_recurring_issues,
)
from src.services import insight_cost_guard
from src.shared.log_safety import sanitize_for_log
from src.ui._helpers import get_locale, redirect_without_refresh, templates

logger = logging.getLogger(__name__)

router = APIRouter()

# 서술이 실패가 아닌 상태 — 이 밖의 status(모르는 값 포함)는 실패로 보고 새로 고침을 건다.
#   실패를 목록으로 적으면 새 실패 status 가 조용히 빠진다. 대시보드 템플릿의 else 분기와 같은 방향.
# Non-failure states; any other status (unknown included) is a failure with Refresh. Listing the
#   failures instead would silently drop a new failure status (same direction as the dashboard's else).
_NARRATIVE_NOT_FAILED = frozenset({"success", "no_data", "disabled", "no_api_key"})

# 서술 자리 조각 — 페이지(캐시 적중)와 조각 경로가 같은 파일을 그린다.
# The narrative slot fragment, drawn by both the page (cache hit) and the fragment route.
_NARRATIVE_FRAGMENT_TEMPLATE = "_repo_insight_narrative.html"


def _get_db() -> Generator[Session, None, None]:
    """DB 세션 의존성 — 테스트에서 override 가능.

    DB session dependency — overrideable in tests.
    """
    with SessionLocal() as db:
        yield db


def _find_repo(db: Session, repo_name: str, user_id: int):
    """사용자 접근 가능한 리포 조회 — 없거나 권한 없으면 None.

    Find user-accessible repo — returns None if not found or unauthorized.
    """
    repo = db.scalar(
        select(Repository).where(Repository.full_name == repo_name)
    )
    if repo is None:
        return None
    if repo.user_id is not None and repo.user_id != user_id:
        return None
    return repo


def _load_page_aggregates(db: Session, repo_id: int, days: int) -> tuple:
    """페이지의 다섯 집계 — 동기 DB 라 워커 스레드에서 부른다.
    The page's five aggregates; sync DB work, called from a worker thread.
    """
    return (
        repo_kpi(db, repo_id, days),
        repo_recurring_issues(db, repo_id, days),
        repo_problem_files(db, repo_id, days),
        repo_ai_suggestions(db, repo_id, days),
        repo_category_breakdown(db, repo_id, days),
    )


def _load_template_attributes(repo: Repository) -> None:
    """템플릿이 읽는 컬럼을 채운다 — 만료된 객체면 여기서 한 번 SELECT, 아니면 DB 를 건드리지 않는다.
    Load the columns the template reads: one SELECT if the object was expired, otherwise no DB access.
    """
    _ = (repo.full_name, repo.user_id)


def _load_narrative_inputs(db: Session, repo_id: int, days: int) -> tuple:
    """서술 프롬프트가 읽는 두 집계 — 조각 경로용(워커 스레드에서).
    The two aggregates the narrative prompt reads, for the fragment route (worker thread).
    """
    return repo_kpi(db, repo_id, days), repo_recurring_issues(db, repo_id, days)


def _narrative_view(narrative: dict | None) -> dict:
    """서술 결과 → 템플릿 변수(`narrative` · `narrative_failed` · `narrative_limited`).

    실패(벤더·우리 코드)면 실패 줄 + 새로 고침 — 부정 캐시를 사용자가 넘는 길. 하루 상한에 닿았고 마지막 결과도
    없으면 «오늘 한도» 줄 — 실패가 아니라 새로 고침도 그리지 않는다.
    Failure → failure line with Refresh; daily cap with no earlier result → a limit line, not a failure.
    """
    failed = bool(narrative) and narrative.get("status") not in _NARRATIVE_NOT_FAILED
    limited = bool(narrative) and narrative.get("status") == "daily_limit"
    return {
        "narrative": narrative if narrative and narrative.get("status") == "success" else None,
        "narrative_failed": failed and not limited,
        "narrative_limited": limited,
    }


@router.get("/repos/{repo_name:path}/insights", response_class=HTMLResponse)
async def repo_insights(  # pylint: disable=too-many-positional-arguments
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    db: Annotated[Session, Depends(_get_db)],
    days: int = Query(default=30, ge=1, le=365),
    refresh: int = 0,
) -> Response:
    """리포별 코드 인사이트 페이지.

    Per-repository code insights page.
    """
    # 기간은 화면 값으로 — 페이지의 수치와 서술이 같은 기간을 말해야 한다(회고 원장 L17 P2-7).
    # On-screen windows only, so the figures and the narrative share the window.
    days = insight_cost_guard.snap_days(days, constants.INSIGHT_DAYS_REPO)
    logger.info(
        "repo_insights user_id=%d repo=%s days=%s",
        current_user.id,
        sanitize_for_log(repo_name),
        sanitize_for_log(str(days), max_len=5),
    )

    # 🔴 이 페이지의 동기 DB(조회·집계·무효화)는 전부 워커 스레드에서 — 루프에서 돌면 운영 왕복(DB 이전 전 ≈0.21 s · 뒤 ≈2 ms)마다
    #   프로세스의 모든 요청이 선다 (#1701). 세션은 한 번에 한 스레드만 쓴다(순차 인계).
    # All sync DB work on this page runs in worker threads; on the loop each production round trip
    #   stalled every request in the process. The session is handed over sequentially.
    repo = await run_in_threadpool(_find_repo, db, repo_name, current_user.id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    # 🔴 GET 인데 쓰기다 — `refresh=1` 은 narrative 캐시를 DELETE 후 재생성하고
    # **Anthropic 유료 호출**을 유발한다. 따라서 "쓰기"는 HTTP 메서드가 아니라
    # DB 변이/외부 부수효과 기준으로 판정해야 한다(메서드 기준이면 이 경로가 그대로 열린다).
    # `refresh=0` 조회는 현행 유지. 가드를 `_find_repo` 안에 넣으면 안 된다 — 반환 규약이
    # `None`(→404)이라 403 을 표현할 수 없고 일반 조회까지 막힌다.
    # 🔴 A GET that writes: `refresh=1` invalidates the narrative cache and triggers a paid
    # Anthropic call, so "write" must be judged by DB mutation / external side effect, not by
    # HTTP method. Plain reads (`refresh=0`) are unaffected; the guard cannot live in `_find_repo`
    # because its contract returns `None` (→404) and cannot express a 403.
    if refresh and repo.user_id is None:
        raise HTTPException(
            status_code=403,
            detail=get_text("errors.repo_unclaimed", get_locale(request)),
        )

    # 새로 고침은 PRG — 위 가드를 모두 지난 뒤 캐시만 지우고 refresh 를 뺀 주소로 303.
    #   재생성은 그 GET 이 캐시 miss 로 한다. 주소에 refresh 가 남으면 F5 마다 유료 호출이 다시 나간다.
    # Refresh is PRG: past every guard above, invalidate and 303 to the URL without refresh; that
    #   GET regenerates on the miss. A URL keeping refresh restarted a paid call on every F5.
    if refresh:
        await run_in_threadpool(
            invalidate_repo_insight_narrative, db, user_id=current_user.id, repo_id=repo.id, days=days,
        )
        return redirect_without_refresh(request)

    kpi, recurring, problem_files, ai_suggestions, breakdown = await run_in_threadpool(
        _load_page_aggregates, db, repo.id, days,
    )

    # AI 내러티브 — API 키 있을 때만. 페이지는 Claude 를 부르지 않는다: 캐시 미스면 자리(`pending`)만 그리고
    #   htmx 가 조각 경로로 채운다 — 서술을 기다리느라 첫 바이트가 늦지 않게(원장 #1706 안 C 를 리포 인사이트에).
    # AI narrative — only with an API key. The page never calls Claude: on a cache miss it draws a
    #   placeholder and htmx fills it from the fragment route, so the first byte does not wait on Claude.
    view = _narrative_view(None)
    narrative_pending = False
    if settings.anthropic_api_key:
        narrative = await repo_insight_narrative(
            db,
            repo.id,
            days,
            repo_full_name=repo.full_name,
            kpi=kpi,
            recurring=recurring,
            user_id=current_user.id,
            language=get_locale(request),
            call_claude=False,
        )
        narrative_pending = narrative.get("status") == "pending"
        if not narrative_pending:
            view = _narrative_view(narrative)
        # 서술 단계의 커밋이 `repo` 를 만료시켰으면 템플릿의 `repo.*` 가 루프 위에서 SELECT 한다 — 여기서 채운다.
        # A commit in the narrative step expired `repo`; reload it here, not from the template on the loop.
        await run_in_threadpool(_load_template_attributes, repo)

    return templates.TemplateResponse(
        request,
        "repo_insights.html",
        {
            "current_user": current_user,
            "repo": repo,
            "days": days,
            "kpi": kpi,
            # 점수는 기간 전체, 이슈 수치는 최근 N건 — 템플릿은 N < 분석 수일 때만 적는다
            # Scores cover the window, issue figures its latest N; the template notes it when N < count
            "issue_basis": issue_basis(kpi["analysis_count"]),
            "recurring_issues": recurring,
            "problem_files": problem_files,
            "ai_suggestions": ai_suggestions,
            "breakdown": breakdown,
            **view,
            "narrative_pending": narrative_pending,
            "daily_cap": constants.INSIGHT_GENERATIONS_PER_USER_PER_DAY,
            "insight_days": constants.INSIGHT_DAYS_REPO,
            "locale": get_locale(request),
        },
    )


@router.get("/repos/{repo_name:path}/insights/narrative", response_class=HTMLResponse)
async def repo_insight_narrative_fragment(
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    db: Annotated[Session, Depends(_get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> Response:
    """리포 인사이트 서술 조각 — 페이지의 자리(`pending`)를 htmx 가 이 응답으로 바꿔 낀다. 유료 호출의 유일한 입구.

    The narrative fragment that replaces the page's placeholder via htmx — the only entry to the paid call.
    """
    days = insight_cost_guard.snap_days(days, constants.INSIGHT_DAYS_REPO)
    repo = await run_in_threadpool(_find_repo, db, repo_name, current_user.id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    # 주소창 · 새 탭으로 열면 조각만 덩그러니 뜬다 — 페이지로 돌려보낸다(그 페이지가 자리를 그리고 다시 부른다).
    #   🔴 주소는 요청 경로가 아니라 DB 에서 찾은 리포 이름으로 만든다 — 요청 글자로 만든 리다이렉트는 CodeQL
    #   `py/url-redirection`(#1899 첫 판 alert #651)이고, 리포를 먼저 찾으니 남의 리포는 리다이렉트 없이 404 다.
    # Opened directly, send the user to the page — built from the stored repo name, never the request path.
    if request.headers.get("HX-Request") != "true":
        return RedirectResponse(url=f"/repos/{quote(repo.full_name, safe='/')}/insights?days={days}", status_code=303)
    locale_value = get_locale(request)
    view = _narrative_view(None)
    if settings.anthropic_api_key:
        kpi, recurring = await run_in_threadpool(_load_narrative_inputs, db, repo.id, days)
        view = _narrative_view(await repo_insight_narrative(
            db,
            repo.id,
            days,
            repo_full_name=repo.full_name,
            kpi=kpi,
            recurring=recurring,
            user_id=current_user.id,
            language=locale_value,
        ))
        await run_in_threadpool(_load_template_attributes, repo)
    return templates.TemplateResponse(
        request,
        _NARRATIVE_FRAGMENT_TEMPLATE,
        {
            "repo": repo,
            "days": days,
            **view,
            "daily_cap": constants.INSIGHT_GENERATIONS_PER_USER_PER_DAY,
            "locale": locale_value,
        },
    )
