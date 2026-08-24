"""operations_service — admin 운영 모니터링 KPI 회귀 가드 (Cycle 80 PR 2).

cache_kpi + api_cost_estimate + merge_kpi + pipeline_latency 영역 검증.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.gate import _merge_attempt_states as _states
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


def _add_merge_attempt(db, success, days_ago=0, state=None, pr_number=42):
    """헬퍼: 과거 시점 MergeAttempt 추가.

    `state` 를 주지 않으면 컬럼 기본값(`legacy`)이 들어간다 — 운영 데이터의 다수가
    그 상태다(실측 2026-08-24: 2,635행 중 2,577행이 `legacy`).
    """
    kwargs = {}
    if state is not None:
        kwargs["state"] = state
    a = MergeAttempt(
        analysis_id=1, repo_name="alice/r1", pr_number=pr_number,
        score=85, threshold=80, success=success,
        attempted_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        **kwargs,
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

    # ── 🔴 «머지 성공» 의 정의 (2026-08-24) ─────────────────────────────
    #
    # `success=True` 는 「이 시도의 GitHub 호출이 성공했다」이지 「머지됐다」가 아니다.
    # native auto-merge 를 **켜기만** 한 행(`enabled_pending_merge`)도 success=True 이고,
    # 그 PR 은 영영 머지되지 않을 수 있다(force-push·체크 실패·사용자 해제).
    #
    # 반대로 순진하게 `state IN (actually_merged, direct_merged)` 로 바꾸면 **더 나빠진다**:
    # 운영 primary 인 재시도 경로가 `state` 를 안 넘겨 `legacy` 로 저장돼 왔기 때문이다
    # (실측 2026-08-24: success=True 733행 중 675행이 `legacy`).
    #
    # 그래서 하이브리드다 — 「실제 머지 상태」 ∪ 「state 를 안 쓰던 시절의 성공」.

    def test_enabled_pending_merge_is_not_counted_as_merged(self, db):
        """🔴 auto-merge 를 **켜기만** 한 것은 머지가 아니다.

        이 행은 `success=True` 다(GitHub 호출은 성공). 그러나 GitHub 이 나중에 머지할 수도,
        안 할 수도 있다. 머지율 KPI 가 이것을 세면 운영자는 실제보다 높은 수치를 본다.
        """
        _add_merge_attempt(db, success=True, days_ago=1, state=_states.DIRECT_MERGED)
        _add_merge_attempt(db, success=True, days_ago=1, state=_states.ENABLED_PENDING_MERGE)
        result = operations_service._merge_kpi(db, days=7)
        assert result["total_attempts"] == 2
        assert result["success_count"] == 1, (
            "enabled_pending_merge 를 머지로 셌다 — 켜기만 하고 머지되지 않은 PR 이다"
        )
        assert result["success_rate_pct"] == 50.0

    def test_disabled_externally_is_not_counted_as_merged(self, db):
        """🔴 켠 뒤 **외부에서 꺼진** 것도 머지가 아니다.

        `mark_disabled_externally` 는 `state` 만 바꾸고 `success` 를 뒤집지 않는다(실측).
        그래서 「success=True 이고 state != pending」 같은 블랙리스트 술어로는 이 행이 샌다 —
        같은 결함이 한 전이 뒤에서 반복된다. 화이트리스트여야 한다.
        """
        _add_merge_attempt(db, success=True, days_ago=1, state=_states.DIRECT_MERGED)
        _add_merge_attempt(db, success=True, days_ago=1, state=_states.DISABLED_EXTERNALLY)
        result = operations_service._merge_kpi(db, days=7)
        assert result["success_count"] == 1, (
            "disabled_externally 를 머지로 셌다 — auto-merge 가 취소된 PR 이다"
        )

    def test_legacy_success_still_counts(self, db):
        """🔴 과잉교정 대조군 — `state` 를 안 쓰던 시절의 성공은 계속 세야 한다.

        운영 success=True 733행 중 **675행이 `legacy`** 다(실측). 이들을 빼면 머지율이
        92% 급감하는데, 그 행들은 실제로 머지된 재시도 경로다. 백필할 신호가 데이터에 없다.
        """
        _add_merge_attempt(db, success=True, days_ago=1)          # state 미지정 → legacy
        _add_merge_attempt(db, success=False, days_ago=1)
        result = operations_service._merge_kpi(db, days=7)
        assert result["success_count"] == 1, (
            "legacy 성공행이 빠졌다 — 운영 머지 실적의 대부분이 이 상태다"
        )

    def test_actually_merged_counts(self, db):
        """webhook 으로 pending → actually_merged 전이한 행은 머지다."""
        _add_merge_attempt(db, success=True, days_ago=1, state=_states.ACTUALLY_MERGED)
        result = operations_service._merge_kpi(db, days=7)
        assert result["success_count"] == 1

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
