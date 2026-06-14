"""사용자 계정 API — Telegram 연동 OTP 발급 + 선호 언어 설정 등.
User account API — Telegram link OTP issuance + preferred language settings, etc.
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import update

from src.auth.session import CurrentUser, require_login
from src.config import settings
from src.database import SessionLocal
from src.models.user import User
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger(__name__)
LOCALE_COOKIE_VALUE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")

# OTP 자릿수 — One-time passcode digit count.
# C12 (회고 P2-c): 6→8 자리. find_by_otp 는 user 무관 전역 풀 조회 + 리미터는 per-sender 라
# 계정 로테이션 시 전역 brute-force 상한이 없다 → 탐색 공간을 10^6→10^8(100배)로 확대해
# per-sender 리미터(OTP_MAX_FAILED_ATTEMPTS)와 곱연산으로 추측 비용을 높인다.
# C12: 6→8 digits. find_by_otp looks up the global (user-agnostic) OTP pool while the limiter is
# per-sender, so account rotation has no global ceiling → widen the space 10^6→10^8 (100x) to
# compound with the per-sender limiter.
_OTP_LENGTH = 8
# OTP 유효 시간(분) — OTP validity window in minutes.
_OTP_TTL_MINUTES = 5

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("/me/telegram-otp", status_code=200)
async def issue_telegram_otp(
    current_user: Annotated[CurrentUser, Depends(require_login)],
) -> dict:
    """Telegram 연동용 8자리 OTP를 발급한다.
    Issue an 8-digit OTP for Telegram account linking.

    기존 OTP가 있으면 덮어쓴다 — 마지막 OTP만 유효.
    Overwrites any existing OTP — only the last issued OTP is valid.
    """
    # secrets.choice 사용 — random 모듈 사용 금지 (보안)
    # Use secrets.choice — never use the random module (security requirement).
    otp = "".join(secrets.choice("0123456789") for _ in range(_OTP_LENGTH))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_OTP_TTL_MINUTES)

    # DB에 OTP 저장 — asyncio.to_thread로 wrap하여 이벤트 루프 블로킹 방지
    # Save OTP to DB — wrapped in asyncio.to_thread to avoid event loop blocking.
    def _do_save() -> None:
        with SessionLocal() as db:
            db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(telegram_otp=otp, telegram_otp_expires_at=expires_at)
            )
            db.commit()

    await asyncio.to_thread(_do_save)

    logger.info("telegram_otp issued for user_id=%d", current_user.id)
    return {
        "otp": otp,
        "expires_at": expires_at.isoformat(),
        "ttl_minutes": _OTP_TTL_MINUTES,
    }


# Phase 2 PR-4 (사이클 84 — 다국어 i18n) — 사용자 선호 언어 설정 API
# Phase 2 PR-4 (Cycle 84 — i18n) — User preferred language settings API


class PreferredLanguageUpdate(BaseModel):
    """선호 언어 변경 요청 본문 (POST /api/users/me/preferred-language).

    Body for POST /api/users/me/preferred-language.
    """

    language: str

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """SUPPORTED_LOCALES 영역 검증 + 정규화.

        Validate against SUPPORTED_LOCALES + normalize.
        """
        v = v.strip().lower() if v else ""
        if not v:
            raise ValueError("language must not be empty")
        supported = {lang.strip() for lang in settings.supported_locales.split(",")}
        if v not in supported:
            raise ValueError(
                f"language '{v}' not in SUPPORTED_LOCALES "
                f"({settings.supported_locales})"
            )
        return v


@router.post(
    "/me/preferred-language",
    status_code=200,
    responses={
        # Defense-in-depth sink-adjacent guard (사실상 도달 불가 — Pydantic validator 가 422 먼저 발화)
        # Defense-in-depth sink-adjacent guard (effectively unreachable — Pydantic validator returns 422 first)
        # Copilot Autofix CodeQL "Construction of a cookie using user-supplied input" 페어
        # Pairs with Copilot Autofix CodeQL "Construction of a cookie using user-supplied input"
        400: {
            "description": (
                "Sink-adjacent guard: invalid locale "
                "(defense-in-depth, normally caught by 422)"
            ),
        },
        # Pydantic body validator 가 SUPPORTED_LOCALES 미지원 / 빈 문자열 시 발화
        # FastAPI auto-422 from Pydantic body validator (unsupported locale / empty)
        422: {
            "description": (
                "Validation error — language not in SUPPORTED_LOCALES or empty"
            ),
        },
        # I18N_DISABLED=1 kill-switch 활성 시 503 (사이클 78 NEW-P0-2 패턴 페어)
        # 503 when I18N_DISABLED=1 kill-switch active (Cycle 78 NEW-P0-2 pair)
        503: {
            "description": "i18n feature is disabled (I18N_DISABLED=1)",
        },
    },
)
async def update_preferred_language(
    body: PreferredLanguageUpdate,
    response: Response,
    current_user: Annotated[CurrentUser, Depends(require_login)],
) -> dict:
    """사용자 선호 언어 변경 — DB + Cookie 동시 갱신 (LocaleMiddleware 페어).

    Update user preferred language — sync DB + Cookie (pairs with LocaleMiddleware).

    DB 갱신 의무 + Cookie `preferred_language` 1년 만료 설정 의무 (LocaleMiddleware
    가 매 request 시 Cookie 우선 감지 — Cookie + DB 동시 갱신으로 즉시 반영).

    Updates User.preferred_language in DB + sets Cookie with 1-year expiry
    (LocaleMiddleware checks Cookie first per request — sync ensures immediate effect).
    """
    if settings.i18n_disabled:
        # kill-switch 활성 시 = 변경 차단 (영문 hardcoded fallback 강제)
        # When kill-switch enabled = block change (force English hardcoded fallback)
        raise HTTPException(
            status_code=503,
            detail="i18n feature is disabled (I18N_DISABLED=1)",
        )

    # Sink 직전 방어: 허용된 locale만 쿠키/DB 반영
    # Sink-adjacent guard: only allow configured locales for cookie/DB
    supported = {lang.strip().lower() for lang in settings.supported_locales.split(",")}
    language = body.language.strip().lower() if body.language else ""
    if language not in supported:
        raise HTTPException(status_code=400, detail="invalid language")
    safe_language = language
    if not LOCALE_COOKIE_VALUE_RE.fullmatch(safe_language):
        raise HTTPException(status_code=400, detail="invalid language")

    # 동기 SQLAlchemy를 asyncio.to_thread로 wrap — 이벤트 루프 블로킹 방지
    # Wrap sync SQLAlchemy in asyncio.to_thread — prevents event loop blocking
    def _do_update() -> None:
        with SessionLocal() as db:
            db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(preferred_language=safe_language)
            )
            db.commit()

    await asyncio.to_thread(_do_update)

    # Cookie 동기화 — LocaleMiddleware 가 매 request 시 우선 감지
    # Cookie sync — LocaleMiddleware checks Cookie first per request
    # 만료 = 1년 (사용자 명시 변경 시까지 유지)
    # max-age = 1 year (until user explicitly changes)
    is_prod = settings.app_base_url.startswith("https")
    # Phase 2 PR-5 (사이클 84 — cross-verify 옵션 C) — httponly=True 보안 강화
    # Phase 2 PR-5 (Cycle 84 — cross-verify option C) — httponly=True security
    # 변경 사유: JS 가 cookie 직접 읽지 않음 (LocaleMiddleware scope.state → Jinja
    # `{{ locale }}` template 변수 주입 페어). XSS 위험 차단 + base.html 의
    # readCookieLang() 함수 폐기 (서버 변수 주입으로 대체).
    # Reason: JS no longer reads cookie (uses Jinja `{{ locale }}` injection from
    # LocaleMiddleware.scope.state). Mitigates XSS + replaces base.html readCookieLang().
    response.set_cookie(
        key="preferred_language",
        value=safe_language,
        max_age=60 * 60 * 24 * 365,  # 1 year
        httponly=True,  # Phase 2 PR-5 — XSS 차단 + 서버측 template 주입 페어
        secure=is_prod,
        samesite="lax",
        path="/",
    )

    # CLAUDE.md L893 정합 — sanitize_for_log helper 사용 의무 (CR/LF/TAB/NUL 제거 + 길이 제한)
    # CLAUDE.md L893 — must use sanitize_for_log helper (strips CR/LF/TAB/NUL + truncates)
    logger.info(
        "preferred_language updated for user_id=%d → '%s'",
        current_user.id,
        sanitize_for_log(safe_language),
    )
    return {
        "language": safe_language,
        "message": "preferred language updated",
    }
