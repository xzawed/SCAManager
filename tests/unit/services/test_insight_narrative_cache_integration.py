"""Cycle 74 PR-B Phase 2-B 🅑 — insight_narrative + cache 통합 테스트.

캐시 hit/miss/refresh 흐름 검증 (Anthropic API 호출 빈도 ↓ — 60% 절감).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.user import User  # noqa: F401  (register on metadata)
from src.models.insight_narrative_cache import InsightNarrativeCache  # noqa: F401
from src.repositories import insight_narrative_cache_repo
from src.services import dashboard_service


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session_ = sessionmaker(bind=engine)
    session = Session_()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_cache(db, user_id=1, days=7, response=None):
    """Helper — pre-populate cache to test hit path."""
    insight_narrative_cache_repo.upsert(
        db, user_id=user_id, days=days,
        response=response or {"status": "success", "positive_highlights": ["cached"], "days": days},
    )


@pytest.mark.asyncio
async def test_cache_hit_skips_claude_api_call(db):
    """캐시 hit 시 Claude API 호출 X (cost-saver)."""
    _seed_cache(db, user_id=1, days=7)
    with patch.object(
        dashboard_service, "_call_insight_claude_api",
        new=AsyncMock(return_value="should not be called"),
    ) as mock_api:
        result = await dashboard_service.insight_narrative(
            db, days=7, user_id=1, api_key="sk-ant-test",
        )
    mock_api.assert_not_awaited()
    assert result["status"] == "success"
    assert result["positive_highlights"] == ["cached"]


@pytest.mark.asyncio
async def test_refresh_invalidates_cache_and_calls_api(db):
    """refresh=True 시 cache 무효화 + Claude API 재호출."""
    _seed_cache(db, user_id=1, days=7)
    fake_response = '{"positive_highlights":["fresh"],"focus_areas":["a","b","c"],"key_metrics":[{"label":"x","value":"1","delta":"+0"},{"label":"y","value":"2","delta":"0"},{"label":"z","value":"3","delta":"0"},{"label":"w","value":"4","delta":"0"}],"next_actions":["n1","n2"]}'

    with patch("src.services.dashboard_service.dashboard_kpi", return_value={"analysis_count": {"value": 5}}), \
         patch("src.services.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.services.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.services.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.services.dashboard_service.anthropic.AsyncAnthropic"), \
         patch.object(
             dashboard_service, "_call_insight_claude_api",
             new=AsyncMock(return_value=fake_response),
         ) as mock_api:
        result = await dashboard_service.insight_narrative(
            db, days=7, user_id=1, api_key="sk-ant-test", refresh=True,
        )
    mock_api.assert_awaited_once()
    assert result["status"] == "success"
    assert result["positive_highlights"] == ["fresh"]


@pytest.mark.asyncio
async def test_user_id_none_bypasses_cache(db):
    """user_id=None (admin/legacy) 시 캐싱 X (호출 매번 발생)."""
    fake_response = '{"positive_highlights":["a"],"focus_areas":["a","b","c"],"key_metrics":[{"label":"x","value":"1","delta":"0"},{"label":"y","value":"2","delta":"0"},{"label":"z","value":"3","delta":"0"},{"label":"w","value":"4","delta":"0"}],"next_actions":["n1","n2"]}'
    with patch("src.services.dashboard_service.dashboard_kpi", return_value={"analysis_count": {"value": 5}}), \
         patch("src.services.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.services.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.services.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.services.dashboard_service.anthropic.AsyncAnthropic"), \
         patch.object(
             dashboard_service, "_call_insight_claude_api",
             new=AsyncMock(return_value=fake_response),
         ) as mock_api:
        await dashboard_service.insight_narrative(
            db, days=7, user_id=None, api_key="sk-ant-test",
        )
    # user_id=None — 캐시 영역 X = 무조건 API 호출
    mock_api.assert_awaited_once()
    # 캐시 row 존재 X (user_id=None 영역 캐싱 안 함)
    rows = db.query(InsightNarrativeCache).all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_success_response_cached_after_api_call(db):
    """첫 호출 (cache miss) → API 호출 → 응답 캐시 저장."""
    fake_response = '{"positive_highlights":["a","b","c"],"focus_areas":["a","b","c"],"key_metrics":[{"label":"x","value":"1","delta":"0"},{"label":"y","value":"2","delta":"0"},{"label":"z","value":"3","delta":"0"},{"label":"w","value":"4","delta":"0"}],"next_actions":["n1","n2"]}'
    with patch("src.services.dashboard_service.dashboard_kpi", return_value={"analysis_count": {"value": 5}}), \
         patch("src.services.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.services.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.services.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.services.dashboard_service.anthropic.AsyncAnthropic"), \
         patch.object(
             dashboard_service, "_call_insight_claude_api",
             new=AsyncMock(return_value=fake_response),
         ):
        await dashboard_service.insight_narrative(
            db, days=7, user_id=1, api_key="sk-ant-test",
        )
    # 캐시 저장 확인
    cached = insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7)
    assert cached is not None
    assert cached["status"] == "success"
