"""approve SHA 결속 — **클라이언트 측** head 검증 (owed #1072 외부 계약 반증 후속).

🔴 **왜 클라이언트 측인가 — GitHub 실측으로 기존 전제가 반증됐다 (2026-07-26, owed #1072)**
`post_github_review(commit_id=분석SHA)` 가 "head 가 이동했으면 GitHub 이 422 로 거부한다"는
전제 위에 서 있었으나, 격리 리포 실측 결과 **거짓**이었다:

| 프로브 | commit_id | 실측 |
|--------|-----------|------|
| 대조군 | PR head | 200 |
| 🔴 핵심 | PR 내 **구** SHA | **200** (거부 안 함 — 리뷰가 그 SHA 로 기록됨) |
| force-push 로 PR 에서 사라진 SHA | 200 | |
| 존재하지 않는 SHA | 422 `The commitOID is not part of the pull request` |

즉 GitHub 의 `commit_id` 검증 기준은 "head 인가"도 "PR 에 포함됐는가"도 아니라 **"저장소에
오브젝트가 존재하는가"** 뿐이다. 분석된 SHA 는 **정의상 저장소에 존재**하므로(그래서 분석됐다)
이 가드는 **원리적으로 발화할 수 없었다** — 104 건의 운영 auto-approve 중 한 번도 차단한 적 없다.

따라서 결속은 **우리 코드가** 강제한다: POST 직전 PR head 를 조회해 분석 SHA 와 다르면
POST 하지 않는다. `_run_auto_merge_retry` 의 `analyzed_sha != head_sha` 가드와 같은 패턴.

🔴 **정직한 한계**: GET→POST 사이 head 가 또 움직이는 레이스는 남는다. 리뷰 API 에는 merge 의
`expected_sha` 같은 서버측 원자성 수단이 **없음이 실측으로 확인**됐으므로 이것이 가용 최선이다.
"""
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.gate.github_review import HeadMovedError, post_github_review

_ANALYZED = "a" * 40
_MOVED = "b" * 40


def _client_mock():
    """POST 를 관측하기 위한 http client 목."""
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    client.post = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_posts_when_head_matches_analyzed_sha():
    """대조군 — head == 분석 SHA 면 정상 POST 되고 payload 에 commit_id 가 실린다."""
    client = _client_mock()
    with patch("src.gate.github_review.get_pr_mergeable_state",
               new=AsyncMock(return_value=("clean", _ANALYZED))), \
         patch("src.gate.github_review.get_http_client", return_value=client):
        await post_github_review("tok", "o/r", 1, "approve", "body", commit_id=_ANALYZED)
    client.post.assert_awaited_once()
    assert client.post.await_args.kwargs["json"]["commit_id"] == _ANALYZED


@pytest.mark.asyncio
async def test_head_moved_raises_and_does_not_post():
    """🔴 핵심 — head 가 이동했으면 **POST 자체를 하지 않는다**(fail-closed).

    GitHub 이 막아주지 않는다는 것이 실측으로 확정됐으므로, POST 가 나가면 미분석 head 를
    가진 PR 에 APPROVE 가 실제로 붙는다.
    """
    client = _client_mock()
    with patch("src.gate.github_review.get_pr_mergeable_state",
               new=AsyncMock(return_value=("clean", _MOVED))), \
         patch("src.gate.github_review.get_http_client", return_value=client):
        with pytest.raises(HeadMovedError):
            await post_github_review("tok", "o/r", 1, "approve", "body", commit_id=_ANALYZED)
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_is_blocked_symmetrically():
    """reject(REQUEST_CHANGES)도 동일 — 다른 커밋을 분석한 결정을 현재 head 에 붙이지 않는다."""
    client = _client_mock()
    with patch("src.gate.github_review.get_pr_mergeable_state",
               new=AsyncMock(return_value=("clean", _MOVED))), \
         patch("src.gate.github_review.get_http_client", return_value=client):
        with pytest.raises(HeadMovedError):
            await post_github_review("tok", "o/r", 1, "reject", "body", commit_id=_ANALYZED)
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_undeterminable_head_is_fail_closed():
    """head 를 판정할 수 없으면(빈 문자열) 통과시키지 않는다 — 가드는 모를 때 닫힌다."""
    client = _client_mock()
    with patch("src.gate.github_review.get_pr_mergeable_state",
               new=AsyncMock(return_value=("unknown", ""))), \
         patch("src.gate.github_review.get_http_client", return_value=client):
        with pytest.raises(HeadMovedError):
            await post_github_review("tok", "o/r", 1, "approve", "body", commit_id=_ANALYZED)
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_commit_id_skips_head_check_backward_compatible():
    """commit_id 미전달 = 결속 미적용(하위 호환) — head 조회조차 하지 않는다."""
    client = _client_mock()
    head = AsyncMock(return_value=("clean", _MOVED))
    with patch("src.gate.github_review.get_pr_mergeable_state", new=head), \
         patch("src.gate.github_review.get_http_client", return_value=client):
        await post_github_review("tok", "o/r", 1, "approve", "body")
    head.assert_not_awaited()
    client.post.assert_awaited_once()
    assert "commit_id" not in client.post.await_args.kwargs["json"]


@pytest.mark.asyncio
async def test_approve_action_head_moved_skips_decision(caplog):
    """🔴 배선(자동 경로) — HeadMovedError 시 gate_decision 을 기록하지 않고 INFO 로 남긴다."""
    import logging as _logging  # pylint: disable=import-outside-toplevel
    from tests.unit.gate.test_gate_actions import _make_ctx  # pylint: disable=import-outside-toplevel
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel

    ctx = _make_ctx(approve_mode="auto", score=80, commit_sha=_ANALYZED)
    err = HeadMovedError("head moved")
    with patch("src.gate.actions.approve.post_github_review", new=AsyncMock(side_effect=err)), \
         patch("src.gate.actions.approve.gate_decision_repo") as mock_gd, \
         patch("src.gate.actions.approve.SessionLocal") as mock_sess:
        mock_sess.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_sess.return_value.__exit__ = MagicMock(return_value=False)
        with caplog.at_level(_logging.INFO, logger="src.gate.actions.approve"):
            await ApproveAction().execute(ctx)
    mock_gd.upsert.assert_not_called()
    assert any("head moved" in r.message for r in caplog.records), "head 이동 INFO 로그 없음"
    assert not any(r.levelno >= _logging.ERROR for r in caplog.records), \
        "정상 fail-closed 인데 ERROR 로 로깅됨"


@pytest.mark.asyncio
async def test_422_no_longer_attributed_to_head_move(caplog):
    """🔴 관측자 정직성 — 422 를 'head 이동'으로 단정하지 않는다.

    실측상 422 는 head 이동이 **아니라** 다른 사유(예: `Can not approve your own pull request`,
    존재하지 않는 commitOID)에서 온다. 원인을 모르는 채 특정 원인을 로그에 적으면 운영자가
    엉뚱한 곳을 파게 된다(이 저장소가 반복해 온 observer-lie).
    """
    import logging as _logging  # pylint: disable=import-outside-toplevel
    from tests.unit.gate.test_gate_actions import _make_ctx  # pylint: disable=import-outside-toplevel
    from src.gate.actions.approve import ApproveAction  # pylint: disable=import-outside-toplevel

    ctx = _make_ctx(approve_mode="auto", score=80, commit_sha=_ANALYZED)
    resp = httpx.Response(422, request=httpx.Request("POST", "https://api.github.com/x"))
    err = httpx.HTTPStatusError("422", request=resp.request, response=resp)
    with patch("src.gate.actions.approve.post_github_review", new=AsyncMock(side_effect=err)), \
         patch("src.gate.actions.approve.gate_decision_repo") as mock_gd, \
         patch("src.gate.actions.approve.SessionLocal") as mock_sess:
        mock_sess.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_sess.return_value.__exit__ = MagicMock(return_value=False)
        with caplog.at_level(_logging.INFO, logger="src.gate.actions.approve"):
            await ApproveAction().execute(ctx)
    mock_gd.upsert.assert_not_called()
    assert not any("head moved" in r.message for r in caplog.records), \
        "422 를 여전히 'head moved' 로 단정 — 관측자가 모르는 원인을 지어냄"
