"""Gate/알림 오케스트레이션 seam 테스트 — resolve_notification_language → 메시지 언어 배선 검증 (사이클 152 P1-3).

Gate/notification orchestration seam tests — verify resolve_notification_language
result is correctly threaded into actual message language (approve.py / merge_retry / engine).

PR-5C 트랩 동형 사각 해소: 코드는 정상이나 "언어 배선" 회귀 가드 테스트가 부재했던 영역.
Closes the PR-5C-style blind spot: code is correct but lacked a regression guard
asserting the resolved language actually flows into generated message text.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402


@pytest.mark.asyncio
async def test_approve_auto_threads_japanese_language_to_review():
    """approve.py _run_auto 가 resolve된 'ja' 언어로 일본어 post_github_review body 생성."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel

    ctx = MagicMock()
    ctx.score = 90
    ctx.result = {"score": 90}  # 정적분석 완료(불완전 마커 부재) — 가드 통과 / static analysis complete
    ctx.config.approve_mode = "auto"
    ctx.config.approve_threshold = 75
    ctx.config.reject_threshold = 40
    ctx.repo_name = "owner/repo"
    ctx.pr_number = 7
    ctx.analysis_id = 1
    ctx.github_token = "ghp_x"

    # resolve_notification_language → "ja" patch → body 가 일본어여야 함
    with patch(
        "src.gate.actions.approve.resolve_notification_language", return_value="ja"
    ), patch(
        "src.gate.actions.approve.post_github_review", new_callable=AsyncMock
    ) as mock_review, patch(
        "src.gate.actions.approve.SessionLocal"
    ), patch(
        "src.gate.actions.approve.gate_decision_repo"
    ):
        await ApproveAction()._run_auto(ctx)  # pylint: disable=protected-access

    assert mock_review.await_count == 1
    # post_github_review(github_token, repo, pr_number, decision, body) — body = 마지막 positional
    body = mock_review.await_args.args[-1]
    assert "自動承認" in body or "承認" in body, f"일본어 body 아님: {body!r}"


@pytest.mark.asyncio
async def test_approve_auto_threads_english_language_to_review():
    """approve.py _run_auto 가 resolve된 'en' 언어로 영어 body 생성 (한국어 부재)."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel

    ctx = MagicMock()
    ctx.score = 90
    ctx.result = {"score": 90}  # 정적분석 완료(불완전 마커 부재) — 가드 통과 / static analysis complete
    ctx.config.approve_mode = "auto"
    ctx.config.approve_threshold = 75
    ctx.config.reject_threshold = 40
    ctx.repo_name = "owner/repo"
    ctx.pr_number = 7
    ctx.analysis_id = 1
    ctx.github_token = "ghp_x"

    with patch(
        "src.gate.actions.approve.resolve_notification_language", return_value="en"
    ), patch(
        "src.gate.actions.approve.post_github_review", new_callable=AsyncMock
    ) as mock_review, patch(
        "src.gate.actions.approve.SessionLocal"
    ), patch(
        "src.gate.actions.approve.gate_decision_repo"
    ):
        await ApproveAction()._run_auto(ctx)  # pylint: disable=protected-access

    assert mock_review.await_count == 1
    body = mock_review.await_args.args[-1]
    assert "Auto-approved" in body
    # 영어 선택 시 한국어 텍스트가 새지 않아야 함
    assert "자동 승인" not in body, f"영어 body 에 한국어 누출: {body!r}"


@pytest.mark.asyncio
async def test_approve_auto_reject_threads_language_to_review():
    """낮은 점수 → reject 분기도 resolve된 언어('ja')로 body 생성."""
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel

    ctx = MagicMock()
    ctx.score = 10
    ctx.result = {"score": 10}  # 정적분석 완료(불완전 마커 부재) — 가드 통과 / static analysis complete
    ctx.config.approve_mode = "auto"
    ctx.config.approve_threshold = 75
    ctx.config.reject_threshold = 40
    ctx.repo_name = "owner/repo"
    ctx.pr_number = 7
    ctx.analysis_id = 1
    ctx.github_token = "ghp_x"

    with patch(
        "src.gate.actions.approve.resolve_notification_language", return_value="ja"
    ), patch(
        "src.gate.actions.approve.post_github_review", new_callable=AsyncMock
    ) as mock_review, patch(
        "src.gate.actions.approve.SessionLocal"
    ), patch(
        "src.gate.actions.approve.gate_decision_repo"
    ):
        await ApproveAction()._run_auto(ctx)  # pylint: disable=protected-access

    assert mock_review.await_count == 1
    body = mock_review.await_args.args[-1]
    assert "自動却下" in body or "却下" in body, f"일본어 reject body 아님: {body!r}"


@pytest.mark.asyncio
async def test_merge_retry_terminal_threads_language_to_telegram():
    """merge_retry_service._notify_merge_terminal 가 language='ja'로 일본어 텍스트 생성."""
    from src.services import merge_retry_service  # pylint: disable=import-outside-toplevel

    row = MagicMock()
    row.repo_full_name = "owner/repo"
    row.pr_number = 7
    row.score = 88
    row.attempts_count = 3
    cfg = MagicMock()

    with patch(
        "src.services.merge_retry_service._resolve_retry_chat_id", return_value="-100123"
    ), patch(
        "src.services.merge_retry_service.telegram_post_message", new_callable=AsyncMock
    ) as mock_post, patch(
        "src.services.merge_retry_service.get_advice", return_value="advice text"
    ):
        await merge_retry_service._notify_merge_terminal(  # pylint: disable=protected-access
            row, cfg, "merge conflict", "conflict", language="ja",
        )

    assert mock_post.await_count == 1
    # telegram_post_message(bot_token, chat_id, {"text": msg, ...}) — text = 3번째 positional dict
    payload = mock_post.await_args.args[2]
    text = payload["text"]
    assert "自動マージ最終失敗" in text or "理由" in text, f"일본어 terminal 아님: {text!r}"
    assert "자동 머지" not in text, f"일본어 선택인데 한국어 누출: {text!r}"


@pytest.mark.asyncio
async def test_engine_notify_merge_failure_threads_english_no_korean():
    """engine._notify_merge_failure(language='en') 시 telegram text 에 한국어 부재."""
    from src.gate import engine  # pylint: disable=import-outside-toplevel

    with patch(
        "src.gate.engine.telegram_post_message", new_callable=AsyncMock
    ) as mock_post:
        await engine._notify_merge_failure(  # pylint: disable=protected-access
            repo_name="owner/repo",
            pr_number=7,
            score=50,
            threshold=75,
            reason="below threshold",
            advice="raise score",
            chat_id="-100123",
            language="en",
        )

    assert mock_post.await_count == 1
    payload = mock_post.await_args.args[2]
    text = payload["text"]
    assert "Auto Merge Failed" in text, f"영어 merge-failed 아님: {text!r}"
    # 영어 선택 시 한국어 텍스트 (사유/머지 등) 가 새지 않아야 함
    assert "사유" not in text and "자동 머지" not in text, \
        f"영어 선택인데 한국어 누출: {text!r}"


def _make_gate_callback_mocks(*, decision: str):
    """handle_gate_callback 의존성 mock 묶음 — (db_cm, analysis, repo, config).
    Build the dependency mock bundle for handle_gate_callback seam tests."""
    db_cm = MagicMock()
    db_cm.__enter__.return_value = MagicMock()
    db_cm.__exit__.return_value = False
    analysis = MagicMock()
    analysis.repo_id = 1
    analysis.pr_number = 7
    analysis.result = {"score": 90}
    analysis.score = 90
    repo = MagicMock()
    repo.full_name = "owner/repo"
    repo.owner.plaintext_token = "ghp_x"
    repo.user_id = 1  # authz: 콜백 소유권 검증용 (사이클 164 P1 #1)
    config = MagicMock()
    config.auto_merge = False  # 머지 분기 skip — body 생성만 검증
    return db_cm, analysis, repo, config


@pytest.mark.asyncio
async def test_gate_callback_approve_threads_japanese_to_review_body():
    """handle_gate_callback(approve) 가 resolve된 'ja' 언어로 일본어 PR Review body 생성 (사이클 154 P0).

    GitHub PR Review body 는 리포 협업자 전체 노출 — 하드코딩 한국어 회귀 차단.
    """
    from src.webhook.providers import telegram  # pylint: disable=import-outside-toplevel

    db_cm, analysis, repo, config = _make_gate_callback_mocks(decision="approve")
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=db_cm), patch(
        "src.webhook.providers.telegram.analysis_repo.find_by_id", return_value=analysis
    ), patch(
        "src.webhook.providers.telegram.repository_repo.find_by_id", return_value=repo
    ), patch(
        "src.webhook.providers.telegram.get_repo_config", return_value=config
    ), patch(
        "src.webhook.providers.telegram.resolve_notification_language", return_value="ja"
    ), patch(
        "src.webhook.providers.telegram.save_gate_decision"
    ), patch(
        "src.webhook.providers.telegram.user_repo.find_by_telegram_user_id", return_value=MagicMock(id=1)
    ), patch(
        "src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock
    ) as mock_review:
        await telegram.handle_gate_callback(1, "approve", "alice", telegram_user_id="1")

    assert mock_review.await_count == 1
    # post_github_review(token, full_name, pr_number, decision, body) — body = 5번째 positional
    body = mock_review.await_args.args[4]
    assert "承認" in body, f"일본어 승인 body 아님: {body!r}"
    assert "승인" not in body, f"일본어 선택인데 한국어 누출: {body!r}"
    assert "alice" in body


@pytest.mark.asyncio
async def test_gate_callback_reject_threads_english_no_korean():
    """handle_gate_callback(reject) 가 'en' 언어로 영어 body 생성 — 한국어 부재."""
    from src.webhook.providers import telegram  # pylint: disable=import-outside-toplevel

    db_cm, analysis, repo, config = _make_gate_callback_mocks(decision="reject")
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=db_cm), patch(
        "src.webhook.providers.telegram.analysis_repo.find_by_id", return_value=analysis
    ), patch(
        "src.webhook.providers.telegram.repository_repo.find_by_id", return_value=repo
    ), patch(
        "src.webhook.providers.telegram.get_repo_config", return_value=config
    ), patch(
        "src.webhook.providers.telegram.resolve_notification_language", return_value="en"
    ), patch(
        "src.webhook.providers.telegram.save_gate_decision"
    ), patch(
        "src.webhook.providers.telegram.user_repo.find_by_telegram_user_id", return_value=MagicMock(id=1)
    ), patch(
        "src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock
    ) as mock_review:
        await telegram.handle_gate_callback(1, "reject", "bob", telegram_user_id="1")

    assert mock_review.await_count == 1
    body = mock_review.await_args.args[4]
    assert "Rejected" in body, f"영어 반려 body 아님: {body!r}"
    assert "반려" not in body, f"영어 선택인데 한국어 누출: {body!r}"


@pytest.mark.asyncio
async def test_gate_callback_approve_threads_korean_default():
    """handle_gate_callback(approve) 가 'ko' default 언어로 한국어 body 생성 — seam 대칭 (사이클 155)."""
    from src.webhook.providers import telegram  # pylint: disable=import-outside-toplevel

    db_cm, analysis, repo, config = _make_gate_callback_mocks(decision="approve")
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=db_cm), patch(
        "src.webhook.providers.telegram.analysis_repo.find_by_id", return_value=analysis
    ), patch(
        "src.webhook.providers.telegram.repository_repo.find_by_id", return_value=repo
    ), patch(
        "src.webhook.providers.telegram.get_repo_config", return_value=config
    ), patch(
        "src.webhook.providers.telegram.resolve_notification_language", return_value="ko"
    ), patch(
        "src.webhook.providers.telegram.save_gate_decision"
    ), patch(
        "src.webhook.providers.telegram.user_repo.find_by_telegram_user_id", return_value=MagicMock(id=1)
    ), patch(
        "src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock
    ) as mock_review:
        await telegram.handle_gate_callback(1, "approve", "carol", telegram_user_id="1")

    assert mock_review.await_count == 1
    body = mock_review.await_args.args[4]
    assert "승인" in body, f"한국어 승인 body 아님: {body!r}"
    assert "carol" in body
