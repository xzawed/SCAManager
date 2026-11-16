"""AI 인사이트 생성 한도 — 기간을 화면 값으로 맞추고, 사용자별 하루 생성 수를 묶는다 (회고 원장 L17 P2-7).

AI insight generation limits: snap the window to on-screen values and cap generations per user per day.

생성 기간은 화면이 주는 값 가운데 요청을 덮는 가장 작은 값이다(가장 큰 값보다 크면 가장 큰 값).
하루 한도는 호출 기록(`claude_api_calls`)의 `user_id` 로 센다 — 인사이트 경로만 사용자에게 귀속한다(리뷰 경로는 `repo_id`).
The window is the smallest on-screen value covering the request (the largest when beyond them). The daily cap is
counted from the call log's `user_id` (only insight calls are attributed to a user; review calls carry `repo_id`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src import constants
from src.repositories import claude_api_cost_repo
from src.shared.time_utils import to_naive_utc


def snap_days(days: int, allowed: tuple[int, ...]) -> int:
    """`days` 를 덮는 가장 작은 화면 값 — 그보다 크면 가장 큰 화면 값. 화면 값은 그대로 돌려준다.

    The smallest on-screen value covering `days`, or the largest one when `days` exceeds them all.
    """
    return min((value for value in allowed if value >= days), default=max(allowed))


def daily_limit_reached(db: Session, *, user_id: int, now: datetime | None = None) -> bool:
    """오늘(UTC 자정부터) 이 사용자에게 귀속된 Claude 호출이 하루 한도에 닿았는가.

    Whether today's (UTC) Claude calls attributed to this user reached the daily cap.
    """
    current = to_naive_utc(now or datetime.now(timezone.utc))
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    used = claude_api_cost_repo.count_user_calls_since(db, user_id=user_id, since=day_start)
    return used >= constants.INSIGHT_GENERATIONS_PER_USER_PER_DAY


def limited(latest: dict | None, fallback: dict) -> dict:
    """상한에 닿았을 때의 응답 — 마지막 결과가 있으면 그것에 «오늘 한도» 표시를, 없으면 `fallback`(한도 상태)을.

    The response at the cap: the latest result flagged as limited, or `fallback` (the limit status) when none.
    """
    cap = constants.INSIGHT_GENERATIONS_PER_USER_PER_DAY
    if latest:
        return {**latest, "daily_limit": True, "daily_cap": cap}
    return {**fallback, "daily_cap": cap}
