"""Phase 2 d-🅓 (사이클 74) — Insight Haiku 모델 분기 회귀 가드.

Insight narrative 영역만 Haiku 사용 (review_code 는 Sonnet 보존 — 명시 제외 영역).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_settings_claude_insight_model_default_haiku():
    """settings.claude_insight_model default = claude-haiku-4-5 (67% 비용 절감)."""
    from src.config import settings
    assert "haiku" in settings.claude_insight_model.lower()


def test_settings_claude_review_model_unchanged():
    """settings.claude_review_model = sonnet 보존 (AI 리뷰 품질 영역 — 명시 제외)."""
    from src.config import settings
    assert "sonnet" in settings.claude_review_model.lower()


@pytest.mark.asyncio
async def test_insight_narrative_uses_insight_model_not_review_model():
    """insight_narrative → claude_insight_model 호출 (review_model 사용 X)."""
    from src.services import dashboard_service
    from src.config import settings

    # 모든 의존성 mock — 실제 API 호출 없이 model 인자 전달만 검증
    fake_kpi = {"analysis_count": {"value": 5}}
    with patch("src.services.dashboard_service.dashboard_kpi", return_value=fake_kpi), \
         patch("src.services.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.services.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.services.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.services.dashboard_service.anthropic.AsyncAnthropic") as mock_client_cls, \
         patch(
             "src.services.dashboard_service._call_insight_claude_api",
             new=AsyncMock(return_value=None),  # api_error 분기 진입
         ) as mock_call:
        mock_client_cls.return_value = MagicMock()
        await dashboard_service.insight_narrative(
            db=MagicMock(), days=7, api_key="sk-ant-test",
        )

    # _call_insight_claude_api 가 정확히 settings.claude_insight_model 로 호출됨
    mock_call.assert_awaited_once()
    call_args = mock_call.call_args
    # 두 번째 positional 인자 = model
    assert call_args.args[1] == settings.claude_insight_model
    assert "haiku" in call_args.args[1].lower()
