"""DB 풀/probe config 하한 검증 회귀 가드 (품질감사 data-layer-003).

DB pool/probe config lower-bound validation regression guard (audit data-layer-003).

db_failover_probe_interval=0 이면 database.py::_probe_primary_loop 의 `while True: time.sleep(interval)`
가 time.sleep(0) busy-loop(100% CPU)로 degenerate. db_pool_size=0/db_pool_timeout<1 도 무조건 오동작.
→ <1 이 항상 broken 인 3 필드만 ge=1 (max_overflow/-1·pool_recycle/-1 sentinel 은 미제약, SQLAlchemy 보존).
"""
import pytest
from pydantic import ValidationError

from src.config import Settings

_REQUIRED_KWARGS = dict(
    database_url="sqlite:///:memory:",
    github_webhook_secret="x",
    github_token="x",
    telegram_bot_token="123:ABC",
    telegram_chat_id="-100",
)


def test_valid_db_defaults_construct_ok():
    """기본값(5/10/30/1800/30)은 검증자가 거부하면 안 된다 (회귀 가드)."""
    s = Settings(**_REQUIRED_KWARGS)
    assert s.db_pool_size == 5
    assert s.db_pool_timeout == 30
    assert s.db_failover_probe_interval == 30


def test_zero_failover_probe_interval_raises():
    """db_failover_probe_interval=0 → busy-loop 위험 → ValidationError."""
    with pytest.raises(ValidationError):
        Settings(**_REQUIRED_KWARGS, db_failover_probe_interval=0)


def test_negative_failover_probe_interval_raises():
    with pytest.raises(ValidationError):
        Settings(**_REQUIRED_KWARGS, db_failover_probe_interval=-5)


def test_zero_pool_size_raises():
    """db_pool_size=0 → 풀 고갈 → ValidationError."""
    with pytest.raises(ValidationError):
        Settings(**_REQUIRED_KWARGS, db_pool_size=0)


def test_zero_pool_timeout_raises():
    with pytest.raises(ValidationError):
        Settings(**_REQUIRED_KWARGS, db_pool_timeout=0)


def test_max_overflow_negative_one_allowed():
    """db_max_overflow=-1(SQLAlchemy 무제한 sentinel)은 미제약 → 허용 (회귀 가드)."""
    s = Settings(**_REQUIRED_KWARGS, db_max_overflow=-1)
    assert s.db_max_overflow == -1


def test_pool_recycle_negative_one_allowed():
    """db_pool_recycle=-1(SQLAlchemy recycle 비활성 sentinel)은 미제약 → 허용 (회귀 가드)."""
    s = Settings(**_REQUIRED_KWARGS, db_pool_recycle=-1)
    assert s.db_pool_recycle == -1


def test_ge1_boundary_value_one_allowed():
    """ge=1 경계값 1 은 허용되어야 한다 (off-by-one 회귀 — 1 까지 거부하면 안 됨)."""
    s = Settings(
        **_REQUIRED_KWARGS,
        db_pool_size=1,
        db_pool_timeout=1,
        db_failover_probe_interval=1,
    )
    assert s.db_pool_size == 1
    assert s.db_pool_timeout == 1
    assert s.db_failover_probe_interval == 1
