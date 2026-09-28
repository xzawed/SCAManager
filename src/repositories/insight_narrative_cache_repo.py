"""InsightNarrativeCache Repository — get / upsert / delete (1h TTL pattern).

Cycle 74 PR-B Phase 2-B 🅑 — Insight 모드 Claude AI 호출 빈도 제한 (60% 절감).
0031 — repo-scoped cache helpers 추가 (get_fresh_repo / upsert_repo / invalidate_repo).
0031 — Add repo-scoped cache helpers (get_fresh_repo / upsert_repo / invalidate_repo).
0033 — record_error / record_error_repo 추가 (에러 빈도 추적).
0033 — Add record_error / record_error_repo (error frequency tracking).
recent_error / recent_error_repo — 최근 실패면 재시도를 잠시 막는 부정 캐시.
recent_error / recent_error_repo — negative cache that briefly blocks a retry after a recent failure.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.models.insight_narrative_cache import InsightNarrativeCache
from src.shared.time_utils import to_naive_utc

# Phase 2-B sub-option default — TTL 1시간 (cross-verify 권장 보수적 default)
# Phase 2-B sub-option default — TTL 1 hour (cross-verify recommended conservative default).
DEFAULT_TTL_SECONDS = 3600

# 부정 캐시 창 — 45 s 기한에 걸린 직후의 새로 고침이 유료 시도를 또 시작하지 않을 만큼(120 s).
#   실패 행은 태어날 때 만료라 성공 캐시로는 못 막았다(새로 고침 8번 = 유료 45 s 시도 8번, 실측).
#   더 길게 잡지 않는 것은 실패 화면의 새로 고침 링크가 이 창을 넘는 길이라서다(refresh 는 행을 지운다).
# Negative-cache window: long enough that a reload right after a 45 s deadline miss does not start
#   another paid attempt (error rows are born expired, so 8 reloads were 8 paid attempts). Kept short
#   because the failure card's Refresh link is the way past it (refresh deletes the row).
NEGATIVE_TTL_SECONDS = 120


def _aware_utc(dt: datetime) -> datetime:
    """naive 는 UTC 로 간주해 aware 로, aware 는 UTC 로 — 컬럼(naive)과 서비스(aware) 값을 같은 축에 둔다.
    Treat naive as UTC and convert aware to UTC so column (naive) and service (aware) values compare.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _recent_error_type(
    row: InsightNarrativeCache | None, now: datetime | None, within_seconds: float,
) -> str | None:
    """행이 창 안의 실패를 담고 있으면 그 유형, 아니면 None — `no_data` 는 실패가 아니다.

    `no_data` 는 Claude 를 부르지 않은 기록이라 막을 유료 호출이 없고, 데이터가 생기면 곧바로 불러야 한다.
    창보다 먼 미래로 찍힌 실패(시계·세션 TZ 어긋남)는 무시한다 — 잘못된 시각이 창보다 오래 막지 않게.
    Return the recorded type when the row holds a failure inside the window, else None. `no_data` is
    not a failure (no paid call to block). A timestamp further in the future than the window (clock or
    session-TZ skew) is ignored so a bad value cannot block longer than the window.
    """
    if row is None or row.last_error_at is None:
        return None
    error_type = row.last_error_type
    if error_type is None or error_type == "no_data":
        return None
    age = _aware_utc(now or datetime.now(timezone.utc)) - _aware_utc(row.last_error_at)
    window = timedelta(seconds=within_seconds)
    if -window < age < window:
        return error_type
    return None


def _clear_error(row: InsightNarrativeCache) -> None:
    """성공이 기록되면 더 오래된 실패가 다음 조회를 막지 않게 지운다 — 누적 횟수는 남긴다.
    On success, clear the older failure so it cannot short-circuit a later read; keep the count.
    """
    row.last_error_at = None
    row.last_error_type = None


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
        _clear_error(existing)
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
    🔴 실패 행은 태어날 때 만료다 — 부정 캐시 창 안의 `last_error_at` 을 가진 행은 남긴다.
    Error rows are born expired, so rows whose `last_error_at` is inside the negative window stay.
    """
    _now = to_naive_utc(now or datetime.now(timezone.utc))
    negative_floor = _now - timedelta(seconds=NEGATIVE_TTL_SECONDS)
    deleted = (
        db.query(InsightNarrativeCache)
        .filter(
            InsightNarrativeCache.expires_at < _now,
            or_(
                InsightNarrativeCache.last_error_at.is_(None),
                InsightNarrativeCache.last_error_at < negative_floor,
            ),
        )
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
        _clear_error(existing)
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


def recent_error(
    db: Session,
    *,
    user_id: int,
    days: int,
    language: str,
    now: datetime | None = None,
    within_seconds: float = NEGATIVE_TTL_SECONDS,
) -> str | None:
    """전체 대시보드 키(repo_id IS NULL)의 창 안 실패 유형 — 없으면 None. 호출부는 적중 시 Claude 를 부르지 않는다.

    Recent failure type for the dashboard key (repo_id IS NULL), or None; callers skip Claude on a hit.
    """
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
    return _recent_error_type(row, now, within_seconds)


def recent_error_repo(
    db: Session,
    *,
    user_id: int,
    repo_id: int,
    days: int,
    language: str,
    now: datetime | None = None,
    within_seconds: float = NEGATIVE_TTL_SECONDS,
) -> str | None:
    """리포 키(user_id, repo_id, days, language)의 창 안 실패 유형 — 없으면 None.

    Recent failure type for the repo key (user_id, repo_id, days, language), or None.
    """
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
    return _recent_error_type(row, now, within_seconds)


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
    성공 응답 캐시와 달리 expires_at 을 현재 시각으로 설정해 `get_fresh` 에는 걸리지 않는다 —
    재시도를 잠시 막는 것은 `recent_error` 가 `last_error_at` 으로 따로 판정한다.
    Unlike success cache, expires_at = now so `get_fresh` never serves it; the brief retry block
    is judged separately by `recent_error` from `last_error_at`.
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
