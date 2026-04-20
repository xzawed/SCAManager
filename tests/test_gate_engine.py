import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import logging
import pytest
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
                        with patch("src.gate.engine.save_gate_decision"):
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
            with patch("src.gate.engine.save_gate_decision"):
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
            with patch("src.gate.engine.save_gate_decision"):
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
            with patch("src.gate.engine.save_gate_decision"):
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
            with patch("src.gate.engine.save_gate_decision"):
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
                with patch("src.gate.engine.save_gate_decision"):
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
                with patch("src.gate.engine.save_gate_decision"):
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
                with patch("src.gate.engine.save_gate_decision"):
                    mock_merge.return_value = (True, None)
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
                    with patch("src.gate.engine.save_gate_decision"):
                        mock_merge.return_value = (True, None)
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
                with patch("src.gate.engine.save_gate_decision"):
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
                    with patch("src.gate.engine.save_gate_decision"):
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
                        with patch("src.gate.engine.save_gate_decision"):
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

async def testsave_gate_decision_called_on_approve():
    """auto approve 시 save_gate_decision이 'approve'로 호출되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine.save_gate_decision") as mock_save:
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


async def testsave_gate_decision_called_on_reject():
    """auto reject 시 save_gate_decision이 'reject'로 호출되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine.save_gate_decision") as mock_save:
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


async def testsave_gate_decision_skip_on_middle_score():
    """중간 점수에서 save_gate_decision이 'skip'으로 호출되어야 한다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock):
            with patch("src.gate.engine.save_gate_decision") as mock_save:
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
            with patch("src.gate.engine.save_gate_decision") as mock_save:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
                        with patch("src.gate.engine.telegram_post_message", new_callable=AsyncMock):
                            mock_merge.return_value = (False, "forbidden: no permission")
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
                with patch("src.gate.engine.save_gate_decision"):
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
            with patch("src.gate.engine.save_gate_decision"):
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
                with patch("src.gate.engine.save_gate_decision"):
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
                with patch("src.gate.engine.save_gate_decision"):
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
                with patch("src.gate.engine.save_gate_decision"):
                    await run_gate_check(
                        repo_name="owner/repo", pr_number=1, analysis_id=1,
                        result={"score": 70, "grade": "C"}, github_token="tok", db=mock_db,
                    )


# ---------------------------------------------------------------------------
# config=None 경로 — DB 직접 조회 분기
# ---------------------------------------------------------------------------

async def test_config_none_calls_get_repo_config():
    """config=None 전달 시 get_repo_config(db, repo_name)를 호출해 설정을 로드한다."""
    mock_db = MagicMock()
    config = _config(pr_review_comment=False, approve_mode="disabled", auto_merge=False)
    with patch("src.gate.engine.get_repo_config", return_value=config) as mock_get:
        with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
            with patch("src.gate.engine.save_gate_decision"):
                await run_gate_check(
                    repo_name="owner/repo",
                    pr_number=1,
                    analysis_id=1,
                    result={"score": 80},
                    github_token="tok",
                    db=mock_db,
                    config=None,  # 명시적 None — DB 조회 분기
                )
                mock_get.assert_called_once_with(mock_db, "owner/repo")


async def test_config_provided_skips_get_repo_config():
    """config이 이미 제공된 경우 get_repo_config를 호출하지 않는다."""
    mock_db = MagicMock()
    config = _config(pr_review_comment=False, approve_mode="disabled", auto_merge=False)
    with patch("src.gate.engine.get_repo_config") as mock_get:
        with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
            with patch("src.gate.engine.save_gate_decision"):
                await run_gate_check(
                    repo_name="owner/repo",
                    pr_number=1,
                    analysis_id=1,
                    result={"score": 80},
                    github_token="tok",
                    db=mock_db,
                    config=config,  # 이미 로드된 config 전달
                )
                mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# _score_from_result — 불완전한 result dict 처리
# ---------------------------------------------------------------------------

def test_score_from_result_empty_dict():
    """result={}인 경우 기본값(score=0, grade='F')으로 ScoreResult를 반환한다."""
    from src.gate.engine import _score_from_result
    sr = _score_from_result({})
    assert sr.total == 0
    assert sr.grade == "F"
    assert sr.code_quality_score == 0
    assert sr.security_score == 0


def test_score_from_result_breakdown_none():
    """result['breakdown']=None인 경우 AttributeError 없이 기본값으로 처리해야 한다."""
    from src.gate.engine import _score_from_result
    sr = _score_from_result({"score": 75, "grade": "B", "breakdown": None})
    assert sr.total == 75
    assert sr.code_quality_score == 0
    assert sr.security_score == 0


def test_score_from_result_partial_breakdown():
    """breakdown에 일부 키만 있는 경우 누락 키는 0으로 처리한다."""
    from src.gate.engine import _score_from_result
    sr = _score_from_result({"score": 80, "grade": "B", "breakdown": {"code_quality": 20}})
    assert sr.code_quality_score == 20
    assert sr.security_score == 0


# ---------------------------------------------------------------------------
# 경계값 — threshold 포함/제외 정확성
# ---------------------------------------------------------------------------

async def test_approve_at_exact_threshold():
    """score == approve_threshold → approve (경계값 포함)."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine.save_gate_decision"):
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo", pr_number=1, analysis_id=1,
                            result={"score": 75}, github_token="tok", db=mock_db,
                        )
                        call = mock_review.call_args
                        decision = call.kwargs.get("decision") or call.args[3]
                        assert decision == "approve"


async def test_reject_threshold_boundary_is_excluded():
    """score == reject_threshold → skip (reject 아님, < reject_threshold만 reject)."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine.save_gate_decision") as mock_save:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo", pr_number=1, analysis_id=1,
                            result={"score": 50}, github_token="tok", db=mock_db,
                        )
                        mock_review.assert_not_called()  # reject 아님
                        mock_save.assert_called_once_with(mock_db, 1, "skip", "auto")


async def test_merge_at_exact_threshold():
    """score == merge_threshold → merge_pr 호출 (경계값 포함)."""
    mock_db = MagicMock()
    config = _config(approve_mode="disabled", auto_merge=True, merge_threshold=75, pr_review_comment=False)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
            with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                with patch("src.gate.engine.save_gate_decision"):
                    mock_merge.return_value = (True, None)
                    await run_gate_check(
                        repo_name="owner/repo", pr_number=1, analysis_id=1,
                        result={"score": 75}, github_token="tok", db=mock_db,
                    )
                    mock_merge.assert_called_once()


# ---------------------------------------------------------------------------
# KeyError 예외 내성 — httpx.HTTPError 외 추가 예외 타입
# ---------------------------------------------------------------------------

async def test_post_pr_comment_keyerror_does_not_abort_gate():
    """post_pr_comment가 KeyError를 던져도 gate 실행이 계속된다."""
    mock_db = MagicMock()
    config = _config(pr_review_comment=True, approve_mode="auto", approve_threshold=75, reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock,
                   side_effect=KeyError("missing_field")):
            with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
                with patch("src.gate.engine.save_gate_decision"):
                    with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo", pr_number=1, analysis_id=1,
                            result={"score": 80}, github_token="tok", db=mock_db,
                        )
                        mock_review.assert_called_once()


async def test_post_github_review_keyerror_does_not_crash():
    """post_github_review가 KeyError를 던져도 run_gate_check가 크래시 없이 완료된다."""
    mock_db = MagicMock()
    config = _config(approve_mode="auto", approve_threshold=75, reject_threshold=50, pr_review_comment=False)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock,
                   side_effect=KeyError("pr_number")):
            with patch("src.gate.engine.save_gate_decision"):
                with patch("src.gate.engine.merge_pr", new_callable=AsyncMock):
                    with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                        await run_gate_check(
                            repo_name="owner/repo", pr_number=1, analysis_id=1,
                            result={"score": 80}, github_token="tok", db=mock_db,
                        )


# ---------------------------------------------------------------------------
# Auto Merge tuple 반환 — Telegram 알림 분기 테스트
# ---------------------------------------------------------------------------

async def test_auto_merge_success_no_telegram():
    """merge_pr → (True, None) 이면 telegram_post_message 미호출."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="disabled",
        auto_merge=True,
        merge_threshold=75,
        pr_review_comment=False,
        notify_chat_id="-100123",
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
            with patch("src.gate.engine.telegram_post_message", new_callable=AsyncMock) as mock_tg:
                with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                    with patch("src.gate.engine.save_gate_decision"):
                        # merge 성공 → (True, None)
                        mock_merge.return_value = (True, None)
                        await run_gate_check(
                            repo_name="owner/repo",
                            pr_number=3,
                            analysis_id=10,
                            result={"score": 80, "grade": "B"},
                            github_token="tok",
                            db=mock_db,
                        )
                        # merge 성공 시 Telegram 알림 없음
                        mock_tg.assert_not_called()


async def test_auto_merge_failure_sends_telegram():
    """merge_pr → (False, "forbidden: ...") 이면 Telegram 1회 호출, text에 repo·PR번호·사유 포함."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="disabled",
        auto_merge=True,
        merge_threshold=75,
        pr_review_comment=False,
        notify_chat_id="-100123",
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
            with patch("src.gate.engine.telegram_post_message", new_callable=AsyncMock) as mock_tg:
                with patch("src.gate.engine.settings") as mock_settings:
                    with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                        with patch("src.gate.engine.save_gate_decision"):
                            mock_settings.telegram_bot_token = "123:ABC"
                            mock_settings.telegram_chat_id = ""
                            # merge 실패 → (False, "forbidden: Resource not accessible")
                            mock_merge.return_value = (False, "forbidden: Resource not accessible")
                            await run_gate_check(
                                repo_name="owner/repo",
                                pr_number=3,
                                analysis_id=10,
                                result={"score": 80, "grade": "B"},
                                github_token="tok",
                                db=mock_db,
                            )
                            # Telegram 1회 호출
                            mock_tg.assert_called_once()
                            call_args = mock_tg.call_args
                            # positional 3번째 인자가 payload dict
                            payload = call_args.args[2]
                            text = payload.get("text", "")
                            # repo 이름, PR 번호, 실패 사유 모두 포함
                            assert "owner/repo" in text
                            assert "3" in text
                            assert "forbidden" in text


async def test_auto_merge_failure_no_chat_id_only_logs():
    """notify_chat_id=None + global chat_id="" → merge 실패해도 Telegram 미호출."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="disabled",
        auto_merge=True,
        merge_threshold=75,
        pr_review_comment=False,
        notify_chat_id=None,  # repo 전용 chat_id 없음
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
            with patch("src.gate.engine.telegram_post_message", new_callable=AsyncMock) as mock_tg:
                with patch("src.gate.engine.settings") as mock_settings:
                    with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                        with patch("src.gate.engine.save_gate_decision"):
                            mock_settings.telegram_bot_token = "123:ABC"
                            mock_settings.telegram_chat_id = ""  # global chat_id도 없음
                            mock_merge.return_value = (False, "forbidden: no permission")
                            await run_gate_check(
                                repo_name="owner/repo",
                                pr_number=3,
                                analysis_id=10,
                                result={"score": 80, "grade": "B"},
                                github_token="tok",
                                db=mock_db,
                            )
                            # chat_id가 없으므로 Telegram 미호출
                            mock_tg.assert_not_called()


async def test_auto_merge_failure_global_fallback_chat_id():
    """notify_chat_id=None + global chat_id 존재 → global chat_id로 Telegram 전송."""
    mock_db = MagicMock()
    config = _config(
        approve_mode="disabled",
        auto_merge=True,
        merge_threshold=75,
        pr_review_comment=False,
        notify_chat_id=None,  # repo 전용 chat_id 없음
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge:
            with patch("src.gate.engine.telegram_post_message", new_callable=AsyncMock) as mock_tg:
                with patch("src.gate.engine.settings") as mock_settings:
                    with patch("src.gate.engine.post_pr_comment", new_callable=AsyncMock):
                        with patch("src.gate.engine.save_gate_decision"):
                            mock_settings.telegram_bot_token = "123:ABC"
                            mock_settings.telegram_chat_id = "-100999"  # global fallback 존재
                            mock_merge.return_value = (False, "forbidden: no permission")
                            await run_gate_check(
                                repo_name="owner/repo",
                                pr_number=3,
                                analysis_id=10,
                                result={"score": 80, "grade": "B"},
                                github_token="tok",
                                db=mock_db,
                            )
                            # global chat_id로 전송
                            mock_tg.assert_called_once()
                            call_args = mock_tg.call_args
                            # positional 2번째 인자가 chat_id
                            assert call_args.args[1] == "-100999"


# ---------------------------------------------------------------------------
# _notify_merge_failure 함수 테스트
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_merge_failure_logs_warning_on_httpx_error(caplog):
    """telegram_post_message 가 HTTPError 를 던져도 예외가 전파되지 않고 warning 으로 기록된다."""
    from src.gate.engine import _notify_merge_failure

    with caplog.at_level(logging.WARNING, logger="src.gate.engine"):
        with patch(
            "src.gate.engine.telegram_post_message",
            new=AsyncMock(side_effect=httpx.ConnectError("boom")),
        ):
            await _notify_merge_failure(
                repo_name="o/r", pr_number=7, score=55, threshold=80,
                reason="conflict", chat_id="123",
            )
    assert any("Telegram merge-failure" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_notify_merge_failure_skipped_when_no_chat_id():
    """chat_id=None 이면 telegram_post_message 호출 안 됨."""
    from src.gate.engine import _notify_merge_failure

    with patch("src.gate.engine.telegram_post_message", new=AsyncMock()) as m:
        await _notify_merge_failure(
            repo_name="o/r", pr_number=7, score=55, threshold=80,
            reason="x", chat_id=None,
        )
    m.assert_not_called()
