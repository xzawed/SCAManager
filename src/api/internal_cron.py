"""내부 Cron 엔드포인트 — Railway native cron 트리거용.
Internal cron endpoints — triggered by Railway native cron jobs.

인증: INTERNAL_CRON_API_KEY 헤더 (admin api_key와 분리).
Auth: INTERNAL_CRON_API_KEY header (separate from admin api_key).
"""
from __future__ import annotations

import hmac as _hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from src.config import settings
from src.database import SessionLocal
from src.services.cron_service import run_trend_check, run_weekly_reports

logger = logging.getLogger(__name__)

# cron 전용 API 키 헤더 스키마 — admin X-API-Key와 동일 헤더명이지만 별도 검증 로직
# Cron-specific API key header — same header name as admin but validated separately
_cron_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _require_cron_key(
    api_key: str | None = Security(_cron_key_header),
) -> None:
    """INTERNAL_CRON_API_KEY 검증.
    Validate the INTERNAL_CRON_API_KEY.

    - 키 미설정 시 503 반환 (운영 환경에서 미설정 차단)
    - 키 불일치 시 401 반환 (타이밍 안전 비교)
    - Returns 503 if key is not configured (blocks accidental open access)
    - Returns 401 on mismatch (timing-safe comparison)
    """
    expected = settings.internal_cron_api_key
    # 키 미설정 시 503 — 실수로 빈 설정에서 노출 방지
    # Return 503 if unconfigured — prevents accidental open access
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Cron API key not configured",
        )
    # 타이밍 공격 방지를 위해 hmac.compare_digest 사용
    # Use hmac.compare_digest to prevent timing attacks
    if api_key is None or not _hmac.compare_digest(expected, api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid cron API key",
        )


router = APIRouter(
    prefix="/api/internal/cron",
    # 라우터 레벨 인증 — 모든 cron 엔드포인트에 일괄 적용
    # Router-level auth dependency — applied to all cron endpoints uniformly
    dependencies=[Depends(_require_cron_key)],
)


@router.post("/weekly", status_code=200)
async def trigger_weekly_reports() -> dict:
    """주간 리포트 cron 트리거.
    Trigger weekly report sending for all repositories.

    Returns:
        {"status": "ok", "sent": <int>} — 발송된 리포트 수
        {"status": "ok", "sent": <int>} — number of reports sent
    """
    # SessionLocal() context manager로 DB 세션 획득 — 함수 종료 시 자동 반환
    # Acquire DB session via SessionLocal() context manager — auto-released on exit
    with SessionLocal() as db:
        sent = await run_weekly_reports(db)
    logger.info("weekly_reports: sent=%d", sent)
    return {"status": "ok", "sent": sent}


@router.post("/trend", status_code=200)
async def trigger_trend_check() -> dict:
    """트렌드 체크 cron 트리거.
    Trigger trend-check alerts for all repositories.

    Returns:
        {"status": "ok", "alerted": <int>} — 경고 발송된 리포 수
        {"status": "ok", "alerted": <int>} — number of repos that received an alert
    """
    # SessionLocal() context manager로 DB 세션 획득 — 함수 종료 시 자동 반환
    # Acquire DB session via SessionLocal() context manager — auto-released on exit
    with SessionLocal() as db:
        alerted = await run_trend_check(db)
    logger.info("trend_check: alerted=%d", alerted)
    return {"status": "ok", "alerted": alerted}
