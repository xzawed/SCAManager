"""TDD Red 테스트 — n8n Envelope + Discriminator 구조 및 notify_n8n_issue() 검증.

구현 예정 변경 사항:
- notify_n8n(): flat payload → envelope 구조 (event_type, source, delivered_at, data)
- notify_n8n_issue(): 신규 함수 (issues 이벤트 릴레이)
- n8n_secret 인자: HMAC-SHA256 서명 헤더 X-SCAManager-Signature-256

이 테스트들은 구현 전 실패(Red) 상태여야 한다.
"""
import hashlib
import hmac
import json
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.notifier.n8n import notify_n8n
from src.scorer.calculator import ScoreResult


# ── 공용 픽스처 ─────────────────────────────────────────────────────────────
# ── Shared fixtures ────────────────────────────────────────────────────────────

def _score() -> ScoreResult:
    return ScoreResult(
        total=82,
        grade="B",
        code_quality_score=22,
        security_score=18,
        breakdown={"code_quality": 22, "security": 18, "commit": 13, "direction": 21, "test": 8},
    )


def _mock_client(post_response: MagicMock | None = None) -> AsyncMock:
    """AsyncClient context manager mock을 반환한다."""
    if post_response is None:
        post_response = MagicMock()
        post_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=post_response)
    return mock_client


def _captured_payload(mock_client: AsyncMock) -> dict:
    """mock_client.post 호출 시 전달된 json payload를 반환한다."""
    call_args = mock_client.post.call_args
    return call_args.kwargs.get("json") or {}


def _captured_headers(mock_client: AsyncMock) -> dict:
    """mock_client.post 호출 시 전달된 headers를 반환한다."""
    call_args = mock_client.post.call_args
    return call_args.kwargs.get("headers") or {}


# ── notify_n8n() envelope 구조 테스트 ────────────────────────────────────────

async def test_notify_n8n_payload_has_event_type_analysis():
    # notify_n8n() 전송 payload 최상위에 event_type="analysis" 가 있어야 한다
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=5,
            score_result=_score(),
        )
    payload = _captured_payload(mock_client)
    assert payload.get("event_type") == "analysis"


async def test_notify_n8n_payload_has_source_scamanager():
    # notify_n8n() 전송 payload 최상위에 source="scamanager" 가 있어야 한다
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=5,
            score_result=_score(),
        )
    payload = _captured_payload(mock_client)
    assert payload.get("source") == "scamanager"


async def test_notify_n8n_payload_has_delivered_at_iso8601():
    # notify_n8n() 전송 payload 최상위에 delivered_at 필드가 ISO8601 UTC 형식으로 있어야 한다
    from datetime import datetime, timezone
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=None,
            score_result=_score(),
        )
    payload = _captured_payload(mock_client)
    delivered_at = payload.get("delivered_at")
    assert delivered_at is not None, "delivered_at 필드가 없음"
    # ISO8601 파싱 가능 여부 검증
    # Verify the timestamp is parseable as ISO 8601.
    dt = datetime.fromisoformat(delivered_at.replace("Z", "+00:00"))
    assert dt.tzinfo is not None, "delivered_at에 timezone 정보가 없음"


async def test_notify_n8n_payload_data_contains_score_grade_breakdown():
    # notify_n8n() 전송 payload의 data 키에 score, grade, breakdown이 있어야 한다
    score = _score()
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            commit_sha="deadbeef",
            pr_number=7,
            score_result=score,
        )
    payload = _captured_payload(mock_client)
    data = payload.get("data", {})
    assert data.get("score") == 82
    assert data.get("grade") == "B"
    assert data.get("breakdown") == score.breakdown
    assert data.get("commit_sha") == "deadbeef"
    assert data.get("pr_number") == 7


async def test_notify_n8n_with_secret_sends_signature_header():
    # notify_n8n(n8n_secret="mysecret") 시 X-SCAManager-Signature-256 헤더가 포함되어야 한다
    secret = "mysecret"
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=None,
            score_result=_score(),
            n8n_secret=secret,
        )
    headers = _captured_headers(mock_client)
    sig_header = headers.get("X-SCAManager-Signature-256", "")
    assert sig_header.startswith("sha256="), f"서명 헤더 형식 오류: {sig_header!r}"
    # HMAC 값 직접 검증
    payload_sent = _captured_payload(mock_client)
    payload_bytes = json.dumps(payload_sent).encode()
    expected_hex = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected_hex}"


async def test_notify_n8n_without_secret_has_no_signature_header():
    # notify_n8n(n8n_secret="") 시 X-SCAManager-Signature-256 헤더가 없어야 한다
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=None,
            score_result=_score(),
            n8n_secret="",
        )
    headers = _captured_headers(mock_client)
    assert "X-SCAManager-Signature-256" not in headers


# ── notify_n8n_issue() 테스트 ────────────────────────────────────────────────

def _sample_issue(body: str = "이슈 본문입니다.") -> dict:
    return {
        "number": 42,
        "title": "버그 리포트",
        "state": "open",
        "body": body,
        "html_url": "https://github.com/owner/repo/issues/42",
        "user": {"login": "octocat"},
    }


def _sample_sender() -> dict:
    return {"login": "octocat", "id": 1}


async def test_notify_n8n_issue_payload_has_event_type_issue():
    # notify_n8n_issue() 전송 payload 최상위에 event_type="issue" 가 있어야 한다
    from src.notifier.n8n import notify_n8n_issue  # 아직 미구현 → ImportError or AttributeError
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="opened",
            issue=_sample_issue(),
            sender=_sample_sender(),
        )
    payload = _captured_payload(mock_client)
    assert payload.get("event_type") == "issue"


async def test_notify_n8n_issue_payload_data_fields():
    # notify_n8n_issue() data에 action, issue, sender, body_truncated 필드가 있어야 한다
    from src.notifier.n8n import notify_n8n_issue
    issue = _sample_issue(body="짧은 본문")
    sender = _sample_sender()
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="closed",
            issue=issue,
            sender=sender,
        )
    payload = _captured_payload(mock_client)
    data = payload.get("data", {})
    assert data.get("action") == "closed"
    assert data.get("issue", {}).get("number") == 42
    assert data.get("sender", {}).get("login") == "octocat"
    assert "body_truncated" in data


async def test_notify_n8n_issue_body_over_8kb_is_truncated():
    # Issue body가 8KB 초과 시 data.body_truncated=True이고 body가 잘려야 한다
    from src.notifier.n8n import notify_n8n_issue
    long_body = "A" * 9000  # 9000 bytes > 8192 bytes
    issue = _sample_issue(body=long_body)
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="opened",
            issue=issue,
            sender=_sample_sender(),
        )
    payload = _captured_payload(mock_client)
    data = payload.get("data", {})
    assert data.get("body_truncated") is True
    sent_body = data.get("issue", {}).get("body", "")
    assert len(sent_body.encode()) <= 8192, "8KB 초과 본문이 절단되지 않음"


async def test_notify_n8n_issue_body_within_8kb_not_truncated():
    # Issue body가 8KB 이하 시 data.body_truncated=False이어야 한다
    from src.notifier.n8n import notify_n8n_issue
    short_body = "B" * 100
    issue = _sample_issue(body=short_body)
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="opened",
            issue=issue,
            sender=_sample_sender(),
        )
    payload = _captured_payload(mock_client)
    data = payload.get("data", {})
    assert data.get("body_truncated") is False


async def test_notify_n8n_issue_skips_when_no_url():
    # webhook_url이 None이면 HTTP 호출 없이 조용히 리턴해야 한다
    from src.notifier.n8n import notify_n8n_issue
    with patch("src.notifier.n8n.build_safe_client") as mock_build:
        await notify_n8n_issue(
            webhook_url=None,
            repo_full_name="owner/repo",
            action="opened",
            issue=_sample_issue(),
            sender=_sample_sender(),
        )
    mock_build.assert_not_called()


async def test_notify_n8n_issue_blocks_ssrf_url():
    # SSRF 위험 URL(private IP 등) 은 validate_external_url 통해 차단되어야 한다
    from src.notifier.n8n import notify_n8n_issue
    with patch("src.notifier.n8n.build_safe_client") as mock_build, \
         patch("src.notifier.n8n.validate_external_url", return_value=False):
        await notify_n8n_issue(
            webhook_url="http://169.254.169.254/latest/meta-data/",
            repo_full_name="owner/repo",
            action="opened",
            issue=_sample_issue(),
            sender=_sample_sender(),
        )
    mock_build.assert_not_called()


async def test_notify_n8n_issue_with_secret_sends_signature_header():
    # notify_n8n_issue(n8n_secret="sec") 시 X-SCAManager-Signature-256 헤더가 포함되어야 한다
    from src.notifier.n8n import notify_n8n_issue
    secret = "sec"
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/issue",
            repo_full_name="owner/repo",
            action="opened",
            issue=_sample_issue(),
            sender=_sample_sender(),
            n8n_secret=secret,
        )
    headers = _captured_headers(mock_client)
    sig_header = headers.get("X-SCAManager-Signature-256", "")
    assert sig_header.startswith("sha256="), f"서명 헤더 없음: {headers}"
    payload_sent = _captured_payload(mock_client)
    payload_bytes = json.dumps(payload_sent).encode()
    expected_hex = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected_hex}"


async def test_notify_n8n_issue_payload_has_source_scamanager():
    # notify_n8n_issue() payload 최상위에 source="scamanager" 가 있어야 한다
    from src.notifier.n8n import notify_n8n_issue
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="reopened",
            issue=_sample_issue(),
            sender=_sample_sender(),
        )
    payload = _captured_payload(mock_client)
    assert payload.get("source") == "scamanager"


async def test_notify_n8n_issue_payload_has_delivered_at():
    # notify_n8n_issue() payload 최상위에 delivered_at ISO8601 필드가 있어야 한다
    from src.notifier.n8n import notify_n8n_issue
    from datetime import datetime
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="opened",
            issue=_sample_issue(),
            sender=_sample_sender(),
        )
    payload = _captured_payload(mock_client)
    delivered_at = payload.get("delivered_at")
    assert delivered_at is not None
    dt = datetime.fromisoformat(delivered_at.replace("Z", "+00:00"))
    assert dt.tzinfo is not None


async def test_notify_n8n_issue_body_none_treated_as_empty():
    # issue body가 None이면 빈 문자열로 처리하고 body_truncated=False여야 한다
    from src.notifier.n8n import notify_n8n_issue
    issue = _sample_issue()
    issue["body"] = None
    mock_client = _mock_client()
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="opened",
            issue=issue,
            sender=_sample_sender(),
        )
    payload = _captured_payload(mock_client)
    data = payload.get("data", {})
    assert data.get("body_truncated") is False


# ── 기존 notify_n8n() 하위 호환 테스트 (envelope 이후에도 동작해야 함) ──────

async def test_notify_n8n_skips_when_no_url():
    # webhook_url이 None이면 HTTP 호출 없이 조용히 리턴해야 한다
    with patch("src.notifier.n8n.build_safe_client") as mock_build:
        await notify_n8n(
            webhook_url=None,
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=None,
            score_result=_score(),
        )
    mock_build.assert_not_called()


async def test_notify_n8n_raises_on_http_error():
    # HTTP 오류 발생 시 예외가 전파되어야 한다
    # An HTTP error must propagate as an exception.
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("Connection error")
    mock_client = _mock_client(post_response=mock_response)
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        with pytest.raises(Exception, match="Connection error"):
            await notify_n8n(
                webhook_url="https://n8n.example.com/webhook/abc",
                repo_full_name="owner/repo",
                commit_sha="abc123",
                pr_number=None,
                score_result=_score(),
            )
