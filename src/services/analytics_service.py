"""주간 집계, 이동 평균, 주요 이슈, chat_id 라우팅 등 분석 집계 서비스.
Analytics aggregation service — weekly summary, moving average, top issues, chat_id routing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.analysis import Analysis
from src.models.repo_config import RepoConfig
from src.models.repository import Repository

logger = logging.getLogger(__name__)


def weekly_summary(
    db: Session,
    repo_id: int,
    week_start: datetime,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """지정된 주간 시작 시각부터 7일간의 분석 요약을 반환한다.
    Return a 7-day analysis summary starting from week_start.

    Returns None if no analyses exist in the window.

    Args:
        db: SQLAlchemy 세션 / SQLAlchemy session
        repo_id: 대상 리포지토리 PK / Target repository PK
        week_start: 집계 시작 시각 (UTC 권장) / Aggregation start time (UTC recommended)
        now: 현재 시각 주입용 (테스트 고정 지원) / Injected current time (for test pinning)

    Returns:
        집계 결과 dict 또는 분석이 없으면 None
        Aggregation result dict or None if no analyses exist.
    """
    # now 기본값 설정 — 테스트에서 고정 시각 주입 가능
    # Default now — allows injecting a fixed time in tests
    _now = now or datetime.now(timezone.utc)
    week_end = week_start + timedelta(days=7)

    # week_end가 now를 초과하면 now로 clamp
    # Clamp week_end to now if it exceeds the current time
    week_end = min(week_end, _now)

    row = db.execute(
        select(
            func.count(Analysis.id).label("count"),  # pylint: disable=not-callable
            func.avg(Analysis.score).label("avg_score"),  # pylint: disable=not-callable
            func.min(Analysis.score).label("min_score"),  # pylint: disable=not-callable
            func.max(Analysis.score).label("max_score"),  # pylint: disable=not-callable
        )
        .where(Analysis.repo_id == repo_id)
        .where(Analysis.score.isnot(None))
        .where(Analysis.created_at >= week_start)
        .where(Analysis.created_at < week_end)
    ).one()

    # 분석 건수가 0이면 집계 없음 → None 반환
    # No analyses in the window → return None
    if not row.count:
        return None

    return {
        "count": row.count,
        "avg_score": round(float(row.avg_score), 1),
        "min_score": row.min_score,
        "max_score": row.max_score,
        "week_start": week_start.isoformat(),
    }


def moving_average(
    db: Session,
    repo_id: int,
    window_days: int = 7,
    *,
    min_samples: int = 5,
    now: datetime | None = None,
) -> float | None:
    """최근 window_days일 이동 평균 점수를 반환한다.
    Return the moving average score over the last window_days days.

    Returns None if fewer than min_samples analyses exist.

    Args:
        db: SQLAlchemy 세션 / SQLAlchemy session
        repo_id: 대상 리포지토리 PK / Target repository PK
        window_days: 이동 평균 윈도우 크기(일) / Window size in days
        min_samples: 최소 샘플 수 미만이면 None 반환 / Return None if below this threshold
        now: 현재 시각 주입용 (테스트 고정 지원) / Injected current time (for test pinning)

    Returns:
        이동 평균 점수(소수점 1자리) 또는 샘플 부족 시 None
        Moving average score (1 decimal place) or None when samples are insufficient.
    """
    # now 기본값 설정 — 테스트에서 고정 시각 주입 가능
    # Default now — allows injecting a fixed time in tests
    _now = now or datetime.now(timezone.utc)
    since = _now - timedelta(days=window_days)

    rows = db.scalars(
        select(Analysis.score)
        .where(Analysis.repo_id == repo_id)
        .where(Analysis.score.isnot(None))
        .where(Analysis.created_at >= since)
        .order_by(Analysis.created_at.desc())
    ).all()

    # 최소 샘플 수 미만이면 신뢰할 수 없는 평균 → None 반환
    # Fewer than min_samples → unreliable average → return None
    if len(rows) < min_samples:
        return None

    return round(sum(rows) / len(rows), 1)


def top_issues(
    db: Session,
    repo_id: int,
    days: int = 30,
    n: int = 5,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """최근 N일간 가장 자주 발생한 이슈 상위 n개를 반환한다.
    Return the top-n most frequent issues from the last `days` days.

    Parses the Analysis.result JSON on the Python side for SQLite/PG compatibility.

    Args:
        db: SQLAlchemy 세션 / SQLAlchemy session
        repo_id: 대상 리포지토리 PK / Target repository PK
        days: 집계 기간(일) / Aggregation period in days
        n: 반환할 최대 이슈 수 / Maximum number of issues to return
        now: 현재 시각 주입용 (테스트 고정 지원) / Injected current time (for test pinning)

    Returns:
        {"message": str, "count": int} dict 리스트 (빈도 내림차순)
        List of {"message": str, "count": int} dicts sorted by frequency descending.
    """
    # now 기본값 설정 — 테스트에서 고정 시각 주입 가능
    # Default now — allows injecting a fixed time in tests
    _now = now or datetime.now(timezone.utc)
    since = _now - timedelta(days=days)

    analyses = db.scalars(
        select(Analysis)
        .where(Analysis.repo_id == repo_id)
        .where(Analysis.created_at >= since)
        .where(Analysis.result.isnot(None))
    ).all()

    # result JSON에서 이슈를 Python-side 파싱 (SQLite/PG 호환)
    # Parse issues from result JSON on the Python side for SQLite/PG compatibility
    counter: dict[str, int] = {}
    for analysis in analyses:
        result = analysis.result or {}
        issues = result.get("issues", [])
        for issue in issues:
            if isinstance(issue, dict):
                # "message" 키 우선, 없으면 "code" 키 사용
                # Prefer "message" key, fall back to "code" key
                key = issue.get("message", "") or issue.get("code", "")
                if key:
                    counter[key] = counter.get(key, 0) + 1

    # 빈도 내림차순 정렬 후 상위 n개 반환
    # Sort by frequency descending and return top-n items
    sorted_issues = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    return [{"message": msg, "count": cnt} for msg, cnt in sorted_issues[:n]]


def resolve_chat_id(repo: Repository, config: RepoConfig | None) -> str | None:
    """chat_id 우선순위에 따라 Telegram 채팅 ID를 반환한다.
    Resolve the Telegram chat_id with priority:
    1. RepoConfig.notify_chat_id
    2. Repository.telegram_chat_id
    3. settings.telegram_chat_id (global fallback)
    4. None → caller must skip with WARNING log

    Args:
        repo: Repository ORM 인스턴스 / Repository ORM instance
        config: RepoConfig ORM 인스턴스 (없으면 None) / RepoConfig ORM instance (None if absent)

    Returns:
        Telegram chat_id 문자열 또는 None (전송 불가 상태)
        Telegram chat_id string or None (no valid destination).
    """
    # 1순위: RepoConfig.notify_chat_id (리포 전용 채팅 ID)
    # Priority 1: RepoConfig.notify_chat_id (repo-specific chat ID)
    if config and config.notify_chat_id:
        return config.notify_chat_id

    # 2순위: Repository.telegram_chat_id (리포 레거시 채팅 ID)
    # Priority 2: Repository.telegram_chat_id (repo-level legacy chat ID)
    if repo.telegram_chat_id:
        return repo.telegram_chat_id

    # 3순위: 전역 settings fallback
    # Priority 3: global settings fallback
    if settings.telegram_chat_id:
        return settings.telegram_chat_id

    # 모든 소스가 없음 → 호출자가 WARNING 로그 후 전송 건너뜀
    # All sources absent → caller must log WARNING and skip sending
    return None
