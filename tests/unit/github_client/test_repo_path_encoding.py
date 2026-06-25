"""github_client issues.py·graphql.py URL 빌드의 repo_path() 인코딩 회귀 가드 (품질감사 webhook-ghclient-001).

Regression guard: issues.py / graphql.py must build GitHub API repo URLs via repo_path()
(checks.py·repos.py 와 일관 — security.md 'repo_path() 경유' 규칙 + SonarCloud S7044 방어 심층).

repo_full_name 은 신뢰 입력(검증된 webhook/DB)이라 실 익스플로잇 위험은 낮으나, 단일출처 인코딩
규칙 일관성을 봉인한다 — repo_path() 는 슬래시 보존 + 그 외 특수문자 percent-encode.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from unittest.mock import AsyncMock, MagicMock, patch

from src.github_client.issues import close_issue, create_issue, get_issue_state
from src.github_client.graphql import get_pr_node_id

_REPO = "owner/re po"  # 공백 = 인코딩되어야 함 / space must be encoded
_ENC = "owner/re%20po"  # 슬래시 보존 + 공백 %20 / slash kept, space encoded


def _resp(json_body):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=json_body)
    return r


async def test_close_issue_url_uses_repo_path_encoding():
    client = AsyncMock()
    client.patch = AsyncMock(return_value=_resp({}))
    with patch("src.github_client.issues.get_http_client", return_value=client):
        await close_issue("token", _REPO, 42)
    url = client.patch.call_args[0][0]
    assert _ENC in url and "re po" not in url


async def test_create_issue_url_uses_repo_path_encoding():
    client = AsyncMock()
    client.post = AsyncMock(return_value=_resp({"number": 1, "html_url": "x", "state": "open"}))
    with patch("src.github_client.issues.get_http_client", return_value=client):
        await create_issue("token", _REPO, title="t", body="b", labels=[])
    url = client.post.call_args[0][0]
    assert _ENC in url and "re po" not in url


async def test_get_issue_state_url_uses_repo_path_encoding():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_resp({"state": "open"}))
    with patch("src.github_client.issues.get_http_client", return_value=client):
        await get_issue_state("token", _REPO, 42)
    url = client.get.call_args[0][0]
    assert _ENC in url and "re po" not in url


async def test_get_pr_node_id_url_uses_repo_path_encoding():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_resp({"node_id": "PR_abc"}))
    with patch("src.github_client.graphql.get_http_client", return_value=client):
        await get_pr_node_id("token", _REPO, 7)
    url = client.get.call_args[0][0]
    assert _ENC in url and "re po" not in url


async def test_normal_repo_full_name_url_unchanged():
    """특수문자 없는 평문 owner/repo 는 슬래시 보존·인코딩 artifact 없이 그대로 (정상 케이스 회귀)."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=_resp({"state": "open"}))
    with patch("src.github_client.issues.get_http_client", return_value=client):
        await get_issue_state("token", "owner/myrepo", 1)
    url = client.get.call_args[0][0]
    assert "/repos/owner/myrepo/issues/1" in url
    assert "%" not in url  # 인코딩 artifact 없음 (슬래시는 safe='/' 로 보존)
