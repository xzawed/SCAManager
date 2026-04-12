import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from src.gate.engine import run_gate_check
from src.scorer.calculator import ScoreResult
from src.config_manager.manager import RepoConfigData


# ---------------------------------------------------------------------------
# 공용 헬퍼
# ---------------------------------------------------------------------------

def _score(total):
    """테스트용 ScoreResult 생성 — total만 다르고 나머지는 고정."""
    return ScoreResult(
        total=total, grade="B",
        code_quality_score=20, security_score=15,
        breakdown={},
    )


def _config(**kwargs):
    """신규 필드를 포함한 RepoConfigData 기본 픽스처.

    모든 테스트가 신규 시그니처(approve_mode, approve_threshold,
    reject_threshold, pr_review_comment, merge_threshold)를 사용한다.
    """
    defaults = dict(
        repo_full_name="owner/repo",
        pr_review_comment=True,
        approve_mode="auto",
        approve_threshold=75,
        reject_threshold=50,
        auto_merge=False,
        merge_threshold=75,
        notify_chat_id=None,
    )
    defaults.update(kwargs)
    return RepoConfigData(**defaults)


# ---------------------------------------------------------------------------
# Review Comment 옵션 테스트
# ---------------------------------------------------------------------------

async def test_review_comment_on_calls_post_pr_comment():
    """pr_review_comment=True → post_pr_comment가 호출되어야 한다."""
    mock_db = MagicMock()
    config = _config(pr_review_comment=True, approve_mode="disabled")
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock) as mock_comment:
            with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
                with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                    with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock):
                        with patch("src.gate.engine._save_gate_decision"):
                            await run_gate_check(
                                repo_name="owner/repo",
                                pr_number=1,
                                analysis_id=1,
                                result={"ai_summary": "ok", "suggestions": []},
                                github_token="tok",
                                db=mock_db,
                            )
                            mock_comment.assert_called_once()


async def test_review_comment_off_skips_post_pr_comment():
    """pr_review_comment=False → post_pr_comment가 호출되지 않아야 한다."""
    mock_db = MagicMock()
    config = _config(pr_review_comment=False, approve_mode="disabled")
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock) as mock_comment:
            with patch("src.gate.engine._save_gate_decision"):
                await run_gate_check(
                    repo_name="owner/repo",
                    pr_number=1,
                    analysis_id=1,
                    result={"score": 80, "grade": "B"},
                    github_token="tok",
                    db=mock_db,
                )
                mock_comment.assert_not_called()


# ---------------------------------------------------------------------------
# Approve 옵션 — auto 모드 테스트
# ---------------------------------------------------------------------------

async def test_auto_approve_high_score():
    """score >= approve_threshold → post_github_review가 'approve'로 호출된다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision"):
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=1,
                            analysis_id=1,
                            result={"score": 80, "grade": "B"},
                            github_token="tok",
                            db=mock_db,
                        )
                        mock_review.assert_called_once()
                        # 네 번째 positional 인자 또는 keyword 'decision'이 "approve"
                        call = mock_review.call_args
                        decision = call.kwargs.get("decision") or call.args[3]
                        assert decision == "approve"


async def test_auto_reject_low_score():
    """score < reject_threshold → post_github_review가 'reject'로 호출된다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision"):
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=1,
                            analysis_id=1,
                            result={"score": 40, "grade": "F"},
                            github_token="tok",
                            db=mock_db,
                        )
                        mock_review.assert_called_once()
                        call = mock_review.call_args
                        decision = call.kwargs.get("decision") or call.args[3]
                        assert decision == "reject"


async def test_auto_skip_middle_score():
    """reject_threshold <= score < approve_threshold → post_github_review 미호출."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision"):
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=1,
                            analysis_id=1,
                            result={"score": 62, "grade": "C"},
                            github_token="tok",
                            db=mock_db,
                        )
                        mock_review.assert_not_called()


# ---------------------------------------------------------------------------
# Approve 옵션 — semi-auto 모드 테스트
# ---------------------------------------------------------------------------

async def test_semi_auto_sends_telegram():
    """approve_mode=semi-auto → send_gate_request가 호출된다."""
    mock_db = MagicMock()
    config = _config(approve_mode="semi-auto", notify_chat_id="-100999")
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock) as mock_send:
            with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                with patch("src.gate.engine._save_gate_decision"):
                    await run_gate_check(
                        repo_name="owner/repo",
                        pr_number=7,
                        analysis_id=5,
                        result={"score": 65, "grade": "C"},
                        github_token="tok",
                        db=mock_db,
                    )
                    mock_send.assert_called_once()
                    assert mock_send.call_args.kwargs["analysis_id"] == 5
                    assert mock_send.call_args.kwargs["chat_id"] == "-100999"


# ---------------------------------------------------------------------------
# Approve 옵션 — disabled 모드 테스트
# ---------------------------------------------------------------------------

async def test_approve_disabled_no_review():
    """approve_mode=disabled → post_github_review가 호출되지 않는다."""
    mock_db = MagicMock()
    config = _config(approve_mode="disabled", pr_review_comment=False)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                with patch("src.gate.engine._save_gate_decision"):
                    await run_gate_check(
                        repo_name="owner/repo",
                        pr_number=1,
                        analysis_id=1,
                        result={"score": 80, "grade": "B"},
                        github_token="tok",
                        db=mock_db,
                    )
                    mock_review.assert_not_called()


# ---------------------------------------------------------------------------
# Auto Merge 독립 동작 테스트
# ---------------------------------------------------------------------------

async def test_auto_merge_independent_of_approve_mode():
    """approve_mode=disabled + auto_merge=True + score >= merge_threshold → merge_pr 호출.

    auto_merge는 approve_mode와 완전 독립적으로 동작해야 한다.
    """
    mock_db = MagicMock()
    config = _config(
        approve_mode="disabled",
        auto_merge=True,
        merge_threshold=75,
        pr_review_comment=False,
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
            with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                with patch("src.gate.engine._save_gate_decision"):
                    mock_merge.return_value = True
                    await run_gate_check(
                        repo_name="owner/repo",
                        pr_number=3,
                        analysis_id=10,
                        result={"score": 80, "grade": "B"},
                        github_token="tok",
                        db=mock_db,
                    )
                    mock_merge.assert_called_once()


async def test_auto_merge_with_auto_approve():
    """approve_mode=auto (고점수) + auto_merge=True → post_github_review AND merge_pr 둘 다 호출."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="auto",
        approve_threshold=75,
        reject_threshold=50,
        auto_merge=True,
        merge_threshold=75,
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine._save_gate_decision"):
                        mock_merge.return_value = True
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=5,
                            analysis_id=20,
                            result={"score": 90, "grade": "A"},
                            github_token="tok",
                            db=mock_db,
                        )
                        mock_review.assert_called_once()
                        mock_merge.assert_called_once()


async def test_auto_merge_below_threshold():
    """auto_merge=True이지만 score < merge_threshold → merge_pr 미호출."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="disabled",
        auto_merge=True,
        merge_threshold=75,
        pr_review_comment=False,
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
            with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                with patch("src.gate.engine._save_gate_decision"):
                    await run_gate_check(
                        repo_name="owner/repo",
                        pr_number=3,
                        analysis_id=10,
                        result={"score": 60, "grade": "C"},
                        github_token="tok",
                        db=mock_db,
                    )
                    mock_merge.assert_not_called()


async def test_auto_merge_false_no_merge():
    """auto_merge=False → score가 충분해도 merge_pr이 호출되지 않는다."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="auto",
        approve_threshold=75,
        reject_threshold=50,
        auto_merge=False,
        merge_threshold=75,
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine._save_gate_decision"):
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=5,
                            analysis_id=20,
                            result={"score": 90, "grade": "A"},
                            github_token="tok",
                            db=mock_db,
                        )
                        mock_merge.assert_not_called()


# ---------------------------------------------------------------------------
# Push 이벤트 — PR 액션 없음 테스트
# ---------------------------------------------------------------------------

async def test_push_event_no_gate_actions():
    """pr_number=None(push 이벤트) → 모든 PR 관련 액션이 호출되지 않는다."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="auto",
        approve_threshold=75,
        reject_threshold=50,
        auto_merge=True,
        merge_threshold=75,
        pr_review_comment=True,
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock) as mock_comment:
            with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
                with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                    with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock) as mock_send:
                        with patch("src.gate.engine._save_gate_decision"):
                            await run_gate_check(
                                repo_name="owner/repo",
                                pr_number=None,  # push 이벤트
                                analysis_id=99,
                                result={"score": 90, "grade": "A"},
                                github_token="tok",
                                db=mock_db,
                            )
                            mock_comment.assert_not_called()
                            mock_review.assert_not_called()
                            mock_merge.assert_not_called()
                            mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 하위 호환성 — 기존 동작 유지 확인
# ---------------------------------------------------------------------------

async def test_save_gate_decision_called_on_approve():
    """auto approve 시 _save_gate_decision이 'approve'로 호출되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=1,
                            analysis_id=42,
                            result={"score": 80, "grade": "B"},
                            github_token="tok",
                            db=mock_db,
                        )
                        mock_save.assert_called_once_with(mock_db, 42, "approve", "auto")


async def test_save_gate_decision_called_on_reject():
    """auto reject 시 _save_gate_decision이 'reject'로 호출되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=1,
                            analysis_id=43,
                            result={"score": 40, "grade": "F"},
                            github_token="tok",
                            db=mock_db,
                        )
                        mock_save.assert_called_once_with(mock_db, 43, "reject", "auto")


async def test_save_gate_decision_skip_on_middle_score():
    """중간 점수에서 _save_gate_decision이 'skip'으로 호출되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=1,
                            analysis_id=44,
                            result={"score": 62, "grade": "C"},
                            github_token="tok",
                            db=mock_db,
                        )
                        mock_save.assert_called_once_with(mock_db, 44, "skip", "auto")


async def test_merge_pr_failure_does_not_raise():
    """merge_pr이 False를 반환해도 run_gate_check이 예외 없이 완료된다."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="auto",
        approve_threshold=75,
        reject_threshold=50,
        auto_merge=True,
        merge_threshold=75,
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                        mock_merge.return_value = False
                        # 예외 없이 완료되어야 한다
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=5,
                            analysis_id=50,
                            result={"score": 80, "grade": "B"},
                            github_token="tok",
                            db=mock_db,
                        )
                        # GateDecision은 merge_pr 결과와 무관하게 저장된다
                        mock_save.assert_called_once_with(mock_db, 50, "approve", "auto")


# ---------------------------------------------------------------------------
# 예외 내성 — 각 단계 예외가 다음 단계를 중단시키지 않아야 한다
# ---------------------------------------------------------------------------

async def test_post_pr_comment_exception_does_not_abort_gate():
    """post_pr_comment가 예외를 던져도 run_gate_check가 계속 실행되어 post_github_review도 호출되어야 한다."""
    mock_db = MagicMock()
    config = _config(pr_review_comment=True, approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock, side_effect=httpx.ConnectError("comment failed")):
            with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
                with patch("src.gate.engine._save_gate_decision"):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo", pr_number=1, analysis_id=1,
                            result={"score": 80, "grade": "B"}, github_token="tok", db=mock_db,
                        )
                        # comment 실패해도 approve는 실행되어야 한다
                        mock_review.assert_called_once()


async def test_post_github_review_exception_does_not_crash():
    """post_github_review가 예외를 던져도 run_gate_check가 크래시 없이 완료되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50, pr_review_comment=False)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock, side_effect=httpx.ConnectError("GitHub API error")):
            with patch("src.gate.engine._save_gate_decision"):
                with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                    with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                        # 예외 없이 완료되어야 한다
                        await run_gate_check(
                            repo_name="owner/repo", pr_number=1, analysis_id=1,
                            result={"score": 80, "grade": "B"}, github_token="tok", db=mock_db,
                        )


async def test_merge_pr_exception_does_not_crash():
    """merge_pr이 예외를 던져도 run_gate_check가 크래시 없이 완료되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="disabled", auto_merge=True, merge_threshold=75, pr_review_comment=False)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.merge_pr", new_callable=AsyncMock, side_effect=httpx.ConnectError("merge error")):
            with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                with patch("src.gate.engine._save_gate_decision"):
                    await run_gate_check(
                        repo_name="owner/repo", pr_number=3, analysis_id=10,
                        result={"score": 90, "grade": "A"}, github_token="tok", db=mock_db,
                    )


async def test_semi_auto_no_notify_chat_id_skips_telegram():
    """approve_mode="semi-auto"이지만 notify_chat_id=None인 경우 send_gate_request가 호출되지 않아야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="semi-auto", notify_chat_id=None, pr_review_comment=False)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock) as mock_send:
            with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                with patch("src.gate.engine._save_gate_decision"):
                    await run_gate_check(
                        repo_name="owner/repo", pr_number=1, analysis_id=1,
                        result={"score": 70, "grade": "C"}, github_token="tok", db=mock_db,
                    )
                    mock_send.assert_not_called()


async def test_send_gate_request_exception_does_not_crash():
    """send_gate_request가 예외를 던져도 run_gate_check가 크래시 없이 완료되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="semi-auto", notify_chat_id="-100999", pr_review_comment=False)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock, side_effect=httpx.ConnectError("Telegram error")):
            with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                with patch("src.gate.engine._save_gate_decision"):
                    await run_gate_check(
                        repo_name="owner/repo", pr_number=1, analysis_id=1,
                        result={"score": 70, "grade": "C"}, github_token="tok", db=mock_db,
                    )
