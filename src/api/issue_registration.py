"""issue_registration API — GitHub Issue 등록 + 상태 조회 엔드포인트.
issue_registration API — endpoints for registering GitHub Issues and querying state.
"""
import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from src.auth.session import get_current_user
from src.database import SessionLocal
from src.i18n.loader import get_text
from src.middleware.rate_limiter import limiter, RATE_LIMIT_API, RATE_LIMIT_HEAVY
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.services.issue_registration_service import (
    get_analysis_issue_status,
    make_ai_issue_key,
    make_static_issue_key,
    register_issue,
)
from src.ui._helpers import get_locale

router = APIRouter(prefix="/api/issues")


class RegisterRequest(BaseModel):
    """Issue 등록 요청 본문. Register issue request body."""

    analysis_id: int
    issue_type: str  # "ai_suggestion" | "static_issue"
    # AI 제안사항용 — issue_key 서버 생성에 사용
    # For AI suggestions — used to generate issue_key server-side
    suggestion_text: str | None = None
    # 정적 분석 이슈용 — issue_key 서버 생성에 사용
    # For static issues — used to generate issue_key server-side
    tool: str | None = None
    category: str | None = None
    message: str | None = None
    # 🔴 정적 이슈용 — 키에서 빠져 서로 다른 파일이 한 슬롯으로 붕괴했다 (#1499).
    #    2026-08-25 이전 분석에는 이 값이 없어 None 이 온다(그때는 옛 동작 그대로).
    # For static issues — absent from pre-2026-08-25 analyses, hence optional.
    file: str | None = None
    title: str
    body: str
    labels: list[str]

    @model_validator(mode="after")
    def _static_issue_must_state_its_file(self):
        """🔴 정적 이슈는 `file` 을 **말해야** 한다 — `null` 이라도 명시해야 한다.

        `make_static_issue_key` 의 keyword-only 필수 인자는 Python 호출부만 막는다.
        실제 호출자는 브라우저이고, 여기 기본값 `None` 이 그대로 「조용히 빈 file」
        구멍이었다(Grok 01a0426a). 필드가 **빠진** 요청은 낡은 클라이언트라 거절하고,
        **명시적 null** 은 받는다 — 파일 키가 없던 시절(2026-08-25 이전) 분석이다.

        슬롯 스쿼팅은 되돌릴 수 없다. 422 는 페이지를 새로 고치면 풀리지만, 잘못 잡은
        슬롯은 풀리지 않는다.

        A static issue must state its file — explicit null is fine, omission is not.
        """
        if self.issue_type == "static_issue" and "file" not in self.model_fields_set:
            raise ValueError(
                "static_issue 는 file 을 명시해야 한다(값이 없으면 null) — "
                "빠뜨리면 서로 다른 파일이 한 dedup 슬롯으로 붕괴한다"
            )
        return self


def _get_analysis_and_repo(db: Session, analysis_id: int, *, current_user_id: int) -> tuple:
    """analysis_id로 Analysis + Repository를 조회하고 소유권을 검증한다. 없으면 404 raise.
    Look up Analysis and Repository by analysis_id and verify ownership. Raises 404 if not found.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    repo = db.query(Repository).filter(Repository.id == analysis.repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    # 🔴 리포 소유권 검증 — user_id=None(소유자 미등록)은 **읽기만** 허용한다(의도된 설계).
    # 쓰기 차단은 호출자(라우트 본문)의 책임 — 이 헬퍼는 읽기 `GET /status` 와 공유되므로
    # 여기에 403 을 넣으면 조회까지 깨진다. `register()` 의 인라인 가드를 볼 것.
    # 🔴 Ownership check — user_id=None (unclaimed) is readable by design; blocking writes is the
    # caller's job. This helper is shared with the read path (`GET /status`), so a 403 here would
    # break reads too. See the inline guard in `register()`.
    if repo.user_id is not None and repo.user_id != current_user_id:
        raise HTTPException(status_code=404)
    return analysis, repo


def _make_issue_key(req: RegisterRequest) -> str:
    """요청에서 issue_key를 생성한다.
    Generate issue_key from the request payload.
    """
    if req.issue_type == "ai_suggestion":
        text = req.suggestion_text or req.title
        return make_ai_issue_key(text)
    # 🔴 title 은 모달에서 **사용자가 고칠 수 있다**. 키에 넣으면 같은 finding 이
    #    입력한 제목에 따라 다른 슬롯을 잡고, 렌더 경로가 만든 키와도 어긋난다.
    #    정규화는 make_static_issue_key 가 한다 — 여기서 또 하면 다시 갈린다.
    # The title is user-editable; a dedup key must not depend on it.
    return make_static_issue_key(req.tool, req.category, req.message, file=req.file)


def _require_api_user(request: Request):
    """세션 사용자 반환, 미인증 시 401 (3 라우트 공통 — S1192 중복 가드 추출).

    Return the session user or raise 401 (shared by 3 routes).
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")
    return current_user


@router.post("/register", status_code=201)
@limiter.limit(RATE_LIMIT_HEAVY)
async def register(request: Request, req: RegisterRequest):
    """AI 분석 이슈를 GitHub Issue로 등록한다.
    Register an AI analysis issue as a GitHub Issue.
    """
    current_user = _require_api_user(request)

    locale = get_locale(request)
    issue_key = _make_issue_key(req)

    # A2: 소유권 검증은 sync DB 쿼리 — asyncio.to_thread로 이벤트 루프 차단 방지
    # A2: Ownership check is sync DB query — offload to thread to avoid blocking event loop
    def _check_ownership():
        with SessionLocal() as _db:
            return _get_analysis_and_repo(_db, req.analysis_id, current_user_id=current_user.id)

    _, repo = await asyncio.to_thread(_check_ownership)

    # 🔴 NULL-owner 쓰기 차단 — 가드를 `_get_analysis_and_repo` 안에 넣으면 안 된다.
    # 그 헬퍼는 읽기 `GET /status` 와 **공유**라, 안에 넣으면 analysis_detail 의 이슈 등록
    # 이력 배지가 무음 소실한다(fetch → 403 → `r.ok ? ... : null` → early return, catch 무음).
    # 여기서 막는 실피해: 중복 판정(`find_by_key`)이 히트하면 409 가 **영구**이고
    # issue_registration_repo 에 삭제 함수가 없어 dedup 슬롯 스쿼팅을 되돌릴 수 없다.
    # 🔴 Block writes to unowned repos here, NOT inside `_get_analysis_and_repo` — that helper is
    # shared with the read path (`GET /status`), where a 403 would silently drop the history badge.
    # Squatting the dedup slot here is irreversible: the 409 is permanent and there is no delete.
    if repo.user_id is None:
        raise HTTPException(
            status_code=403,
            detail=get_text("errors.repo_unclaimed", locale),
        )

    with SessionLocal() as db:
        try:
            result = await register_issue(
                db,
                analysis_id=req.analysis_id,
                repo_id=repo.id,
                repo_full_name=repo.full_name,
                github_token=current_user.plaintext_token,
                issue_type=req.issue_type,
                issue_key=issue_key,
                title=req.title,
                body=req.body,
                labels=req.labels,
            )
        except ValueError as exc:
            # "DUPLICATE:<number>" 형식
            # "DUPLICATE:<number>" format
            if str(exc).startswith("DUPLICATE:"):
                issue_num = str(exc).split(":")[1]
                raise HTTPException(
                    status_code=409,
                    detail=get_text("errors.issue_duplicate", locale, num=issue_num),
                ) from exc
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                raise HTTPException(
                    status_code=403,
                    detail=get_text("errors.issue_no_write_permission", locale),
                ) from exc
            raise HTTPException(
                status_code=502,
                detail=get_text("errors.github_api_error", locale),
            ) from exc

    return result


@router.get("/status")
@limiter.limit(RATE_LIMIT_API)
async def get_status(request: Request, analysis_id: int):
    """analysis_detail용 등록 이력 + GitHub 상태 동기화 결과를 반환한다.
    Return registration history and synced GitHub state for analysis_detail.
    """
    current_user = _require_api_user(request)

    def _check():
        with SessionLocal() as _db:
            return _get_analysis_and_repo(_db, analysis_id, current_user_id=current_user.id)

    _, repo = await asyncio.to_thread(_check)

    with SessionLocal() as db:
        statuses = await get_analysis_issue_status(
            db,
            analysis_id=analysis_id,
            repo_full_name=repo.full_name,
            github_token=current_user.plaintext_token,
        )

    return {"registrations": statuses}
