"""operations_service — admin 운영 모니터링 KPI (Cycle 80 PR 2 신설).

5+1 cross-verify (관점 🅔 옵션 🅑) — operations 대시보드 KPI 5종:
- cache_hit_rate (claude_metrics 메모리 카운터)
- silent_cache_fallback ratio (silent fallback streak 영역)
- API 비용 — 최근 N일 claude_api_calls 실측 합 (DB · 재배포해도 유지)
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
from src.repositories import claude_api_cost_repo, merge_attempt_repo
from src.models.user import User
from src.shared.claude_metrics import get_cache_stats
from src.shared.time_utils import to_naive_utc


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


def _api_cost_kpi(db: Session, days: int = 7) -> dict[str, Any]:
    """API 비용 카드 — 최근 N일 `claude_api_calls` 에 기록된 호출의 실측 합(전체 테넌트).

    API cost card — totals of the calls recorded in `claude_api_calls` over the last N days.
    호출마다 기록 경로가 실제 토큰과 그 모델의 요율로 매긴 비용을 더할 뿐이다 — 모델을 가정하거나 출력 토큰을 짓지 않고,
    DB 에 있어 재배포해도 유지된다(사용자 11-17 결정 «실측 합으로»).
    Sums what was recorded per call; no assumed model, no invented output tokens; survives redeploys.
    """
    # naive UTC — ClaudeApiCall.created_at 은 naive 컬럼 / naive column
    until = to_naive_utc(datetime.now(timezone.utc))
    totals = claude_api_cost_repo.window_totals(db, since=until - timedelta(days=days), until=until)
    return {
        "recorded_usd": round(totals["cost_usd"], 4),
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "call_count": totals["call_count"],
        "days": days,
    }


def _merge_kpi(db: Session, days: int = 7) -> dict[str, Any]:
    """merge success rate 카드 데이터 — 최근 N일 (auto_merge 글로벌).

    Merge success rate — last N days (global auto_merge).
    """
    # naive UTC — MergeAttempt.attempted_at 은 naive 컬럼 (회고 P1-B grep 전수)
    # naive UTC — attempted_at is a naive column
    since = to_naive_utc(datetime.now(timezone.utc)) - timedelta(days=days)
    total = db.scalar(
        select(func.count(MergeAttempt.id))  # pylint: disable=not-callable
        .where(MergeAttempt.attempted_at >= since)
    ) or 0
    # 🔴 `success.is_(True)` 가 아니다 — 그것은 「GitHub 호출이 성공했다」이지 「머지됐다」가
    #    아니다. auto-merge 를 **켜기만** 한 행도 success=True 이고, 그 PR 은 영영 머지되지
    #    않을 수 있다. 판정 정의는 `_merge_attempt_states.is_merged` 한 곳이다.
    #    Counting `success` would include merges that were only *enabled*.
    success = db.scalar(
        select(func.count(MergeAttempt.id))  # pylint: disable=not-callable
        .where(MergeAttempt.attempted_at >= since)
        .where(merge_attempt_repo.merged_sql_predicate())
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
    return {
        "cache": _cache_kpi(),
        "api_cost": _api_cost_kpi(db, days=days),
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
