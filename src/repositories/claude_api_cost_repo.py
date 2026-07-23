"""claude_api_cost_repo — ClaudeApiCall 영속화 + 사용자 비용 집계 단일 출처.
claude_api_cost_repo — persist ClaudeApiCall + user cost aggregation (single source)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models.claude_api_call import ClaudeApiCall
from src.models.repository import Repository

# 모델 패밀리 매핑 — claude_metrics 와 동일 규칙(sonnet/haiku/opus/other)
# Model-family mapping — same rule as claude_metrics.
_FAMILIES = ("opus", "sonnet", "haiku")


def _family(model: str) -> str:
    m = (model or "").lower()
    for fam in _FAMILIES:
        if fam in m:
            return fam
    return "other"


def record(  # pylint: disable=too-many-arguments,too-many-locals
    db: Session, *, model: str, status: str,
    input_tokens: int, output_tokens: int, cache_read_tokens: int, cache_creation_tokens: int,
    cost_usd: float, duration_ms: float,
    repo_id: int | None = None, user_id: int | None = None, error_type: str = "",
    now: datetime | None = None,
) -> None:
    """비용 메트릭 1행 INSERT (항상 신규). 호출자(log_claude_api_call)가 fail-safe 로 감쌈.
    Insert one cost-metric row. Caller (log_claude_api_call) wraps this fail-safe."""
    row = ClaudeApiCall(
        created_at=now or datetime.now(timezone.utc),
        model=model, status=status,
        input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0),
        cache_read_tokens=int(cache_read_tokens or 0), cache_creation_tokens=int(cache_creation_tokens or 0),
        cost_usd=float(cost_usd or 0.0), duration_ms=float(duration_ms or 0.0),
        repo_id=repo_id, user_id=user_id, error_type=error_type or None,
    )
    db.add(row)
    db.commit()


def _owned_repo_ids_subquery(user_id: int):
    """사용자 소유 repo id 서브쿼리 — 레거시 repo(user_id IS NULL) 포함, dashboard owner 필터와 동일 컨벤션
    (`dashboard_service._apply_analysis_user_filter`/`_apply_merge_attempt_user_filter`, db.md: 레거시
    repo 전역 노출). 레거시 repo 는 분석/머지 KPI 에는 이미 노출되므로 비용 KPI 에서만 누락되면
    동일 대시보드 내 owner 시맨틱이 불일치한다.
    Subquery of the user's owned repo ids — includes legacy repos (user_id IS NULL), matching the
    dashboard owner-filter convention (`_apply_analysis_user_filter`/`_apply_merge_attempt_user_filter`,
    db.md: legacy repos are globally visible). Legacy repos already show up in the analysis/merge
    KPIs, so omitting them here alone would make owner semantics inconsistent on the same dashboard."""
    return select(Repository.id).where(
        (Repository.user_id == user_id) | (Repository.user_id.is_(None))
    )


def _window_cost_rows(  # pylint: disable=too-many-arguments
    db: Session, owner, since: datetime, until: datetime, *, until_inclusive: bool,
):
    """윈도우 [since, until) 또는 [since, until] 내 owner 필터링된 (model, cost_usd) 로우 조회.
    Query (model, cost_usd) rows filtered by owner within [since, until) or [since, until].

    하한은 항상 포함 — dashboard_kpi(dashboard_service.py) 와 동일 컨벤션.
    current 윈도우는 상한 포함(until_inclusive=True, "지금" 정확 일치 레코드 포함),
    previous 윈도우는 상한 배타(until_inclusive=False, cur_since 경계 이중 집계 방지).
    Lower bound is always inclusive — same convention as dashboard_kpi (dashboard_service.py).
    The current window's upper bound is inclusive (until_inclusive=True, includes a row whose
    created_at exactly equals "now"); the previous window's upper bound is exclusive
    (until_inclusive=False, avoids double-count at the cur_since seam)."""
    query = (
        select(ClaudeApiCall.model, ClaudeApiCall.cost_usd)
        .where(owner)
        .where(ClaudeApiCall.created_at >= since)
    )
    if until_inclusive:
        query = query.where(ClaudeApiCall.created_at <= until)
    else:
        query = query.where(ClaudeApiCall.created_at < until)
    return db.execute(query).all()


def user_cost_summary(db: Session, *, user_id: int, days: int = 30, now: datetime | None = None) -> dict:
    """사용자 귀속 비용 집계 — user_id 직접 OR repo_id 소유 간접. 모델별·delta 포함.
    Aggregate cost attributed to a user (direct user_id OR owned repo_id). By-model + delta."""
    # 🔴 naive UTC 정규화 (종합감사 P2) — ClaudeApiCall.created_at 은 naive DateTime 컬럼이라 aware
    #   경계와 비교하면 PG(TIMESTAMP WITHOUT TIME ZONE)에서 세션 타임존 의존 → 비용/KPI 윈도우 경계 흔들림.
    # Normalize to naive UTC — comparing aware bounds against the naive column is PG session-tz dependent.
    _now = now or datetime.now(timezone.utc)
    if _now.tzinfo is not None:
        _now = _now.astimezone(timezone.utc).replace(tzinfo=None)
    cur_since = _now - timedelta(days=days)
    prev_since = _now - timedelta(days=days * 2)
    owner = or_(
        ClaudeApiCall.user_id == user_id,
        ClaudeApiCall.repo_id.in_(_owned_repo_ids_subquery(user_id)),
    )
    cur = _window_cost_rows(db, owner, cur_since, _now, until_inclusive=True)
    prev = _window_cost_rows(db, owner, prev_since, cur_since, until_inclusive=False)
    by_model = {"sonnet": 0.0, "haiku": 0.0, "opus": 0.0, "other": 0.0}
    for model, cost in cur:
        by_model[_family(model)] += float(cost or 0.0)
    total = round(sum(by_model.values()), 6)
    return {
        "total_usd": total,
        "call_count": len(cur),
        "by_model": {k: round(v, 6) for k, v in by_model.items()},
        "delta_usd": round(total - sum(float(c or 0.0) for _, c in prev), 6) if prev else None,
    }
