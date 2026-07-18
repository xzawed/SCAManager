"""InsightNarrativeCache Repository — get / upsert / delete (1h TTL pattern).

Cycle 74 PR-B Phase 2-B 🅑 — Insight 모드 Claude AI 호출 빈도 제한 (60% 절감).
0031 — repo-scoped cache helpers 추가 (get_fresh_repo / upsert_repo / invalidate_repo).
0031 — Add repo-scoped cache helpers (get_fresh_repo / upsert_repo / invalidate_repo).
0033 — record_error / record_error_repo 추가 (에러 빈도 추적).
0033 — Add record_error / record_error_repo (error frequency tracking).
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
    db: Session,
    *,
    user_id: int,
    days: int,
    language: str = "en",
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """전체 대시보드 캐시 조회 — 만료 미경과 시 response_json 반환, 없거나 만료면 None.

    Get global dashboard cache — return response_json if not expired, else None.
    """
    now = now or datetime.now(timezone.utc)
    row = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.repo_id.is_(None),
            InsightNarrativeCache.language == language,
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
    db: Session,
    *,
    user_id: int,
    days: int,
    language: str = "en",
    response: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> InsightNarrativeCache:
    """전체 대시보드 캐시 upsert — (user_id, days, language, repo_id=NULL) 키 기준.

    Upsert global dashboard cache by (user_id, days, language, repo_id=NULL).
    """
    now = now or datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    existing = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.repo_id.is_(None),
            InsightNarrativeCache.language == language,
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
        user_id=user_id, days=days, language=language, repo_id=None,
        response_json=response, created_at=now, expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def invalidate(db: Session, *, user_id: int, days: int) -> bool:
    """전체 대시보드 캐시 강제 무효화 (DELETE, repo_id=NULL — 모든 언어 행).

    Force invalidate global dashboard cache (DELETE, repo_id=NULL — all language rows).
    Returns True if any row deleted, False if none.

    🔴 C14: 전역 캐시는 부분 유니크 (user_id, days, language) 키라 동일 (user_id, days)에 언어별
    다중 행이 공존한다. 이전 `.first()` 단일 삭제는 ORDER BY 없이 비결정적으로 무관한 언어 행을
    지워 cross-language eviction(타 언어 캐시 부수 손실 → 불필요한 Claude API 재생성)을 유발했다.
    bulk delete 로 (user_id, days, global)의 모든 언어 행을 결정론적으로 무효화한다.
    C14: the global cache is keyed (user_id, days, language) so multiple language rows coexist; the old
    `.first()` single-delete non-deterministically evicted an unrelated language. Bulk-delete all.
    """
    deleted = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.repo_id.is_(None),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted > 0


def purge_expired(db: Session, *, now: datetime | None = None) -> int:
    """만료된 캐시 행을 삭제하고 삭제 건수를 반환한다 — retention sweep 용 GC.

    Delete expired cache rows and return the count — GC for the retention sweep.

    🔴 `get_fresh` 는 만료 행에 대해 None 만 반환하고 **행을 지우지 않는다** → days∈[1,365] × 언어 ×
    저장소 키 조합이 사용자 조회마다 upsert 되어 만료 행이 영구 누적된다(준비도 감사 #12, GC 0).
    이 함수가 `expires_at < now` 행을 정리한다. 이미 TTL 이 지난 행이라 삭제해도 캐시 손실 0.
    🔴 get_fresh only returns None for expired rows without deleting them, so stale rows pile up
    forever. This purges `expires_at < now`; they are already past TTL so nothing useful is lost.
    """
    _now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    deleted = (
        db.query(InsightNarrativeCache)
        .filter(InsightNarrativeCache.expires_at < _now)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


# ─── 0031: repo-scoped cache helpers ─────────────────────────────────────────
# ─── 0031: 리포별 캐시 헬퍼 ─────────────────────────────────────────────────


def get_fresh_repo(
    db: Session,
    *,
    user_id: int,
    repo_id: int,
    days: int,
    language: str = "en",
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """리포별 캐시 조회 — 만료 미경과 시 response_json 반환, 없거나 만료면 None.

    Get repo-specific cache — return response_json if not expired, else None.
    """
    now = now or datetime.now(timezone.utc)
    row = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.repo_id == repo_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.language == language,
        )
        .first()
    )
    if row is None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        return None
    return dict(row.response_json or {})


def upsert_repo(
    db: Session,
    *,
    user_id: int,
    repo_id: int,
    days: int,
    language: str = "en",
    response: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> InsightNarrativeCache:
    """리포별 캐시 upsert — (user_id, repo_id, days, language) 키 기준.

    Upsert repo-specific cache by (user_id, repo_id, days, language).
    """
    now = now or datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    existing = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.repo_id == repo_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.language == language,
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
        user_id=user_id, repo_id=repo_id, days=days, language=language,
        response_json=response, created_at=now, expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def record_error(
    db: Session,
    *,
    user_id: int,
    days: int,
    language: str = "en",
    error_type: str,
    now: datetime | None = None,
) -> None:
    """전체 대시보드 에러 발생 시 호출 — row 없으면 생성, 있으면 카운터 증가.

    Call on dashboard insight error — creates row if absent, increments counter.
    성공 응답 캐시와 달리 expires_at 을 현재 시각으로 설정해 즉시 만료 상태 유지.
    Unlike success cache, sets expires_at = now so it never blocks a fresh retry.
    """
    now = now or datetime.now(timezone.utc)
    existing = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.repo_id.is_(None),
            InsightNarrativeCache.language == language,
        )
        .first()
    )
    if existing is not None:
        existing.last_error_at = now
        existing.error_count = (existing.error_count or 0) + 1
        existing.last_error_type = error_type
    else:
        # 에러 전용 row — response_json 은 빈 dict, expires_at = now (즉시 만료)
        # Error-only row — response_json empty dict, expires_at = now (immediately expired)
        existing = InsightNarrativeCache(
            user_id=user_id, days=days, language=language, repo_id=None,
            response_json={}, created_at=now, expires_at=now,
            last_error_at=now, error_count=1, last_error_type=error_type,
        )
        db.add(existing)
    db.commit()


def record_error_repo(
    db: Session,
    *,
    user_id: int,
    repo_id: int,
    days: int,
    language: str = "en",
    error_type: str,
    now: datetime | None = None,
) -> None:
    """리포별 insight 에러 발생 시 호출 — row 없으면 생성, 있으면 카운터 증가.

    Call on repo insight error — creates row if absent, increments counter.
    """
    now = now or datetime.now(timezone.utc)
    existing = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.user_id == user_id,
            InsightNarrativeCache.repo_id == repo_id,
            InsightNarrativeCache.days == days,
            InsightNarrativeCache.language == language,
        )
        .first()
    )
    if existing is not None:
        existing.last_error_at = now
        existing.error_count = (existing.error_count or 0) + 1
        existing.last_error_type = error_type
    else:
        existing = InsightNarrativeCache(
            user_id=user_id, repo_id=repo_id, days=days, language=language,
            response_json={}, created_at=now, expires_at=now,
            last_error_at=now, error_count=1, last_error_type=error_type,
        )
        db.add(existing)
    db.commit()


def invalidate_repo(
    db: Session,
    *,
    user_id: int,
    repo_id: int,
    days: int,
    language: str | None = None,
) -> int:
    """리포별 캐시 강제 무효화 (DELETE).

    Force invalidate repo-specific cache (DELETE).

    language=None 시 해당 (user_id, repo_id, days) 모든 언어 행 삭제.
    language=None: delete all language variants for (user_id, repo_id, days).
    Returns count of deleted rows.
    """
    q = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == user_id,
        InsightNarrativeCache.repo_id == repo_id,
        InsightNarrativeCache.days == days,
    )
    if language is not None:
        q = q.filter(InsightNarrativeCache.language == language)
    rows = q.all()
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)
