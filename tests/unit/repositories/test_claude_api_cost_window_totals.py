"""관리자 «운영» 화면의 API 비용 = 기간 안에 기록된 호출의 실측 합 (회고 원장 이관 K11 P2-20 · P2-54).

화면은 메모리 카운터의 입력 토큰에 «Sonnet 가정 + 출력 = 입력의 1/8» 을 곱해 비용을 지어냈다 — 운영 관측상 실제 호출은
다른 모델이었다. 사용자 11-17 결정 «실측 합으로 (Recommended)»: 호출마다 남는 `claude_api_calls` 의 합으로 바꾸고 기간을 밝힌다.

이 파일이 잠그는 것: 창 [since, until] 의 두 끝을 포함하고 밖은 뺀다 · 테넌트를 거르지 않는다(관리자 화면 · 워커 세션) ·
비용 · 토큰 · 호출 수를 기록 그대로 더한다 · 빈 창은 0.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.claude_api_call import ClaudeApiCall
from src.models.repository import Repository  # noqa: F401
from src.models.user import User  # noqa: F401
from src.repositories import claude_api_cost_repo

UNTIL = datetime(2026, 11, 17, 12, 0, 0)
SINCE = UNTIL - timedelta(days=7)


@pytest.fixture(name="db")
def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _call(db, at, *, cost, inp, out, user_id=None, repo_id=None, model="claude-haiku-4-5", status="success"):
    db.add(ClaudeApiCall(created_at=at, model=model, status=status, input_tokens=inp, output_tokens=out,
                         cache_read_tokens=0, cache_creation_tokens=0, cost_usd=cost, duration_ms=1.0,
                         user_id=user_id, repo_id=repo_id))
    db.commit()


def test_an_empty_window_is_zero(db):
    totals = claude_api_cost_repo.window_totals(db, since=SINCE, until=UNTIL)
    assert totals == {"call_count": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}


def test_both_ends_are_inside_and_the_outside_is_left_out(db):
    """🔴 경계 — 창 시작 · 끝 시각의 기록은 들고, 1초 바깥은 빠진다."""
    _call(db, SINCE, cost=0.5, inp=10, out=1)
    _call(db, UNTIL, cost=0.25, inp=20, out=2)
    _call(db, SINCE - timedelta(seconds=1), cost=100.0, inp=9_000, out=900)
    _call(db, UNTIL + timedelta(seconds=1), cost=200.0, inp=8_000, out=800)
    totals = claude_api_cost_repo.window_totals(db, since=SINCE, until=UNTIL)
    assert totals == {"call_count": 2, "cost_usd": 0.75, "input_tokens": 30, "output_tokens": 3}


def test_every_tenant_and_status_is_summed(db):
    """테넌트를 거르지 않는다 — 사용자 귀속 · 리포 귀속 · 귀속 없음 · 실패 호출이 모두 기록 그대로 더해진다."""
    mid = SINCE + timedelta(days=3)
    _call(db, mid, cost=0.125, inp=100, out=10, user_id=7)
    _call(db, mid, cost=0.5, inp=200, out=20, repo_id=9, model="claude-sonnet-5")
    _call(db, mid, cost=0.0625, inp=300, out=30)
    _call(db, mid, cost=0.0, inp=0, out=0, status="api_error")
    totals = claude_api_cost_repo.window_totals(db, since=SINCE, until=UNTIL)
    assert totals == {"call_count": 4, "cost_usd": 0.6875, "input_tokens": 600, "output_tokens": 60}
