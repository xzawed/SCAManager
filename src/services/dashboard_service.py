"""Dashboard service — Phase 1 PR 4 (MVP-B 신규 함수).
Dashboard service for the new /dashboard route (replaces deprecated /insights/*).

함수 3종:
- dashboard_kpi(db, days, *, now) -> KPI 4 카드 (평균 점수 / 분석 건수 / 보안 HIGH / 활성 리포)
- dashboard_trend(db, days, *, now) -> 날짜별 평균 점수 추세 (라인 차트)
- frequent_issues_v2(db, days, *, n, now) -> global 자주 발생 이슈 (Q7 신규 — category/language/tool 포함)

기존 analytics_service 의 (top_issues / author_trend / repo_comparison / leaderboard) 폐기 4종을 대체하는
새 데이터 모델. now 인자 의존성 주입 패턴 (analytics_service 와 동일) — freezegun 미사용.

Replaces deprecated analytics_service.{top_issues,author_trend,repo_comparison,leaderboard}.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.analysis import Analysis
from src.models.repository import Repository
from src.scorer.calculator import calculate_grade


# ─── KPI ──────────────────────────────────────────────────────────────────


def dashboard_kpi(
    db: Session,
    days: int = 7,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """KPI 4 카드 데이터 — 현재 days 윈도우 + 직전 동일 days 윈도우 비교 (delta).

    Returns:
        {
          "avg_score": {"value": float|None, "grade": str|None, "delta": float|None},
          "analysis_count": {"value": int, "delta": int},
          "high_security_issues": {"value": int, "delta": int},
          "active_repos": {"value": int, "total": int, "delta": int},
        }

    delta = 현재 윈도우 - 직전 윈도우 (양수 = 개선, 단 high_security_issues 는 음수가 개선).
    """
    _now = now or datetime.now(timezone.utc)
    cur_since = _now - timedelta(days=days)
    prev_since = _now - timedelta(days=days * 2)

    # 현재 + 직전 윈도우 분석 (delta 비교용)
    # Pull current and previous window analyses (for delta comparison)
    cur_analyses = list(db.scalars(
        select(Analysis)
        .where(Analysis.created_at >= cur_since)
        .where(Analysis.created_at <= _now)
    ).all())
    prev_analyses = list(db.scalars(
        select(Analysis)
        .where(Analysis.created_at >= prev_since)
        .where(Analysis.created_at < cur_since)
    ).all())

    total_repos = db.scalar(select(func.count(Repository.id)))  # pylint: disable=not-callable

    return {
        "avg_score": _kpi_avg(cur_analyses, prev_analyses),
        "analysis_count": {
            "value": len(cur_analyses),
            "delta": len(cur_analyses) - len(prev_analyses),
        },
        "high_security_issues": _kpi_security(cur_analyses, prev_analyses),
        "active_repos": _kpi_active_repos(cur_analyses, prev_analyses, int(total_repos or 0)),
    }


def _kpi_avg(cur: list[Analysis], prev: list[Analysis]) -> dict[str, Any]:
    """평균 점수 + 등급 + delta 카드 빌더."""
    cur_scored = [a.score for a in cur if a.score is not None]
    prev_scored = [a.score for a in prev if a.score is not None]
    avg_value = round(sum(cur_scored) / len(cur_scored), 1) if cur_scored else None
    prev_avg = round(sum(prev_scored) / len(prev_scored), 1) if prev_scored else None
    grade = calculate_grade(int(avg_value)) if avg_value is not None else None
    delta = (
        round(avg_value - prev_avg, 1) if (avg_value is not None and prev_avg is not None) else None
    )
    return {"value": avg_value, "grade": grade, "delta": delta}


def _kpi_security(cur: list[Analysis], prev: list[Analysis]) -> dict[str, int]:
    """보안 HIGH 이슈 카운트 + delta 카드 빌더."""
    cur_high = _count_high_security(cur)
    return {"value": cur_high, "delta": cur_high - _count_high_security(prev)}


def _kpi_active_repos(
    cur: list[Analysis], prev: list[Analysis], total: int
) -> dict[str, int]:
    """활성 리포 수 + 전체 + delta 카드 빌더."""
    cur_active = len({a.repo_id for a in cur})
    return {
        "value": cur_active,
        "total": total,
        "delta": cur_active - len({a.repo_id for a in prev}),
    }


def _count_high_security(analyses: list[Analysis]) -> int:
    """Analysis.result['issues'] JSON 중 category=security AND severity=HIGH 카운트.

    PR #185 회귀 가드로 issues JSON 에 category/severity 필드 보장됨.
    """
    total = 0
    for a in analyses:
        result = a.result or {}
        for issue in result.get("issues", []):
            if not isinstance(issue, dict):
                continue
            if issue.get("category") == "security" and issue.get("severity", "").upper() == "HIGH":
                total += 1
    return total


# ─── 추세 (라인 차트) ─────────────────────────────────────────────────────


def dashboard_trend(
    db: Session,
    days: int = 7,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """날짜별 평균 점수 추세 (라인 차트용).

    Returns:
        [{"date": "YYYY-MM-DD", "avg_score": float, "count": int}, ...]
        날짜 오름차순.
    """
    _now = now or datetime.now(timezone.utc)
    since = _now - timedelta(days=days)

    analyses = db.scalars(
        select(Analysis)
        .where(Analysis.created_at >= since)
        .where(Analysis.score.isnot(None))
        .order_by(Analysis.created_at.asc())
    ).all()

    # Python-side 날짜별 그룹화 — SQLite/PG 날짜 함수 불일치 회피
    daily: dict[str, list[int]] = {}
    for a in analyses:
        date_str = a.created_at.strftime("%Y-%m-%d") if a.created_at else ""
        if date_str:
            daily.setdefault(date_str, []).append(a.score)

    return [
        {
            "date": date_str,
            "avg_score": round(sum(scores) / len(scores), 1),
            "count": len(scores),
        }
        for date_str, scores in sorted(daily.items())
    ]


# ─── 자주 발생 이슈 (Q7 신규) ─────────────────────────────────────────────


def frequent_issues_v2(
    db: Session,
    days: int = 7,
    *,
    n: int = 5,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """global 자주 발생 이슈 — category/language/tool 보존.

    폐기된 top_issues 와 차이:
    - repo_id 인자 제거 (global 집계)
    - category/language/tool 필드 반환

    Returns:
        [{"message": str, "count": int, "category": str, "language": str, "tool": str}, ...]
        빈도 내림차순, 최대 n 개.
    """
    _now = now or datetime.now(timezone.utc)
    since = _now - timedelta(days=days)

    analyses = db.scalars(
        select(Analysis)
        .where(Analysis.created_at >= since)
        .where(Analysis.result.isnot(None))
    ).all()

    # message 키로 카운트 + 첫 번째 발견 시점의 category/language/tool 저장
    counter: dict[str, int] = {}
    meta: dict[str, dict[str, str]] = {}
    for a in analyses:
        result = a.result or {}
        for issue in result.get("issues", []):
            if not isinstance(issue, dict):
                continue
            key = issue.get("message") or issue.get("code")
            if not key:
                continue
            counter[key] = counter.get(key, 0) + 1
            if key not in meta:
                meta[key] = {
                    "category": issue.get("category", ""),
                    "language": issue.get("language", ""),
                    "tool": issue.get("tool", ""),
                }

    sorted_items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    return [
        {
            "message": msg,
            "count": cnt,
            "category": meta[msg]["category"],
            "language": meta[msg]["language"],
            "tool": meta[msg]["tool"],
        }
        for msg, cnt in sorted_items[:n]
    ]
