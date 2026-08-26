"""github_client issues.py·graphql.py URL 빌드의 repo_path() 인코딩 회귀 가드 (품질감사 webhook-ghclient-001).

Regression guard: issues.py / graphql.py must build GitHub API repo URLs via repo_path()
(checks.py·repos.py 와 일관 — security.md 'repo_path() 경유' 규칙 + SonarCloud S7044 방어 심층).

봉인하는 성질: **raw 사용자 값이 요청 URL 에 들어가지 않는다.** repo_path() 는 owner/repo
화이트리스트를 강제하고, 밖의 이름은 요청을 보내기 전에 ValueError 로 거부한다.

Sealed property: a raw user value never reaches the request URL.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.github_client.issues import close_issue, create_issue, get_issue_state
from src.github_client.graphql import get_pr_node_id

# 🔴 repo_path 가 화이트리스트(`[A-Za-z0-9._-]{1,39}/[A-Za-z0-9._-]{1,100}`)가 된 뒤로는
# 공백 같은 문자가 **인코딩되는 게 아니라 거부된다**. 허용 문자는 전부 unreserved 라
# percent-encoding 이 일어날 여지 자체가 없다 — 그래서 이 파일의 봉인 축을
# 「특수문자를 인코딩한다」에서 「부정 이름은 URL 에 닿기 전에 거부된다」로 옮긴다.
# 지키는 성질은 같고 더 강하다: raw 사용자 값이 요청 URL 에 절대 들어가지 않는다.
#
# The whitelist rejects rather than encodes; the sealed property is unchanged but stronger.
_REPO = "owner/re po"  # 화이트리스트 밖 — 거부되어야 함 / outside the whitelist


def _resp(json_body):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=json_body)
    return r


async def test_close_issue_rejects_names_outside_the_whitelist():
    client = AsyncMock()
    client.patch = AsyncMock(return_value=_resp({}))
    with patch("src.github_client.issues.get_http_client", return_value=client):
        with pytest.raises(ValueError, match="charset"):
            await close_issue("token", _REPO, 42)
    client.patch.assert_not_awaited()


async def test_create_issue_rejects_names_outside_the_whitelist():
    client = AsyncMock()
    client.post = AsyncMock(return_value=_resp({"number": 1, "html_url": "x", "state": "open"}))
    with patch("src.github_client.issues.get_http_client", return_value=client):
        with pytest.raises(ValueError, match="charset"):
            await create_issue("token", _REPO, title="t", body="b", labels=[])
    client.post.assert_not_awaited()


async def test_get_issue_state_rejects_names_outside_the_whitelist():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_resp({"state": "open"}))
    with patch("src.github_client.issues.get_http_client", return_value=client):
        with pytest.raises(ValueError, match="charset"):
            await get_issue_state("token", _REPO, 42)
    client.get.assert_not_awaited()


async def test_get_pr_node_id_rejects_names_outside_the_whitelist():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_resp({"node_id": "PR_abc"}))
    with patch("src.github_client.graphql.get_http_client", return_value=client):
        with pytest.raises(ValueError, match="charset"):
            await get_pr_node_id("token", _REPO, 7)
    client.get.assert_not_awaited()


async def test_normal_repo_full_name_url_unchanged():
    """특수문자 없는 평문 owner/repo 는 슬래시 보존·인코딩 artifact 없이 그대로 (정상 케이스 회귀)."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=_resp({"state": "open"}))
    with patch("src.github_client.issues.get_http_client", return_value=client):
        await get_issue_state("token", "owner/myrepo", 1)
    url = client.get.call_args[0][0]
    assert "/repos/owner/myrepo/issues/1" in url
    assert "%" not in url  # 인코딩 artifact 없음 (슬래시는 safe='/' 로 보존)
