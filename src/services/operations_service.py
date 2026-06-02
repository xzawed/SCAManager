"""operations_service — admin 운영 모니터링 KPI (Cycle 80 PR 2 신설).

5+1 cross-verify (관점 🅔 옵션 🅑) — operations 대시보드 KPI 5종:
- cache_hit_rate (claude_metrics 메모리 카운터)
- silent_cache_fallback ratio (silent fallback streak 영역)
- API 비용 추정 (estimate_claude_cost_usd)
- merge success rate (MergeAttempt aggregate 재사용)
- pipeline 단계 latency p95 (stage_metrics 영역)

Phase 1 = 메모리 카운터 영역만 (process restart 시 reset). Phase 2 영역 = DB persist
(NEW-P1-1 cross-verify — 사용처 ≥3 도달 전 정책 16 4번 원칙 부합).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.i18n.loader import get_i18n_metrics
from src.models.merge_attempt import MergeAttempt
from src.models.user import User
from src.shared.claude_metrics import (
    estimate_claude_cost_usd,
    get_cache_stats,
)


def _cache_kpi() -> dict[str, Any]:
    """cache_hit_rate + silent_fallback streak 카드 데이터.

    cache_hit_rate + silent_fallback streak card data.
    """
    stats = get_cache_stats()
    total_calls = int(stats.get("total_calls") or 0)
    cache_read = int(stats.get("cache_read_tokens") or 0)
    cache_creation = int(stats.get("cache_creation_tokens") or 0)
    input_tokens = int(stats.get("input_tokens") or 0)
    cache_hit_rate = float(stats.get("cache_hit_rate") or 0.0)

    return {
        "total_calls": total_calls,
        "cache_hit_rate_pct": round(cache_hit_rate * 100, 1),
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "input_tokens": input_tokens,
        # process restart 시 reset 명시 (사용자 인지 의무)
        # process restart resets — user awareness required
        "memory_only": True,
    }


def _api_cost_estimate(stats: dict[str, int | float]) -> dict[str, Any]:
    """API 비용 추정 — Sonnet default (가장 가능성 ↑).

    API cost estimate — Sonnet default (most likely model).
    process restart 시 reset 명시.
    """
    input_tok = int(stats.get("input_tokens") or 0)
    cache_read = int(stats.get("cache_read_tokens") or 0)
    cache_creation = int(stats.get("cache_creation_tokens") or 0)
    # output_tokens 부재 (claude_metrics 카운터 미수집) — input 의 1/8 추정 (heuristic)
    # output_tokens absent — estimated as input/8 (heuristic from cycle 72 baseline)
    output_estimate = input_tok // 8

    cost_usd = estimate_claude_cost_usd(
        model="claude-sonnet-4-6",
        input_tokens=input_tok,
        output_tokens=output_estimate,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
    )
    return {
        "estimated_usd": round(cost_usd, 4),
        "input_tokens": input_tok,
        "output_estimate": output_estimate,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "model": "claude-sonnet-4-6 (assumed default)",
    }


def _merge_kpi(db: Session, days: int = 7) -> dict[str, Any]:
    """merge success rate 카드 데이터 — 최근 N일 (auto_merge 글로벌).

    Merge success rate — last N days (global auto_merge).
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    total = db.scalar(
        select(func.count(MergeAttempt.id))  # pylint: disable=not-callable
        .where(MergeAttempt.attempted_at >= since)
    ) or 0
    success = db.scalar(
        select(func.count(MergeAttempt.id))  # pylint: disable=not-callable
        .where(MergeAttempt.attempted_at >= since)
        .where(MergeAttempt.success.is_(True))
    ) or 0
    rate = (success / total * 100) if total > 0 else 0.0
    return {
        "total_attempts": int(total),
        "success_count": int(success),
        "success_rate_pct": round(rate, 1),
        "days": days,
    }


def _i18n_language_distribution(db: Session) -> dict[str, Any]:
    """사용자 preferred_language 분포 KPI (Phase 5 PR-17 — 사이클 84).

    User preferred_language distribution KPI (Phase 5 PR-17 — Cycle 84).

    User.preferred_language NOT NULL default 'en' (alembic 0030) — 사용자 명시 결정 분포.
    """
    rows = db.execute(
        select(User.preferred_language, func.count(User.id))  # pylint: disable=not-callable
        .group_by(User.preferred_language)
    ).all()

    distribution: dict[str, int] = {}
    for lang, count in rows:
        distribution[lang or "unknown"] = int(count or 0)

    total = sum(distribution.values())
    # 비율 (%) 계산 — 0건 시 0% 반환
    # Percentage breakdown — 0% when no users
    percentages = {
        lang: round((count / total * 100), 1) if total > 0 else 0.0
        for lang, count in distribution.items()
    }
    return {
        "distribution": distribution,
        "percentages": percentages,
        "total_users": total,
    }


def _i18n_fallback_rate() -> dict[str, Any]:
    """i18n fallback rate KPI (Phase 5 PR-17 — 사이클 84).

    i18n fallback rate KPI (Phase 5 PR-17 — Cycle 84).

    fallback_rate = (lookups_fallback + lookups_missing) / lookups_total × 100
    높은 비율 = 번역 누락 영역 ↑ 의미 (운영자 액션 의무).
    Higher rate = more missing translations (operator action required).
    process restart 시 reset (memory_only). Phase 6 영역 = DB persist.
    """
    metrics = get_i18n_metrics()
    return {
        "lookups_total": metrics["lookups_total"],
        "lookups_hit": metrics["lookups_hit"],
        "lookups_fallback": metrics["lookups_fallback"],
        "lookups_missing": metrics["lookups_missing"],
        "fallback_rate_pct": metrics["fallback_rate_pct"],
        # process restart 시 reset 명시 (사용자 인지 의무)
        # process restart resets — user awareness required
        "memory_only": True,
    }


def operations_kpi(db: Session, days: int = 7) -> dict[str, Any]:
    """admin 운영 모니터링 KPI 카드 데이터 (Cycle 80 PR 2 + 사이클 84 PR-17 i18n).

    Admin operations dashboard KPI cards (Cycle 80 PR 2 + Cycle 84 PR-17 i18n).

    Phase 5 PR-17 (사이클 84) — i18n KPI 2 카드 추가:
    - language_distribution = User.preferred_language 분포 (en/ko/ja)
    - i18n_fallback = fallback rate (메모리 카운터)
    """
    stats = get_cache_stats()
    return {
        "cache": _cache_kpi(),
        "api_cost": _api_cost_estimate(stats),
        "merge": _merge_kpi(db, days=days),
        # pipeline_latency 영역 = stage_metrics 메모리 카운터 부재
        # (logger.info 만 — 사용처 ≥3 도달 후 메모리 카운터 추가 결정)
        # Phase 2 영역 (NEW-P1-1 cross-verify 정합)
        "pipeline_latency": {
            "available": False,
            "reason": "Phase 2 scope — stage_metrics in-memory counter infra not yet present",
        },
        # Phase 5 PR-17 (사이클 84) — i18n KPI 2 카드
        # Phase 5 PR-17 (Cycle 84) — i18n KPI 2 cards
        "language_distribution": _i18n_language_distribution(db),
        "i18n_fallback": _i18n_fallback_rate(),
        "days": days,
    }
