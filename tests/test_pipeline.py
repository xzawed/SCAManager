import pytest
from unittest.mock import AsyncMock, MagicMock, patch


PUSH_DATA = {
    "repository": {"full_name": "owner/repo"},
    "after": "abc123def456",
    "commits": [{"id": "abc123def456", "message": "feat: add awesome feature"}],
}

PR_DATA = {
    "repository": {"full_name": "owner/repo"},
    "number": 7,
    "pull_request": {"head": {"sha": "def456abc123"}, "title": "feat: new PR title"},
}


@pytest.fixture
def mock_deps():
    with (
        patch("src.worker.pipeline.get_push_files") as mock_push,
        patch("src.worker.pipeline.get_pr_files") as mock_pr,
        patch("src.worker.pipeline.review_code", new_callable=AsyncMock) as mock_ai,
        patch("src.worker.pipeline.calculate_score") as mock_score,
        patch("src.worker.pipeline.send_analysis_result", new_callable=AsyncMock) as mock_telegram,
        patch("src.worker.pipeline.post_pr_comment", new_callable=AsyncMock) as mock_comment,
        patch("src.worker.pipeline.SessionLocal") as mock_session_cls,
        patch("src.worker.pipeline.settings") as mock_settings,
    ):
        from src.analyzer.static import StaticAnalysisResult
        from src.scorer.calculator import ScoreResult
        from src.github_client.diff import ChangedFile
        from src.analyzer.ai_review import AiReviewResult

        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_settings.telegram_chat_id = "-100123"
        mock_settings.anthropic_api_key = "sk-test"

        mock_push.return_value = [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]
        mock_pr.return_value = [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]
        mock_ai.return_value = AiReviewResult(
            commit_score=17, ai_score=16, has_tests=True,
            summary="Good change", suggestions=[]
        )
        mock_score.return_value = ScoreResult(
            total=85, grade="B",
            code_quality_score=28, security_score=20,
            breakdown={
                "code_quality": 28, "security": 20,
                "commit_message": 17, "ai_review": 16, "test_coverage": 4,
            },
        )

        mock_db = MagicMock()
        mock_repo = MagicMock(id=1)
        # Call sequence: 1) repo creation (None→create), 2) repo lookup (found),
        # 3) dup check (None), 4) get_repo_config (None→defaults)
        mock_db.query.return_value.filter_by.return_value.first.side_effect = [
            None, mock_repo, None, None,
        ]
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        mock_session_cls.return_value = mock_db

        yield {
            "push": mock_push, "pr": mock_pr,
            "ai": mock_ai, "score": mock_score,
            "telegram": mock_telegram, "comment": mock_comment,
            "db": mock_db,
        }


async def test_push_event_calls_full_pipeline(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["push"].assert_called_once()
    mock_deps["ai"].assert_called_once()
    mock_deps["score"].assert_called_once()
    mock_deps["telegram"].assert_called_once()
    assert mock_deps["db"].commit.call_count == 2  # repo creation + analysis save


async def test_pr_event_calls_full_pipeline(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", PR_DATA)

    mock_deps["pr"].assert_called_once()
    mock_deps["ai"].assert_called_once()
    mock_deps["telegram"].assert_called_once()


async def test_pr_event_posts_github_comment(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", PR_DATA)

    mock_deps["comment"].assert_called_once()
    call_kwargs = mock_deps["comment"].call_args[1]
    assert call_kwargs["pr_number"] == 7
    assert call_kwargs["repo_name"] == "owner/repo"


async def test_push_event_does_not_post_github_comment(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["comment"].assert_not_called()


async def test_no_python_files_skips_pipeline(mock_deps):
    mock_deps["push"].return_value = []
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["ai"].assert_not_called()
    mock_deps["telegram"].assert_not_called()


async def test_no_python_files_still_creates_repository(mock_deps):
    """Even when no Python files changed, the Repository should be created in DB."""
    mock_deps["push"].return_value = []
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    # Repository should have been added and committed even though pipeline was skipped
    from src.models.repository import Repository
    add_calls = mock_deps["db"].add.call_args_list
    added_repos = [c[0][0] for c in add_calls if isinstance(c[0][0], Repository)]
    assert len(added_repos) == 1
    assert added_repos[0].full_name == "owner/repo"
    mock_deps["db"].commit.assert_called()


async def test_duplicate_commit_is_skipped(mock_deps):
    existing = MagicMock()
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None,
        existing,
    ]
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["telegram"].assert_not_called()


async def test_push_commit_message_extracted(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    call_args = mock_deps["ai"].call_args
    assert call_args[0][1] == "feat: add awesome feature"


async def test_pr_title_used_as_commit_message(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", PR_DATA)

    call_args = mock_deps["ai"].call_args
    assert call_args[0][1] == "feat: new PR title"


async def test_ai_review_result_passed_to_scorer(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    from src.analyzer.ai_review import AiReviewResult
    await run_analysis_pipeline("push", PUSH_DATA)

    score_call = mock_deps["score"].call_args
    ai_review_arg = score_call[1].get("ai_review") or (score_call[0][1] if len(score_call[0]) > 1 else None)
    assert isinstance(ai_review_arg, AiReviewResult)


async def test_db_result_stores_ai_summary(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    analysis_added = mock_deps["db"].add.call_args_list[-1][0][0]
    assert "ai_summary" in analysis_added.result


async def test_pipeline_calls_gate_for_pr(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    from src.analyzer.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_deps["pr"].return_value = [MagicMock(filename="a.py", content="x=1", patch="@@ +1")]
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, has_tests=False, summary="ok")
    mock_deps["score"].return_value = ScoreResult(
        total=80, grade="B", code_quality_score=25, security_score=20, breakdown={}
    )

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), MagicMock(id=1), None,
    ]
    mock_db.refresh = MagicMock()

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        with patch("src.worker.pipeline.get_repo_config",
                   return_value=MagicMock(n8n_webhook_url=None)):
            await run_analysis_pipeline("pull_request", PR_DATA)
            mock_gate.assert_called_once()


async def test_pipeline_calls_n8n_when_url_set(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    from src.analyzer.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_deps["push"].return_value = [MagicMock(filename="a.py", content="x=1", patch="@@ +1")]
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, has_tests=False, summary="ok")
    mock_deps["score"].return_value = ScoreResult(
        total=80, grade="B", code_quality_score=25, security_score=20, breakdown={}
    )

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), MagicMock(id=1), None,
    ]
    mock_db.refresh = MagicMock()

    from src.config_manager.manager import RepoConfigData
    with patch("src.worker.pipeline.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo",
                                           n8n_webhook_url="https://n8n.test/webhook/x")):
        with patch("src.worker.pipeline.notify_n8n", new_callable=AsyncMock) as mock_n8n:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)
                mock_n8n.assert_called_once()
                assert mock_n8n.call_args.kwargs["webhook_url"] == "https://n8n.test/webhook/x"


async def test_pipeline_skips_gate_for_push(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    from src.analyzer.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_deps["push"].return_value = [MagicMock(filename="a.py", content="x=1", patch="@@ +1")]
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, has_tests=False, summary="ok")
    mock_deps["score"].return_value = ScoreResult(
        total=80, grade="B", code_quality_score=25, security_score=20, breakdown={}
    )

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), MagicMock(id=1), None,
    ]
    mock_db.refresh = MagicMock()

    with patch("src.worker.pipeline.get_repo_config",
               return_value=MagicMock(n8n_webhook_url=None)):
        with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
            await run_analysis_pipeline("push", PUSH_DATA)
            mock_gate.assert_not_called()
