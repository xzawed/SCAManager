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

from src.models.merge_attempt import MergeAttempt
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
        "model": "claude-sonnet-4-6 (default 추정)",
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


def operations_kpi(db: Session, days: int = 7) -> dict[str, Any]:
    """admin 운영 모니터링 KPI 5 카드 데이터 (Cycle 80 PR 2).

    Admin operations dashboard KPI 5 cards (Cycle 80 PR 2).
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
            "reason": "Phase 2 영역 — stage_metrics 메모리 카운터 인프라 부재 (정책 16 4번 원칙)",
        },
        "days": days,
    }
