"""GateAction ABC + GateContext + Action 구현체 단위 테스트.
Unit tests for GateAction ABC, GateContext, and Action implementations.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_config(pr_review_comment=True, approve_mode="disabled", auto_merge=False):
    cfg = MagicMock()
    cfg.pr_review_comment = pr_review_comment
    cfg.approve_mode = approve_mode
    cfg.auto_merge = auto_merge
    cfg.merge_threshold = 80
    cfg.approve_threshold = 70
    cfg.reject_threshold = 50
    cfg.notify_chat_id = "-100"
    return cfg


# ─── GateContext ──────────────────────────────────────────────────────────────

def test_gate_context_is_frozen():
    """GateContext는 frozen dataclass여야 한다.
    GateContext must be a frozen dataclass (immutable).
    """
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    ctx = GateContext(
        repo_name="owner/repo",
        pr_number=42,
        analysis_id=1,
        result={"score": 85},
        github_token="ghp_test",
        config=_make_config(),
        score=85,
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        ctx.score = 90  # type: ignore[misc]


def test_gate_context_score_field():
    """GateContext.score는 직접 설정한 값을 반환해야 한다.
    GateContext.score must return the value set at construction.
    """
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    ctx = GateContext(
        repo_name="owner/repo", pr_number=1, analysis_id=1,
        result={"score": 72}, github_token="tok",
        config=_make_config(), score=72,
    )
    assert ctx.score == 72


def test_gate_action_is_abstract():
    """GateAction을 직접 인스턴스화할 수 없어야 한다.
    GateAction must not be directly instantiable.
    """
    from src.gate.actions import GateAction  # pylint: disable=import-outside-toplevel
    with pytest.raises(TypeError):
        GateAction()  # type: ignore[abstract]


def test_gate_actions_list_exists():
    """GATE_ACTIONS 리스트가 존재해야 한다.
    GATE_ACTIONS list must exist as a list.
    """
    from src.gate.actions import GATE_ACTIONS  # pylint: disable=import-outside-toplevel
    assert isinstance(GATE_ACTIONS, list)


# ─── ReviewCommentAction ─────────────────────────────────────────────────────

def _make_ctx(pr_review_comment=True, score=85, approve_mode="disabled", auto_merge=False):
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(
        pr_review_comment=pr_review_comment,
        approve_mode=approve_mode,
        auto_merge=auto_merge,
    )
    return GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        result={"score": score}, github_token="ghp_test",
        config=cfg, score=score,
    )


def test_review_comment_action_is_applicable_when_enabled():
    """pr_review_comment=True이면 is_applicable이 True를 반환해야 한다."""
    from src.gate.actions.review_comment import ReviewCommentAction  # pylint: disable=import-outside-toplevel
    assert ReviewCommentAction().is_applicable(_make_config(pr_review_comment=True)) is True


def test_review_comment_action_is_not_applicable_when_disabled():
    """pr_review_comment=False이면 is_applicable이 False를 반환해야 한다."""
    from src.gate.actions.review_comment import ReviewCommentAction  # pylint: disable=import-outside-toplevel
    assert ReviewCommentAction().is_applicable(_make_config(pr_review_comment=False)) is False


@pytest.mark.asyncio
async def test_review_comment_action_execute_calls_post_pr_comment():
    """execute()가 post_pr_comment를 호출해야 한다."""
    from src.gate.actions.review_comment import ReviewCommentAction  # pylint: disable=import-outside-toplevel
    ctx = _make_ctx(pr_review_comment=True)
    # Action이 직접 구현 보유 → actions.review_comment 네임스페이스로 패치
    # Action owns the implementation → patch actions.review_comment namespace
    with patch("src.gate.actions.review_comment.post_pr_comment", new=AsyncMock()) as mock_post, \
         patch("src.gate.actions.review_comment.SessionLocal") as mock_sess, \
         patch("src.gate.actions.review_comment.resolve_notification_language", return_value="en"):
        mock_sess.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_sess.return_value.__exit__ = MagicMock(return_value=False)
        await ReviewCommentAction().execute(ctx)
    mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_review_comment_action_skips_when_disabled():
    """pr_review_comment=False이면 execute()가 post_pr_comment를 호출하지 않아야 한다."""
    from src.gate.actions.review_comment import ReviewCommentAction  # pylint: disable=import-outside-toplevel
    ctx = _make_ctx(pr_review_comment=False)
    with patch("src.gate.actions.review_comment.post_pr_comment", new=AsyncMock()) as mock_post:
        await ReviewCommentAction().execute(ctx)
    mock_post.assert_not_awaited()


# ─── ApproveAction ────────────────────────────────────────────────────────────

def test_approve_action_is_applicable_when_auto():
    """approve_mode='auto'이면 is_applicable이 True여야 한다."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    assert ApproveAction().is_applicable(_make_config(approve_mode="auto")) is True


def test_approve_action_is_applicable_when_semi_auto():
    """approve_mode='semi-auto'이면 is_applicable이 True여야 한다."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    assert ApproveAction().is_applicable(_make_config(approve_mode="semi-auto")) is True


def test_approve_action_is_not_applicable_when_disabled():
    """approve_mode='disabled'이면 is_applicable이 False여야 한다."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    assert ApproveAction().is_applicable(_make_config(approve_mode="disabled")) is False


@pytest.mark.asyncio
async def test_approve_action_auto_calls_post_github_review():
    """auto 모드에서 score >= approve_threshold이면 post_github_review를 호출해야 한다."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    ctx = _make_ctx(approve_mode="auto", score=80)  # 80 >= threshold(70)
    # Action이 직접 구현 보유 → actions.approve 네임스페이스로 패치
    with patch("src.gate.actions.approve.post_github_review", new=AsyncMock()) as mock_review, \
         patch("src.gate.actions.approve.gate_decision_repo"), \
         patch("src.gate.actions.approve.SessionLocal") as mock_sess:
        mock_sess.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_sess.return_value.__exit__ = MagicMock(return_value=False)
        await ApproveAction().execute(ctx)
    mock_review.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_action_semi_auto_calls_send_gate_request():
    """semi-auto 모드에서 execute()가 send_gate_request를 호출해야 한다."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    ctx = _make_ctx(approve_mode="semi-auto", score=75)
    with patch("src.gate.actions.approve.send_gate_request", new=AsyncMock()) as mock_gate, \
         patch("src.gate.actions.approve._score_from_result", return_value=MagicMock()):
        await ApproveAction().execute(ctx)
    mock_gate.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_action_semi_auto_skips_when_ai_review_failed():
    """🔴 C6: AI 리뷰 실제 실패(api_error/parse_error) 시 semi-auto 승인 요청 미발송.

    인플레 기본 점수를 사람에게 승인 버튼으로 노출하면 오해된 점수로 approve+merge 될 수
    있으므로 발송하지 않는다 (_run_auto 가드 대칭 — 이전엔 자동 경로에만 가드 존재).
    """
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(approve_mode="semi-auto")
    cfg.notify_chat_id = "-100123"
    ctx = GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        result={"score": 89, "ai_review_status": "api_error"},  # 인플레 default, 실제 AI 실패
        github_token="ghp_test", config=cfg, score=89,
    )
    with patch("src.gate.actions.approve.send_gate_request", new=AsyncMock()) as mock_gate:
        await ApproveAction().execute(ctx)
    mock_gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_action_semi_auto_skips_when_static_analysis_incomplete():
    """🔴 C6: 정적분석 불완전(타임아웃) 시 semi-auto 승인 요청 미발송 (_run_auto 가드 대칭)."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(approve_mode="semi-auto")
    cfg.notify_chat_id = "-100123"
    ctx = GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        result={"score": 90, "static_analysis_incomplete": True},
        github_token="ghp_test", config=cfg, score=90,
    )
    with patch("src.gate.actions.approve.send_gate_request", new=AsyncMock()) as mock_gate:
        await ApproveAction().execute(ctx)
    mock_gate.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_action_auto_skips_when_static_analysis_incomplete():
    """정적분석 불완전(타임아웃) 시 score 충족이어도 post_github_review 를 호출하지 않아야 한다.
    Must not call post_github_review even when score qualifies, if static analysis is incomplete.

    result["static_analysis_incomplete"]=True → 인플레 점수의 auto-approve 차단 (#779 approve 경로 확장).
    """
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(approve_mode="auto")
    ctx = GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        result={"score": 90, "static_analysis_incomplete": True},  # 90 >= threshold(70) 이나 불완전
        github_token="ghp_test", config=cfg, score=90,
    )
    with patch("src.gate.actions.approve.post_github_review", new=AsyncMock()) as mock_review, \
         patch("src.gate.actions.approve.gate_decision_repo"), \
         patch("src.gate.actions.approve.SessionLocal") as mock_sess:
        mock_sess.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_sess.return_value.__exit__ = MagicMock(return_value=False)
        await ApproveAction().execute(ctx)
    mock_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_action_auto_skips_when_ai_review_failed():
    """AI 리뷰 실제 실패(api_error/parse_error) 시 score 충족이어도 auto-approve 보류.
    Hold auto-approve when the AI review genuinely failed — neutral defaults inflate the score.

    result["ai_review_status"]="api_error" → 미수행 AI 점수의 auto-approve 차단 (#8 fail-closed).
    """
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(approve_mode="auto")
    ctx = GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        # 90 >= threshold(70) 이나 AI 리뷰 실패 → 차단
        result={"score": 90, "ai_review_status": "api_error"},
        github_token="ghp_test", config=cfg, score=90,
    )
    with patch("src.gate.actions.approve.post_github_review", new=AsyncMock()) as mock_review, \
         patch("src.gate.actions.approve.gate_decision_repo"), \
         patch("src.gate.actions.approve.SessionLocal") as mock_sess:
        mock_sess.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_sess.return_value.__exit__ = MagicMock(return_value=False)
        await ApproveAction().execute(ctx)
    mock_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_action_auto_proceeds_when_ai_no_api_key():
    """AI 리뷰 의도적 미수행(no_api_key)은 실패가 아니므로 auto-approve 보존 (회귀 가드).
    Intentional AI skip (no_api_key) is not a failure — auto-approve must still proceed.
    """
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(approve_mode="auto")
    ctx = GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        result={"score": 90, "ai_review_status": "no_api_key"},  # 의도적 미수행 — 차단 대상 아님
        github_token="ghp_test", config=cfg, score=90,
    )
    with patch("src.gate.actions.approve.post_github_review", new=AsyncMock()) as mock_review, \
         patch("src.gate.actions.approve.gate_decision_repo"), \
         patch("src.gate.actions.approve.resolve_notification_language", return_value="en"), \
         patch("src.gate.actions.approve.SessionLocal") as mock_sess:
        mock_sess.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_sess.return_value.__exit__ = MagicMock(return_value=False)
        await ApproveAction().execute(ctx)
    mock_review.assert_awaited_once()


# ─── AutoMergeAction ─────────────────────────────────────────────────────────

def test_auto_merge_action_is_applicable_when_enabled():
    """auto_merge=True이면 is_applicable이 True여야 한다."""
    from src.gate.actions.auto_merge import AutoMergeAction  # pylint: disable=import-outside-toplevel
    assert AutoMergeAction().is_applicable(_make_config(auto_merge=True)) is True


def test_auto_merge_action_is_not_applicable_when_disabled():
    """auto_merge=False이면 is_applicable이 False여야 한다."""
    from src.gate.actions.auto_merge import AutoMergeAction  # pylint: disable=import-outside-toplevel
    assert AutoMergeAction().is_applicable(_make_config(auto_merge=False)) is False


@pytest.mark.asyncio
async def test_auto_merge_action_execute_delegates_to_impl():
    """execute()가 score >= merge_threshold이면 engine._run_auto_merge에 위임해야 한다."""
    from src.gate.actions.auto_merge import AutoMergeAction  # pylint: disable=import-outside-toplevel
    ctx = _make_ctx(auto_merge=True, score=90)  # 90 >= threshold(80)
    # Action은 engine._run_auto_merge에 위임 → engine 네임스페이스로 패치
    with patch("src.gate.engine._run_auto_merge", new=AsyncMock()) as mock_impl:
        await AutoMergeAction().execute(ctx)
    mock_impl.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_merge_action_skips_when_static_analysis_incomplete():
    """정적분석 불완전(타임아웃) 시 score 충족이어도 _run_auto_merge 를 호출하지 않아야 한다.

    result["static_analysis_incomplete"]=True → 미분석 코드 자동 머지 차단 (auto-merge 안전성).
    """
    from src.gate.actions.auto_merge import AutoMergeAction  # pylint: disable=import-outside-toplevel
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(auto_merge=True)
    ctx = GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        result={"score": 90, "static_analysis_incomplete": True},  # 90 >= threshold 이나 불완전
        github_token="ghp_test", config=cfg, score=90,
    )
    with patch("src.gate.engine._run_auto_merge", new=AsyncMock()) as mock_impl:
        await AutoMergeAction().execute(ctx)
    mock_impl.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_merge_action_skips_when_ai_review_failed():
    """AI 리뷰 실제 실패(api_error/parse_error) 시 score 충족이어도 _run_auto_merge 미호출.

    result["ai_review_status"]="parse_error" → 미수행 AI 점수의 자동 머지 차단 (#8 fail-closed).
    """
    from src.gate.actions.auto_merge import AutoMergeAction  # pylint: disable=import-outside-toplevel
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(auto_merge=True)
    ctx = GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        result={"score": 90, "ai_review_status": "parse_error"},  # 90 >= threshold 이나 AI 실패
        github_token="ghp_test", config=cfg, score=90,
    )
    with patch("src.gate.engine._run_auto_merge", new=AsyncMock()) as mock_impl:
        await AutoMergeAction().execute(ctx)
    mock_impl.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_merge_action_proceeds_when_ai_no_api_key():
    """AI 의도적 미수행(no_api_key)은 차단 대상 아님 — 자동 머지 보존 (회귀 가드)."""
    from src.gate.actions.auto_merge import AutoMergeAction  # pylint: disable=import-outside-toplevel
    from src.gate.actions import GateContext  # pylint: disable=import-outside-toplevel
    cfg = _make_config(auto_merge=True)
    ctx = GateContext(
        repo_name="owner/repo", pr_number=42, analysis_id=1,
        result={"score": 90, "ai_review_status": "no_api_key"},  # 의도적 미수행 — 차단 대상 아님
        github_token="ghp_test", config=cfg, score=90,
    )
    with patch("src.gate.engine._run_auto_merge", new=AsyncMock()) as mock_impl:
        await AutoMergeAction().execute(ctx)
    mock_impl.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_merge_action_skips_when_score_below_threshold():
    """score < merge_threshold이면 execute()가 내부 구현을 호출하지 않아야 한다."""
    from src.gate.actions.auto_merge import AutoMergeAction  # pylint: disable=import-outside-toplevel
    ctx = _make_ctx(auto_merge=True, score=70)  # 70 < threshold(80)
    with patch("src.gate.actions.auto_merge._run_auto_merge_action_impl", new=AsyncMock()) as mock_impl:
        await AutoMergeAction().execute(ctx)
    mock_impl.assert_not_awaited()
