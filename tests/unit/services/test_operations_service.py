"""operations_service — admin 운영 모니터링 KPI 회귀 가드 (Cycle 80 PR 2).

cache_kpi + api_cost_estimate + merge_kpi + pipeline_latency 영역 검증.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.merge_attempt import MergeAttempt
from src.services import operations_service
from src.shared import claude_metrics


@pytest.fixture
def db():
    """In-memory SQLite + 단위 격리."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def _reset_cache_stats():
    """모듈 레벨 cache 카운터 reset (테스트 격리)."""
    claude_metrics.reset_cache_stats()
    yield
    claude_metrics.reset_cache_stats()


# ─── _cache_kpi ──────────────────────────────────────────────────────


class TestCacheKpi:
    def test_initial_zero_state(self):
        result = operations_service._cache_kpi()
        assert result["total_calls"] == 0
        assert result["cache_hit_rate_pct"] == 0.0
        assert result["memory_only"] is True

    def test_after_api_call_log(self):
        claude_metrics.log_claude_api_call(
            model="claude-sonnet-4-6", duration_ms=100,
            input_tokens=1000, output_tokens=200, status="success",
            cache_read_tokens=4000,
        )
        result = operations_service._cache_kpi()
        assert result["total_calls"] == 1
        assert result["input_tokens"] == 1000
        assert result["cache_read_tokens"] == 4000
        # cache_hit_rate = 4000 / (4000 + 1000) = 0.8 → 80%
        assert result["cache_hit_rate_pct"] == 80.0


# ─── _api_cost_estimate ──────────────────────────────────────────────


class TestApiCostEstimate:
    def test_zero_when_no_calls(self):
        stats = claude_metrics.get_cache_stats()
        result = operations_service._api_cost_estimate(stats)
        assert result["estimated_usd"] == 0.0
        assert result["input_tokens"] == 0

    def test_cost_with_cache(self):
        # 1M input + 500K cache_read 시뮬레이션
        # Sonnet input $3/M + cache_read 0.1× ($0.30/M)
        # output_estimate = 1M / 8 = 125K (output $15/M = $1.875)
        stats = {
            "input_tokens": 1_000_000,
            "cache_read_tokens": 500_000,
            "cache_creation_tokens": 0,
            "total_calls": 100,
            "cache_hit_rate": 0.333,
        }
        result = operations_service._api_cost_estimate(stats)
        assert result["input_tokens"] == 1_000_000
        assert result["output_estimate"] == 125_000
        # cost > 0
        assert result["estimated_usd"] > 0


# ─── _merge_kpi ──────────────────────────────────────────────────────


def _add_merge_attempt(db, success, days_ago=0):
    """헬퍼: 과거 시점 MergeAttempt 추가."""
    a = MergeAttempt(
        analysis_id=1, repo_name="alice/r1", pr_number=42,
        score=85, threshold=80, success=success,
        attempted_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(a)
    db.commit()


class TestMergeKpi:
    def test_no_attempts_zero(self, db):
        result = operations_service._merge_kpi(db, days=7)
        assert result["total_attempts"] == 0
        assert result["success_count"] == 0
        assert result["success_rate_pct"] == 0.0

    def test_success_rate_calculation(self, db):
        # 4 시도 = 3 성공 + 1 실패 → 75%
        for _ in range(3):
            _add_merge_attempt(db, success=True, days_ago=1)
        _add_merge_attempt(db, success=False, days_ago=1)
        result = operations_service._merge_kpi(db, days=7)
        assert result["total_attempts"] == 4
        assert result["success_count"] == 3
        assert result["success_rate_pct"] == 75.0

    def test_days_window_filter(self, db):
        # 최근 1건 + 과거 100일전 1건 — days=7 = 1 만 카운트
        _add_merge_attempt(db, success=True, days_ago=1)
        _add_merge_attempt(db, success=True, days_ago=100)
        result = operations_service._merge_kpi(db, days=7)
        assert result["total_attempts"] == 1


# ─── operations_kpi (전체) ──────────────────────────────────────────


class TestOperationsKpi:
    def test_returns_5_card_data(self, db):
        result = operations_service.operations_kpi(db, days=7)
        assert "cache" in result
        assert "api_cost" in result
        assert "merge" in result
        assert "pipeline_latency" in result
        assert result["days"] == 7

    def test_pipeline_latency_unavailable_phase_2(self, db):
        """Phase 2 영역 — 메모리 카운터 부재 명시."""
        result = operations_service.operations_kpi(db, days=7)
        assert result["pipeline_latency"]["available"] is False
        assert "Phase 2" in result["pipeline_latency"]["reason"]

    def test_days_parameter_propagation(self, db):
        """days 파라미터 = merge_kpi 에 전달."""
        result = operations_service.operations_kpi(db, days=30)
        assert result["days"] == 30
        assert result["merge"]["days"] == 30
