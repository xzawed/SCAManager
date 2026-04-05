import pytest
from unittest.mock import AsyncMock, MagicMock, patch


PUSH_DATA = {
    "repository": {"full_name": "owner/repo"},
    "after": "abc123def456",
}

PR_DATA = {
    "repository": {"full_name": "owner/repo"},
    "number": 7,
    "pull_request": {"head": {"sha": "def456abc123"}},
}


@pytest.fixture
def mock_deps():
    with (
        patch("src.worker.pipeline.get_push_files") as mock_push,
        patch("src.worker.pipeline.get_pr_files") as mock_pr,
        patch("src.worker.pipeline.analyze_file") as mock_analyze,
        patch("src.worker.pipeline.calculate_score") as mock_score,
        patch("src.worker.pipeline.send_analysis_result", new_callable=AsyncMock) as mock_notify,
        patch("src.worker.pipeline.SessionLocal") as mock_session_cls,
        patch("src.worker.pipeline.settings") as mock_settings,
    ):
        from src.analyzer.static import StaticAnalysisResult
        from src.scorer.calculator import ScoreResult
        from src.github_client.diff import ChangedFile

        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_settings.telegram_chat_id = "-100123"

        mock_push.return_value = [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]
        mock_pr.return_value = [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]
        mock_analyze.return_value = StaticAnalysisResult("app.py")
        mock_score.return_value = ScoreResult(
            total=85, grade="B",
            code_quality_score=28, security_score=20,
            breakdown={},
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        mock_session_cls.return_value = mock_db

        yield {
            "push": mock_push, "pr": mock_pr,
            "analyze": mock_analyze, "score": mock_score,
            "notify": mock_notify, "db": mock_db,
        }


@pytest.mark.asyncio
async def test_push_event_calls_full_pipeline(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["push"].assert_called_once()
    mock_deps["analyze"].assert_called_once()
    mock_deps["score"].assert_called_once()
    mock_deps["notify"].assert_called_once()
    mock_deps["db"].commit.assert_called_once()


@pytest.mark.asyncio
async def test_pr_event_calls_full_pipeline(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", PR_DATA)

    mock_deps["pr"].assert_called_once_with(
        mock_deps["pr"].call_args[0][0], "owner/repo", 7
    )
    mock_deps["notify"].assert_called_once()


@pytest.mark.asyncio
async def test_no_python_files_skips_pipeline(mock_deps):
    mock_deps["push"].return_value = []
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["analyze"].assert_not_called()
    mock_deps["notify"].assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_commit_is_skipped(mock_deps):
    existing = MagicMock()
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None,
        existing,
    ]
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["notify"].assert_not_called()
