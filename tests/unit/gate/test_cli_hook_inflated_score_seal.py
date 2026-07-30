"""CLI-hook parse_error 인플레 점수 → PR gate fail-open 봉인 회귀 가드 (사이클 165 회고 P2-②).

#25 가 CLI hook 의 score/grade **컬럼** 만 NULL 화했으나 `result` dict 의 인플레 score(89)는 보존되고
(build_analysis_result_dict), gate(engine.run_gate_check)는 컬럼이 아닌 **result dict 의 score**
(engine.py `result.get("score", 0)`)를 읽는다.

🔴 **2026-07-30 감사 정정** — 이 docstring 은 원래 "차단은 #8 ai_review_failed **단일 가드**에 전적으로
의존한다(static_analysis_incomplete 가드는 CLI 훅이 정적분석을 안 돌려 incomplete=False 라 무력)"
라고 적어 **갭을 정확히 서술해 두고도 닫지 않았다**. 그 결과 AI 리뷰가 성공한 정상 경로에는 차단이
전혀 없어, 정적분석 0회 · 45/45 만점 · 총점 89 인 CLI 훅 분석이 auto-merge 를 통과했다.
이제 `src/api/hook.py` 가 `static_analysis_incomplete=True` 를 항상 부여해 그 경로를 닫는다.
🔴 The original docstring described this gap precisely and left it open; hook.py now closes it.

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

    🔴 `static_analysis_incomplete=True` 는 `src/api/hook.py` 가 **항상** 부여한다(2026-07-30 감사).
    CLI 훅은 정적분석을 한 번도 돌리지 않으면서 45/45 만점을 받으므로, timeout·crash 로 정적분석이
    불완전한 경우와 동일하게 취급한다. 이 키가 빠지면 아래 success 경로가 무검증 auto-merge 로 뚫린다.
    🔴 hook.py always sets static_analysis_incomplete — the CLI hook is credited 45/45 static points
    without ever running an analyzer, so it is treated exactly like a timed-out/crashed analysis.
    """
    return {
        "score": 89,
        "grade": "B",
        "ai_review_status": ai_status,
        "source": "cli",
        "static_analysis_incomplete": True,
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


async def test_run_gate_check_cli_hook_success_also_blocks_automerge():
    """🔴 2026-07-30 감사 — 반전된 테스트.

    이전 이름은 `..._success_allows_automerge` 였고 `mock_am.assert_awaited_once()` 로
    **결함을 정상 동작으로 고정**하고 있었다. AI 리뷰가 성공한 정상 경로(status='success')에서는
    `ai_review_failed` 가드가 발화하지 않으므로, CLI 훅 분석(정적분석 0회 · 45/45 만점 · 총점 89)이
    `merge_threshold=75` 를 넘겨 **미검증 코드가 auto-merge** 됐다. 제품의 기본 기능(pre-push 훅)이
    곧 게이트 우회 경로였다.

    이제 `hook.py` 가 `static_analysis_incomplete=True` 를 부여하므로 정상 경로도 차단된다.
    🔴 Inverted: the old control test pinned the defect. The success path had no guard at all, so a
    CLI-hook analysis (zero static analysis, full 45 static points, total 89) auto-merged.
    """
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
    mock_am.assert_not_awaited()  # static_analysis_incomplete 가드가 정상 경로도 차단


def test_hook_endpoint_sets_static_analysis_incomplete():
    """🔴 배선 테스트 (3-불변식 ③) — 가드 자체가 아니라 `hook.py` 가 마커를 **실제로 부여**하는지.

    위 테스트들은 result dict 를 손으로 만들므로, `hook.py` 가 마커 부여를 그만둬도 전부 green 이다.
    AST 로 `result_dict["static_analysis_incomplete"] = True` 대입이 존재함을 단언해 그 구멍을 막는다.
    🔴 Wiring test: the tests above hand-build the dict, so they stay green if hook.py stops setting
    the marker. Assert the assignment exists in the real source.
    """
    import ast  # pylint: disable=import-outside-toplevel
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    src = Path(__file__).resolve().parents[3] / "src" / "api" / "hook.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    found = any(
        isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant) and node.value.value is True
        and any(
            isinstance(t, ast.Subscript)
            and isinstance(t.slice, ast.Constant)
            and t.slice.value == "static_analysis_incomplete"
            for t in node.targets
        )
        for node in ast.walk(tree)
    )
    assert found, (
        "src/api/hook.py 가 static_analysis_incomplete=True 를 부여하지 않는다 — "
        "CLI 훅 분석이 정적분석 0회 상태로 auto-merge 될 수 있다."
    )


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


async def test_regate_does_not_gate_on_cli_hook_result(db_session):
    """🔴 2026-07-30 감사 결정 ① — 반전된 테스트.

    이전 이름은 `..._passes_cli_hook_parse_error_result_to_gate` 였고 `assert_awaited_once()` +
    `analysis.pr_number == 7` 로 **CLI 결과가 gate 로 흘러가는 것을 정상 동작으로 봉인**했다.
    그 결합이 곧 결함이었다 — CLI 훅은 정적분석을 한 번도 돌리지 않으므로(45/45 무검증),
    그 result 에 pr_number 를 붙여 gate 를 돌리면 **그 SHA 는 영영 full 분석 없이 확정**된다.

    이제 `_regate_pr_if_needed` 는 CLI 결과를 만나면 gate 를 돌리지 않고 물러난다. 같은 이벤트의
    full 분석 경로(`_ensure_repo` 가 CLI 행을 중복으로 보지 않음)가 이어서 실행되어 행을 교체한다.
    상세 봉인: `tests/unit/worker/test_cli_analysis_supersede.py`.
    🔴 Inverted: the old test pinned the CLI→gate coupling that was itself the defect.
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

    mock_gate.assert_not_awaited()  # CLI 결과로는 게이트하지 않는다
    db_session.refresh(analysis)
    assert analysis.pr_number is None, (
        "CLI 행에 pr_number 가 붙으면 그 SHA 가 무검증 결과로 확정된다"
    )
