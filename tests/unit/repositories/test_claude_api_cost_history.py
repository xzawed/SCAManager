"""claude_api_cost_repo — 재시작 기준 조회: 모델별 마지막 성공 · 마지막 행이 거부인 모델 (Issue #1905 ①a Task 2).

Restart-baseline queries: each model's last success, and the models whose last row is a rejection.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.claude_api_call import ClaudeApiCall  # noqa: F401  (Base.metadata 등록 / register on metadata)
from src.repositories import claude_api_cost_repo

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
SINCE = T0 - timedelta(days=30)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _row(db, model: str, *, at: datetime, status: str = "success", error_type: str = "") -> None:
    claude_api_cost_repo.record(
        db, model=model, status=status, input_tokens=10, output_tokens=5,
        cache_read_tokens=0, cache_creation_tokens=0, cost_usd=0.0, duration_ms=100.0,
        error_type=error_type, now=at,
    )


def test_recent_success_models_orders_by_last_success(db):
    _row(db, "claude-haiku-4-5", at=T0 - timedelta(days=40))
    _row(db, "claude-haiku-4-5", at=T0 + timedelta(hours=1))
    _row(db, "claude-sonnet-5", at=T0 + timedelta(hours=2))
    _row(db, "claude-haiku-4-5", at=T0 + timedelta(hours=3))
    # 실패만 있는 판 · 창 밖에서만 성공한 판은 빠진다 / error-only and out-of-window models are left out
    _row(db, "claude-opus-5", at=T0 + timedelta(hours=4), status="error", error_type="APIConnectionError")
    _row(db, "claude-fable-5-1", at=T0 - timedelta(days=31))

    got = claude_api_cost_repo.recent_success_models(db, since=SINCE)

    assert [model for model, _ in got] == ["claude-haiku-4-5", "claude-sonnet-5"]
    assert got[0][1].replace(tzinfo=None) == datetime(2026, 11, 1, 3, 0)


def test_rejected_models_uses_last_row_only(db):
    # 거부 뒤 성공 → 거부 아님 / rejected then succeeded -> not rejected
    _row(db, "claude-sonnet-5-5", at=T0 + timedelta(hours=1), status="error", error_type="model_rejected")
    _row(db, "claude-sonnet-5-5", at=T0 + timedelta(hours=2))
    # 성공 뒤 거부 → 거부 / succeeded then rejected -> rejected
    _row(db, "claude-haiku-5-5", at=T0 + timedelta(hours=1))
    _row(db, "claude-haiku-5-5", at=T0 + timedelta(hours=2), status="error", error_type="model_rejected")
    # 거부가 마지막이지만 다른 오류 / last row is a different error
    _row(db, "claude-opus-5-5", at=T0 + timedelta(hours=1), status="error", error_type="RateLimitError")
    # 창 밖 거부 / rejection outside the window
    _row(db, "claude-fable-5-2", at=T0 - timedelta(days=31), status="error", error_type="model_rejected")

    assert claude_api_cost_repo.rejected_models(db, since=SINCE) == {"claude-haiku-5-5"}
