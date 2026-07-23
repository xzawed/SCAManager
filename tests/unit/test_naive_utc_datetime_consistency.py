"""naive/aware datetime 일관성 — DB 컬럼(naive)과 비교 경계·삽입값을 naive UTC 로 통일 (종합감사 P2).

Naive/aware datetime consistency (comprehensive audit P2).

🔴 이 결함은 SQLite 단위 테스트에서 **행동으로 재현 불가**하다: SQLAlchemy 의 SQLite DateTime 은
저장/조회 시 tzinfo 를 벗겨 naive/aware 를 구별하지 않기 때문이다. 결함은 PG(TIMESTAMP WITHOUT TIME
ZONE)에서 세션 타임존이 UTC 가 아닐 때만 드러난다. 따라서 이 파일은 DB 왕복 대신 **코드가 DB 계층에
넘기는 datetime 값이 naive 인지**를 직접 관측한다(뮤테이션 catch 가능).
The bug is not reproducible via SQLite behavior (SQLite strips tzinfo), so these tests observe the
code-level datetime values handed to the DB layer directly, which IS mutation-catchable.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")

# pylint: disable=wrong-import-position
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import src.repositories.claude_api_cost_repo as cost_repo
import src.services.analytics_service as analytics_service
import src.services.operations_service as operations_service
from src.models.analysis_attempt import AnalysisAttempt
from src.shared.time_utils import now_naive_utc, to_naive_utc


# ---------------------------------------------------------------------------
# to_naive_utc / now_naive_utc 헬퍼 (2026-07-23 회고 P1-B — grep 전수 단일 출처)
# ---------------------------------------------------------------------------


def test_to_naive_utc_converts_aware_to_naive_utc():
    """aware(+09:00) → naive UTC(tzinfo=None, 벽시계 UTC 로 변환)."""
    aware = datetime(2026, 7, 23, 21, 0, tzinfo=timezone(timedelta(hours=9)))  # 12:00 UTC
    out = to_naive_utc(aware)
    assert out.tzinfo is None
    assert out == datetime(2026, 7, 23, 12, 0)  # UTC 벽시계 / UTC wall-clock


def test_to_naive_utc_passes_naive_through():
    """이미 naive 면 그대로 통과 (idempotent)."""
    naive = datetime(2026, 7, 23, 12, 0)
    assert to_naive_utc(naive) is naive


def test_now_naive_utc_is_naive():
    """now_naive_utc() 는 tzinfo=None 을 반환."""
    assert now_naive_utc().tzinfo is None


def test_analysis_attempt_started_at_default_is_naive():
    """AnalysisAttempt.started_at 의 Python default 가 naive UTC 를 생성한다.
    orphan sweep 의 `_now_naive()` cutoff 와 동일 규약 — aware 삽입 시 PG 세션-tz 의존.
    The started_at default must yield a naive datetime to match the naive cutoff convention.
    """
    default_callable = AnalysisAttempt.__table__.c.started_at.default.arg
    value = default_callable(MagicMock())  # SQLAlchemy 는 실행 컨텍스트를 넘긴다 / passes a context
    assert isinstance(value, datetime)
    assert value.tzinfo is None, "started_at default 가 aware — naive UTC 여야 한다(PG 세션-tz 안전)"


def test_user_cost_summary_passes_naive_window_bounds(monkeypatch):
    """user_cost_summary 가 _window_cost_rows 에 naive UTC 경계를 넘긴다 (aware `now` 주입 시에도).
    Cost window bounds handed to the query layer must be naive UTC even when an aware `now` is injected.
    """
    captured = []

    def _fake_window(db, owner, since, until, *, until_inclusive):  # noqa: ARG001
        captured.append((since, until))
        return []

    monkeypatch.setattr(cost_repo, "_window_cost_rows", _fake_window)
    monkeypatch.setattr(cost_repo, "_owned_repo_ids_subquery", lambda uid: [])

    aware_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    cost_repo.user_cost_summary(MagicMock(), user_id=1, days=30, now=aware_now)

    assert captured, "_window_cost_rows 미호출 — 경계 관측 불가"
    for since, until in captured:
        assert since.tzinfo is None, f"cur/prev since 가 aware: {since!r}"
        assert until.tzinfo is None, f"cur/prev until 이 aware: {until!r}"


def test_moving_average_uses_naive_query_bounds():
    """moving_average 의 WHERE 경계 바인드 값이 naive UTC 다 (aware `now` 주입 시에도).
    moving_average's WHERE-bound datetimes must be naive UTC even when an aware `now` is injected.
    """
    mock_db = MagicMock()
    mock_db.scalars.return_value.all.return_value = []

    aware_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    analytics_service.moving_average(mock_db, repo_id=1, window_days=7, now=aware_now)

    stmt = mock_db.scalars.call_args.args[0]
    dt_params = [v for v in stmt.compile().params.values() if isinstance(v, datetime)]
    assert dt_params, "WHERE 절에 datetime 바인드가 없다 — 관측 불가"
    assert all(v.tzinfo is None for v in dt_params), (
        f"moving_average WHERE 경계가 aware: {[p for p in dt_params if p.tzinfo]!r}"
    )


# ---------------------------------------------------------------------------
# grep-전수 스윕 대표 소비처 (2026-07-23 회고 P1-B) — #1197 이 3곳만 고친 것 확장
# ---------------------------------------------------------------------------


def test_weekly_summary_normalizes_aware_week_start_and_now():
    """weekly_summary 가 aware week_start + aware now 를 받아도 naive 경계로 쿼리한다.
    (min(week_end, _now) 가 naive/aware 혼합으로 TypeError 나지 않고, WHERE 경계는 naive).
    weekly_summary must accept aware inputs without TypeError and query with naive bounds.
    """
    mock_db = MagicMock()
    mock_db.execute.return_value.one.return_value = MagicMock(count=0)
    aware_start = datetime(2026, 7, 16, 0, 0, tzinfo=timezone.utc)
    aware_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)

    analytics_service.weekly_summary(mock_db, repo_id=1, week_start=aware_start, now=aware_now)

    stmt = mock_db.execute.call_args.args[0]
    dt_params = [v for v in stmt.compile().params.values() if isinstance(v, datetime)]
    assert dt_params, "WHERE 경계 datetime 바인드 없음 — 관측 불가"
    assert all(v.tzinfo is None for v in dt_params), (
        f"weekly_summary WHERE 경계가 aware: {[p for p in dt_params if p.tzinfo]!r}"
    )


def test_operations_merge_kpi_uses_naive_bound():
    """operations _merge_kpi 의 MergeAttempt.attempted_at >= since 경계가 naive UTC."""
    mock_db = MagicMock()
    mock_db.scalar.return_value = 0
    operations_service._merge_kpi(mock_db, days=7)  # pylint: disable=protected-access

    stmt = mock_db.scalar.call_args.args[0]
    dt_params = [v for v in stmt.compile().params.values() if isinstance(v, datetime)]
    assert dt_params, "MergeAttempt WHERE 경계 datetime 바인드 없음"
    assert all(v.tzinfo is None for v in dt_params), (
        f"_merge_kpi since 경계가 aware: {[p for p in dt_params if p.tzinfo]!r}"
    )
