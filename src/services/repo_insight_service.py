"""리포별 코드 인사이트 서비스 — 5 집계 함수 + AI narrative.

Repository-level code insight service — 5 aggregation functions + AI narrative.

모든 집계 함수는 Analysis.result JSON을 Python-side 루프로 처리 (최근 30건 상한).
All aggregation functions process Analysis.result JSON Python-side (max 30 rows).
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.analysis import Analysis
from src.scorer.calculator import calculate_grade
from src.shared.claude_metrics import extract_anthropic_usage, log_claude_api_call
from src.shared.lang_names import LANG_NAMES

logger = logging.getLogger(__name__)

# 집계 최대 분석 건수 — Python 루프 O(N×이슈수) 상한
# Max analyses per aggregation — caps Python loop O(N×issues)
_MAX_ANALYSES = 30


def _fetch_analyses(
    db: Session, repo_id: int, days: int, now: datetime
) -> list[Analysis]:
    """최근 days 내 분석 최대 _MAX_ANALYSES 건 조회 (created_at 내림차순).

    Fetch up to _MAX_ANALYSES analyses within `days` window, newest first.
    """
    since = now - timedelta(days=days)
    return list(
        db.scalars(
            select(Analysis)
            .where(Analysis.repo_id == repo_id)
            .where(Analysis.created_at >= since)
            .where(Analysis.created_at <= now)
            .where(Analysis.result.isnot(None))
            .order_by(Analysis.created_at.desc())
            .limit(_MAX_ANALYSES)
        ).all()
    )


def compute_score_kpi(
    cur: list,
    prev: list,
) -> tuple[float | None, float | None, str]:
    """평균점수/score_delta/등급 계산 공유 헬퍼.
    Shared helper: compute avg_score, score_delta, grade from two analysis lists.
    """
    cur_scores = [a.score for a in cur if a.score is not None]
    prev_scores = [a.score for a in prev if a.score is not None]
    avg_score = round(sum(cur_scores) / len(cur_scores), 1) if cur_scores else None
    prev_avg = round(sum(prev_scores) / len(prev_scores), 1) if prev_scores else None
    score_delta = (
        round(avg_score - prev_avg, 1)
        if (avg_score is not None and prev_avg is not None)
        else None
    )
    grade = calculate_grade(int(avg_score)) if avg_score is not None else "?"
    return avg_score, score_delta, grade


def repo_kpi(  # pylint: disable=too-many-locals
    db: Session, repo_id: int, days: int = 30, now: datetime | None = None
) -> dict[str, Any]:
    """KPI 4종 — 평균 점수/등급/분석수/최다 반복 이슈/보안 HIGH/점수 delta.

    Returns KPI dict with avg_score, grade, analysis_count, top_recurring_issue,
    top_recurring_count, high_security_count, score_delta.
    """
    _now = now or datetime.now(timezone.utc)
    cur = _fetch_analyses(db, repo_id, days, _now)

    # 직전 동일 기간 (delta 비교용)
    # Previous identical window for delta comparison
    prev_since = _now - timedelta(days=days * 2)
    prev_until = _now - timedelta(days=days)
    prev = list(
        db.scalars(
            select(Analysis)
            .where(Analysis.repo_id == repo_id)
            .where(Analysis.created_at >= prev_since)
            .where(Analysis.created_at < prev_until)
            .where(Analysis.result.isnot(None))
            .limit(_MAX_ANALYSES)
        ).all()
    )

    avg_score, score_delta, grade = compute_score_kpi(cur, prev)

    # 이슈 빈도 카운트
    # Issue frequency count
    issue_counter: dict[str, int] = {}
    high_security = 0
    for a in cur:
        for issue in (a.result or {}).get("issues", []):
            if not isinstance(issue, dict):
                continue
            key = issue.get("message") or issue.get("code")
            if key:
                issue_counter[key] = issue_counter.get(key, 0) + 1
            if (
                issue.get("category") == "security"
                and issue.get("severity", "").upper() in ("HIGH", "ERROR")
            ):
                high_security += 1

    top_issue, top_count = None, 0
    if issue_counter:
        top_issue, top_count = max(issue_counter.items(), key=lambda x: x[1])

    return {
        "avg_score": avg_score,
        "grade": grade,
        "analysis_count": len(cur),
        "top_recurring_issue": top_issue,
        "top_recurring_count": top_count,
        "high_security_count": high_security,
        "score_delta": score_delta,
    }


def repo_score_trend(
    db: Session, repo_id: int, days: int = 30, now: datetime | None = None
) -> list[dict[str, Any]]:
    """날짜별 평균 점수 시계열 — 트렌드 차트용.

    Returns daily avg score series for trend chart.
    Bins analyses by date (UTC), oldest first.
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    # 날짜별 점수 집계 (KST 아닌 UTC 기준)
    # Group scores by date (UTC)
    buckets: dict[str, list[float]] = {}
    for a in analyses:
        if a.score is None:
            continue
        date_key = a.created_at.strftime("%Y-%m-%d") if a.created_at else "unknown"
        buckets.setdefault(date_key, []).append(float(a.score))

    return [
        {
            "date": date_key,
            "avg_score": round(sum(scores) / len(scores), 1),
            "count": len(scores),
        }
        for date_key, scores in sorted(buckets.items())
    ]


def repo_recurring_issues(
    db: Session, repo_id: int, days: int = 30, n: int = 10, now: datetime | None = None
) -> list[dict[str, Any]]:
    """이슈 빈도 Top N — category/severity/tool/language 포함, 빈도 내림차순.

    Top N issues by frequency, sorted descending.
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counter: dict[str, int] = {}
    meta: dict[str, dict[str, str]] = {}
    for a in analyses:
        for issue in (a.result or {}).get("issues", []):
            if not isinstance(issue, dict):
                continue
            key = issue.get("message") or issue.get("code")
            if not key:
                continue
            counter[key] = counter.get(key, 0) + 1
            if key not in meta:
                meta[key] = {
                    "category": issue.get("category", ""),
                    "severity": issue.get("severity", ""),
                    "tool": issue.get("tool", ""),
                    "language": issue.get("language", ""),
                }

    return [
        {
            "message": msg,
            "count": cnt,
            "category": meta[msg]["category"],
            "severity": meta[msg]["severity"],
            "tool": meta[msg]["tool"],
            "language": meta[msg]["language"],
        }
        for msg, cnt in sorted(counter.items(), key=lambda x: x[1], reverse=True)[:n]
    ]


def repo_problem_files(
    db: Session, repo_id: int, days: int = 30, n: int = 5, now: datetime | None = None
) -> list[dict[str, Any]]:
    """문제 파일 Top N — file_feedbacks[].file 빈도 집계 + 프로그레스 바용 pct.

    Top N problem files by frequency, with pct relative to max count.
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counter: dict[str, int] = {}
    for a in analyses:
        for fb in (a.result or {}).get("file_feedbacks", []):
            if not isinstance(fb, dict):
                continue
            fname = fb.get("file")
            if fname:
                counter[fname] = counter.get(fname, 0) + 1

    if not counter:
        return []

    sorted_items = sorted(counter.items(), key=lambda x: x[1], reverse=True)[:n]
    max_count = sorted_items[0][1]
    return [
        {"file": fname, "count": cnt, "pct": round(cnt / max_count * 100)}
        for fname, cnt in sorted_items
    ]


def repo_ai_suggestions(
    db: Session, repo_id: int, days: int = 30, n: int = 10, now: datetime | None = None
) -> list[dict[str, Any]]:
    """AI 제안 Top N — 60자 prefix 그룹화, ai_review_status=success 분석만 포함.

    Top N AI suggestions grouped by 60-char prefix, success analyses only.
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counter: dict[str, int] = {}
    for a in analyses:
        if (a.result or {}).get("ai_review_status") != "success":
            continue
        for suggestion in (a.result or {}).get("ai_suggestions", []):
            if not isinstance(suggestion, str) or not suggestion.strip():
                continue
            prefix = suggestion[:60]
            counter[prefix] = counter.get(prefix, 0) + 1

    return [
        {"suggestion": prefix, "count": cnt}
        for prefix, cnt in sorted(counter.items(), key=lambda x: x[1], reverse=True)[:n]
    ]


def repo_category_breakdown(
    db: Session, repo_id: int, days: int = 30, now: datetime | None = None
) -> dict[str, int]:
    """이슈 카테고리×심각도 4-way 분포 — Chart.js 도넛용.

    4-way issue distribution for Chart.js donut chart.
    """
    _now = now or datetime.now(timezone.utc)
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counts: dict[str, int] = {
        "security_error": 0,
        "security_warning": 0,
        "code_quality_error": 0,
        "code_quality_warning": 0,
    }
    for a in analyses:
        for issue in (a.result or {}).get("issues", []):
            if not isinstance(issue, dict):
                continue
            category = issue.get("category", "")
            severity = issue.get("severity", "").lower()
            is_error = severity in ("error", "high")
            if category == "security":
                counts["security_error" if is_error else "security_warning"] += 1
            elif category == "code_quality":
                counts["code_quality_error" if is_error else "code_quality_warning"] += 1

    counts["total"] = sum(counts.values())
    return counts


# ─── AI 내러티브 ──────────────────────────────────────────────────────────


def _extract_narrative_json(text: str) -> str:
    """Claude 응답에서 JSON 추출 — 코드 블록 우선, {~} fallback.

    Extract JSON from Claude response — prefer fenced block, fallback to braces.
    """
    cleaned = text.strip()
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if block:
        return block.group(1)
    first, last = cleaned.find("{"), cleaned.rfind("}")
    if first != -1 and last > first:
        return cleaned[first : last + 1]  # noqa: E203
    return cleaned


async def repo_insight_narrative(  # pylint: disable=too-many-arguments,too-many-locals
    db: Session,
    repo_id: int,
    days: int = 30,
    *,
    repo_full_name: str = "",
    kpi: dict[str, Any],
    recurring: list[dict[str, Any]],
    now: datetime | None = None,
    refresh: bool = False,
    user_id: int | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """리포별 Claude AI 진단 내러티브 — 1h TTL 캐시 + refresh 지원.

    Repo-level Claude AI narrative — 1h TTL cache + refresh support.
    Returns: {"text": str, "status": "success"|"no_api_key"|"no_data"|"api_error"}
    """
    api_key = settings.anthropic_api_key
    if not api_key:
        return {"text": "", "status": "no_api_key"}

    _now = now or datetime.now(timezone.utc)

    if user_id is not None:
        # pylint: disable=import-outside-toplevel
        from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415

        if refresh:
            insight_narrative_cache_repo.invalidate_repo(
                db, user_id=user_id, repo_id=repo_id, days=days
            )
        else:
            cached = insight_narrative_cache_repo.get_fresh_repo(
                db, user_id=user_id, repo_id=repo_id, days=days, language=language, now=_now,
            )
            if cached:
                return cached

    if not kpi.get("analysis_count"):
        if user_id is not None:
            from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
            insight_narrative_cache_repo.record_error_repo(
                db, user_id=user_id, repo_id=repo_id, days=days,
                language=language, error_type="no_data", now=_now,
            )
        return {"text": "", "status": "no_data"}

    user_prompt = (
        f"Repository: {repo_full_name}\n"
        f"Period: last {days} days\n"
        f"Avg score: {kpi.get('avg_score')} ({kpi.get('grade')}), "
        f"delta: {kpi.get('score_delta')}\n"
        f"Analyses: {kpi.get('analysis_count')}\n"
        f"Security HIGH: {kpi.get('high_security_count')}\n"
        f"Top recurring issue: {kpi.get('top_recurring_issue')} "
        f"({kpi.get('top_recurring_count')} times)\n"
        f"Top 5 issues: {json.dumps(recurring[:5], ensure_ascii=False)}\n\n"
        f"Please provide a 2-3 paragraph diagnostic narrative "
        f"in {LANG_NAMES.get(language, 'Korean')} summarizing "
        "this repository's code quality status, key recurring problems, and concrete "
        "next steps. Respond with strict JSON only: {\"text\": \"...narrative...\"}"
    )

    start = time.perf_counter()
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=60.0, max_retries=2)
    try:
        response = await client.messages.create(
            model=settings.claude_insight_model,
            max_tokens=600,
            messages=[{"role": "user", "content": user_prompt}],
        )
        duration_ms = (time.perf_counter() - start) * 1000
        input_tokens, output_tokens = extract_anthropic_usage(response)
        log_claude_api_call(
            model=settings.claude_insight_model,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="success",
        )
        raw = response.content[0].text
        data = json.loads(_extract_narrative_json(raw))
        result: dict[str, Any] = {"text": str(data.get("text", raw)), "status": "success"}
    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        duration_ms = (time.perf_counter() - start) * 1000
        log_claude_api_call(
            model=settings.claude_insight_model,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            status="error",
            error_type=type(exc).__name__,
        )
        logger.exception("repo_insight_narrative API call failed")
        if user_id is not None:
            from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
            insight_narrative_cache_repo.record_error_repo(
                db, user_id=user_id, repo_id=repo_id, days=days,
                language=language, error_type=type(exc).__name__, now=_now,
            )
        return {"text": "", "status": "api_error"}

    if user_id is not None:
        # pylint: disable=import-outside-toplevel
        from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415

        insight_narrative_cache_repo.upsert_repo(
            db, user_id=user_id, repo_id=repo_id, days=days,
            language=language, response=result, now=_now,
        )

    return result
