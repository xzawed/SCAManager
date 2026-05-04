"""InsightNarrativeCache Repository — get / upsert / delete (1h TTL pattern).

Cycle 74 PR-B Phase 2-B 🅑 — Insight 모드 Claude AI 호출 빈도 제한 (60% 절감).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.models.insight_narrative_cache import InsightNarrativeCache

# Phase 2-B sub-option default — TTL 1시간 (cross-verify 권장 보수적 default)
# Phase 2-B sub-option default — TTL 1 hour (cross-verify recommended conservative default).
DEFAULT_TTL_SECONDS = 3600


def get_fresh(
    db: Session, *, user_id: int, days: int, now: datetime | None = None,
) -> dict[str, Any] | None:
    """캐시 조회 — 만료 미경과 시 response_json 반환, 없거나 만료면 None.

    Get cache — return response_json if not expired, else None.
    """
    now = now or datetime.now(timezone.utc)
    row = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.days == days,
        )
        .first()
    )
    if row is None:
        return None
    # SQLite 호환: expires_at 가 naive datetime 일 수 있어 정규화
    # SQLite compat: expires_at may be naive — normalize.
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        return None
    return dict(row.response_json or {})


def upsert(
    db: Session, *, user_id: int, days: int, response: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS, now: datetime | None = None,
) -> InsightNarrativeCache:
    """캐시 upsert — (user_id, days) 키 기준 INSERT 또는 UPDATE.

    Upsert cache by (user_id, days). INSERT if absent, UPDATE if present.
    """
    now = now or datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    existing = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.days == days,
        )
        .first()
    )
    if existing is not None:
        existing.response_json = response
        existing.created_at = now
        existing.expires_at = expires_at
        db.commit()
        db.refresh(existing)
        return existing

    row = InsightNarrativeCache(
        user_id=user_id, days=days, response_json=response,
        created_at=now, expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def invalidate(db: Session, *, user_id: int, days: int) -> bool:
    """사용자 명시 Refresh 시 강제 무효화 (DELETE).

    Force invalidate (DELETE) on user-explicit Refresh.
    Returns True if deleted, False if not found.
    """
    row = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.days == days,
        )
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
