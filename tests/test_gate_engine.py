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


# --- auto_merge 분기 테스트 (Red: RepoConfigData.auto_merge 필드가 아직 존재하지 않음) ---

async def test_auto_approve_with_auto_merge_calls_merge_pr():
    # auto 모드 + approve 결정 + auto_merge=True → merge_pr이 호출되는지 검증
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50,
                            auto_merge=True)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine._save_gate_decision"):
                with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                    mock_merge.return_value = True
                    await run_gate_check(mock_db, "tok", "bot", "owner/repo", 5, 1, _score(80))
                    mock_merge.assert_called_once()


async def test_auto_approve_without_auto_merge_does_not_call_merge_pr():
    # auto 모드 + approve 결정 + auto_merge=False → merge_pr이 호출되지 않는지 검증
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50,
                            auto_merge=False)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine._save_gate_decision"):
                with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                    await run_gate_check(mock_db, "tok", "bot", "owner/repo", 5, 1, _score(80))
                    mock_merge.assert_not_called()


async def test_auto_reject_does_not_call_merge_pr():
    # auto 모드 + reject 결정 시 auto_merge=True여도 merge_pr이 호출되지 않는지 검증
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50,
                            auto_merge=True)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine._save_gate_decision"):
                with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                    await run_gate_check(mock_db, "tok", "bot", "owner/repo", 5, 1, _score(40))
                    mock_merge.assert_not_called()


async def test_auto_approve_merge_pr_failure_does_not_raise():
    # merge_pr가 False를 반환해도 run_gate_check이 예외 없이 완료되는지 검증
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50,
                            auto_merge=True)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                    mock_merge.return_value = False
                    # 예외 없이 완료되어야 함
                    await run_gate_check(mock_db, "tok", "bot", "owner/repo", 5, 1, _score(80))
                    # GateDecision은 merge_pr 결과와 무관하게 저장되어야 함
                    mock_save.assert_called_once_with(mock_db, 1, "approve", "auto")
