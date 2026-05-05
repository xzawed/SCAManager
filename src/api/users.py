"""사용자 계정 API — Telegram 연동 OTP 발급 + 선호 언어 설정 등.
User account API — Telegram link OTP issuance + preferred language settings, etc.
"""
from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

# OTP 자릿수 — One-time passcode digit count.
_OTP_LENGTH = 6
# OTP 유효 시간(분) — OTP validity window in minutes.
_OTP_TTL_MINUTES = 5

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("/me/telegram-otp", status_code=200)
async def issue_telegram_otp(
    current_user: Annotated[CurrentUser, Depends(require_login)],
) -> dict:
    """Telegram 연동용 6자리 OTP를 발급한다.
    Issue a 6-digit OTP for Telegram account linking.

    기존 OTP가 있으면 덮어쓴다 — 마지막 OTP만 유효.
    Overwrites any existing OTP — only the last issued OTP is valid.
    """
    # secrets.choice 사용 — random 모듈 사용 금지 (보안)
    # Use secrets.choice — never use the random module (security requirement).
    otp = "".join(secrets.choice("0123456789") for _ in range(_OTP_LENGTH))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_OTP_TTL_MINUTES)

    # DB에 OTP 저장 — 기존 값을 덮어씀으로써 마지막 발급 OTP만 유효하게 유지
    # Save OTP to DB — overwrite any existing value so only the latest OTP is valid.
    with SessionLocal() as db:
        db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(telegram_otp=otp, telegram_otp_expires_at=expires_at)
        )
        db.commit()

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


@router.post("/me/preferred-language", status_code=200)
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

    with SessionLocal() as db:
        db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(preferred_language=language)
        )
        db.commit()

    # Cookie 동기화 — LocaleMiddleware 가 매 request 시 우선 감지
    # Cookie sync — LocaleMiddleware checks Cookie first per request
    # 만료 = 1년 (사용자 명시 변경 시까지 유지)
    # max-age = 1 year (until user explicitly changes)
    is_prod = settings.app_base_url.startswith("https")
    response.set_cookie(
        key="preferred_language",
        value=language,
        max_age=60 * 60 * 24 * 365,  # 1 year
        httponly=False,  # JavaScript 읽기 가능 (헤더 dropdown 표시 영역)
        secure=is_prod,
        samesite="lax",
        path="/",
    )

    logger.info(
        "preferred_language updated for user_id=%d → '%s'",
        current_user.id,
        language,
    )
    return {
        "language": language,
        "message": "preferred language updated",
    }
