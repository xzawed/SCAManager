"""리포 설정 관련 페이지/폼/webhook 재설치 엔드포인트."""
from __future__ import annotations

import ipaddress
import secrets
from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from dataclasses import fields as dataclass_fields

from src.auth.session import CurrentUser, require_login
from src.config_manager.manager import RepoConfigData, get_repo_config, upsert_repo_config
from src.database import SessionLocal
from src.github_client.repos import (
    WEBHOOK_EVENTS,
    commit_scamanager_files,
    create_webhook,
    delete_webhook,
    list_webhooks,
)
from src.models.repo_config import RepoConfig
from src.repositories import repo_config_repo
from src.shared.log_safety import sanitize_for_log
from src.ui._helpers import (
    GITHUB_WEBHOOK_PATH,
    get_accessible_repo,
    logger,
    templates,
    webhook_base_url,
)

router = APIRouter()

# SSRF 방어: 내부 네트워크 및 클라우드 메타데이터 주소 차단
# SSRF defence: block internal network and cloud metadata addresses.
_BLOCKED_HOSTS = frozenset({
    "localhost", "127.0.0.1", "::1",
    "0.0.0.0",  # noqa: S104
    "169.254.169.254",  # AWS/GCP IMDS
    "metadata.google.internal",  # GCP metadata
    "fd00::ec2",  # AWS IPv6 IMDS
})


def _is_safe_webhook_url(url: str | None) -> bool:  # pylint: disable=too-many-return-statements
    """사용자 제공 URL이 SSRF 공격에 안전한지 검증한다.
    Validates that a user-supplied URL is safe against SSRF attacks.

    반환값 7개는 SSRF 방어 경로 각각이 명확한 실패 사유를 나타내므로 의도적.
    7 return statements are intentional — each guards a distinct SSRF failure path."""
    if not url:
        return True
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        if host in _BLOCKED_HOSTS:
            return False
        # 사설 IP 대역, 루프백, 링크-로컬 주소 차단
        # Block private/loopback/link-local IP ranges.
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass  # 호스트명(도메인)은 IP 파싱 실패가 정상 / Domain names will fail IP parsing — that is fine.
        return True
    except Exception:  # pylint: disable=broad-except
        return False


def _validate_webhook_urls(form) -> None:
    """폼의 모든 webhook URL을 검증한다. 안전하지 않으면 HTTPException(400)."""
    webhook_fields = (
        "n8n_webhook_url", "discord_webhook_url",
        "slack_webhook_url", "custom_webhook_url",
    )
    for field in webhook_fields:
        url = form.get(field) or ""
        if url and not _is_safe_webhook_url(url):
            raise HTTPException(
                status_code=400,
                detail=f"유효하지 않은 URL: {field}. 내부 네트워크 주소는 사용할 수 없습니다.",
            )


async def _detect_stale_webhook(
    token: str,
    repo_full_name: str,
    webhook_id: int | None,
) -> bool:
    """등록된 webhook 이 check_suite 이벤트를 구독하지 않으면 True 를 반환한다.
    Returns True if the registered webhook is missing the check_suite event subscription.

    조회 실패 시 False 반환 — 배너를 오 표시하지 않도록 실패 시 안전 기본값 사용.
    Returns False on any error — fail-safe default avoids false banner display.
    """
    if not webhook_id or not token:
        return False
    try:
        hooks = await list_webhooks(token, repo_full_name)
        for hook in hooks:
            if hook.get("id") == webhook_id:
                hook_events = hook.get("events", [])
                # WEBHOOK_EVENTS 에 포함된 이벤트 중 누락된 것이 있으면 stale
                # Stale if any event from WEBHOOK_EVENTS is missing from the registered hook
                return any(ev not in hook_events for ev in WEBHOOK_EVENTS)
        # webhook_id 와 일치하는 훅 없음 → 배너 표시 불필요
        # No hook matching webhook_id — no banner needed
        return False
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        safe_repo_full_name = sanitize_for_log(repo_full_name)
        logger.debug("_detect_stale_webhook: API call failed for %s: %s", safe_repo_full_name, exc)
        return False


# 단순 모드에서 그대로 노출되는 핵심 필드 4개 (+ Telegram OTP 는 user 글로벌이라 별도)
# 4 core fields exposed in simple mode (Telegram OTP is user-global, handled separately)
_SIMPLE_MODE_FIELDS = frozenset({
    "notify_chat_id", "pr_review_comment", "auto_merge", "merge_threshold",
})


def _detect_initial_mode(config: RepoConfigData, railway_api_token_set: bool) -> str:
    """단순 모드 노출 5개 핵심 필드 외에 사용자가 한 번이라도 비-기본값으로 저장한 흔적이 있으면 'advanced' 반환.
    Return 'advanced' when any non-simple-mode field carries a non-default value.

    이 신호는 클라이언트의 localStorage 가 비어있을 때만 사용되는 server fallback.
    `data-initial-mode` 속성으로 템플릿에 내려가고, JS `initSettingsMode()` 가 우선순위를
    localStorage > data-initial-mode > 'simple' 순으로 적용한다.
    """
    default = RepoConfigData(repo_full_name=config.repo_full_name)
    for field in dataclass_fields(RepoConfigData):
        name = field.name
        if name == "repo_full_name" or name in _SIMPLE_MODE_FIELDS:
            continue
        if getattr(config, name) != getattr(default, name):
            return "advanced"
    if railway_api_token_set:
        return "advanced"
    return "simple"


@router.get("/repos/{repo_name:path}/settings", response_class=HTMLResponse)
async def repo_settings(  # pylint: disable=too-many-positional-arguments,too-many-locals
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    hook_ok: int = 0,
    hook_fail: int = 0,
    saved: int = 0,
    save_error: int = 0,
):
    """리포 Gate·알림 설정 페이지를 렌더링한다."""
    with SessionLocal() as db:
        repo = get_accessible_repo(db, repo_name, current_user)
        config = get_repo_config(db, repo_name)
        config_orm = repo_config_repo.find_by_full_name(db, repo_name)
        railway_webhook_token = config_orm.railway_webhook_token if config_orm else None
        railway_api_token_set = bool(config_orm and config_orm.railway_api_token)
        repo_webhook_id = repo.webhook_id

    railway_webhook_url = ""
    if railway_webhook_token:
        base = webhook_base_url(request)
        railway_webhook_url = f"{base}/webhooks/railway/{railway_webhook_token}"

    # check_suite 이벤트 구독 여부 확인 — 없으면 재등록 배너 표시 (Phase 12)
    # Check whether check_suite is subscribed — show reinstall banner if missing (Phase 12)
    webhook_stale = await _detect_stale_webhook(
        token=current_user.plaintext_token or "",
        repo_full_name=repo_name,
        webhook_id=repo_webhook_id,
    )

    # 알림 채널 미설정 + Telegram 미연결 → 온보딩 배너 표시
    # Show onboarding banner when no notification channel is configured and Telegram is not linked.
    onboarding_needed = (
        not config.notify_chat_id and
        not current_user.is_telegram_connected
    )

    # 사용자 신호 기반 초기 모드 판정 — localStorage 가 비어있을 때만 fallback 으로 사용됨
    # User-signal initial-mode detection — used as fallback only when localStorage is empty
    initial_mode = _detect_initial_mode(config, railway_api_token_set)

    return templates.TemplateResponse(request, "settings.html", {
        "repo_name": repo_name, "config": config,
        "hook_ok": bool(hook_ok), "hook_fail": bool(hook_fail),
        "saved": bool(saved), "save_error": bool(save_error),
        "current_user": current_user,
        "railway_webhook_url": railway_webhook_url,
        "railway_api_token_set": railway_api_token_set,
        "webhook_stale": webhook_stale,
        "onboarding_needed": onboarding_needed,
        "initial_mode": initial_mode,
    })


@router.post(
    "/repos/{repo_name:path}/settings",
    responses={400: {"description": "Invalid webhook URL (SSRF blocked)"}},
)
async def update_repo_settings(
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """폼 데이터로 리포 Gate·알림 설정을 저장한다."""
    form = await request.form()
    # SSRF 방어: webhook URL 사전 검증 — 내부 네트워크 요청 차단
    # SSRF defence: validate webhook URLs before saving — blocks internal network requests.
    _validate_webhook_urls(form)
    with SessionLocal() as db:
        get_accessible_repo(db, repo_name, current_user)
        try:
            upsert_repo_config(db, RepoConfigData(
                repo_full_name=repo_name,
                pr_review_comment=form.get("pr_review_comment") == "on",
                approve_mode=form.get("approve_mode", "disabled"),
                approve_threshold=int(form.get("approve_threshold", 75)),
                reject_threshold=int(form.get("reject_threshold", 50)),
                notify_chat_id=form.get("notify_chat_id") or None,
                n8n_webhook_url=form.get("n8n_webhook_url") or None,
                discord_webhook_url=form.get("discord_webhook_url", "") or None,
                slack_webhook_url=form.get("slack_webhook_url", "") or None,
                custom_webhook_url=form.get("custom_webhook_url", "") or None,
                email_recipients=form.get("email_recipients", "") or None,
                auto_merge=form.get("auto_merge") == "on",
                merge_threshold=int(form.get("merge_threshold", 75)),
                commit_comment=form.get("commit_comment") == "on",
                create_issue=form.get("create_issue") == "on",
                railway_deploy_alerts=form.get("railway_deploy_alerts") == "on",
                auto_merge_issue_on_failure=form.get("auto_merge_issue_on_failure") == "on",
                leaderboard_opt_in=form.get("leaderboard_opt_in") == "on",
            ))
            # railway_webhook_token, railway_api_token — RepoConfigData 외부 관리
            config_orm = repo_config_repo.find_by_full_name(db, repo_name)
            if config_orm and not config_orm.railway_webhook_token:
                config_orm.railway_webhook_token = secrets.token_hex(32)
            new_api_token = form.get("railway_api_token", "")
            if config_orm and new_api_token and new_api_token != "****":
                from src.crypto import encrypt_token  # pylint: disable=import-outside-toplevel
                config_orm.railway_api_token = encrypt_token(new_api_token)
            if config_orm:
                db.commit()
        except ValueError:
            # NOSONAR 이유: SonarCloud taint analysis 가 str.replace 기반 커스텀
            # sanitizer 를 인식하지 못함 — log_safety 모듈에서 실제 방어 완료.
            logger.warning(  # NOSONAR python:S5145 — sanitized via log_safety
                "Invalid threshold values for %s, settings not saved",
                sanitize_for_log(repo_name),
            )
            return RedirectResponse(
                url=f"/repos/{repo_name}/settings?save_error=1", status_code=303
            )
    return RedirectResponse(url=f"/repos/{repo_name}/settings?saved=1", status_code=303)


@router.post("/repos/{repo_name:path}/reinstall-hook")
async def reinstall_hook(
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """기존 등록 리포에 .scamanager/ 파일을 재커밋한다."""
    with SessionLocal() as db:
        get_accessible_repo(db, repo_name, current_user)
        config = repo_config_repo.find_by_full_name(db, repo_name)
        if config is None:
            config = RepoConfig(
                repo_full_name=repo_name,
                hook_token=secrets.token_hex(32),
            )
            db.add(config)
        elif not config.hook_token:
            config.hook_token = secrets.token_hex(32)
        db.commit()
        hook_token = config.hook_token

    server_url = webhook_base_url(request)
    ok = await commit_scamanager_files(
        current_user.plaintext_token or "",
        repo_name,
        server_url,
        hook_token,
    )

    status = "hook_ok" if ok else "hook_fail"
    return RedirectResponse(
        url=f"/repos/{repo_name}/settings?{status}=1",
        status_code=303,
    )


@router.post("/repos/{repo_name:path}/reinstall-webhook")
async def reinstall_webhook(
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """GitHub Webhook을 삭제하고 새 URL(HTTPS)로 재등록한다. 중복 웹훅도 모두 정리한다."""
    with SessionLocal() as db:
        repo = get_accessible_repo(db, repo_name, current_user)
        token = current_user.plaintext_token or ""

        webhook_url = webhook_base_url(request) + GITHUB_WEBHOOK_PATH

        try:
            all_hooks = await list_webhooks(token, repo_name)
            for hook in all_hooks:
                hook_url = hook.get("config", {}).get("url", "")
                if GITHUB_WEBHOOK_PATH in hook_url:
                    await delete_webhook(token, repo_name, hook["id"])
                    logger.info("Deleted duplicate webhook id=%d url=%s", hook["id"], hook_url)
        except (httpx.HTTPError, KeyError, ValueError, OSError) as exc:
            logger.warning("Webhook cleanup failed, proceeding with reinstall: %s", exc)

        new_secret = secrets.token_hex(32)
        new_id = await create_webhook(token, repo_name, webhook_url, new_secret)

        repo.webhook_id = new_id
        repo.webhook_secret = new_secret
        db.commit()

    return RedirectResponse(
        url=f"/repos/{repo_name}/settings?hook_ok=1",
        status_code=303,
    )
