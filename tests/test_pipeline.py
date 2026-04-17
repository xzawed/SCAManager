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
        # Call sequence: 1) repo creation (None→create), 2) dup check (None),
        # 3) repo lookup in second session (found), 4) get_repo_config (None→defaults)
        mock_db.query.return_value.filter_by.return_value.first.side_effect = [
            None, None, mock_repo, None,
        ]
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        # Support both SessionLocal() and `with SessionLocal() as db:` patterns
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = mock_db

        yield {
            "push": mock_push, "pr": mock_pr,
            "ai": mock_ai, "score": mock_score,
            "telegram": mock_telegram,
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


async def test_pr_event_calls_gate_engine(mock_deps):
    """PR 이벤트 시 gate engine이 호출된다 (PR comment는 gate engine 내부에서 처리)."""
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        await run_analysis_pipeline("pull_request", PR_DATA)

    mock_gate.assert_called_once()
    call_kwargs = mock_gate.call_args.kwargs
    assert call_kwargs["pr_number"] == 7
    assert call_kwargs["repo_name"] == "owner/repo"


async def test_push_event_calls_gate_with_pr_number_none(mock_deps):
    """push 이벤트 시 gate engine은 pr_number=None + commit_sha로 호출된다.

    Phase 3-A 이후 push 이벤트도 run_gate_check을 호출한다
    (내부에서 push_commit_comment 옵션 처리).
    """
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        await run_analysis_pipeline("push", PUSH_DATA)

    mock_gate.assert_called_once()
    call_kwargs = mock_gate.call_args.kwargs
    assert call_kwargs["pr_number"] is None
    assert call_kwargs["commit_sha"] == PUSH_DATA["after"]
    assert call_kwargs["repo_name"] == "owner/repo"


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
        MagicMock(id=1), None, MagicMock(id=1),
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
        MagicMock(id=1), None, MagicMock(id=1),
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


async def test_pipeline_invokes_gate_for_push(mock_deps):
    """Phase 3-A: push 이벤트도 gate engine을 pr_number=None으로 호출한다."""
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
        MagicMock(id=1), None, MagicMock(id=1),
    ]
    mock_db.refresh = MagicMock()

    with patch("src.worker.pipeline.get_repo_config",
               return_value=MagicMock(n8n_webhook_url=None)):
        with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
            await run_analysis_pipeline("push", PUSH_DATA)
            mock_gate.assert_called_once()
            assert mock_gate.call_args.kwargs["pr_number"] is None


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
    # 순서: 첫 번째 세션 repo 조회 → SHA 중복 체크(None=중복 없음) → (파일 없어 조기 종료)
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [repo, None]
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
    # 순서: 첫 번째 세션 repo 조회 → SHA 중복 체크(None=중복 없음) → (파일 없어 조기 종료)
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [repo, None]
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


# ---------------------------------------------------------------------------
# PR Gate 3-옵션 분리 재설계 — pipeline 관련 테스트 (Red)
#
# 신규 설계에서는 post_pr_comment가 pipeline._build_notify_tasks에서 제거되고
# gate engine(run_gate_check) 내부로 이동한다.
# pipeline은 pr_review_comment 옵션 판단을 gate engine에 위임한다.
# ---------------------------------------------------------------------------

async def test_pipeline_pr_review_comment_not_in_notify_tasks(mock_deps):
    """신규 설계에서 _build_notify_tasks는 post_pr_comment를 포함하지 않는다.

    gate engine이 pr_review_comment 옵션을 처리하므로, pipeline의
    notify tasks에서 post_pr_comment는 제거되어야 한다.
    """
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), None, MagicMock(id=1),
    ]
    mock_db.refresh = MagicMock()

    from src.config_manager.manager import RepoConfigData

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
        with patch("src.worker.pipeline.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            await run_analysis_pipeline("pull_request", PR_DATA)

    # 신규 설계: pipeline이 직접 post_pr_comment를 호출하지 않는다
    # post_pr_comment는 gate engine 내부에서 pr_review_comment 플래그에 따라 처리된다
    # (pipeline에서 직접 import하지 않으므로 import 여부로 검증)
    import src.worker.pipeline as pl_module
    assert not hasattr(pl_module, "post_pr_comment"), \
        "pipeline은 post_pr_comment를 직접 import하지 않아야 한다"


async def test_pipeline_passes_new_gate_signature(mock_deps):
    """pipeline이 run_gate_check를 새 시그니처로 호출한다.

    신규 시그니처: run_gate_check(repo_name, pr_number, analysis_id, result, github_token, db)
    기존 시그니처: run_gate_check(db, github_token, telegram_bot_token, repo_full_name, ...)
    """
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), None, MagicMock(id=1),
    ]
    mock_db.refresh = MagicMock()

    from src.config_manager.manager import RepoConfigData

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        with patch("src.worker.pipeline.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            await run_analysis_pipeline("pull_request", PR_DATA)

    mock_gate.assert_called_once()
    # 새 시그니처에는 telegram_bot_token 인자가 없다
    call_kwargs = mock_gate.call_args.kwargs
    assert "telegram_bot_token" not in call_kwargs
    # 새 시그니처 필수 인자 확인
    assert "repo_name" in call_kwargs or len(mock_gate.call_args.args) > 0
    assert "pr_number" in call_kwargs or len(mock_gate.call_args.args) > 1


# ---------------------------------------------------------------------------
# Task 1 — SHA 중복 체크 이동 및 result dict ai_review_status 필드 테스트
# (Red 단계: SHA 중복 체크가 아직 review_code 이전으로 이동하지 않음)
# ---------------------------------------------------------------------------

async def test_sha_duplicate_skips_before_review_code(mock_deps):
    """중복 SHA가 감지되면 review_code가 호출되지 않아야 한다.

    현재 구현은 review_code 호출 후 DB 저장 직전에 중복 체크하므로 이 테스트는 Red 상태다.
    구현 후: SHA 중복 체크를 repo 등록 직후, 파일 fetch 전으로 이동하면 Green이 된다.
    """
    # 첫 번째 first(): repo 없음(생성), 두 번째 first(): repo 조회 성공, 세 번째 first(): 중복 SHA 발견
    existing_analysis = MagicMock()
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None,             # 첫 번째 세션: repo 없음 → 생성
        existing_analysis,  # 첫 번째 세션: SHA 중복 감지 (파일 fetch 전에 조기 종료)
    ]

    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    # SHA 중복 → review_code 미호출
    mock_deps["ai"].assert_not_called()


async def test_sha_duplicate_skips_before_file_fetch(mock_deps):
    """중복 SHA가 감지되면 get_push_files / get_pr_files가 호출되지 않아야 한다."""
    existing_analysis = MagicMock()
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None,             # 첫 번째 세션: repo 없음 → 생성
        existing_analysis,  # 첫 번째 세션: SHA 중복 감지 (파일 fetch 전에 조기 종료)
    ]

    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    # SHA 중복 → 파일 fetch 미호출
    mock_deps["push"].assert_not_called()


async def test_result_dict_contains_ai_review_status(mock_deps):
    """_build_result_dict() 결과에 ai_review_status 키가 포함되어야 한다.

    현재 _build_result_dict는 ai_review_status를 반환하지 않으므로 Red 상태다.
    구현 후: ai_review.status 값을 result dict에 포함하면 Green이 된다.
    """
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    analysis_added = mock_deps["db"].add.call_args_list[-1][0][0]
    # result dict에 ai_review_status 키가 존재해야 한다
    assert "ai_review_status" in analysis_added.result


# ---------------------------------------------------------------------------
# 알림 디스패처(_build_notify_tasks) 조합 검증
# discord / slack / n8n 채널 설정 여부에 따른 호출 분기,
# repo_config 로드 실패 시 Telegram 전용 fallback,
# gate 예외 발생 시 Analysis DB 저장 보장
# ---------------------------------------------------------------------------

async def test_discord_notifier_called_when_configured(mock_deps):
    """repo_config.discord_webhook_url이 설정된 경우 send_discord_notification이 호출된다."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData

    # get_repo_config를 직접 patch하므로 두 번째 DB 세션은 repo 조회(mock_repo)만 필요
    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        discord_webhook_url="https://discord.com/api/webhooks/test",
    )
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.worker.pipeline.send_discord_notification",
                   new_callable=AsyncMock) as mock_discord:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_discord.assert_called_once()


async def test_discord_notifier_not_called_when_not_configured(mock_deps):
    """repo_config.discord_webhook_url이 없으면 send_discord_notification이 호출되지 않는다."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo,
    ]
    mock_deps["db"].refresh = MagicMock()

    # discord_webhook_url 미설정
    config = RepoConfigData(repo_full_name="owner/repo")
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.worker.pipeline.send_discord_notification",
                   new_callable=AsyncMock) as mock_discord:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_discord.assert_not_called()


async def test_slack_notifier_called_when_configured(mock_deps):
    """repo_config.slack_webhook_url이 설정된 경우 send_slack_notification이 호출된다."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        slack_webhook_url="https://hooks.slack.com/services/T000/B000/xxx",
    )
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.worker.pipeline.send_slack_notification",
                   new_callable=AsyncMock) as mock_slack:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_slack.assert_called_once()


async def test_repo_config_none_sends_only_telegram(mock_deps):
    """get_repo_config 로드 실패 시 Telegram 만 발송되고 Discord/Slack은 미발송이다."""
    from src.worker.pipeline import run_analysis_pipeline

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo,
    ]
    mock_deps["db"].refresh = MagicMock()

    # get_repo_config 예외 → pipeline이 repo_config=None으로 fallback
    from sqlalchemy.exc import SQLAlchemyError
    with patch("src.worker.pipeline.get_repo_config", side_effect=SQLAlchemyError("config error")):
        with patch("src.worker.pipeline.send_discord_notification",
                   new_callable=AsyncMock) as mock_discord:
            with patch("src.worker.pipeline.send_slack_notification",
                       new_callable=AsyncMock) as mock_slack:
                with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                    await run_analysis_pipeline("push", PUSH_DATA)

    # Telegram은 global fallback으로 항상 발송
    mock_deps["telegram"].assert_called_once()
    # Discord/Slack은 config 없으므로 미발송
    mock_discord.assert_not_called()
    mock_slack.assert_not_called()


async def test_gate_check_exception_still_saves_analysis(mock_deps):
    """gate check 예외가 발생해도 Analysis DB 저장은 이미 완료되어야 한다."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.models.analysis import Analysis

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo,
    ]
    mock_deps["db"].refresh = MagicMock()

    with patch("src.worker.pipeline.run_gate_check",
               new_callable=AsyncMock, side_effect=Exception("gate error")):
        with patch("src.worker.pipeline.get_repo_config", return_value=MagicMock(
            discord_webhook_url=None,
            slack_webhook_url=None,
            custom_webhook_url=None,
            email_recipients=None,
            n8n_webhook_url=None,
            notify_chat_id=None,
        )):
            await run_analysis_pipeline("pull_request", PR_DATA)

    # gate 예외 이전에 db.add(analysis) + db.commit()이 이미 호출됨
    add_calls = mock_deps["db"].add.call_args_list
    added_analyses = [c[0][0] for c in add_calls if isinstance(c[0][0], Analysis)]
    assert len(added_analyses) == 1


async def test_n8n_notifier_called_when_configured(mock_deps):
    """repo_config.n8n_webhook_url이 설정된 경우 notify_n8n이 호출된다."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        n8n_webhook_url="https://n8n.example.com/webhook/test",
    )
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.worker.pipeline.notify_n8n", new_callable=AsyncMock) as mock_n8n:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_n8n.assert_called_once()
