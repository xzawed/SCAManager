"""리포 추가 페이지 + GitHub 리포 목록 + `POST /repos/add`."""
from __future__ import annotations

import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.session import CurrentUser, require_login
from src.database import SessionLocal
from src.github_client.repos import (
    commit_scamanager_files,
    create_webhook,
    list_user_repos,
)
from src.i18n.loader import get_text
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.repositories import repo_config_repo, repository_repo
from src.shared.log_safety import sanitize_for_log
from src.ui._helpers import (
    GITHUB_WEBHOOK_PATH,
    get_locale,
    logger,
    templates,
    webhook_base_url,
)

router = APIRouter()

# user_id → (repos_list, expiry_monotonic) — GitHub API 중복 호출 방지 TTL 캐시
# user_id → (repos_list, expiry_monotonic) — TTL cache to avoid redundant GitHub API calls.
_user_repos_cache: dict[int, tuple[list[dict], float]] = {}
# _required_contexts_cache / _webhook_secret_cache 와 동일 5분 TTL
# Same 5-minute TTL as _required_contexts_cache / _webhook_secret_cache.
_USER_REPOS_CACHE_TTL = 300
# 🔴 상한 — 인증 사용자 누적 증가에 따른 무한 캐시 성장 차단 (api.md webhook-secret 캐시 패턴, 감사 api-ui-001)
# Cap entries to bound growth across distinct authenticated users (mirrors the webhook-secret cache).
_USER_REPOS_CACHE_MAX = 1024


def _store_user_repos(user_id: int, repos: list[dict], now: float) -> None:
    """TTL 캐시에 저장하되 상한 초과 시 만료분 정리 + 가장 빨리 만료될 엔트리 evict."""
    # Store with TTL; on overflow purge expired then evict the soonest-to-expire entry.
    if user_id not in _user_repos_cache and len(_user_repos_cache) >= _USER_REPOS_CACHE_MAX:
        for k in [k for k, (_, exp) in _user_repos_cache.items() if now >= exp]:
            del _user_repos_cache[k]
        if len(_user_repos_cache) >= _USER_REPOS_CACHE_MAX:
            del _user_repos_cache[min(_user_repos_cache, key=lambda k: _user_repos_cache[k][1])]
    _user_repos_cache[user_id] = (repos, now + _USER_REPOS_CACHE_TTL)


@router.get("/repos/add", response_class=HTMLResponse)
async def add_repo_page(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """리포 추가 페이지를 렌더링한다."""
    return templates.TemplateResponse(
        request,
        "add_repo.html",
        {"current_user": current_user, "locale": get_locale(request)},
    )


@router.get("/api/github/repos")
async def github_repos_list(
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """사용자의 GitHub 리포 목록 중 미등록 리포만 반환한다."""
    # 토큰 없으면 빈 목록 반환 (401 전파 방지)
    # Return empty list if token missing (prevent 401 propagation)
    if not current_user.plaintext_token:
        return []

    # GitHub API 응답은 TTL 캐시로 재사용 — existing_names 는 항상 최신 DB 조회
    # Reuse GitHub API response via TTL cache — existing_names always queries fresh DB.
    now = time.monotonic()
    cached = _user_repos_cache.get(current_user.id)
    if cached and now < cached[1]:
        all_repos = cached[0]
    else:
        try:
            all_repos = await list_user_repos(current_user.plaintext_token)
        except Exception:  # pylint: disable=broad-exception-caught
            # GitHub API 오류(401/403/429/timeout) 시 빈 목록 반환
            # Return empty list on GitHub API error (401/403/429/timeout)
            return []
        _store_user_repos(current_user.id, all_repos, now)

    with SessionLocal() as db:
        existing_names = {
            r.full_name for r in db.query(Repository).filter(
                Repository.user_id == current_user.id
            ).all()
        }
    return [r for r in all_repos if r["full_name"] not in existing_names]


@router.post("/repos/add")
async def add_repo(  # pylint: disable=too-many-locals
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """리포를 등록하고 GitHub Webhook을 생성한다."""
    locale = get_locale(request)
    form = await request.form()
    repo_full_name = (form.get("repo_full_name") or "").strip()
    if not repo_full_name:
        raise HTTPException(
            status_code=400,
            detail=get_text("errors.repo_name_required", locale),
        )

    with SessionLocal() as db:
        existing = repository_repo.find_by_full_name(db, repo_full_name)
        if existing:
            if existing.user_id is not None:
                # 에러 코드만 URL 로 전달 → 템플릿이 코드→i18n 매핑 (한국어 URL 노출 제거)
                # Pass only error code in URL → template maps code→i18n (no hardcoded text in URL)
                return RedirectResponse(
                    url="/repos/add?error=already_registered",
                    status_code=303,
                )
            # 🔴 소유권 이전 전 GitHub 접근 검증 (WBS P1 — IDOR-인접 차단): user_id=NULL 미소유 리포를
            # 폼 입력(repo_full_name)만으로 탈취하는 것을 막는다. 신규 repo 경로의 create_webhook(token)
            # 암묵 검증과 대칭 — 접근 권한 없으면 403.
            # Verify GitHub access before ownership transfer — blocks claiming an unowned repo via form alone.
            # 🔴 try 범위는 이 호출 한 줄 — 아래 403 raise 를 감싸면 "권한 없음"이 502 로 삼켜진다.
            # 🔴 Scope the try to this call only — wrapping the 403 below would mask it as a 502.
            try:
                accessible = await list_user_repos(current_user.plaintext_token or "")
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-except
                # GitHub 상류 장애(401/403/429/timeout)는 서버 버그가 아니므로 500 이 아닌 502.
                # 🔴 원시 예외 문구는 토큰이 섞일 수 있어 응답에 절대 노출하지 않는다.
                # GitHub upstream failure is not a server bug → 502, not 500.
                # 🔴 Never surface the raw exception — it can embed the token.
                logger.warning(
                    "add_repo: GitHub 리포 목록 조회 실패 (%s): %s",
                    sanitize_for_log(repo_full_name), type(exc).__name__,
                )
                raise HTTPException(
                    status_code=502,
                    detail=get_text("errors.github_unavailable", locale),
                ) from exc
            if repo_full_name not in {r.get("full_name") for r in accessible}:
                raise HTTPException(
                    status_code=403,
                    detail=get_text("errors.repo_access_denied", locale),
                )
            existing.user_id = current_user.id
            db.commit()
            return RedirectResponse(url=f"/repos/{repo_full_name}", status_code=303)

    webhook_secret = secrets.token_hex(32)
    hook_token = secrets.token_hex(32)
    webhook_url = webhook_base_url(request) + GITHUB_WEBHOOK_PATH
    webhook_id = await create_webhook(
        current_user.plaintext_token or "",
        repo_full_name,
        webhook_url,
        webhook_secret,
    )

    with SessionLocal() as db:
        repo = Repository(
            full_name=repo_full_name,
            user_id=current_user.id,
            webhook_secret=webhook_secret,
            webhook_id=webhook_id,
        )
        db.add(repo)
        db.commit()

        config = repo_config_repo.find_by_full_name(db, repo_full_name)
        if config is None:
            config = RepoConfig(repo_full_name=repo_full_name, hook_token=hook_token)
            db.add(config)
        else:
            config.hook_token = hook_token
        db.commit()

    server_url = webhook_base_url(request)
    await commit_scamanager_files(
        current_user.plaintext_token or "",
        repo_full_name,
        server_url,
        hook_token,
    )

    return RedirectResponse(
        url=f"/repos/{repo_full_name}?hook_installed=1",
        status_code=303,
    )
