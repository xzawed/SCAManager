import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.n8n import notify_n8n
from src.scorer.calculator import ScoreResult


def _score():
    return ScoreResult(total=82, grade="B", code_quality_score=28, security_score=20, breakdown={})


async def test_notify_n8n_posts_to_webhook():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    score = ScoreResult(total=82, grade="B", code_quality_score=28, security_score=20, breakdown={})
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=5,
            score_result=score,
        )

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
    assert url == "https://n8n.example.com/webhook/abc"
    payload = call_args.kwargs.get("json") or (call_args.args[1] if len(call_args.args) > 1 else {})
    assert payload["event_type"] == "analysis"
    assert payload["repo"] == "owner/repo"
    data = payload["data"]
    assert data["score"] == 82
    assert data["grade"] == "B"


async def test_notify_n8n_skips_when_no_url():
    with patch("src.notifier.n8n.build_safe_client") as mock_build:
        score = ScoreResult(total=80, grade="B", code_quality_score=25, security_score=20, breakdown={})
        await notify_n8n(webhook_url=None, repo_full_name="owner/repo", commit_sha="abc123", pr_number=None, score_result=score)
    mock_build.assert_not_called()


async def test_notify_n8n_blocks_ssrf_url():
    # SSRF 차단(validate_external_url=False) 시 build_safe_client 미호출 (Theme B S2 — n8n.py:52-54).
    # notify_n8n_issue 는 별도 커버됨(test_n8n_envelope) — 여기선 notify_n8n(분석 페이로드) 차단 봉인.
    with patch("src.notifier.n8n.build_safe_client") as mock_build, \
         patch("src.notifier.n8n.validate_external_url", return_value=False):
        score = ScoreResult(total=80, grade="B", code_quality_score=25, security_score=20, breakdown={})
        await notify_n8n(
            webhook_url="http://169.254.169.254/hook",
            repo_full_name="owner/repo", commit_sha="abc123", pr_number=None, score_result=score,
        )
    mock_build.assert_not_called()


async def test_notify_n8n_raises_on_error():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("Connection error")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    score = ScoreResult(total=80, grade="B", code_quality_score=25, security_score=20, breakdown={})
    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        with pytest.raises(Exception, match="Connection error"):
            await notify_n8n(
                webhook_url="https://n8n.example.com/webhook/abc",
                repo_full_name="owner/repo",
                commit_sha="abc123",
                pr_number=None,
                score_result=score,
            )


# ── repo_token 파라미터 테스트 (Red phase) ──────────────────────────────────────

async def test_notify_n8n_issue_includes_repo_token_in_payload():
    # repo_token="ghp_abc" 전달 시 POST 페이로드의 data["repo_token"]이 "ghp_abc"여야 한다
    from src.notifier.n8n import notify_n8n_issue
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="opened",
            issue={"number": 1, "title": "test", "body": ""},
            sender={"login": "octocat"},
            n8n_secret="shh",
            repo_token="ghp_abc",
        )

    mock_client.post.assert_called_once()
    payload = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
    data = payload["data"]
    assert data["repo_token"] == "ghp_abc", \
        f"data['repo_token']이 'ghp_abc'여야 하지만 실제 값: {data.get('repo_token')!r}"


async def test_notify_n8n_issue_repo_token_defaults_empty():
    # repo_token 미전달 시 POST 페이로드의 data["repo_token"]이 ""이어야 한다
    from src.notifier.n8n import notify_n8n_issue
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="opened",
            issue={"number": 1, "title": "test", "body": ""},
            sender={"login": "octocat"},
        )

    mock_client.post.assert_called_once()
    payload = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
    data = payload["data"]
    assert "repo_token" in data, \
        "data 딕셔너리에 'repo_token' 키가 없음 — notify_n8n_issue()에 repo_token 파라미터 추가 필요"
    assert data["repo_token"] == "", \
        f"repo_token 기본값이 ''이어야 하지만 실제 값: {data.get('repo_token')!r}"


async def test_notify_n8n_issue_omits_repo_token_without_secret():
    # 자격증명 유출 가드: n8n_secret 미설정 시 repo_token 이 전달돼도 페이로드에서 빈 문자열로 생략돼야 한다
    # Credential-leak guard: with no n8n_secret, a passed repo_token must be omitted (empty) from the payload
    from src.notifier.n8n import notify_n8n_issue
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("src.notifier.n8n.validate_external_url", return_value=True), \
         patch("src.notifier.n8n.build_safe_client", return_value=mock_client):
        await notify_n8n_issue(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            action="opened",
            issue={"number": 1, "title": "test", "body": ""},
            sender={"login": "octocat"},
            repo_token="ghp_secret_token",  # n8n_secret 미설정 → 토큰 유출 금지 / no secret → must not leak
        )

    mock_client.post.assert_called_once()
    payload = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
    data = payload["data"]
    assert data["repo_token"] == "", \
        f"시크릿 없이 repo_token 이 유출됨 (자격증명 유출 결함): {data.get('repo_token')!r}"
