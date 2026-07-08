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
    """사용자 소유 repo id 서브쿼리 (dashboard owner 필터 방향과 동일).
    Subquery of the user's owned repo ids (same direction as the dashboard owner filter)."""
    return select(Repository.id).where(Repository.user_id == user_id)


def _window_cost_rows(db: Session, owner, since: datetime, until: datetime):
    """윈도우 (since, until] 내 owner 필터링된 (model, cost_usd) 로우 조회.
    Query (model, cost_usd) rows filtered by owner within the (since, until] window.

    하한 배타/상한 포함 — cur_since 경계 이중 집계 방지 + "지금"(now) 정확히 일치하는 레코드 포함.
    Exclusive lower / inclusive upper — avoids double-count at the cur_since seam while still
    including a row whose created_at exactly equals "now"."""
    return db.execute(
        select(ClaudeApiCall.model, ClaudeApiCall.cost_usd)
        .where(owner)
        .where(ClaudeApiCall.created_at > since)
        .where(ClaudeApiCall.created_at <= until)
    ).all()


def user_cost_summary(db: Session, *, user_id: int, days: int = 30, now: datetime | None = None) -> dict:
    """사용자 귀속 비용 집계 — user_id 직접 OR repo_id 소유 간접. 모델별·delta 포함.
    Aggregate cost attributed to a user (direct user_id OR owned repo_id). By-model + delta."""
    _now = now or datetime.now(timezone.utc)
    cur_since = _now - timedelta(days=days)
    prev_since = _now - timedelta(days=days * 2)
    owner = or_(
        ClaudeApiCall.user_id == user_id,
        ClaudeApiCall.repo_id.in_(_owned_repo_ids_subquery(user_id)),
    )
    cur = _window_cost_rows(db, owner, cur_since, _now)
    prev = _window_cost_rows(db, owner, prev_since, cur_since)
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
