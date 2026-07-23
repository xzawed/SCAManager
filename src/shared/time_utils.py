"""시간 유틸 — naive/aware datetime 일관성 단일 출처 (종합감사 P2 + 2026-07-23 회고 P1-B).

Time utilities — single source for naive/aware datetime consistency.

🔴 배경: 이 저장소의 DateTime 컬럼은 전부 **naive**(`TIMESTAMP WITHOUT TIME ZONE`)인데, 서비스/
리포 계층은 `datetime.now(timezone.utc)`(aware)로 윈도우 경계를 만들어 컬럼과 비교했다. SQLite
단위 테스트는 tzinfo 를 벗겨 이 불일치를 숨기지만, PostgreSQL 세션 타임존이 UTC 가 아니면 경계가
세션-tz 에 의존해 흔들린다. #1197 이 3곳만 고쳐(정책 16 grep 전수 위반) 회고 P1-B 로 재적발됨.
The repo's DateTime columns are all naive; comparing them against aware bounds is PG session-tz
dependent (SQLite hides it by stripping tzinfo). This helper unifies the normalization.
"""
from __future__ import annotations

from datetime import datetime, timezone


def to_naive_utc(dt: datetime) -> datetime:
    """aware datetime → naive UTC(tzinfo=None); 이미 naive 면 그대로 통과.
    Convert an aware datetime to naive UTC (tzinfo=None); pass a naive datetime through unchanged.

    naive DateTime 컬럼(`TIMESTAMP WITHOUT TIME ZONE`)과 비교·삽입할 경계/값을 만들 때 경유한다.
    Use this for any bound/value that will be compared against — or inserted into — a naive column.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def now_naive_utc() -> datetime:
    """현재 UTC 시각 — naive(tzinfo=None). 리포별 `_now_naive()` 중복의 공용 대체.
    Current UTC time as naive (tzinfo=None) — shared replacement for per-repo `_now_naive()`."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
