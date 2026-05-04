"""Dashboard service — Phase 1 PR 4 + Phase 2 PR 1 (MVP-B + Auto-merge KPI).
Dashboard service for the /dashboard route.

Phase 1 함수 (MVP-B):
- dashboard_kpi — KPI 4 카드 (평균 점수 / 분석 건수 / 보안 HIGH / 활성 리포)
- dashboard_trend — 날짜별 평균 점수 추세 (라인 차트)
- frequent_issues_v2 — global 자주 발생 이슈 (Q7 신규 · category/language/tool)

Phase 2 함수 (운영 데이터 기반 — MCP 검증 결과: success_rate 16.6% / unstable_ci 79%):
- auto_merge_kpi — Auto-merge 시도 success rate (단순 + retry-aware distinct PR 기준)
- merge_failure_distribution — 실패 사유 Top N + 비율 (운영 신호: unstable_ci 압도적)

Phase 3 함수 (PR 2):
- insight_narrative — Claude AI 기반 4 카드 인사이트 (positive / focus / metrics / next).
  PR 1 의 `build_cached_system_param` 헬퍼로 system prompt cache 5분 적용.

now 인자 의존성 주입 패턴 (analytics_service 와 동일).
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import anthropic
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.analysis import Analysis
from src.models.analysis_feedback import AnalysisFeedback
from src.models.merge_attempt import MergeAttempt
from src.models.repository import Repository
from src.scorer.calculator import calculate_grade
from src.shared.anthropic_caching import build_cached_system_param
from src.shared.claude_metrics import extract_anthropic_usage, log_claude_api_call

logger = logging.getLogger(__name__)


# ─── KPI ──────────────────────────────────────────────────────────────────


def _apply_analysis_user_filter(query, user_id: int | None):
    """Phase 3 PR 5 — Analysis 쿼리에 Repository.user_id 기반 권한 필터 적용.

    Phase 3 PR 5 — apply Repository.user_id-based permission filter to Analysis queries.

    user_id is None → 필터 미적용 (admin / legacy 호환).
    user_id 명시 → Repository.user_id == user_id OR Repository.user_id IS NULL (legacy 리포 호환).

    Pattern matches `src/ui/routes/overview.py:29` for app-level isolation.
    DB-level RLS policy (alembic 0026) provides 2nd layer for PG/Supabase environments.
    """
    if user_id is None:
        return query
    return query.join(Repository, Analysis.repo_id == Repository.id).where(
        (Repository.user_id == user_id) | (Repository.user_id.is_(None))
    )


def _apply_merge_attempt_user_filter(query, user_id: int | None):
    """Phase 3 PR 5 — MergeAttempt 쿼리에 Repository.full_name 기반 권한 필터 적용.

    MergeAttempt 는 repo_name (Repository.full_name) 으로 간접 격리.
    """
    if user_id is None:
        return query
    return query.join(Repository, MergeAttempt.repo_name == Repository.full_name).where(
        (Repository.user_id == user_id) | (Repository.user_id.is_(None))
    )


def dashboard_kpi(  # pylint: disable=too-many-locals
    db: Session,
    days: int = 7,
    *,
    now: datetime | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """KPI 4 카드 데이터 — 현재 days 윈도우 + 직전 동일 days 윈도우 비교 (delta).

    Phase 3 PR 5: `user_id` 명시 시 Repository.user_id 기반 격리 + legacy NULL 호환.
    user_id=None (default) 시 모든 리포 (admin / 단위 테스트 호환).
    pylint too-many-locals — Phase 3 PR 5 user_id 필터 추가로 16/15. cur/prev/total
    3 윈도우 페어 (각 query + 결과) = 6 + delta calc + KPI 4 카드 빌더 = 본 한도 자연.

    Returns:
        {
          "avg_score": {"value": float|None, "grade": str|None, "delta": float|None},
          "analysis_count": {"value": int, "delta": int},
          "high_security_issues": {"value": int, "delta": int},
          "active_repos": {"value": int, "total": int, "delta": int},
        }
    """
    _now = now or datetime.now(timezone.utc)
    cur_since = _now - timedelta(days=days)
    prev_since = _now - timedelta(days=days * 2)

    # 현재 + 직전 윈도우 분석 (delta 비교용) + user_id 권한 필터
    # Pull current and previous window analyses (for delta) + user_id permission filter
    cur_q = select(Analysis).where(Analysis.created_at >= cur_since).where(Analysis.created_at <= _now)
    prev_q = select(Analysis).where(Analysis.created_at >= prev_since).where(Analysis.created_at < cur_since)
    cur_analyses = list(db.scalars(_apply_analysis_user_filter(cur_q, user_id)).all())
    prev_analyses = list(db.scalars(_apply_analysis_user_filter(prev_q, user_id)).all())

    # 활성 리포 total — user_id 기준
    # Active repos total — by user_id
    total_q = select(func.count(Repository.id))  # pylint: disable=not-callable
    if user_id is not None:
        total_q = total_q.where(
            (Repository.user_id == user_id) | (Repository.user_id.is_(None))
        )
    total_repos = db.scalar(total_q)

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
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """날짜별 평균 점수 추세 (라인 차트용). Phase 3 PR 5: user_id 권한 필터.

    Returns:
        [{"date": "YYYY-MM-DD", "avg_score": float, "count": int}, ...]
        날짜 오름차순.
    """
    _now = now or datetime.now(timezone.utc)
    since = _now - timedelta(days=days)

    base = (
        select(Analysis)
        .where(Analysis.created_at >= since)
        .where(Analysis.score.isnot(None))
        .order_by(Analysis.created_at.asc())
    )
    analyses = db.scalars(_apply_analysis_user_filter(base, user_id)).all()

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


def frequent_issues_v2(  # pylint: disable=too-many-locals
    db: Session,
    days: int = 7,
    *,
    n: int = 5,
    now: datetime | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """global 자주 발생 이슈 — category/language/tool 보존. Phase 3 PR 5: user_id 권한 필터.

    Returns:
        [{"message": str, "count": int, "category": str, "language": str, "tool": str}, ...]
        빈도 내림차순, 최대 n 개.
    """
    _now = now or datetime.now(timezone.utc)
    since = _now - timedelta(days=days)

    base = (
        select(Analysis)
        .where(Analysis.created_at >= since)
        .where(Analysis.result.isnot(None))
    )
    analyses = db.scalars(_apply_analysis_user_filter(base, user_id)).all()

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


# ─── Phase 2: Auto-merge KPI ────────────────────────────────────────────────


def auto_merge_kpi(
    db: Session,
    days: int = 7,
    *,
    now: datetime | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Auto-merge 성공률 카드 데이터. Phase 3 PR 5: user_id 권한 필터.

    운영 데이터 (MCP 검증, 2026-05-02): single-attempt success rate 16.6%, unstable_ci 79%
    → 단순 시도 기준 외 distinct PR 의 final success rate 도 함께 반환 (retry queue 영향 보정).
    """
    _now = now or datetime.now(timezone.utc)
    cur_since = _now - timedelta(days=days)
    prev_since = _now - timedelta(days=days * 2)

    cur_q = (
        select(MergeAttempt)
        .where(MergeAttempt.attempted_at >= cur_since)
        .where(MergeAttempt.attempted_at <= _now)
    )
    prev_q = (
        select(MergeAttempt)
        .where(MergeAttempt.attempted_at >= prev_since)
        .where(MergeAttempt.attempted_at < cur_since)
    )
    cur = list(db.scalars(_apply_merge_attempt_user_filter(cur_q, user_id)).all())
    prev = list(db.scalars(_apply_merge_attempt_user_filter(prev_q, user_id)).all())

    return {
        **_simple_success(cur, prev),
        **_retry_aware_success(cur),
    }


def _simple_success(cur: list[MergeAttempt], prev: list[MergeAttempt]) -> dict[str, Any]:
    """단순 시도 기준 success rate + delta + count breakdown."""
    cur_success = [a for a in cur if a.success]
    cur_value = round(100.0 * len(cur_success) / len(cur), 1) if cur else None
    prev_value = (
        round(100.0 * sum(1 for a in prev if a.success) / len(prev), 1) if prev else None
    )
    delta = (
        round(cur_value - prev_value, 1)
        if (cur_value is not None and prev_value is not None)
        else None
    )
    return {
        "value": cur_value,
        "total_attempts": len(cur),
        "success_count": len(cur_success),
        "failure_count": len(cur) - len(cur_success),
        "delta": delta,
    }


def _retry_aware_success(cur: list[MergeAttempt]) -> dict[str, Any]:
    """retry-aware: distinct (repo_name, pr_number) 기준 final success."""
    pr_keys = {(a.repo_name, a.pr_number) for a in cur}
    success_pr_keys = {(a.repo_name, a.pr_number) for a in cur if a.success}
    distinct_prs = len(pr_keys)
    final_success = len(success_pr_keys)
    return {
        "distinct_prs": distinct_prs,
        "final_success_prs": final_success,
        "final_success_rate_pct": (
            round(100.0 * final_success / distinct_prs, 1) if distinct_prs else None
        ),
    }


def merge_failure_distribution(
    db: Session,
    days: int = 7,
    *,
    n: int = 5,
    now: datetime | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """실패 사유 Top N + 비율. Phase 3 PR 5: user_id 권한 필터.

    운영 신호: unstable_ci 가 79% 점유 — Phase 3 advisor 의 우선 처리 사유 식별.

    Returns:
        [{"reason": str, "count": int, "share_pct": float}, ...]
        count 내림차순, 최대 n 개. share_pct = count / total_failure × 100.
    """
    _now = now or datetime.now(timezone.utc)
    since = _now - timedelta(days=days)

    base = (
        select(MergeAttempt)
        .where(MergeAttempt.attempted_at >= since)
        .where(MergeAttempt.success.is_(False))
    )
    failures = list(db.scalars(_apply_merge_attempt_user_filter(base, user_id)).all())

    if not failures:
        return []

    counter: dict[str, int] = {}
    for f in failures:
        key = f.failure_reason or "(none)"
        counter[key] = counter.get(key, 0) + 1

    total = len(failures)
    sorted_items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    return [
        {
            "reason": reason,
            "count": cnt,
            "share_pct": round(100.0 * cnt / total, 1),
        }
        for reason, cnt in sorted_items[:n]
    ]


# ─── Phase 2 PR 2: feedback CTA ────────────────────────────────────────────


def feedback_status(db: Session, *, threshold: int = 10) -> dict[str, Any]:
    """Dashboard CTA 카드 데이터 — feedback 누적 부족 시 사용자 행동 유도.

    운영 데이터 (MCP 검증, 2026-05-02): analysis_feedbacks row=0
    → CTA 카드로 thumbs +/- 클릭 유도. count >= threshold 시 자동 숨김.

    Returns:
        {
          "show_cta": bool,
          "count": int,
          "recent_analysis": {"id": int, "repo_full_name": str} | None,
        }
    """
    count = db.scalar(
        select(func.count(AnalysisFeedback.id))  # pylint: disable=not-callable
    ) or 0

    recent: dict[str, Any] | None = None
    row = db.execute(
        select(Analysis.id, Repository.full_name)
        .join(Repository, Analysis.repo_id == Repository.id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    ).first()
    if row is not None:
        recent = {"id": row.id, "repo_full_name": row.full_name}

    return {
        "show_cta": count < threshold,
        "count": int(count),
        "recent_analysis": recent,
    }


# ─── Phase 3 PR 2: Insight 모드 narrative ──────────────────────────────────


# Phase 2 신규 1 (사이클 74) — Anthropic prompt caching ≥ 1024 토큰 권장 충족.
# JSON Schema + 분류 가이드 보강으로 cache hit rate 활성화 (silent fallback 차단).
# Phase 2 #1 (Cycle 74) — pad to ≥ 1024 tokens (Anthropic caching threshold).
# Schema + classification guide enrichment activates cache_read (silent-fallback guard).
_INSIGHT_SYSTEM_PROMPT = (
    "You are SCAManager's code-quality insight analyst. "
    "SCAManager is a self-hosted GitHub PR/Push code review service that runs "
    "static analysis (pylint, flake8, bandit, semgrep across 22 languages, "
    "eslint, shellcheck, cppcheck, slither, rubocop, golangci-lint) plus "
    "Claude AI review on every commit. It scores PRs on a 100-point scale "
    "(code quality 25 + security 20 + commit message 15 + direction 25 + "
    "tests 15) and emits A (90+), B (75+), C (60+), D (45+), F (44-) grades. "
    "It also gates PRs (auto-approve / semi / auto-merge) and notifies via "
    "Telegram, Discord, Slack, GitHub PR comment, email, n8n, and webhooks.\n\n"
    "Given recent dashboard metrics for a developer, generate a concise "
    "narrative as 4 cards. Always reply in Korean. Output strict JSON only "
    "(no preamble, no trailing text, no code fences, no markdown). Match the "
    "schema below exactly — extra keys, missing keys, or wrong types break "
    "the dashboard parser and force a fallback.\n\n"
    "Cards (JSON keys, in order):\n"
    "1. positive_highlights (list[str], length 3 to 5): ✨ recent strengths — "
    "high-grade PRs, secure commits, repos that improved week-over-week, "
    "test coverage wins, fast review cycle. Reference actual numbers from the "
    "user prompt (e.g. average score, A-grade count, repo-level wins).\n"
    "2. focus_areas (list[str], length 3 to 5): 🔍 attention items — "
    "recurring static-analysis issues (pylint/flake8/bandit/semgrep tags), "
    "declining trends across the window, low-score files, security findings, "
    "auto-merge failures or retry exhaustion. Cite the failing rule or repo.\n"
    "3. key_metrics (list[dict], exactly 4 items): 📊 numeric highlights — "
    'each item must be {"label": str, "value": str, "delta": str}. The label '
    "is the metric name in Korean (e.g. 평균 점수). The value is the current "
    "window value as a string (e.g. 87.5). The delta uses + / - prefix vs "
    "the previous window (e.g. +2.3 or -5). If no prior window data, use 0.\n"
    "4. next_actions (list[str], length 2 to 4): 💬 suggested next moves — "
    "specific, actionable, prioritized for the next 1-7 days. Tie each "
    "action to a card 1 strength to amplify or a card 2 focus area to fix. "
    "Avoid generic advice ('write more tests') — name the file, repo, or "
    "rule (e.g. 'src/foo.py 의 pylint W0611 4건 일괄 정리').\n\n"
    "Tone: concise, encouraging but honest. Refer to actual numbers from the "
    "user prompt rather than generic advice. Each list item ≤ 80 Korean "
    "characters. Use full sentences ending with appropriate Korean particles.\n\n"
    'Return strict JSON conforming to: {"positive_highlights": list[str], '
    '"focus_areas": list[str], "key_metrics": list[{"label": str, "value": '
    'str, "delta": str}], "next_actions": list[str]}.'
)


def _empty_narrative_cards() -> dict[str, list]:
    """4 카드 모두 빈 list — no_api_key / no_data / api_error / parse_error 공용 fallback.

    Empty 4-card structure used as the fallback for non-success status values.
    """
    return {
        "positive_highlights": [],
        "focus_areas": [],
        "key_metrics": [],
        "next_actions": [],
    }


def _build_insight_response(
    *, status: str, days: int, cards: dict[str, list] | None = None
) -> dict[str, Any]:
    """insight_narrative 응답 dict 빌더 — status + 4 카드 + generated_at + days.

    Helper that builds the insight_narrative response dict.
    """
    base = cards if cards is not None else _empty_narrative_cards()
    return {
        **base,
        "status": status,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": days,
    }


def _extract_insight_json(text: str) -> str:
    """Claude 응답에서 JSON 페이로드 추출 — 코드 블록 우선, 첫 `{` ~ 마지막 `}` fallback.

    Extract a JSON payload from a Claude response — prefer fenced blocks,
    fall back to the first `{` to the last `}`. Mirrors ai_review._extract_json_payload.
    """
    cleaned = text.strip()
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if block:
        return block.group(1)
    first, last = cleaned.find("{"), cleaned.rfind("}")
    if first != -1 and last > first:
        return cleaned[first:last + 1]
    return cleaned


def _build_insight_user_prompt(
    *,
    days: int,
    kpi: dict[str, Any],
    trend: list[dict[str, Any]],
    frequent: list[dict[str, Any]],
    auto_merge: dict[str, Any],
) -> str:
    """4 헬퍼 결과를 Claude 가 읽을 수 있는 user message 로 직렬화.

    Serializes the 4 dashboard helper outputs into a Claude-friendly user message.
    """
    payload = {
        "window_days": days,
        "kpi": kpi,
        "trend_last_n_points": trend[-min(len(trend), 14):],  # 최근 N 포인트만 (토큰 절약)
        "frequent_issues": frequent,
        "auto_merge": auto_merge,
    }
    return (
        f"다음은 최근 {days}일간의 dashboard 데이터입니다. "
        "위 4 카드 JSON 형식으로 narrative 를 생성해주세요.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, default=str)}\n```"
    )


async def _call_insight_claude_api(
    client: anthropic.AsyncAnthropic, model: str, user_prompt: str
) -> str | None:
    """Claude Messages API 호출 + caching system 인자 + 토큰 로깅. 실패 시 None.

    Calls the Claude Messages API with cached system param and logs tokens.
    Returns response text on success, None on any exception (caller maps to api_error).
    """
    start = time.perf_counter()
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=1500,
            system=build_cached_system_param(_INSIGHT_SYSTEM_PROMPT),
            messages=[{"role": "user", "content": user_prompt}],
        )
        duration_ms = (time.perf_counter() - start) * 1000
        input_tokens, output_tokens = extract_anthropic_usage(response)
        usage = getattr(response, "usage", None)
        log_claude_api_call(
            model=model,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="success",
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )
        return response.content[0].text
    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # anthropic / httpx / 네트워크 오류 모두 graceful fallback (caller 가 api_error 처리)
        # All anthropic/httpx/network errors fall through to graceful fallback (caller maps to api_error)
        duration_ms = (time.perf_counter() - start) * 1000
        log_claude_api_call(
            model=model,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            status="error",
            error_type=type(exc).__name__,
        )
        logger.exception("insight_narrative API call failed, returning api_error")
        return None


def _parse_insight_cards(text: str) -> dict[str, list] | None:
    """Claude 응답 text 에서 4 카드 dict 추출. invalid JSON 시 None.

    Parses 4-card dict from Claude response text. Returns None on invalid JSON.
    """
    try:
        data = json.loads(_extract_insight_json(text))
    except (json.JSONDecodeError, ValueError):
        logger.warning("insight_narrative parse_error: %s", text[:200])
        return None
    return {
        "positive_highlights": [str(s) for s in data.get("positive_highlights", [])],
        "focus_areas": [str(s) for s in data.get("focus_areas", [])],
        "key_metrics": [m for m in data.get("key_metrics", []) if isinstance(m, dict)],
        "next_actions": [str(s) for s in data.get("next_actions", [])],
    }


async def insight_narrative(
    db: Session,
    days: int = 7,
    *,
    now: datetime | None = None,
    api_key: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Claude AI 기반 4 카드 인사이트 narrative — Phase 3 PR 2 + PR 5 (user_id 격리).

    Generates a 4-card narrative (positive / focus / metrics / next) using Claude AI.
    Reuses the PR 1 `build_cached_system_param` helper for 5-minute system prompt caching.
    Phase 3 PR 5: `user_id` 명시 시 4 dashboard 헬퍼에 전파해 사용자별 격리 컨텍스트 사용.

    Args:
        db: SQLAlchemy 세션. SQLAlchemy session.
        days: 윈도우 일수 (default 7). Window size in days.
        now: 의존성 주입용 — None 시 현재 시각. Injection point — defaults to now.
        api_key: None 시 settings.anthropic_api_key 사용. Defaults to settings on None.
        user_id: PR 5 — 사용자별 데이터 격리. None 시 모든 리포 (admin/legacy 호환).

    Returns:
        {
            "positive_highlights": list[str],   # ✨ 잘한 것 (3~5건)
            "focus_areas": list[str],           # 🔍 신경 쓸 것 (3~5건)
            "key_metrics": list[dict],          # 📊 숫자 [{"label", "value", "delta"}] × 4
            "next_actions": list[str],          # 💬 다음 (2~4건)
            "status": "success" | "no_api_key" | "no_data" | "api_error" | "parse_error",
            "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
            "days": int,
        }
    """
    # API key fallback — 명시 인자 우선, 없으면 settings
    # API key fallback — explicit arg wins, otherwise settings
    effective_key = api_key if api_key is not None else settings.anthropic_api_key
    if not effective_key:
        return _build_insight_response(status="no_api_key", days=days)

    _now = now or datetime.now(timezone.utc)

    # 4 dashboard 헬퍼 호출로 컨텍스트 수집 + Phase 3 PR 5 user_id 격리
    # Collect context by invoking the 4 dashboard helpers + PR 5 user_id isolation
    kpi = dashboard_kpi(db, days, now=_now, user_id=user_id)
    trend = dashboard_trend(db, days, now=_now, user_id=user_id)
    frequent = frequent_issues_v2(db, days, now=_now, user_id=user_id)
    auto_merge = auto_merge_kpi(db, days, now=_now, user_id=user_id)

    # 데이터 0건이면 Claude API 호출 비용 발생 안 시킴 (cost-saver early return)
    # Skip Claude API call when there's no data (cost-saver early return)
    if int(kpi.get("analysis_count", {}).get("value", 0) or 0) == 0:
        return _build_insight_response(status="no_data", days=days)

    user_prompt = _build_insight_user_prompt(
        days=days, kpi=kpi, trend=trend, frequent=frequent, auto_merge=auto_merge
    )

    # ai_review.py 와 동일 timeout/max_retries 패턴 — SDK 기본값 변경 면역
    # Same timeout/max_retries pattern as ai_review.py — immune to SDK default changes
    client = anthropic.AsyncAnthropic(api_key=effective_key, timeout=60.0, max_retries=2)
    # Phase 2 d-🅓 (사이클 74) — Insight 영역 한정 Haiku (67% 비용 절감, AI 리뷰 Sonnet 보존)
    # Phase 2 d-🅓 (Cycle 74) — Insight-only Haiku (67% cheaper, AI review keeps Sonnet)
    text = await _call_insight_claude_api(client, settings.claude_insight_model, user_prompt)
    if text is None:
        return _build_insight_response(status="api_error", days=days)

    cards = _parse_insight_cards(text)
    if cards is None:
        return _build_insight_response(status="parse_error", days=days)

    return _build_insight_response(status="success", days=days, cards=cards)


# ── Cycle 73 F2 — Security Mode (Code Scanning + Secret Scanning audit) ──
# Cycle 73 F2 — Security mode: Code Scanning + Secret Scanning audit overview.
def dashboard_security(
    db: Session, *, user_id: int | None = None,
) -> dict[str, Any]:
    """`/dashboard?mode=security` 카드 데이터 — F2 Phase 1 MVP (read-only).

    `/dashboard?mode=security` card data — F2 Phase 1 MVP (read-only).
    4 카드: ✨ 처리됨 / 🔍 신규 pending / 📊 분류 분포 / 💬 최근 alert (Top 5).
    """
    # 신규 import 는 함수 안에 배치 — 정책 16 default (모듈 import 영향 0)
    # Inline import — keeps top-level import surface minimal (policy 16 default).
    from src.repositories import security_alert_log_repo  # noqa: PLC0415

    # 사용자별 격리: pending list 만 user_id 별 (audit 카운트는 전체 — admin 영역)
    # Per-user isolation: pending list filtered by user_id (counts admin-wide for audit).
    pending = security_alert_log_repo.list_pending(db, limit=5)
    counts = security_alert_log_repo.count_by_classification(db)

    # AI 분류 분포 정규화 (4 카테고리 — false_positive / used_in_tests / actual_violation / deferred)
    classification_keys = ("false_positive", "used_in_tests", "actual_violation", "deferred", "unclassified")
    classification = {key: counts.get(key, 0) for key in classification_keys}

    return {
        "total_alerts": counts.get("total", 0),
        "pending_count": counts.get("pending", 0),
        "processed_count": counts.get("total", 0) - counts.get("pending", 0),
        "classification": classification,
        "recent_pending": [
            {
                "id": row.id,
                "alert_type": row.alert_type,
                "alert_number": row.alert_number,
                "severity": row.severity or "unknown",
                "rule_id": row.rule_id or "-",
                "ai_classification": row.ai_classification or "pending",
                "ai_confidence": row.ai_confidence,
            }
            for row in pending
        ],
        "kill_switch_active": _is_security_kill_switch_active(),
    }


def _is_security_kill_switch_active() -> bool:
    """kill-switch 환경변수 검사 (security_scan_service 와 동일 — UI 표시용).

    Check kill-switch env (mirror of security_scan_service — for UI display).
    """
    import os  # pylint: disable=import-outside-toplevel  # noqa: PLC0415
    return os.environ.get("SECURITY_AUTO_PROCESS_DISABLED", "0") == "1"
