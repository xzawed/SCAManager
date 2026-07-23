"""merge_retry_service 소유권 CAS 배선 테스트 (종합감사 P1-5, 2026-07-23).

repo 계층이 expected_claim_token CAS 를 지원하는 것(behavior)과, 서비스가 실제로 그 토큰을
write-back 에 **전달하는 것**(wiring)은 별개다. repo 만 고쳐도 서비스가 토큰을 안 넘기면 CAS 는
영영 무력이다(정의≠배선, guards.md 3-불변식 §3). 이 파일은 3개 write-back 함수 각각이 소유권
토큰을 repo 계층에 실제로 전달하는지 실행 관측으로 단언한다.

The repo layer *supporting* CAS and the service *passing* the token are different things — this file
observes the actual calls to prove the service threads the token to every write-back site.
"""
# pylint: disable=redefined-outer-name,protected-access
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_settings_token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import src.services.merge_retry_service as svc

_NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def _row(**over):
    """write-back 경로가 참조하는 필드를 갖춘 가짜 queue row.
    Fake queue row with the fields the write-back paths reference.
    """
    base = dict(
        id=7, claim_token="TOK-A", attempts_count=1, max_attempts=30,
        analysis_id=11, repo_full_name="owner/repo", pr_number=3,
        score=90, threshold_at_enqueue=75, commit_sha="abc123",
        notify_chat_id=None, status="pending",
    )
    base.update(over)
    return SimpleNamespace(**base)


def _counts():
    return {"claimed": 1, "succeeded": 0, "terminal": 0, "expired": 0,
            "abandoned": 0, "released": 0, "skipped": 0}


# ---------------------------------------------------------------------------
# _process_single_retry — 캡처한 row.claim_token 을 write-back 에 전달
# ---------------------------------------------------------------------------


async def test_process_single_retry_threads_token_on_abandon():
    """max_attempts 초과 abandon 경로가 mark_abandoned 에 row.claim_token 을 CAS 로 전달.
    The max_attempts abandon path passes row.claim_token to mark_abandoned as the CAS guard.
    """
    row = _row(claim_token="TOK-XYZ", attempts_count=30, max_attempts=30)
    counts = _counts()
    with patch.object(svc, "merge_retry_repo") as repo, \
         patch.object(svc, "log_merge_attempt"):
        await svc._process_single_retry(MagicMock(), row, _NOW, counts)

    repo.mark_abandoned.assert_called_once()
    assert repo.mark_abandoned.call_args.kwargs["expected_claim_token"] == "TOK-XYZ"


async def test_process_single_retry_threads_token_on_already_merged():
    """이미 머지된 PR → mark_succeeded 가 row.claim_token 을 CAS 로 전달.
    Already-merged PR → mark_succeeded receives row.claim_token as the CAS guard.
    """
    row = _row(claim_token="TOK-M")
    counts = _counts()
    cfg = SimpleNamespace(auto_merge=True, merge_threshold=70,
                          notify_chat_id=None, auto_merge_issue_on_failure=False)
    with patch.object(svc, "merge_retry_repo") as repo, \
         patch.object(svc, "log_merge_attempt"), \
         patch.object(svc, "_resolve_github_token", return_value="ghp_x"), \
         patch.object(svc, "get_repo_config", return_value=cfg), \
         patch.object(svc, "resolve_notification_language", return_value="ko"), \
         patch.object(svc, "_get_pr_data", new=AsyncMock(return_value={"merged": True})):
        await svc._process_single_retry(MagicMock(), row, _NOW, counts)

    repo.mark_succeeded.assert_called_once()
    assert repo.mark_succeeded.call_args.kwargs["expected_claim_token"] == "TOK-M"


# ---------------------------------------------------------------------------
# _handle_merge_failure — 받은 토큰을 3 write-back 에 forward
# ---------------------------------------------------------------------------


async def test_handle_merge_failure_forwards_token_to_terminal():
    """_handle_merge_failure 가 받은 expected_claim_token 을 mark_terminal 로 forward.
    _handle_merge_failure forwards the received token to mark_terminal.
    """
    row = _row()
    counts = _counts()
    cfg = SimpleNamespace(merge_threshold=70, notify_chat_id=None,
                          auto_merge_issue_on_failure=False)
    with patch.object(svc, "merge_retry_repo") as repo, \
         patch.object(svc, "log_merge_attempt"), \
         patch.object(svc, "parse_reason_tag", return_value="permission_denied"), \
         patch.object(svc, "should_retry", return_value=False), \
         patch.object(svc, "is_expired", return_value=False), \
         patch.object(svc, "_get_ci_status_safe", new=AsyncMock(return_value="unknown")), \
         patch.object(svc, "_notify_merge_terminal", new=AsyncMock()):
        await svc._handle_merge_failure(
            MagicMock(), row=row, cfg=cfg, token="ghp_x", pr_data={"base": {"ref": "main"}},
            reason="permission", now=_NOW, language="ko", counts=counts,
            expected_claim_token="TOK-FWD",
        )

    repo.mark_terminal.assert_called_once()
    assert repo.mark_terminal.call_args.kwargs["expected_claim_token"] == "TOK-FWD"


# ---------------------------------------------------------------------------
# _recover_and_release — loop 가 캡처한 원본 토큰을 release_claim 으로 전달
# ---------------------------------------------------------------------------


def test_recover_and_release_threads_original_token():
    """_recover_and_release 가 원본 토큰을 release_claim CAS 로 전달 + 성공 시에만 released 증가.
    _recover_and_release passes the original token to release_claim; increments only on success.
    """
    row = _row(status="pending")
    counts = _counts()
    db = MagicMock()
    with patch.object(svc, "merge_retry_repo") as repo:
        repo.release_claim.return_value = True
        svc._recover_and_release(
            db, row, _NOW, counts, reason="infra_error", exc=RuntimeError("boom"),
            expected_claim_token="TOK-ORIG",
        )

    repo.release_claim.assert_called_once()
    assert repo.release_claim.call_args.kwargs["expected_claim_token"] == "TOK-ORIG"
    assert counts["released"] == 1


def test_recover_and_release_skips_counter_when_cas_misses():
    """release_claim 이 False(소유권 상실) 반환 시 released 카운터 미증가.
    When release_claim returns False (ownership lost), the released counter must not increment.
    """
    row = _row(status="pending")
    counts = _counts()
    db = MagicMock()
    with patch.object(svc, "merge_retry_repo") as repo:
        repo.release_claim.return_value = False  # 다른 워커가 재클레임 / another worker reclaimed
        svc._recover_and_release(
            db, row, _NOW, counts, reason="infra_error", exc=RuntimeError("boom"),
            expected_claim_token="TOK-STALE",
        )

    assert counts["released"] == 0


# ---------------------------------------------------------------------------
# process_pending_retries — loop 가 원본 토큰을 캡처해 복구 경로로 전달 (mutation red)
# ---------------------------------------------------------------------------


async def test_loop_captures_original_token_before_recover():
    """_process_single_retry 예외 시, loop 가 claim 당시 토큰을 _recover_and_release 로 넘긴다.
    On _process_single_retry error, the loop hands the claim-time token to _recover_and_release.
    """
    claimed = [_row(claim_token="TOK-LOOP")]
    with patch.object(svc.merge_retry_repo, "claim_batch", return_value=claimed), \
         patch.object(svc, "_process_single_retry", new=AsyncMock(side_effect=RuntimeError("x"))), \
         patch.object(svc, "_recover_and_release") as recover:
        await svc.process_pending_retries(MagicMock(), now=_NOW)

    recover.assert_called_once()
    assert recover.call_args.kwargs["expected_claim_token"] == "TOK-LOOP"
