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
        patch("src.notifier.telegram.send_analysis_result", new_callable=AsyncMock) as mock_telegram,
        patch("src.worker.pipeline.SessionLocal") as mock_session_cls,
        patch("src.worker.pipeline.settings") as mock_settings,
        # 정적분석 subprocess(Semgrep 등) 실행 차단 — 테스트당 ~7s 절약
        patch("src.worker.pipeline._run_static_analysis",
              new_callable=AsyncMock, return_value=[]),
        # Phase S.4 — repository/analysis/config 조회를 함수 단위로 직접 patch.
        # 기존 `filter_by.return_value.first.side_effect` 단일 체인이 repo/analysis
        # 두 쿼리를 묶어서 mock 하던 방식은 `repository_repo.find_by_full_name`
        # 내부를 `filter` 기반으로 바꾸면 체인이 분리되어 회귀 (Phase S.1-4, S.3-D 실패).
        # 아래 3개 patch 는 내부 ORM 구현과 무관하게 동작하므로 S.3-D 전환 가능.
        patch("src.worker.pipeline.repository_repo.find_by_full_name") as mock_find_repo,
        patch("src.worker.pipeline.analysis_repo.find_by_sha") as mock_find_analysis,
        patch("src.worker.pipeline.get_repo_config") as mock_get_config,
    ):
        from src.scorer.calculator import ScoreResult
        from src.github_client.diff import ChangedFile
        from src.analyzer.io.ai_review import AiReviewResult
        from src.config_manager.manager import RepoConfigData

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
        # 기본 동작: 1차 조회 None (생성) → 2차 조회 mock_repo (발견). 중복 없음.
        # 각 테스트에서 mock_deps["find_repo"].side_effect 등으로 override.
        mock_find_repo.side_effect = [None, mock_repo]
        mock_find_analysis.return_value = None
        mock_get_config.return_value = RepoConfigData(repo_full_name="owner/repo")

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
            "find_repo": mock_find_repo,
            "find_analysis": mock_find_analysis,
            "get_config": mock_get_config,
            "mock_repo": mock_repo,
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


async def test_push_event_does_not_call_gate_with_pr_number(mock_deps):
    """push 이벤트 시 gate engine은 pr_number=None으로 호출된다 (또는 미호출)."""
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        await run_analysis_pipeline("push", PUSH_DATA)

    # push 이벤트는 pr_number=None이므로 gate engine이 호출되지 않는다
    mock_gate.assert_not_called()


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


async def test_concurrent_insert_race_skips_duplicate_notify(mock_deps):
    """save_new 가 DB unique 제약으로 기존 레코드(created=False)를 반환하면 알림을 재발송하지 않는다.

    동시 webhook 가 find_by_sha 재확인을 통과해도 마지막 안전망인 DB 제약이 중복 삽입을 차단한다.
    이때 기존 레코드가 이미 알림/게이트를 처리했으므로 중복 알림·PR 코멘트를 방지해야 한다
    (정합성 감사 P1 — result_dict=None race-recovery 신호 재사용).
    """
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.worker.pipeline import run_analysis_pipeline

    # 이미 존재하는 레코드 (다른 webhook 가 처리 완료, pr_number 이미 설정)
    # Existing record already handled by a concurrent webhook (pr_number already set)
    existing = MagicMock(id=99, pr_number=7, result={"score": 85})
    with patch("src.worker.pipeline.analysis_repo.save_new", return_value=(existing, False)):
        with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
            await run_analysis_pipeline("pull_request", PR_DATA)

    # 중복 알림 차단 — result_dict=None 으로 notify 스킵
    # Duplicate notification blocked — notify skipped via result_dict=None
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
    # 1차 repo 조회에서 이미 존재 → dup 감지 시 analysis 조회가 existing 반환
    mock_deps["find_repo"].side_effect = [mock_deps["mock_repo"]]
    mock_deps["find_analysis"].return_value = existing
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
    from src.analyzer.io.ai_review import AiReviewResult
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
    from src.analyzer.io.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_deps["pr"].return_value = [MagicMock(filename="a.py", content="x=1", patch="@@ +1")]
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, test_score=0, summary="ok")
    mock_deps["score"].return_value = ScoreResult(
        total=80, grade="B", code_quality_score=25, security_score=20, breakdown={}
    )

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), None, MagicMock(id=1), None,
    ]
    mock_db.refresh = MagicMock()

    from src.config_manager.manager import RepoConfigData
    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        with patch("src.worker.pipeline.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            await run_analysis_pipeline("pull_request", PR_DATA)
            mock_gate.assert_called_once()


async def test_pipeline_calls_n8n_when_url_set(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    from src.analyzer.io.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_deps["push"].return_value = [MagicMock(filename="a.py", content="x=1", patch="@@ +1")]
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, test_score=0, summary="ok")
    mock_deps["score"].return_value = ScoreResult(
        total=80, grade="B", code_quality_score=25, security_score=20, breakdown={}
    )

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), None, MagicMock(id=1), None,
    ]
    mock_db.refresh = MagicMock()

    from src.config_manager.manager import RepoConfigData
    with patch("src.worker.pipeline.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo",
                                           n8n_webhook_url="https://n8n.test/webhook/x")):
        with patch("src.notifier.n8n.notify_n8n", new_callable=AsyncMock) as mock_n8n:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)
                mock_n8n.assert_called_once()
                assert mock_n8n.call_args.kwargs["webhook_url"] == "https://n8n.test/webhook/x"


async def test_pipeline_skips_gate_for_push(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    from src.analyzer.io.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_deps["push"].return_value = [MagicMock(filename="a.py", content="x=1", patch="@@ +1")]
    mock_deps["ai"].return_value = AiReviewResult(commit_score=15, ai_score=15, test_score=0, summary="ok")
    mock_deps["score"].return_value = ScoreResult(
        total=80, grade="B", code_quality_score=25, security_score=20, breakdown={}
    )

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), None, MagicMock(id=1), None,
    ]
    mock_db.refresh = MagicMock()

    from src.config_manager.manager import RepoConfigData
    with patch("src.worker.pipeline.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")):
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
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    event_data = {
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"head": {"sha": "abc123"}, "title": "feat: test"},
        "number": 1,
    }

    from src.worker.pipeline import run_analysis_pipeline
    with (
        patch("src.worker.pipeline.SessionLocal", return_value=mock_db),
        patch("src.worker.pipeline.repository_repo.find_by_full_name", return_value=repo),
        patch("src.worker.pipeline.analysis_repo.find_by_sha", return_value=None),
        patch("src.worker.pipeline.get_pr_files", return_value=[]) as mock_get_files,
    ):
        await run_analysis_pipeline("pull_request", event_data)

    # owner 토큰이 사용됐는지 확인
    # Verify the owner token was used.
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
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    event_data = {
        "repository": {"full_name": "owner/legacy-repo"},
        "after": "def456",
        "commits": [{"message": "fix: legacy"}],
    }

    # settings.github_token 을 직접 mock — conftest 의 GITHUB_TOKEN 환경변수가
    # 빈 문자열로 이미 export 된 환경에서는 setdefault 가 작동 안 함.
    # PR B-2 (2026-05-02): 환경 의존성 제거.
    from src.worker.pipeline import run_analysis_pipeline
    with (
        patch("src.worker.pipeline.settings") as mock_settings,
        patch("src.worker.pipeline.SessionLocal", return_value=mock_db),
        patch("src.worker.pipeline.repository_repo.find_by_full_name", return_value=repo),
        patch("src.worker.pipeline.analysis_repo.find_by_sha", return_value=None),
        patch("src.worker.pipeline.get_push_files", return_value=[]) as mock_get_files,
    ):
        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_chat_id = ""  # _ensure_repo path 에서 사용
        mock_settings.anthropic_api_key = ""
        await run_analysis_pipeline("push", event_data)

    mock_get_files.assert_called_once()
    assert mock_get_files.call_args[0][0] == "ghp_test"  # mock 으로 주입한 token


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
# 신규 설계에서는 post_pr_comment가 pipeline.build_notification_tasks에서 제거되고
# gate engine(run_gate_check) 내부로 이동한다.
# pipeline은 pr_review_comment 옵션 판단을 gate engine에 위임한다.
# ---------------------------------------------------------------------------

async def test_pipeline_pr_review_comment_not_in_notify_tasks(mock_deps):
    """신규 설계에서 build_notification_tasks는 post_pr_comment를 포함하지 않는다.

    gate engine이 pr_review_comment 옵션을 처리하므로, pipeline의
    notify tasks에서 post_pr_comment는 제거되어야 한다.
    """
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), None, MagicMock(id=1), None,
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
        MagicMock(id=1), None, MagicMock(id=1), None,
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
    # Verify mandatory arguments of the new signature.
    assert "repo_name" in call_kwargs or len(mock_gate.call_args.args) > 0
    assert "pr_number" in call_kwargs or len(mock_gate.call_args.args) > 1
    # config가 이미 로드된 RepoConfigData로 전달되어야 한다 (중복 DB 조회 방지)
    assert "config" in call_kwargs, "config 파라미터가 run_gate_check에 전달되지 않음 — 중복 DB 조회 발생"
    assert call_kwargs["config"] is not None, "config가 None으로 전달됨 — get_repo_config 재조회 발생"


async def test_pipeline_marks_result_incomplete_on_static_timeout(mock_deps):
    """정적분석 타임아웃 시 run_gate_check 에 전달되는 result 에 static_analysis_incomplete=True 마커가 있어야 한다.

    이 마커가 AutoMergeAction 의 auto-merge 차단 신호 — 미분석 코드 자동 머지 방지(관측 마커 겸용).
    """
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), None, MagicMock(id=1), None,
    ]
    mock_db.refresh = MagicMock()

    from src.config_manager.manager import RepoConfigData

    # 정적분석이 타임아웃 → ([], True) 반환
    # Static analysis times out → returns ([], True)
    with patch("src.worker.pipeline._run_static_with_timeout",
               new=AsyncMock(return_value=([], True))):
        with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
            with patch("src.worker.pipeline.get_repo_config",
                       return_value=RepoConfigData(repo_full_name="owner/repo")):
                await run_analysis_pipeline("pull_request", PR_DATA)

    mock_gate.assert_called_once()
    result_arg = mock_gate.call_args.kwargs["result"]
    assert result_arg.get("static_analysis_incomplete") is True, \
        "정적분석 타임아웃 시 result 에 static_analysis_incomplete=True 마커가 없음 — auto-merge 차단 불가"


async def test_pipeline_persists_incomplete_marker_to_saved_analysis(mock_deps):
    """정적분석 incomplete 시 DB 저장되는 Analysis.result 에도 마커가 영속돼야 한다 (사이클 164 회고 P1 종단 봉인).

    기존 test 는 마커→run_gate_check 전파만 검증 — 본 테스트는 _save_and_gate 가 result_dict 에
    마커를 심어 db.add 되는 Analysis.result 에 영속되는지(관측 마커 겸용) end-to-end 봉인.
    """
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    with patch("src.worker.pipeline._run_static_with_timeout",
               new=AsyncMock(return_value=([], True))):
        with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
            await run_analysis_pipeline("pull_request", PR_DATA)

    analysis_added = mock_deps["db"].add.call_args_list[-1][0][0]
    assert analysis_added.result.get("static_analysis_incomplete") is True, \
        "저장된 Analysis.result 에 incomplete 마커가 영속되지 않음 — 관측/재게이트 회귀 위험"


async def test_pipeline_no_incomplete_marker_when_static_ok(mock_deps):
    """정적분석 정상 완료 시 result 에 static_analysis_incomplete 마커가 없어야 한다 (회귀 가드)."""
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch
    from src.analyzer.io.static import StaticAnalysisResult

    mock_db = mock_deps["db"]
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1), None, MagicMock(id=1), None,
    ]
    mock_db.refresh = MagicMock()

    from src.config_manager.manager import RepoConfigData

    with patch("src.worker.pipeline._run_static_with_timeout",
               new=AsyncMock(return_value=([StaticAnalysisResult(filename="a.py", issues=[])], False))):
        with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
            with patch("src.worker.pipeline.get_repo_config",
                       return_value=RepoConfigData(repo_full_name="owner/repo")):
                await run_analysis_pipeline("pull_request", PR_DATA)

    mock_gate.assert_called_once()
    result_arg = mock_gate.call_args.kwargs["result"]
    assert "static_analysis_incomplete" not in result_arg, \
        "정상 완료인데 static_analysis_incomplete 마커가 잘못 설정됨"


# ---------------------------------------------------------------------------
# Task 1 — SHA 중복 체크 이동 및 result dict ai_review_status 필드 테스트
# (Red 단계: SHA 중복 체크가 아직 review_code 이전으로 이동하지 않음)
# ---------------------------------------------------------------------------

async def test_sha_duplicate_skips_before_review_code(mock_deps):
    """중복 SHA가 감지되면 review_code가 호출되지 않아야 한다.

    현재 구현은 review_code 호출 후 DB 저장 직전에 중복 체크하므로 이 테스트는 Red 상태다.
    구현 후: SHA 중복 체크를 repo 등록 직후, 파일 fetch 전으로 이동하면 Green이 된다.
    """
    # 첫 번째 세션: repo 없음 → 생성, analysis 조회 시 existing 감지 (파일 fetch 전 조기 종료)
    existing_analysis = MagicMock()
    mock_deps["find_repo"].side_effect = [None, mock_deps["mock_repo"]]
    mock_deps["find_analysis"].return_value = existing_analysis

    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    # SHA 중복 → review_code 미호출
    mock_deps["ai"].assert_not_called()


async def test_sha_duplicate_skips_before_file_fetch(mock_deps):
    """중복 SHA가 감지되면 get_push_files / get_pr_files가 호출되지 않아야 한다."""
    existing_analysis = MagicMock()
    mock_deps["find_repo"].side_effect = [None, mock_deps["mock_repo"]]
    mock_deps["find_analysis"].return_value = existing_analysis

    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    # SHA 중복 → 파일 fetch 미호출
    mock_deps["push"].assert_not_called()


async def test_result_dict_contains_ai_review_status(mock_deps):
    """build_analysis_result_dict() 결과에 ai_review_status 키가 포함되어야 한다.

    현재 build_analysis_result_dict는 ai_review_status를 반환하지 않으므로 Red 상태다.
    구현 후: ai_review.status 값을 result dict에 포함하면 Green이 된다.
    """
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    analysis_added = mock_deps["db"].add.call_args_list[-1][0][0]
    # result dict에 ai_review_status 키가 존재해야 한다
    assert "ai_review_status" in analysis_added.result


# ---------------------------------------------------------------------------
# 알림 디스패처(build_notification_tasks) 조합 검증
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
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        discord_webhook_url="https://discord.com/api/webhooks/test",
    )
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.discord.send_discord_notification",
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
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    # discord_webhook_url 미설정
    config = RepoConfigData(repo_full_name="owner/repo")
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.discord.send_discord_notification",
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
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        slack_webhook_url="https://hooks.slack.com/services/T000/B000/xxx",
    )
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.slack.send_slack_notification",
                   new_callable=AsyncMock) as mock_slack:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_slack.assert_called_once()


async def test_repo_config_none_sends_only_telegram(mock_deps):
    """get_repo_config 로드 실패 시 Telegram 만 발송되고 Discord/Slack은 미발송이다."""
    from src.worker.pipeline import run_analysis_pipeline

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    # get_repo_config 예외 → pipeline이 repo_config=None으로 fallback
    from sqlalchemy.exc import SQLAlchemyError
    with patch("src.worker.pipeline.get_repo_config", side_effect=SQLAlchemyError("config error")):
        with patch("src.notifier.discord.send_discord_notification",
                   new_callable=AsyncMock) as mock_discord:
            with patch("src.notifier.slack.send_slack_notification",
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
    from src.config_manager.manager import RepoConfigData

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    with patch("src.worker.pipeline.run_gate_check",
               new_callable=AsyncMock, side_effect=Exception("gate error")):
        with patch("src.worker.pipeline.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
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
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        n8n_webhook_url="https://n8n.example.com/webhook/test",
    )
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.n8n.notify_n8n", new_callable=AsyncMock) as mock_n8n:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_n8n.assert_called_once()


# ---------------------------------------------------------------------------
# 신규 알림 — commit_comment / create_issue
# ---------------------------------------------------------------------------

async def test_commit_comment_called_on_push_when_enabled(mock_deps):
    """commit_comment=True + Push 이벤트 → post_commit_comment 호출."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(repo_full_name="owner/repo", commit_comment=True)
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.github_commit_comment.post_commit_comment",
                   new_callable=AsyncMock) as mock_cc:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_cc.assert_called_once()


async def test_commit_comment_not_called_on_pr_event(mock_deps):
    """commit_comment=True여도 PR 이벤트에서는 호출되지 않는다 (PR은 gate의 pr_review_comment가 처리)."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(repo_full_name="owner/repo", commit_comment=True)
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.github_commit_comment.post_commit_comment",
                   new_callable=AsyncMock) as mock_cc:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("pull_request", PR_DATA)

    mock_cc.assert_not_called()


async def test_commit_comment_not_called_when_disabled(mock_deps):
    """commit_comment=False(기본값)일 때는 Push 이벤트에서도 호출되지 않는다."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(repo_full_name="owner/repo", commit_comment=False)
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.github_commit_comment.post_commit_comment",
                   new_callable=AsyncMock) as mock_cc:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_cc.assert_not_called()


async def test_create_issue_called_on_low_score(mock_deps):
    """create_issue=True + score < reject_threshold → create_low_score_issue 호출."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData
    from src.scorer.calculator import ScoreResult

    # 낮은 점수로 덮어쓰기
    # Overwrite with a low score.
    mock_deps["score"].return_value = ScoreResult(
        total=30, grade="F",
        code_quality_score=10, security_score=10,
        breakdown={"code_quality": 10, "security": 10,
                   "commit_message": 5, "ai_review": 3, "test_coverage": 2},
    )

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        create_issue=True,
        reject_threshold=50,
    )
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.github_issue.create_low_score_issue",
                   new_callable=AsyncMock) as mock_issue:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_issue.assert_called_once()


async def test_create_issue_called_on_security_high_even_when_score_high(mock_deps):
    """create_issue=True + bandit HIGH 존재 → 점수가 높아도 Issue 생성."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData
    from src.analyzer.io.static import StaticAnalysisResult, AnalysisIssue

    # 점수 높게 유지 (85) → 보안 HIGH만으로 트리거돼야 함
    # Keep score high (85) → issue creation must be triggered by bandit HIGH alone.
    high_issue_result = StaticAnalysisResult(
        filename="app.py",
        issues=[AnalysisIssue(tool="bandit", severity="HIGH",
                              message="B602: subprocess call with shell=True", line=10)],
    )

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        create_issue=True,
        reject_threshold=50,
    )
    with patch("src.worker.pipeline._run_static_analysis",
               new_callable=AsyncMock, return_value=[high_issue_result]):
        with patch("src.worker.pipeline.get_repo_config", return_value=config):
            with patch("src.notifier.github_issue.create_low_score_issue",
                       new_callable=AsyncMock) as mock_issue:
                with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                    await run_analysis_pipeline("push", PUSH_DATA)

    mock_issue.assert_called_once()


async def test_create_issue_called_only_once_when_both_conditions_match(mock_deps):
    """점수 낮고 보안 HIGH 둘 다여도 Issue는 1회만 생성된다 (OR, 중복 방지)."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData
    from src.scorer.calculator import ScoreResult
    from src.analyzer.io.static import StaticAnalysisResult, AnalysisIssue

    mock_deps["score"].return_value = ScoreResult(
        total=30, grade="F",
        code_quality_score=10, security_score=10,
        breakdown={"code_quality": 10, "security": 10,
                   "commit_message": 5, "ai_review": 3, "test_coverage": 2},
    )

    high_issue_result = StaticAnalysisResult(
        filename="app.py",
        issues=[AnalysisIssue(tool="bandit", severity="HIGH", message="B602", line=10)],
    )

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(
        repo_full_name="owner/repo",
        create_issue=True,
        reject_threshold=50,
    )
    with patch("src.worker.pipeline._run_static_analysis",
               new_callable=AsyncMock, return_value=[high_issue_result]):
        with patch("src.worker.pipeline.get_repo_config", return_value=config):
            with patch("src.notifier.github_issue.create_low_score_issue",
                       new_callable=AsyncMock) as mock_issue:
                with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                    await run_analysis_pipeline("push", PUSH_DATA)

    assert mock_issue.call_count == 1


async def test_create_issue_not_called_when_disabled(mock_deps):
    """create_issue=False(기본값)일 때는 점수 낮아도 Issue 생성되지 않는다."""
    from src.worker.pipeline import run_analysis_pipeline
    from src.config_manager.manager import RepoConfigData
    from src.scorer.calculator import ScoreResult

    mock_deps["score"].return_value = ScoreResult(
        total=30, grade="F",
        code_quality_score=10, security_score=10,
        breakdown={"code_quality": 10, "security": 10,
                   "commit_message": 5, "ai_review": 3, "test_coverage": 2},
    )

    mock_repo = MagicMock(id=1)
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None, None, mock_repo, None,
    ]
    mock_deps["db"].refresh = MagicMock()

    config = RepoConfigData(repo_full_name="owner/repo", create_issue=False)
    with patch("src.worker.pipeline.get_repo_config", return_value=config):
        with patch("src.notifier.github_issue.create_low_score_issue",
                   new_callable=AsyncMock) as mock_issue:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)

    mock_issue.assert_not_called()


# ---------------------------------------------------------------------------
# Phase H PR-3A — PyGithub blocking I/O 가 asyncio.to_thread 로 wrap 됨
# 12-에이전트 감사 Critical C3 — sync PyGithub 가 async 컨텍스트에서 직접
# 호출되어 이벤트 루프 블록. _collect_files 호출 시 asyncio.to_thread 로 wrap.
# ---------------------------------------------------------------------------


async def test_collect_files_wrapped_in_asyncio_to_thread(mock_deps):
    """_collect_files (PyGithub sync I/O) 가 asyncio.to_thread 경유로 호출된다.

    sync 호출이 이벤트 루프를 블록하면 같은 BackgroundTask 슬롯에서 다른
    webhook 처리가 정체. asyncio.to_thread 로 별도 스레드에서 실행해야 안전.
    """
    from src.worker.pipeline import run_analysis_pipeline
    from unittest.mock import AsyncMock, patch

    # asyncio.to_thread 호출 횟수 추적
    real_to_thread = __import__("asyncio").to_thread
    to_thread_calls = []

    async def _spy_to_thread(fn, *args, **kwargs):
        to_thread_calls.append(getattr(fn, "__name__", str(fn)))
        return await real_to_thread(fn, *args, **kwargs)

    with patch("src.worker.pipeline.asyncio.to_thread", side_effect=_spy_to_thread), \
         patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
        await run_analysis_pipeline("push", PUSH_DATA)

    # _collect_files 가 to_thread 경유 호출됨
    assert "_collect_files" in to_thread_calls, (
        f"_collect_files 미호출 — to_thread 호출 목록: {to_thread_calls}"
    )


# ── 타임아웃 테스트 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_static_with_timeout_returns_empty_on_timeout():
    """완료된 파일이 하나도 없는 채 deadline 초과 시 (빈 리스트, incomplete=True) 반환.

    incomplete=True 는 auto-merge 차단 신호 — 미분석 코드 자동 머지 방지.
    """
    import asyncio
    from src.worker.pipeline import _run_static_with_timeout
    from src.github_client.diff import ChangedFile

    async def _slow(files, repo_config=None):          # 타임아웃보다 오래 걸리는 가짜 분석
        await asyncio.sleep(10)
        return []

    with patch("src.worker.pipeline._run_static_analysis", side_effect=_slow):
        with patch("src.worker.pipeline.PIPELINE_ANALYSIS_TIMEOUT", 0.01):
            result = await _run_static_with_timeout([ChangedFile("a.py", "x=1\n", "@@")])

    assert result == ([], True)


@pytest.mark.asyncio
async def test_run_static_with_timeout_returns_results_when_fast():
    """분석이 타임아웃 내에 완료되면 (정상 결과, incomplete=False) 를 반환해야 한다."""
    from src.worker.pipeline import _run_static_with_timeout
    from src.analyzer.io.static import StaticAnalysisResult
    from src.github_client.diff import ChangedFile

    fake_result = [StaticAnalysisResult(filename="app.py", issues=[])]

    async def _fast(files, repo_config=None):
        return fake_result

    with patch("src.worker.pipeline._run_static_analysis", side_effect=_fast):
        result = await _run_static_with_timeout([ChangedFile("app.py", "x=1\n", "@@")])

    assert result == (fake_result, False)


@pytest.mark.asyncio
async def test_run_static_with_timeout_preserves_partial_results_on_deadline():
    """배치 deadline 초과 시 그때까지 완료된 파일 결과를 보존하고 incomplete=True 반환 (Q3 B).

    이전 동작은 타임아웃 시 전량 폐기 ([], True) 였으나, 부분결과 보존으로
    완료된 파일 분석은 점수에 반영되고 incomplete 마커로 auto-merge 만 차단한다.
    """
    import asyncio
    from src.worker.pipeline import _run_static_with_timeout
    from src.analyzer.io.static import StaticAnalysisResult
    from src.github_client.diff import ChangedFile

    f1 = ChangedFile("a.py", "x=1\n", "@@")
    f2 = ChangedFile("b.py", "y=2\n", "@@")
    r1 = StaticAnalysisResult(filename="a.py", issues=[])

    async def _per_file(files, repo_config=None):
        # _run_static_with_timeout 는 파일별로 [f] 단일 리스트로 호출한다
        f = files[0]
        if f.filename == "a.py":
            return [r1]
        await asyncio.sleep(10)  # b.py: 느림 → deadline 초과
        return [StaticAnalysisResult(filename="b.py", issues=[])]

    with patch("src.worker.pipeline._run_static_analysis", side_effect=_per_file):
        with patch("src.worker.pipeline.PIPELINE_ANALYSIS_TIMEOUT", 0.2):
            results, incomplete = await _run_static_with_timeout([f1, f2])

    assert incomplete is True            # deadline 초과 → auto-merge 차단 신호
    assert results == [r1]               # a.py 부분 결과 보존, b.py 는 폐기 (deadline)


@pytest.mark.asyncio
async def test_run_static_with_timeout_isolates_single_file_exception():
    """한 파일의 analyze_file 예외가 다른 파일 분석·AI리뷰를 막지 않고 빈 결과로 격리된다 (Q2 A).

    이전 동작은 list comprehension 이라 한 파일 예외가 전체 배치를 중단시켰으나,
    파일 단위 격리로 실패 파일은 빈 StaticAnalysisResult 가 되고 나머지는 정상 분석된다.
    일부 파일만 실패하면 incomplete=False (Q2=A — 나머지 정상 분석 보존).
    """
    from src.worker.pipeline import _run_static_with_timeout
    from src.analyzer.io.static import StaticAnalysisResult
    from src.github_client.diff import ChangedFile

    good = StaticAnalysisResult(filename="good.py", issues=[])

    async def _per_file(files, repo_config=None):
        f = files[0]
        if f.filename == "bad.py":
            raise OSError("disk full")
        return [good]

    files = [ChangedFile("bad.py", "x\n", "@@"), ChangedFile("good.py", "y\n", "@@")]
    with patch("src.worker.pipeline._run_static_analysis", side_effect=_per_file):
        results, incomplete = await _run_static_with_timeout(files)

    assert len(results) == 2
    assert results[0].filename == "bad.py" and results[0].issues == []  # 격리된 빈 결과
    assert results[1] is good                                            # 정상 파일 보존
    assert incomplete is False                                           # 일부 실패는 incomplete 아님


@pytest.mark.asyncio
async def test_run_static_with_timeout_marks_incomplete_when_all_files_fail():
    """비어있지 않은 배치의 모든 파일이 analyze_file 예외로 실패하면 incomplete=True (안전망).

    실 분석 0건이므로 빈 결과의 만점 인플레가 미분석 코드 auto-merge 로 이어지지 않도록
    fail-closed 처리한다 (Q2=A 격리가 전량-실패 시 만들 수 있는 fail-open 회귀 방지).
    """
    from src.worker.pipeline import _run_static_with_timeout
    from src.github_client.diff import ChangedFile

    async def _all_fail(files, repo_config=None):
        raise OSError("disk full")

    files = [ChangedFile("a.py", "x\n", "@@"), ChangedFile("b.py", "y\n", "@@")]
    with patch("src.worker.pipeline._run_static_analysis", side_effect=_all_fail):
        results, incomplete = await _run_static_with_timeout(files)

    assert len(results) == 2                       # 빈 결과 2개 보존 (관측용)
    assert all(r.issues == [] for r in results)
    assert incomplete is True                      # 전량 실패 → auto-merge 차단 신호


# ---------------------------------------------------------------------------
# _send_notifications — BaseException 처리 (B2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_notifications_handles_cancelled_error():
    """asyncio.CancelledError(BaseException 서브클래스)가 로그 출력 후 묵살되어야 한다.
    CancelledError must be logged and not re-raised (BaseException fix).
    """
    import asyncio
    from src.worker.pipeline import _send_notifications  # pylint: disable=import-outside-toplevel

    cancelled = asyncio.CancelledError("cancelled")
    with patch("src.worker.pipeline.logger") as mock_logger:
        # CancelledError를 반환하는 gather 결과 시뮬레이션
        with patch("src.worker.pipeline.asyncio.gather",
                   new=AsyncMock(return_value=[cancelled])):
            # 예외가 전파되지 않아야 한다 — BaseException 경로 커버
            await _send_notifications([AsyncMock()], ["test_channel"])
    mock_logger.error.assert_called_once()
    assert "test_channel" in mock_logger.error.call_args[0][1]


# ---------------------------------------------------------------------------
# _regate_pr_if_needed — result=None 가드 (B3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regate_pr_skips_when_result_is_none():
    """existing.result=None이면 run_gate_check를 호출하지 않고 조기 종료해야 한다.
    Must return early without calling run_gate_check when existing.result is None.
    """
    from src.worker.pipeline import _regate_pr_if_needed  # pylint: disable=import-outside-toplevel

    mock_db = MagicMock()
    # pr_number=None → guard 통과, sha lookup 필요
    mock_repo = MagicMock(id=1, full_name="owner/repo")
    mock_repo.owner = MagicMock(plaintext_token="tok")
    # pr_number=None이어야 `existing.pr_number == pr_number(5)` 조건 통과
    mock_existing = MagicMock(id=10, pr_number=None, result=None)

    with patch("src.worker.pipeline.repository_repo") as mock_repo_repo:
        mock_repo_repo.find_by_full_name.return_value = mock_repo
        with patch("src.worker.pipeline.analysis_repo") as mock_analysis_repo:
            mock_analysis_repo.find_by_sha.return_value = mock_existing
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
                await _regate_pr_if_needed(mock_db, "owner/repo", "abc123", 5)

    mock_gate.assert_not_called()


@pytest.mark.asyncio
async def test_race_recover_existing_skips_when_result_is_none():
    """existing.result=None이면 run_gate_check를 호출하지 않고 repo_config를 반환해야 한다.
    Must return repo_config without calling run_gate_check when existing.result is None.
    """
    from src.worker.pipeline import _race_recover_existing  # pylint: disable=import-outside-toplevel
    from src.worker.pipeline import _AnalysisSaveParams  # pylint: disable=import-outside-toplevel

    mock_db = MagicMock()
    # pr_number가 있어야 'params.pr_number is None' early-return을 통과
    # existing.pr_number=None이어야 'existing.pr_number is not None' early-return을 통과
    mock_existing = MagicMock(id=20, pr_number=None, result=None)
    mock_repo_config = MagicMock()

    params = _AnalysisSaveParams(
        repo_name="owner/repo",
        commit_sha="abc123",
        commit_message="feat: test",
        pr_number=7,
        owner_token="tok",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=MagicMock(),
    )

    with patch("src.worker.pipeline.get_repo_config", return_value=mock_repo_config):
        with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
            result = await _race_recover_existing(mock_db, params, mock_existing)

    mock_gate.assert_not_called()
    assert result is mock_repo_config


async def test_race_recover_existing_skips_when_pr_number_already_set():
    """existing.pr_number 가 이미 다른 non-None 값이면 덮어쓰지 않고 run_gate_check 미호출 (first-writer-wins).

    `_regate_pr_if_needed`(#794)와 대칭 — 동일 head SHA 를 두 PR 이 공유하는 race 경로에서도
    잘못된 PR 에 gate 가 적용되는 것을 차단한다 (사이클 164 회고 P2 — 대칭 가드 봉인).
    """
    from src.worker.pipeline import _race_recover_existing  # pylint: disable=import-outside-toplevel
    from src.worker.pipeline import _AnalysisSaveParams  # pylint: disable=import-outside-toplevel

    mock_db = MagicMock()
    # existing.pr_number=10 (이미 PR #10 으로 gate됨), 신규 params.pr_number=11
    mock_existing = MagicMock(id=20, pr_number=10, result={"score": 80})
    mock_repo_config = MagicMock()

    params = _AnalysisSaveParams(
        repo_name="owner/repo",
        commit_sha="abc123",
        commit_message="feat: test",
        pr_number=11,
        owner_token="tok",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=MagicMock(),
    )

    with patch("src.worker.pipeline.get_repo_config", return_value=mock_repo_config):
        with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
            result = await _race_recover_existing(mock_db, params, mock_existing)

    mock_gate.assert_not_called()
    assert mock_existing.pr_number == 10, "pr_number 가 덮어써짐 — first-writer-wins 위반"
    mock_db.commit.assert_not_called()
    assert result is mock_repo_config


# ---------------------------------------------------------------------------
# branch/tag 삭제 push (zero-SHA) 조기 종료 회귀 테스트 (정합성 감사 area=gate P2)
# Branch/tag-delete push (zero-SHA) early-termination regression tests
#
# GitHub 은 브랜치/태그 삭제 push 시 data["after"] 를 all-zeros SHA("0"*40, zero-SHA
# 컨벤션)로, head_commit 을 None 으로 보낸다. 분석할 커밋이 없으므로 _ensure_repo
# (repo 등록) + _collect_files (get_push_files API) 진입 전에 즉시 종료해야 한다.
# 가드 부재 시 존재하지 않는 SHA 조회 → 매번 404 + 예외 로그 (pipeline.py:251).
#
# GitHub sends data["after"] as an all-zeros SHA ("0"*40, the zero-SHA convention)
# and head_commit as None on a branch/tag-delete push. With no commit to analyze, the
# pipeline must terminate before _ensure_repo / _collect_files. Without the guard it
# queries a nonexistent SHA → 404 + exception log on every delete push.
# ---------------------------------------------------------------------------


async def test_branch_delete_zero_sha_push_skips_pipeline(mock_deps):
    """all-zeros SHA(brach/tag 삭제 push)는 repo 등록·파일 수집 전에 조기 종료해야 한다.
    An all-zeros SHA (branch/tag-delete push) must terminate before repo lookup / file collection.
    """
    zero_sha_data = {
        "repository": {"full_name": "owner/repo"},
        "after": "0" * 40,       # GitHub zero-SHA (branch/tag delete) / GitHub zero-SHA(브랜치·태그 삭제)
        "head_commit": None,     # 삭제 push 는 head_commit None / delete push sends head_commit None
        "commits": [],
    }
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", zero_sha_data)

    # 가드로 _ensure_repo / _collect_files 진입 전 return → repo 조회·파일 수집 모두 미호출
    # Guard returns before _ensure_repo / _collect_files → neither repo lookup nor file fetch runs
    mock_deps["find_repo"].assert_not_called()
    mock_deps["push"].assert_not_called()


async def test_empty_sha_push_skips_pipeline(mock_deps):
    """빈 SHA("") push 도 동일하게 repo 등록·파일 수집 전에 조기 종료해야 한다.
    An empty SHA ("") push must likewise terminate before repo lookup / file collection.
    """
    empty_sha_data = {
        "repository": {"full_name": "owner/repo"},
        "after": "",             # 빈 SHA — after 키 누락 시 _extract_event_metadata default
        "head_commit": None,     # 삭제 push 는 head_commit None / delete push sends head_commit None
        "commits": [],
    }
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", empty_sha_data)

    # 빈 SHA 도 분석 대상 커밋 없음 → repo 조회·파일 수집 모두 미호출
    # Empty SHA also has no commit to analyze → neither repo lookup nor file fetch runs
    mock_deps["find_repo"].assert_not_called()
    mock_deps["push"].assert_not_called()


@pytest.mark.parametrize(
    "sha,expected_blank",
    [
        ("0" * 40, True),    # GitHub zero-SHA (40-zero branch/tag delete) — blank
        ("", True),          # 빈 SHA / empty SHA — blank
        ("0" * 7, True),     # short-SHA all-zeros (길이 무관) — blank
        ("abc123def456", False),               # 정상 SHA / normal SHA
        ("0a1b2c3d4e5f60718293a4b5c6d7e8f901020304", False),  # 0 포함 실 40-hex — not blank
        ("0000000a", False),                   # 한 글자만 비-0 → not blank
    ],
)
def test_is_blank_sha_classifies_zero_and_empty(sha, expected_blank):
    """_is_blank_sha 는 빈/all-zeros SHA 만 blank 로 판정하고 정상 hex SHA 는 통과시킨다.
    _is_blank_sha flags only empty/all-zeros SHAs; any SHA with a non-zero char passes.

    set(sha)=={"0"} 오탐(예: <= 로 잘못 수정) 회귀를 직접 봉인 (pipeline-reviewer P2-B).
    Directly seals regressions in the set comparison (e.g. an accidental <= rewrite).
    """
    from src.worker.pipeline import _is_blank_sha  # pylint: disable=import-outside-toplevel
    assert _is_blank_sha(sha) is expected_blank


# ---------------------------------------------------------------------------
# _ensure_repo 동시 INSERT race (IntegrityError) 복구 회귀 테스트 (정합성 감사 area=gate P2)
# _ensure_repo concurrent-INSERT race (IntegrityError) recovery regression tests
# (integrity audit area=gate P2 — pipeline.py:263)
#
# 동시 webhook 2건이 같은 신규 repo 를 처리하면 둘 다 find_by_full_name → None →
# save_new → db.commit() 시도 → Repository.full_name unique 제약으로 한 워커가
# IntegrityError 를 맞는다. 곧 추가할 수정은 save_new+commit 을 try/except IntegrityError
# 로 감싸 — IntegrityError 시 db.rollback() + find_by_full_name 재조회로 복구한다.
# When two concurrent webhooks process the same new repo, both find_by_full_name → None →
# save_new → db.commit(); one worker hits IntegrityError on the full_name unique constraint.
# The upcoming fix wraps save_new+commit in try/except IntegrityError — on IntegrityError it
# rolls back and re-queries find_by_full_name to recover the row another worker created.
# ---------------------------------------------------------------------------


def test_ensure_repo_recovers_from_concurrent_insert_race():
    """동시 INSERT race 로 commit 이 IntegrityError 면 rollback 후 재조회한 repo 로 복구해야 한다.
    On a concurrent-INSERT IntegrityError at commit, must roll back and recover via re-fetch.

    현재 구현(_ensure_repo 가 IntegrityError 를 잡지 않음)에서는 db.commit() 의
    IntegrityError 가 그대로 전파되어 (mock_existing, "ghp_test") 반환 단언 도달 전에
    호출 자체가 raise → 테스트가 에러로 실패 = Red.
    With the current impl (no try/except), the commit IntegrityError propagates and the call
    raises before the (mock_existing, "ghp_test") assertion is reached → test errors out = Red.
    """
    from src.worker.pipeline import _ensure_repo  # pylint: disable=import-outside-toplevel
    from sqlalchemy.exc import IntegrityError  # pylint: disable=import-outside-toplevel

    # db.commit() 이 unique 제약 위반으로 IntegrityError 를 던지도록 mock
    # Mock db.commit() to raise IntegrityError on the unique-constraint violation
    mock_db = MagicMock()
    mock_db.commit.side_effect = IntegrityError(
        "INSERT repositories", {}, Exception("duplicate key full_name")
    )

    # 다른 워커가 이미 만든 repo (재조회로 복구되는 대상)
    # The repo another worker already created (recovered via re-fetch)
    mock_existing = MagicMock(id=5)
    mock_existing.owner = None  # owner_token 분기 skip → owner_token 은 "ghp_test" 유지
    #                            # skip owner_token branch → owner_token stays "ghp_test"

    with (
        # 1차 None → save_new 진입 / 2차 mock_existing → race 복구 재조회
        # 1st None → enters save_new / 2nd mock_existing → race-recovery re-fetch
        patch(
            "src.worker.pipeline.repository_repo.find_by_full_name",
            side_effect=[None, mock_existing],
        ) as mock_find_repo,
        patch(
            "src.worker.pipeline.repository_repo.save_new",
            return_value=MagicMock(),
        ),
        # 중복 분석 없음 → None 반환 끝까지 진행
        # No duplicate analysis → returns None, proceeds to the end
        patch("src.worker.pipeline.analysis_repo.find_by_sha", return_value=None),
        patch("src.worker.pipeline.settings") as mock_settings,
    ):
        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_chat_id = "-100"

        # 핵심(Red): 예외 없이 (mock_existing, "ghp_test") 반환해야 한다
        # Core (Red): must return (mock_existing, "ghp_test") without raising
        result = _ensure_repo(mock_db, "owner/repo", "sha123")

    assert result == (mock_existing, "ghp_test")
    mock_db.rollback.assert_called_once()  # IntegrityError 시 정확히 1회 rollback
    assert mock_find_repo.call_count == 2  # 최초 조회 + race 복구 재조회


def test_ensure_repo_reraises_when_refetch_also_none():
    """재조회도 None 이면 (unique race 가 아닌 진짜 오류) IntegrityError 를 그대로 전파해야 한다.
    If the re-fetch is also None (a real error, not a unique race), must re-raise IntegrityError.

    현재 구현도 commit 시점에서 IntegrityError 를 raise 하나, rollback 미호출 + 재조회 경로
    부재 — 구현 후엔 rollback → 재조회 None → re-raise 경로가 핵심 검증 대상이다.
    The current impl already raises at commit, but without rollback or the re-fetch path; after
    the fix the rollback → re-fetch-None → re-raise path is the behavior under test.
    """
    from src.worker.pipeline import _ensure_repo  # pylint: disable=import-outside-toplevel
    from sqlalchemy.exc import IntegrityError  # pylint: disable=import-outside-toplevel

    mock_db = MagicMock()
    mock_db.commit.side_effect = IntegrityError(
        "INSERT repositories", {}, Exception("duplicate key full_name")
    )

    with (
        # 1차 None → save_new 진입 / 2차도 None → unique race 아님 → 진짜 오류 전파
        # 1st None → enters save_new / 2nd also None → not a unique race → propagate real error
        patch(
            "src.worker.pipeline.repository_repo.find_by_full_name",
            side_effect=[None, None],
        ) as mock_find_repo,
        patch(
            "src.worker.pipeline.repository_repo.save_new",
            return_value=MagicMock(),
        ),
        patch("src.worker.pipeline.analysis_repo.find_by_sha", return_value=None),
        patch("src.worker.pipeline.settings") as mock_settings,
    ):
        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_chat_id = "-100"

        with pytest.raises(IntegrityError):
            _ensure_repo(mock_db, "owner/repo", "sha123")

    # bare commit raise 와 구별되게 rollback → 재조회 → re-raise 경로를 봉인한다 (review 수렴 지적).
    # Seal the rollback → re-fetch → re-raise path distinctly from a bare commit raise (converged review note).
    mock_db.rollback.assert_called_once()
    assert mock_find_repo.call_count == 2
