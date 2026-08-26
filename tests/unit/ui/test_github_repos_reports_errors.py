"""GitHub 조회 실패를 «리포 없음» 으로 보고한다 — 사용자에게 거짓을 단정한다 (감사 A8, #1519).

🔴 실측. `GET /api/github/repos` 는 `list_user_repos` 의 **모든** 예외를 삼키고
HTTP 200 + `[]` 를 돌려준다:

    except Exception:  # 401 · 403 · 429 · timeout 전부
        return []

클라이언트(`add_repo.html`)는 `repos.length === 0` 을 보고 이렇게 **단정**한다:

    "모든 리포가 이미 등록되었거나 접근 가능한 리포가 없습니다."

토큰이 만료됐거나 rate limit 에 걸린 것을 「리포가 없다」고 말하는 것이다. 사용자는
재인증하면 될 일을 「등록할 게 없구나」로 읽고 떠난다.

🔴 **클라이언트에는 이미 오류 경로가 있다** — `add_repo.html:228` 이 `!resp.ok` 를
검사하고 `:260` 이 `loadFailed` 문구를 띄운다. 서버가 오류를 **오류로 알리기만** 하면
그 경로가 살아난다. 새 UI 가 필요 없다.

이 파일이 봉인하는 것:
1. GitHub 오류는 **비-200** 으로 나간다 — 클라이언트의 기존 오류 경로가 발화한다.
2. 토큰 부재는 그대로 200 + `[]` — 「아직 연결 안 함」은 오류가 아니다.
3. 진짜 «리포 없음» 도 그대로 200 + `[]` — 과잉 오류가 되지 않는다.

The client already has an error branch; the server just never lets it fire.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import io  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from src.ui.routes import add_repo as AR  # noqa: E402


class _User:
    id = 1
    plaintext_token = "ghp_live"


@pytest.fixture(autouse=True)
def _clear_cache():
    AR._user_repos_cache.clear()  # noqa: SLF001
    yield
    AR._user_repos_cache.clear()  # noqa: SLF001


async def _call(user=None):
    return await AR.github_repos_list(user or _User())


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_client_already_has_an_error_branch():
    """🔴 전제 — 템플릿에 오류 경로가 실제로 있는가.

    없다면 「서버만 고치면 된다」는 이 파일의 근거가 무너진다.
    """
    html = io.open("src/templates/add_repo.html", encoding="utf-8").read()
    assert "!resp.ok" in html, "클라이언트가 응답 상태를 안 본다"
    assert "loadFailed" in html, "클라이언트에 로딩 실패 문구 경로가 없다"


@pytest.mark.asyncio
async def test_a_genuine_empty_list_is_still_a_success():
    """대조군 — 진짜 «리포 없음» 은 오류가 아니다."""
    with patch.object(AR, "list_user_repos", AsyncMock(return_value=[])), \
         patch.object(AR, "SessionLocal") as sess:
        sess.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = []
        result = await _call()
    assert result == []


@pytest.mark.asyncio
async def test_missing_token_is_not_an_error():
    """대조군 — 토큰 미연결은 「아직 연결 안 함」이지 오류가 아니다."""
    class _NoToken:
        id = 2
        plaintext_token = None

    assert await _call(_NoToken()) == []


# ─── 결함 ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [
    httpx.HTTPStatusError(
        "401", request=httpx.Request("GET", "https://api.github.com/x"),
        response=httpx.Response(401, request=httpx.Request("GET", "https://api.github.com/x")),
    ),
    httpx.HTTPStatusError(
        "429", request=httpx.Request("GET", "https://api.github.com/x"),
        response=httpx.Response(429, request=httpx.Request("GET", "https://api.github.com/x")),
    ),
    httpx.ConnectTimeout("timeout"),
    httpx.ConnectError("dns"),
])
async def test_github_failure_is_reported_not_disguised_as_empty(exc):
    """🔴 GitHub 조회 실패가 «리포 없음» 으로 위장되지 않는다.

    위장하면 사용자는 재인증하면 될 일을 「등록할 게 없다」로 읽는다.
    """
    from fastapi import HTTPException  # noqa: PLC0415

    with patch.object(AR, "list_user_repos", AsyncMock(side_effect=exc)):
        with pytest.raises(HTTPException) as excinfo:
            await _call()

    assert excinfo.value.status_code >= 400, (
        f"실패가 성공 상태코드로 나갔다: {excinfo.value.status_code}"
    )


@pytest.mark.asyncio
async def test_a_failure_is_not_cached_as_an_empty_list():
    """🔴 실패를 캐시에 «빈 목록» 으로 넣지 않는다.

    넣으면 회복 후에도 TTL 동안 「리포 없음」이 계속 나온다.
    """
    from fastapi import HTTPException  # noqa: PLC0415

    with patch.object(AR, "list_user_repos", AsyncMock(side_effect=httpx.ConnectError("dns"))):
        with pytest.raises(HTTPException):
            await _call()

    assert _User.id not in AR._user_repos_cache, (  # noqa: SLF001
        f"실패가 캐시됐다: {AR._user_repos_cache}"  # noqa: SLF001
    )
