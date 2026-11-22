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
async def test_insight_narrative_uses_insight_model_not_review_model(monkeypatch):
    """insight_narrative → claude_insight_model 저장값으로 호출 (review_model 사용 X) · 그 값은 검증판으로 해석된다.

    두 설정을 서로 다른 계열(auto:haiku · auto:sonnet)로 두고 검증판을 심는다 — 리뷰 값을 넘기거나 해석을 건너뛰면 어긋난다.
    해석은 공용 도우미가 한다(#1905 ①b) — 그래서 넘기는 값은 저장값 그대로이고, 아래에서 실제 create 의 판을 본다.
    The two settings follow different lines with seeded verified models; passing the review value or skipping the
    resolution both diverge. The shared helper resolves (#1905 ①b): the stored value goes in, the create call is checked.
    """
    from src.services import dashboard_service
    from src.config import settings
    from src.shared import model_catalog as mc

    monkeypatch.setattr(settings, "claude_insight_model", "auto:haiku")
    monkeypatch.setattr(settings, "claude_review_model", "auto:sonnet")
    mc.set_verified("haiku", "claude-haiku-5-5")
    mc.set_verified("sonnet", "claude-sonnet-5-5")

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

    # _call_insight_claude_api 가 인사이트 설정의 저장값으로 호출됨 / called with the insight setting's stored value
    mock_call.assert_awaited_once()
    call_args = mock_call.call_args
    # 두 번째 positional 인자 = 저장값 / the second positional argument is the stored value
    assert call_args.args[1] == "auto:haiku"

    # 그 저장값이 실제 create 에서 검증된 Haiku 로 풀린다 / the stored value resolves to the verified Haiku
    response = MagicMock()
    response.content = [MagicMock(type="text", text="{}")]
    response.stop_reason = "end_turn"
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    with patch("src.services.dashboard_service.log_claude_api_call"):
        await dashboard_service._call_insight_claude_api(  # pylint: disable=protected-access
            client, call_args.args[1], "prompt")
    assert client.messages.create.await_args.kwargs["model"] == "claude-haiku-5-5"
