"""리포별 코드 인사이트 서비스 — 5 집계 함수 + AI narrative.

Repository-level code insight service — 5 aggregation functions + AI narrative.

모든 집계 함수는 Analysis.result JSON을 Python-side 루프로 처리 (최근 30건 상한).
All aggregation functions process Analysis.result JSON Python-side (max 30 rows).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.anthropic_caching import first_text_block
from src.config import settings
from src.models.analysis import Analysis
from src.scorer.calculator import calculate_grade
from src.scorer.reliability import score_is_unreliable
from src.shared.claude_metrics import (
    ANTHROPIC_PAGE_DEADLINE_SECONDS, ANTHROPIC_RETRY_AFTER_CAP_PAGE_SECONDS, aclose_anthropic_client,
    extract_anthropic_usage, log_claude_api_call, new_async_anthropic, release_session_before_claude,
)
from src.shared.feature_kill_switch import is_disabled
from src.shared.lang_names import LANG_NAMES
from src.shared.time_utils import to_naive_utc

logger = logging.getLogger(__name__)

# 집계 최대 분석 건수 — Python 루프 O(N×이슈수) 상한
# Max analyses per aggregation — caps Python loop O(N×issues)
_MAX_ANALYSES = 30

# 서술 출력 상한 — 600 은 운영 6건 중 5건이 정확히 닿았다(#1700). 대시보드 서술과 같은 1500:
#   잘리지 않은 유일한 실측이 589 토큰이라 약 2.5배 여유, Haiku p10 처리율 ~54 tok/s 로도 ~28s 라 45s 기한 안이다.
# Narrative output cap: 600 was hit by 5 of 6 production calls. 1500 as on the dashboard narrative,
#   ~2.5x the only uncut sample (589) and ~28s at Haiku's p10 rate, inside the 45s page deadline.
_NARRATIVE_MAX_TOKENS = 1500


class _NarrativeTruncated(Exception):
    """상한에서 멈췄고 본문도 읽을 수 없는 응답 — 파서 버그와 구별해 `max_tokens` 로 기록한다.
    Stopped at the output cap with an unreadable body; recorded as `max_tokens`, not a parser failure.
    """


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


def _reliable_score_list(rows: list) -> list[float]:
    """score 가 있고 신뢰 가능한 행의 점수 목록 (R46).
    Scores from rows that have a score and are not score_is_unreliable (R46).
    """
    out: list[float] = []
    for row in rows:
        if row.score is None:
            continue
        result = getattr(row, "result", None)
        if score_is_unreliable(result if isinstance(result, dict) else None):
            continue
        out.append(float(row.score))
    return out


def compute_score_kpi(
    cur: list,
    prev: list,
) -> tuple[float | None, float | None, str]:
    """평균점수/score_delta/등급 계산 공유 헬퍼 (R46: 신뢰 불가 점수 제외).
    Shared helper: compute avg_score, score_delta, grade — excludes unreliable scores (R46).
    """
    cur_scores = _reliable_score_list(cur)
    prev_scores = _reliable_score_list(prev)
    avg_score = round(sum(cur_scores) / len(cur_scores), 1) if cur_scores else None
    prev_avg = round(sum(prev_scores) / len(prev_scores), 1) if prev_scores else None
    score_delta = (
        round(avg_score - prev_avg, 1)
        if (avg_score is not None and prev_avg is not None)
        else None
    )
    grade = calculate_grade(int(avg_score)) if avg_score is not None else "?"
    return avg_score, score_delta, grade


def _count_issues_and_high_security(analyses: list) -> tuple[dict[str, int], int]:
    """분석 목록에서 이슈 빈도 카운터 + 보안 HIGH/ERROR 카운트 집계.

    Aggregate the issue-frequency counter + count of HIGH/ERROR security issues from analyses.
    """
    issue_counter: dict[str, int] = {}
    high_security = 0
    for a in analyses:
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
    return issue_counter, high_security


def repo_kpi(  # pylint: disable=too-many-locals
    db: Session, repo_id: int, days: int = 30, now: datetime | None = None
) -> dict[str, Any]:
    """KPI 4종 — 평균 점수/등급/분석수/최다 반복 이슈/보안 HIGH/점수 delta.

    Returns KPI dict with avg_score, grade, analysis_count, top_recurring_issue,
    top_recurring_count, high_security_count, score_delta.
    """
    _now = to_naive_utc(now or datetime.now(timezone.utc))
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
            # cur(_fetch_analyses)와 동일하게 정렬 — limit(_MAX_ANALYSES) 결정성 확보(감사 services-002)
            # Order like cur so the limited window is deterministic (avoids flaky score_delta).
            .order_by(Analysis.created_at.desc())
            .limit(_MAX_ANALYSES)
        ).all()
    )

    avg_score, score_delta, grade = compute_score_kpi(cur, prev)

    issue_counter, high_security = _count_issues_and_high_security(cur)

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
    _now = to_naive_utc(now or datetime.now(timezone.utc))
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
    _now = to_naive_utc(now or datetime.now(timezone.utc))
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
    _now = to_naive_utc(now or datetime.now(timezone.utc))
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
    _now = to_naive_utc(now or datetime.now(timezone.utc))
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


def _classify_issue_bucket(issue: object) -> str | None:
    """이슈를 category×severity 4-way 버킷 키로 분류 (해당 없으면 None).

    Classify an issue into one of the 4-way category×severity bucket keys (None if not applicable).
    """
    if not isinstance(issue, dict):
        return None
    category = issue.get("category", "")
    is_error = issue.get("severity", "").upper() in ("HIGH", "ERROR")
    if category == "security":
        return "security_error" if is_error else "security_warning"
    if category == "code_quality":
        return "code_quality_error" if is_error else "code_quality_warning"
    return None


def repo_category_breakdown(
    db: Session, repo_id: int, days: int = 30, now: datetime | None = None
) -> dict[str, int]:
    """이슈 카테고리×심각도 4-way 분포 — Chart.js 도넛용.

    4-way issue distribution for Chart.js donut chart.
    """
    _now = to_naive_utc(now or datetime.now(timezone.utc))
    analyses = _fetch_analyses(db, repo_id, days, _now)

    counts: dict[str, int] = {
        "security_error": 0,
        "security_warning": 0,
        "code_quality_error": 0,
        "code_quality_warning": 0,
    }
    for a in analyses:
        for issue in (a.result or {}).get("issues", []):
            key = _classify_issue_bucket(issue)
            if key:
                counts[key] += 1

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


def _narrative_text(raw: str, *, at_cap: bool) -> str:
    """응답에서 서술 문자열을 꺼낸다 — 상한에서 멈췄으면 `{"text": 문자열}` 로 닫힌 본문만 받는다 (#1700).

    스키마가 `{"text": string}` 하나라 본문이 닫혔다는 것은 모델이 문자열을 끝냈다는 뜻이다 — ai_review 와 같은 관용.
    상한에서 멈췄는데 읽을 수 없으면 `_NarrativeTruncated`, 상한이 아니면 원래 예외 그대로다.
    With the {"text": string} schema a closed body means the string was finished, so at the cap it is kept
    (the ai_review idiom); an unreadable body at the cap raises _NarrativeTruncated, otherwise the original error.
    """
    try:
        data = json.loads(_extract_narrative_json(raw))
        text = str(data.get("text", raw))
    except (ValueError, AttributeError) as exc:
        if at_cap:
            raise _NarrativeTruncated from exc
        raise
    # 상한에서는 `text` 폴백(raw)을 받지 않는다 — 기대한 모양이 아니면 읽을 수 없는 본문이다.
    # At the cap the raw-text fallback is refused: anything but {"text": str} is unreadable.
    if at_cap and not isinstance(data.get("text"), str):
        raise _NarrativeTruncated
    return text


def _log_narrative_failure(exc: Exception, status: str, output_tokens: int) -> str:
    """실패를 로그에 남기고 기록할 error_type 을 돌려준다 — 잘림은 WARNING + `max_tokens` (#1700).

    except 블록 안에서 부른다 — `logger.exception` 이 처리 중인 예외를 싣는다.
    Called inside the except block; truncation is a WARNING and `max_tokens`, the rest keep the class name.
    """
    if isinstance(exc, _NarrativeTruncated):
        logger.warning(
            "repo_insight_narrative truncated at max_tokens=%d (output_tokens=%d)",
            _NARRATIVE_MAX_TOKENS, output_tokens,
        )
        return "max_tokens"
    logger.exception("repo_insight_narrative failed (status=%s, exc=%s)", status, type(exc).__name__)
    return type(exc).__name__


def _record_narrative_error(
    db: Session, *, user_id: int | None, repo_id: int, days: int,
    language: str, error_type: str, now: datetime,
) -> None:
    """user_id 가 있으면 내러티브 캐시에 에러 기록 (no_data/api_error/internal_error 공통).

    기록하는 것은 `error_type` 이지 반환 status 가 아니다 — 예외 클래스명이거나 리터럴
    `no_data` · `max_tokens`(상한에서 멈췄고 본문을 읽을 수 없음, #1700)다. #1458 의
    벤더/우리코드 분류는 반환 dict 에만 있고 캐시 동작은 바뀌지 않는다.
    Records error_type, not the returned status: an exception class name or the literal
    `no_data` / `max_tokens` (stopped at the cap with an unreadable body). The #1458
    vendor/ours split lives in the return dict only and does not change caching behaviour.
    """
    if user_id is None:
        return
    from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    insight_narrative_cache_repo.record_error_repo(
        db, user_id=user_id, repo_id=repo_id, days=days,
        language=language, error_type=error_type, now=now,
    )


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
    Returns: {"text": str, "status": "success"|"no_api_key"|"no_data"|"api_error"
                                |"internal_error"|"disabled"}
      🔴 `api_error` = 벤더(`anthropic.APIError` · 페이지 기한 초과), `internal_error` = 우리 코드.
      api_error means the vendor failed; internal_error means our code did.
    """
    # 비용 제어 — INSIGHT_DISABLED=1 시 리포 내러티브 전면 차단(API 호출 0).
    # Cost control — INSIGHT_DISABLED=1 disables the per-repo narrative entirely.
    if is_disabled("INSIGHT"):
        return {"text": "", "status": "disabled"}

    api_key = settings.anthropic_api_key
    if not api_key:
        return {"text": "", "status": "no_api_key"}

    # 🔴 aware 유지 (회고 P1-B) — 이 함수의 _now 는 컬럼 비교가 아니라 insight_narrative_cache_repo
    #   에만 전달된다. 캐시 repo 는 DB 읽기값을 aware 로 정규화해 비교하는 자체 규약이라 aware now 필요.
    #   (형제 함수들은 _fetch_analyses 로 Analysis.created_at[naive] 과 비교하므로 to_naive_utc 사용.)
    # Keep aware here — this _now only feeds the cache repo, which uses an aware-normalization convention.
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
        _record_narrative_error(
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

    # 🔴 Claude 를 기다리는 동안 풀 연결·열린 트랜잭션을 쥐지 않는다 — 이후 캐시 쓰기는 새 트랜잭션 (#1697).
    # Release the pooled connection before the Claude await; later cache writes open a new transaction.
    release_session_before_claude(db)
    start = time.perf_counter()
    # 🔴 **실제로 소비된 토큰은 error 경로에서도 보고한다** (backlog R65).
    # 응답을 받은 뒤 파싱이 실패해도 토큰은 **이미 과금**됐다 — 0 으로 적으면 비용 과소 계상.
    # 호출 자체가 실패하면 값이 갱신되지 않아 0 이 남고, 그 경우엔 0 이 맞다.
    # Report tokens actually consumed on the error path too; they are billed once the API responds.
    _tokens: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
    client = new_async_anthropic(
        api_key=api_key, timeout=60.0, max_retries=2,
        caller="repo_insight", retry_after_cap=ANTHROPIC_RETRY_AFTER_CAP_PAGE_SECONDS,
    )
    # 전체 기한 — 안에는 SDK 호출만 둔다. 파싱이 밖이어야 벤더/우리 코드 라벨이 갈린다 (#1697).
    # Total deadline around the SDK call only; parsing stays outside so the vendor/ours split holds.
    deadline = asyncio.timeout(ANTHROPIC_PAGE_DEADLINE_SECONDS)
    try:
        async with deadline:
            response = await client.messages.create(
                model=settings.claude_insight_model,
                max_tokens=_NARRATIVE_MAX_TOKENS,
                # 🔴 응답 형식을 스키마로 강제 (backlog R51). 아래 `data.get("text", raw)`
                #    폴백은 절단·호출실패를 위해 그대로 둔다 — 스키마는 그 축을 닫지 않는다.
                # Schema-enforced shape; the raw-text fallback below stays for truncation/failure.
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                            "additionalProperties": False,
                        },
                    }
                },
                messages=[{"role": "user", "content": user_prompt}],
            )
        duration_ms = (time.perf_counter() - start) * 1000
        input_tokens, output_tokens = extract_anthropic_usage(response)
        _tokens.update(input_tokens=input_tokens, output_tokens=output_tokens)
        # 🔴 **추출·파싱을 로그보다 먼저** (backlog R63). 이전에는 `status="success"` 를 먼저
        # 기록하고 그 뒤 파싱이 실패하면 except 가 `status="error"` 를 **또** 남겨,
        # 한 번의 API 호출이 비용 테이블에 **2행**을 만들었다(성공률·비용 집계 왜곡).
        # Extract and parse before logging: the old order produced two rows for one call.
        # 🔴 상한 판정은 `stop_reason` 으로만 한다 — 출력 토큰 수로 추정하지 않는다 (#1700).
        #   SDK `StopReason` 의 정확한 값 비교다. 닫힌 본문은 success + 경고, 못 읽으면 `max_tokens`.
        #   `stop_sequence` · `refusal` 등 다른 값은 상한이 아니다 — 파싱 결과가 그대로 판정한다.
        # Cap detection reads stop_reason only; a closed body at the cap is kept with a warning.
        at_cap = getattr(response, "stop_reason", None) == "max_tokens"
        raw = first_text_block(response)
        result: dict[str, Any] = {"text": _narrative_text(raw, at_cap=at_cap), "status": "success"}
        if at_cap:
            logger.warning(
                "repo_insight_narrative reached max_tokens=%d (output_tokens=%d), body closed and kept",
                _NARRATIVE_MAX_TOKENS, output_tokens,
            )
        # 🔴 로그는 **결과 조립이 끝난 뒤**다 (R63 · Grok `32b9a2f9` 2차 적발).
        # 1차 수정은 `json.loads` 뒤로만 옮겼는데, 유효 JSON 이 **dict 가 아니면**
        # (`"문자열"` · `[1,2]`) 그 다음 줄의 `data.get` 이 터져 여전히
        # `['success', 'error']` 2행이었다. success 로그는 **더 이상 예외가 날 수 없는
        # 지점** 이후에만 찍는다.
        # Log only after the result is fully built: a valid but non-dict JSON made
        # `data.get` raise *after* the success row was already written.
        log_claude_api_call(
            model=settings.claude_insight_model,
            duration_ms=duration_ms,
            status="success",
            repo_id=repo_id,
            user_id=user_id,
            **_tokens,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # 🔴 **벤더 실패와 우리 코드 버그를 다른 status 로 가른다** (#1458).
        #   try 안에는 API 호출과 **그 뒤의 파싱**이 함께 있다(R63 — 2행 기록을 막느라
        #   의도적으로 넣었다). 그래서 `json.loads` 실패도 여기로 오는데, 예전에는 전부
        #   `api_error` 였다. 운영 실측 3건이 그랬다: `output_tokens=600` — **과금까지 된
        #   뒤 우리 파서가 터진 것**을 벤더 장애로 집계했다.
        #   판정 근거는 `anthropic.APIError` 하위 여부뿐이다(형제 호출부와 동일한 축).
        # Split vendor failures from our own bugs: this try covers the API call AND the
        # parsing that follows it, so a JSONDecodeError used to be recorded as api_error.
        #   기한 초과도 벤더 지연이다 — 단 `TimeoutError` 이고 «우리» 기한이 끝났을 때만 (#1697).
        #   클래스만 보면 우리 코드의 TimeoutError 가, expired() 만 보면 기한 뒤 파싱 실패가 벤더로 샌다.
        # A deadline miss is vendor too, but only a TimeoutError raised when OUR deadline expired.
        vendor = isinstance(exc, anthropic.APIError) or (
            isinstance(exc, TimeoutError) and deadline.expired()
        )
        #   잘림은 새 status 없이 기존 `internal_error`(수정 전 JSONDecodeError 경로와 같은 값)로 두고
        #   error_type 만 `max_tokens` 로 가른다 — 상한은 우리 설정이다.
        # Truncation keeps the existing internal_error status; only error_type says max_tokens.
        status = "api_error" if vendor else "internal_error"
        duration_ms = (time.perf_counter() - start) * 1000
        error_type = _log_narrative_failure(exc, status, _tokens["output_tokens"])
        log_claude_api_call(
            model=settings.claude_insight_model,
            duration_ms=duration_ms,
            status="error",
            error_type=error_type,
            repo_id=repo_id,
            user_id=user_id,
            **_tokens,
        )
        _record_narrative_error(
            db, user_id=user_id, repo_id=repo_id, days=days,
            language=language, error_type=error_type, now=_now,
        )
        return {"text": "", "status": status}
    finally:
        # 호출당 생성한 AsyncAnthropic httpx 커넥션 풀 해제 — 미종료 시 FD 누수 (WBS P1).
        # Close the per-call AsyncAnthropic httpx pool — leaks FDs/connections if left open.
        await aclose_anthropic_client(client)

    if user_id is not None:
        # pylint: disable=import-outside-toplevel
        from src.repositories import insight_narrative_cache_repo  # noqa: PLC0415

        insight_narrative_cache_repo.upsert_repo(
            db, user_id=user_id, repo_id=repo_id, days=days,
            language=language, response=result, now=_now,
        )

    return result
