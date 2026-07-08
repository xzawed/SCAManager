"""cost_metrics_service — 순수 위임 검증(repo 호출 확인).
cost_metrics_service — verifies pure delegation to the repo."""
from unittest.mock import patch

from src.services import cost_metrics_service


def test_delegates_to_repo():
    with patch("src.services.cost_metrics_service.claude_api_cost_repo.user_cost_summary",
               return_value={"total_usd": 1.23}) as m:
        out = cost_metrics_service.user_cost_summary(db=None, user_id=7, days=30)
    assert out == {"total_usd": 1.23}
    m.assert_called_once()
