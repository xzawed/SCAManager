"""INSIGHT_DISABLED=1 시 두 내러티브가 API 호출 없이 disabled 반환.
Both narratives short-circuit to disabled without an Anthropic call when INSIGHT_DISABLED=1."""
import asyncio
from unittest.mock import patch
from src.services.dashboard_service import insight_narrative
from src.services.repo_insight_service import repo_insight_narrative


def test_dashboard_insight_disabled(monkeypatch):
    monkeypatch.setenv("INSIGHT_DISABLED", "1")
    with patch("anthropic.AsyncAnthropic") as mock_client:
        result = asyncio.run(insight_narrative(db=None, days=7, api_key="sk-live"))
    assert result["status"] == "disabled"
    mock_client.assert_not_called()


def test_repo_insight_disabled(monkeypatch):
    monkeypatch.setenv("INSIGHT_DISABLED", "1")
    with patch("anthropic.AsyncAnthropic") as mock_client:
        result = asyncio.run(
            repo_insight_narrative(
                db=None, repo_id=1, kpi={"analysis_count": 5}, recurring=[]
            )
        )
    assert result["status"] == "disabled"
    mock_client.assert_not_called()
