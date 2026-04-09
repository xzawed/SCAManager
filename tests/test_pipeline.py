import pytest
from unittest.mock import AsyncMock, MagicMock, patch


PUSH_DATA = {
    "repository": {"full_name": "owner/repo"},
    "after": "abc123def456",
    "head_commit": {"id": "abc123def456", "message": "feat: add awesome feature"},
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
            commit_score=17, ai_score=16, test_score=10,
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


async def test_no_files_at_all_skips_pipeline(mock_deps):
    mock_deps["push"].return_value = []
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["ai"].assert_not_called()
    mock_deps["telegram"].assert_not_called()


async def test_non_python_files_still_run_ai_review(mock_deps):
    """비-Python 파일만 있어도 AI 리뷰와 알림이 실행되어야 한다."""
    from src.github_client.diff import ChangedFile
    mock_deps["push"].return_value = [ChangedFile("README.md", "# Hello\n", "@@ +1 @@")]
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["ai"].assert_called_once()
    mock_deps["telegram"].assert_called_once()


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


async def test_repo_created_even_when_api_fails(mock_deps):
    """GitHub API 호출 실패 시에도 Repository는 DB에 생성되어야 한다."""
    mock_deps["push"].side_effect = Exception("GitHub API error")
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

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


async def test_db_stores_commit_message(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    analysis_added = mock_deps["db"].add.call_args_list[-1][0][0]
    assert analysis_added.commit_message == "feat: add awesome feature"


async def test_db_result_stores_source_push(mock_deps):
    """Push 이벤트 시 result에 source='push'가 저장된다."""
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    analysis_added = mock_deps["db"].add.call_args_list[-1][0][0]
    assert analysis_added.result["source"] == "push"


async def test_db_result_stores_source_pr(mock_deps):
    """PR 이벤트 시 result에 source='pr'이 저장된다."""
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", PR_DATA)

    analysis_added = mock_deps["db"].add.call_args_list[-1][0][0]
    assert analysis_added.result["source"] == "pr"


async def test_pipeline_calls_gate_for_pr(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    from src.analyzer.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_deps["pr"].return_value = [MagicMock(filename="a.py", content="x=1", patch="@@ +1")]
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, test_score=0, summary="ok")
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
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, test_score=0, summary="ok")
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
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, test_score=0, summary="ok")
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


@pytest.mark.asyncio
async def test_pipeline_uses_owner_github_token():
    """리포 owner의 github_access_token이 있으면 settings.github_token 대신 사용한다."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.models.user import User
    from src.models.repository import Repository

    owner = User(id=1, github_id="111", github_login="owner", email="o@e.com",
                 display_name="Owner", github_access_token="gho_owner_token")
    repo = MagicMock(spec=Repository)
    repo.id = 10
    repo.full_name = "owner/repo"
    repo.owner = owner

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    event_data = {
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"head": {"sha": "abc123"}, "title": "feat: test"},
        "number": 1,
    }

    from src.worker.pipeline import run_analysis_pipeline
    with patch("src.worker.pipeline.SessionLocal", return_value=mock_db):
        with patch("src.worker.pipeline.get_pr_files", return_value=[]) as mock_get_files:
            await run_analysis_pipeline("pull_request", event_data)

    # owner 토큰이 사용됐는지 확인
    mock_get_files.assert_called_once()
    assert mock_get_files.call_args[0][0] == "gho_owner_token"


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_settings_token_when_no_owner():
    """owner나 github_access_token이 없으면 settings.github_token을 사용한다."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.models.repository import Repository

    repo = MagicMock(spec=Repository)
    repo.id = 20
    repo.full_name = "owner/legacy-repo"
    repo.owner = None  # 소유자 없는 레거시 리포

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    event_data = {
        "repository": {"full_name": "owner/legacy-repo"},
        "after": "def456",
        "commits": [{"message": "fix: legacy"}],
    }

    from src.worker.pipeline import run_analysis_pipeline
    with patch("src.worker.pipeline.SessionLocal", return_value=mock_db):
        with patch("src.worker.pipeline.get_push_files", return_value=[]) as mock_get_files:
            await run_analysis_pipeline("push", event_data)

    mock_get_files.assert_called_once()
    assert mock_get_files.call_args[0][0] == "ghp_test"  # conftest의 GITHUB_TOKEN


async def test_pr_body_included_in_commit_message(mock_deps):
    """PR body가 있으면 title + body를 합쳐서 커밋 메시지로 사용한다."""
    pr_data_with_body = {
        "repository": {"full_name": "owner/repo"},
        "number": 7,
        "pull_request": {
            "head": {"sha": "def456abc123"},
            "title": "feat: new PR title",
            "body": "This PR adds a new feature.\n\n- Change 1\n- Change 2",
        },
    }
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", pr_data_with_body)

    call_args = mock_deps["ai"].call_args
    commit_msg = call_args[0][1]
    assert "feat: new PR title" in commit_msg
    assert "This PR adds a new feature." in commit_msg
    assert "- Change 1" in commit_msg


async def test_pr_empty_body_returns_title_only(mock_deps):
    """PR body가 None이거나 빈 문자열이면 title만 반환한다."""
    pr_data_null_body = {
        "repository": {"full_name": "owner/repo"},
        "number": 7,
        "pull_request": {
            "head": {"sha": "def456abc123"},
            "title": "feat: new PR title",
            "body": None,
        },
    }
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", pr_data_null_body)

    call_args = mock_deps["ai"].call_args
    assert call_args[0][1] == "feat: new PR title"


async def test_push_head_commit_preferred(mock_deps):
    """push 이벤트에서 head_commit이 있으면 commits[0] 대신 사용한다."""
    push_data_multi = {
        "repository": {"full_name": "owner/repo"},
        "after": "bbb222",
        "head_commit": {"id": "bbb222", "message": "fix: head commit message"},
        "commits": [
            {"id": "aaa111", "message": "chore: older commit"},
            {"id": "bbb222", "message": "fix: head commit message"},
        ],
    }
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", push_data_multi)

    call_args = mock_deps["ai"].call_args
    assert call_args[0][1] == "fix: head commit message"
