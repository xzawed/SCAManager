import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, MagicMock, patch
from src.gate.engine import run_gate_check
from src.scorer.calculator import ScoreResult
from src.config_manager.manager import RepoConfigData


def _score(total): return ScoreResult(total=total, grade="B", code_quality_score=20, security_score=15, breakdown={})


async def test_disabled_mode_does_nothing():
    mock_db = MagicMock()
    with patch("src.gate.engine.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo", gate_mode="disabled")):
        with patch("src.gate.engine.post_github_review") as mock_review:
            await run_gate_check(mock_db, "tok", "bot", "owner/repo", 1, 1, _score(80))
            mock_review.assert_not_called()


async def test_auto_approve():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                await run_gate_check(mock_db, "tok", "bot", "owner/repo", 1, 1, _score(80))
                assert mock_review.call_args.args[3] == "approve"
                mock_save.assert_called_once_with(mock_db, 1, "approve", "auto")


async def test_auto_reject():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                await run_gate_check(mock_db, "tok", "bot", "owner/repo", 1, 1, _score(40))
                assert mock_review.call_args.args[3] == "reject"
                mock_save.assert_called_once_with(mock_db, 1, "reject", "auto")


async def test_auto_skip_between_thresholds():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                await run_gate_check(mock_db, "tok", "bot", "owner/repo", 1, 1, _score(62))
                mock_review.assert_not_called()
                mock_save.assert_called_once_with(mock_db, 1, "skip", "auto")


async def test_semi_auto_sends_telegram():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="semi-auto",
                            notify_chat_id="-100999")
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock) as mock_send:
            await run_gate_check(mock_db, "tok", "bot", "owner/repo", 7, 5, _score(65))
            mock_send.assert_called_once()
            assert mock_send.call_args.kwargs["analysis_id"] == 5
            assert mock_send.call_args.kwargs["chat_id"] == "-100999"


async def test_semi_auto_no_chat_id_skips():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="semi-auto",
                            notify_chat_id=None)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock) as mock_send:
            await run_gate_check(mock_db, "tok", "bot", "owner/repo", 7, 5, _score(65))
            mock_send.assert_not_called()
