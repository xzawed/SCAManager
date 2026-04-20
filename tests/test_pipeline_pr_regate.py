"""tests/test_pipeline_pr_regate.py

TDD Red 단계 — push 이벤트 먼저 도착 후 pull_request 이벤트가 뒤따르는 경우
run_analysis_pipeline이 gate 재실행(re-gate)을 올바르게 수행하는지 검증한다.

근본 원인:
    _ensure_repo()가 동일 SHA를 발견하면 즉시 None 반환 → early-return.
    이로 인해 push로 저장된 Analysis(pr_number=None)에 대해
    이후 PR 이벤트에서 run_gate_check가 영구적으로 누락된다.

수정 후 기대 동작:
    pull_request 이벤트에서 동일 SHA + pr_number=None Analysis 발견 시
    → pr_number 업데이트 + run_gate_check 1회 호출 + 알림 dispatcher 미호출
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# DB Base 및 ORM 모델 import (conftest.py가 환경변수 주입 후 실행)
from src.database import Base
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.scorer.calculator import ScoreResult
from src.analyzer.ai_review import AiReviewResult
from src.github_client.diff import ChangedFile


# ---------------------------------------------------------------------------
# 공용 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_db():
    """SQLite in-memory DB 세션 — Repository·Analysis ORM 테이블 포함."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def base_repo(sqlite_db):
    """owner/testrepo Repository를 SQLite DB에 미리 등록해 반환한다."""
    repo = Repository(full_name="owner/testrepo", telegram_chat_id="-100test")
    sqlite_db.add(repo)
    sqlite_db.commit()
    sqlite_db.refresh(repo)
    return repo


@pytest.fixture
def mock_score_result():
    return ScoreResult(
        total=78, grade="B",
        code_quality_score=22, security_score=18,
        breakdown={
            "code_quality": 22, "security": 18,
            "commit_message": 13, "ai_review": 18, "test_coverage": 7,
        },
    )


@pytest.fixture
def mock_ai_result():
    return AiReviewResult(
        commit_score=13, ai_score=18, test_score=7,
        summary="Looks reasonable", suggestions=[],
    )


@pytest.fixture
def mock_files():
    return [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]


# ---------------------------------------------------------------------------
# 공용 mock helper — run_analysis_pipeline의 외부 의존성 일괄 패치
# ---------------------------------------------------------------------------

def _make_mock_session_cls(sqlite_db):
    """SessionLocal()이 sqlite_db 세션을 반환하도록 context-manager mock을 구성한다."""
    mock_session_cls = MagicMock()
    mock_session_cls.return_value.__enter__ = MagicMock(return_value=sqlite_db)
    mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
    return mock_session_cls


# ---------------------------------------------------------------------------
# 시나리오 A: push 먼저 → PR opened — gate 재실행 검증
# ---------------------------------------------------------------------------

async def test_scenario_a_pr_regate_updates_pr_number_and_calls_gate(
    sqlite_db, base_repo, mock_score_result, mock_ai_result, mock_files
):
    """push로 저장된 Analysis(pr_number=None)에 PR 이벤트가 도착하면
    pr_number를 PR 번호로 업데이트하고 run_gate_check를 1회 호출해야 한다."""

    # Given: push 이벤트가 먼저 도착해 pr_number=None Analysis가 존재
    existing_analysis = Analysis(
        repo_id=base_repo.id,
        commit_sha="abc123",
        commit_message="feat: push commit",
        pr_number=None,
        score=75,
        grade="B",
        result={"source": "push"},
    )
    sqlite_db.add(existing_analysis)
    sqlite_db.commit()
    sqlite_db.refresh(existing_analysis)
    existing_id = existing_analysis.id

    pr_data = {
        "repository": {"full_name": "owner/testrepo"},
        "number": 42,
        "pull_request": {
            "head": {"sha": "abc123"},
            "title": "feat: my PR",
            "body": "",
        },
    }

    mock_session_cls = _make_mock_session_cls(sqlite_db)

    with (
        patch("src.worker.pipeline.SessionLocal", mock_session_cls),
        patch("src.worker.pipeline.get_pr_files", return_value=mock_files),
        patch("src.worker.pipeline.review_code", new_callable=AsyncMock, return_value=mock_ai_result),
        patch("src.worker.pipeline.calculate_score", return_value=mock_score_result),
        patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate,
        patch("src.worker.pipeline.build_notification_tasks", return_value=([], [])) as mock_notify,
        patch("src.worker.pipeline.settings") as mock_settings,
    ):
        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_settings.telegram_chat_id = "-100test"
        mock_settings.anthropic_api_key = "sk-test"

        from src.worker.pipeline import run_analysis_pipeline
        await run_analysis_pipeline("pull_request", pr_data)

    # Then: Analysis.pr_number가 42로 업데이트되어야 한다
    sqlite_db.refresh(existing_analysis)
    assert existing_analysis.pr_number == 42, (
        f"pr_number가 업데이트되지 않았습니다: {existing_analysis.pr_number}"
    )

    # Then: run_gate_check가 정확히 1회 호출되어야 한다
    mock_gate.assert_called_once()
    gate_kwargs = mock_gate.call_args.kwargs
    assert gate_kwargs["pr_number"] == 42
    assert gate_kwargs["analysis_id"] == existing_id
    assert gate_kwargs["repo_name"] == "owner/testrepo"

    # Then: build_notification_tasks는 호출되지 않아야 한다 (중복 알림 방지)
    mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# 시나리오 B: PR 이벤트가 신규 SHA로 직접 도착 — 기존 정상 경로 유지
# ---------------------------------------------------------------------------

async def test_scenario_b_new_sha_pr_event_creates_analysis_and_calls_gate(
    sqlite_db, base_repo, mock_score_result, mock_ai_result, mock_files
):
    """SHA=xyz999로 기존 Analysis가 없을 때 PR 이벤트가 도착하면
    새 Analysis(pr_number=43)를 생성하고 run_gate_check를 호출해야 한다."""

    # Given: SHA=xyz999 Analysis가 DB에 없음
    pr_data = {
        "repository": {"full_name": "owner/testrepo"},
        "number": 43,
        "pull_request": {
            "head": {"sha": "xyz999"},
            "title": "feat: brand new PR",
            "body": "",
        },
    }

    mock_session_cls = _make_mock_session_cls(sqlite_db)

    with (
        patch("src.worker.pipeline.SessionLocal", mock_session_cls),
        patch("src.worker.pipeline.get_pr_files", return_value=mock_files),
        patch("src.worker.pipeline.review_code", new_callable=AsyncMock, return_value=mock_ai_result),
        patch("src.worker.pipeline.calculate_score", return_value=mock_score_result),
        patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate,
        patch("src.worker.pipeline.settings") as mock_settings,
    ):
        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_settings.telegram_chat_id = "-100test"
        mock_settings.anthropic_api_key = "sk-test"

        from src.worker.pipeline import run_analysis_pipeline
        await run_analysis_pipeline("pull_request", pr_data)

    # Then: 새 Analysis가 pr_number=43으로 생성되어야 한다
    saved = (
        sqlite_db.query(Analysis)
        .filter_by(commit_sha="xyz999", repo_id=base_repo.id)
        .first()
    )
    assert saved is not None, "새 Analysis가 DB에 생성되지 않았습니다"
    assert saved.pr_number == 43

    # Then: run_gate_check가 호출되어야 한다
    mock_gate.assert_called_once()
    gate_kwargs = mock_gate.call_args.kwargs
    assert gate_kwargs["pr_number"] == 43
    assert gate_kwargs["repo_name"] == "owner/testrepo"


# ---------------------------------------------------------------------------
# 시나리오 C: 동일 SHA + 동일 pr_number 재수신 — gate 재실행 없이 skip
# ---------------------------------------------------------------------------

async def test_scenario_c_same_sha_same_pr_number_skips_gate(
    sqlite_db, base_repo, mock_score_result, mock_ai_result, mock_files
):
    """동일 SHA의 Analysis(pr_number=42)가 이미 존재할 때
    같은 pr_number=42 PR 이벤트를 다시 수신하면
    run_gate_check를 호출하지 않아야 한다 (이미 처리 완료)."""

    # Given: SHA=abc123의 Analysis(pr_number=42)가 이미 존재
    existing_analysis = Analysis(
        repo_id=base_repo.id,
        commit_sha="abc123",
        commit_message="feat: already gated",
        pr_number=42,
        score=78,
        grade="B",
        result={"source": "pr"},
    )
    sqlite_db.add(existing_analysis)
    sqlite_db.commit()

    pr_data = {
        "repository": {"full_name": "owner/testrepo"},
        "number": 42,
        "pull_request": {
            "head": {"sha": "abc123"},
            "title": "feat: already gated",
            "body": "",
        },
    }

    mock_session_cls = _make_mock_session_cls(sqlite_db)

    with (
        patch("src.worker.pipeline.SessionLocal", mock_session_cls),
        patch("src.worker.pipeline.get_pr_files", return_value=mock_files),
        patch("src.worker.pipeline.review_code", new_callable=AsyncMock, return_value=mock_ai_result),
        patch("src.worker.pipeline.calculate_score", return_value=mock_score_result),
        patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate,
        patch("src.worker.pipeline.build_notification_tasks", return_value=([], [])) as mock_notify,
        patch("src.worker.pipeline.settings") as mock_settings,
    ):
        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_settings.telegram_chat_id = "-100test"
        mock_settings.anthropic_api_key = "sk-test"

        from src.worker.pipeline import run_analysis_pipeline
        await run_analysis_pipeline("pull_request", pr_data)

    # Then: run_gate_check는 호출되지 않아야 한다 (이미 동일 pr_number로 처리됨)
    mock_gate.assert_not_called()

    # Then: Analysis.pr_number는 그대로 42여야 한다
    sqlite_db.refresh(existing_analysis)
    assert existing_analysis.pr_number == 42


# ---------------------------------------------------------------------------
# 시나리오 D: pr_number UPDATE 중 SQLAlchemyError 발생 → rollback 후 조용히 return
# ---------------------------------------------------------------------------

async def test_regate_pr_if_needed_rolls_back_on_commit_error(caplog):
    """pr_number UPDATE 에서 SQLAlchemyError 발생 시 rollback 후 조용히 return."""
    import logging
    from sqlalchemy.exc import SQLAlchemyError
    from src.worker import pipeline as pipeline_mod

    db = MagicMock()
    db.commit.side_effect = SQLAlchemyError("db down")

    existing = MagicMock()
    existing.pr_number = None
    existing.id = 42
    existing.result = {"score": 80}

    repo = MagicMock()
    repo.id = 1
    repo.owner = None  # error path returns before owner_token branch

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=existing), \
         patch.object(pipeline_mod, "run_gate_check", new=AsyncMock()) as run_gate, \
         caplog.at_level(logging.ERROR, logger="src.worker.pipeline"):
        await pipeline_mod._regate_pr_if_needed(
            db=db, repo_name="o/r", commit_sha="deadbeef", pr_number=7,
        )

    db.rollback.assert_called_once()
    db.commit.assert_called_once()
    run_gate.assert_not_called()
    assert any("pr_number update failed" in r.message for r in caplog.records)
