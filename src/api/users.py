"""사용자 계정 API — Telegram 연동 OTP 발급 등.
User account API — Telegram link OTP issuance, etc.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import update

from src.auth.session import CurrentUser, require_login
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
