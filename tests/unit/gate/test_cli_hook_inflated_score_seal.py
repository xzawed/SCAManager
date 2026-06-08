"""CLI-hook parse_error 인플레 점수 → PR gate fail-open 봉인 회귀 가드 (사이클 165 회고 P2-②).

#25 가 CLI hook 의 score/grade **컬럼** 만 NULL 화했으나 `result` dict 의 인플레 score(89)는 보존되고
(build_analysis_result_dict), gate(engine.run_gate_check)는 컬럼이 아닌 **result dict 의 score**
(engine.py `result.get("score", 0)`)를 읽는다. 따라서 CLI-hook parse_error 분석이 동일 SHA PR 로
_regate_pr_if_needed 될 때 auto-merge/auto-approve 차단은 **#8 ai_review_failed 단일 가드**에 전적으로
의존한다(static_analysis_incomplete 가드는 CLI 훅이 정적분석을 안 돌려 incomplete=False 라 무력).

본 테스트는 그 단일 가드가 run_gate_check orchestrator 수준에서 CLI-hook 의 인플레 result 를 받아
실제로 auto-merge·auto-approve 를 차단함을 봉인한다 — #8 가드 제거/우회(AI_REVIEW_FAILED_STATUSES
변경 등) 시 fail-open 회귀로 즉시 fail. (기존 test_gate_actions 는 액션 단위 / 본 테스트는 orchestrator
+ 실제 CLI-hook result 형태로 결합 불변을 봉인.)
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config_manager.manager import RepoConfigData
from src.database import Base
from src.gate.engine import run_gate_check
from src.models.analysis import Analysis  # noqa: F401 — create_all 테이블 등록
from src.models.repository import Repository  # noqa: F401


def _cli_hook_result(ai_status: str) -> dict:
    """CLI-hook 분석 result dict — score 컬럼은 NULL(#25)이나 dict score 는 인플레 89 보존.

    Build the result dict a CLI hook persists: the score/grade DB columns are NULL on parse_error
    (#25), but the result dict keeps the inflated 89 — which is exactly what the gate reads.
    """
    return {
        "score": 89,
        "grade": "B",
        "ai_review_status": ai_status,
        "source": "cli",
        "breakdown": {
            "commit_message": 13, "code_quality": 25, "security": 20,
            "ai_review": 21, "test_coverage": 10,
        },
    }


async def test_run_gate_check_cli_hook_parse_error_blocks_automerge_and_approve():
    """CLI-hook parse_error 인플레 89 점수가 gate 에 도달해도 #8 가드가 auto-merge·approve 차단."""
    config = RepoConfigData(
        repo_full_name="owner/repo",
        auto_merge=True, merge_threshold=75,       # AutoMergeAction applicable
        approve_mode="auto", approve_threshold=70,  # ApproveAction applicable
        pr_review_comment=False,                     # ReviewCommentAction 비활성 (DB I/O 회피)
    )
    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am, \
         patch("src.gate.actions.approve.post_github_review", new_callable=AsyncMock) as mock_review:
        await run_gate_check(
            repo_name="owner/repo", pr_number=7, analysis_id=1,
            result=_cli_hook_result("parse_error"),
            github_token="t", db=MagicMock(), config=config,
        )
    # 두 액션 모두 ai_review_failed 가드에서 early-return (SessionLocal 전) → 부수효과 미실행.
    mock_am.assert_not_awaited()      # auto-merge 차단 (#8)
    mock_review.assert_not_awaited()  # auto-approve 차단 (#8)


async def test_run_gate_check_cli_hook_success_allows_automerge():
    """대조군: ai_review_status='success' 면 동일 인플레 점수라도 정상 auto-merge 진행(가드가 정상 경로 미차단)."""
    config = RepoConfigData(
        repo_full_name="owner/repo",
        auto_merge=True, merge_threshold=75,
        approve_mode="disabled",     # ApproveAction 비활성 — auto_merge 만 격리 검증(SessionLocal 회피)
        pr_review_comment=False,
    )
    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
        await run_gate_check(
            repo_name="owner/repo", pr_number=7, analysis_id=1,
            result=_cli_hook_result("success"),
            github_token="t", db=MagicMock(), config=config,
        )
    mock_am.assert_awaited_once()  # success → auto-merge 정상 진행 (가드가 정상 경로 미차단)


@pytest.fixture
def db_session():
    """in-memory SQLite 단일 세션 — _regate 배선 테스트용(run_gate_check 는 mock 이라 단일 세션 충분)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


async def test_regate_passes_cli_hook_parse_error_result_to_gate(db_session):
    """_regate→gate 배선 봉인: CLI-hook parse_error Analysis(컬럼 NULL)가 동일 SHA PR 로 _regate 될 때
    run_gate_check 에 인플레 result(ai_review_status='parse_error', dict score 89)가 변형 없이 전달됨.

    gate 측 차단은 위 orchestrator 테스트가 봉인 — 본 테스트는 _regate 가 컬럼 NULL 과 무관하게
    인플레 result dict 를 gate 로 흘려보냄을 확인해 #8 ↔ _regate 결합을 봉인(기존 _regate 통합
    테스트는 run_gate_check 를 mock 한 채 source=push/pr 만 다뤄 본 경로 미보호).
    """
    from src.worker.pipeline import _regate_pr_if_needed  # pylint: disable=import-outside-toplevel

    repo = Repository(full_name="owner/repo")
    db_session.add(repo)
    db_session.flush()
    analysis = Analysis(
        repo_id=repo.id, commit_sha="cli_sha", pr_number=None,
        score=None, grade=None,                       # #25: parse_error 컬럼 NULL
        result=_cli_hook_result("parse_error"),       # dict 인플레 score 89 보존
    )
    db_session.add(analysis)
    db_session.commit()

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        await _regate_pr_if_needed(db_session, "owner/repo", "cli_sha", pr_number=7)

    mock_gate.assert_awaited_once()
    passed = mock_gate.await_args.kwargs["result"]
    assert passed["ai_review_status"] == "parse_error"  # 변형 없이 전달
    assert passed["score"] == 89                         # 컬럼 NULL 과 무관하게 dict 인플레 점수
    assert analysis.pr_number == 7                        # pr_number 부여(first-writer) 확인
