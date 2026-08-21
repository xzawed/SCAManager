"""공개 리포에는 `hook_token` 을 커밋하지 않는다 (2026-08-21 전수 감사).

## 사고

`commit_scamanager_files` 는 `.scamanager/config.json` 에 **살아 있는 `hook_token` 을 평문**으로
넣어 사용자 GitHub 리포에 커밋한다. 그런데 그 경로에 **리포 공개/비공개 검사가 없었다** --
같은 모듈 `list_user_repos` 가 `private` 를 읽지만 이 경로는 참조하지 않는다.

공개 리포면 그 토큰이 공개된다. 그 토큰은 `POST /api/hook/result` 를 **X-API-Key 없이**
인증하므로(`src/api/hook.py:147`), 누구나 그 리포의 `score`/`grade` 행을 써 넣을 수 있다.

🔴 **완화는 있다** — `src/api/hook.py:285` 가 `static_analysis_incomplete = True` 를 무조건
세워 auto-merge 를 막는다. 그래서 강제 머지는 불가하고 **점수·대시보드 오염**이 가능하다.
그럼에도 High 다: 게이팅 제품의 **1차 산출물**에 대한 무인증 쓰기다.

## 왜 「토큰만 빼고 쓰기」가 아니라 「쓰지 않기」인가 (Grok claim-review `01a024b5`)

처음 설계는 공개 리포에 `token` 없이 config 를 쓰고 사용자에게 env 로 넣으라고 안내하는
것이었다. **실측이 그것을 막았다** -- 커밋되는 훅 스크립트는 토큰을 config.json 에서만 읽고
**env 폴백이 없다**(`TOKEN=$(python3 -c "... d['token'] ..." "${CONFIG}")`).
토큰을 빼면 훅이 설치된 것처럼 보이고 첫 실행에서 조용히 죽는다.

env 폴백을 추가하는 안도 있었으나, 그 스크립트는 **사용자 리포에 커밋되는 분산 계약**이라
이미 옛 스크립트를 가진 클론은 고쳐지지 않는다. 쓰는 쪽에서 막는 것이 완결된 차단이다.

## 이 파일이 강제하는 것

1. 공개 리포 → Contents API 쓰기 **0회**, `False` 반환.
2. 비공개 리포 → 종전대로 쓴다(기능 보존).
3. visibility 조회 실패 → **fail-closed**, 쓰기 0회.
4. 어떤 경우에도 `install-hook.sh` 는 토큰을 담지 않는다(대조군).
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from src.github_client import repos as repos_mod  # noqa: E402


def _client(*, private: bool | None, get_raises: Exception | None = None):
    """GitHub API 더블.

    🔴 `.get` 은 **URL 로 두 경로를 구별**한다 — visibility 조회(`/repos/{full}`)와
    커밋 루프의 기존-파일 sha 조회(`/repos/{full}/contents/...`) 가 **같은 `.get`** 이다.
    통째로 raise 시키면 예외가 sha 조회에서 터져 PUT 이 안 나가고, 테스트가
    **틀린 이유로 통과**한다(실측: 뮤테이션 `fail_open`·`swallow_lookup` 이 생존했다).
    """
    c = MagicMock()

    async def _get(url, **_kw):
        if "/contents/" in url:                      # 커밋 루프의 sha 조회 — 항상 정상
            r = MagicMock(status_code=404)
            r.json = MagicMock(return_value={})
            r.raise_for_status = MagicMock()
            return r
        if get_raises is not None:                   # visibility 조회만 실패시킨다
            raise get_raises
        r = MagicMock(status_code=200)
        r.json = MagicMock(return_value={} if private is None else {"private": private})
        r.raise_for_status = MagicMock()
        return r

    c.get = AsyncMock(side_effect=_get)
    put_resp = MagicMock(status_code=201)
    put_resp.raise_for_status = MagicMock()
    c.put = AsyncMock(return_value=put_resp)
    return c


async def _run(client):
    with patch.object(repos_mod, "get_http_client", return_value=client):
        return await repos_mod.commit_scamanager_files(
            "ghp_user", "owner/repo", "https://sca.example", "SECRET_HOOK_TOKEN",
        )


def _put_bodies(client):
    """PUT 으로 나간 본문 전량 (base64 디코드 전 원문 포함)."""
    return " ".join(str(call) for call in client.put.call_args_list)


class TestPublicRepoNeverReceivesTheToken:
    """공개 리포에 토큰이 나가지 않는가."""

    async def test_public_repo_writes_nothing(self):
        """🔴 핵심 — 공개면 Contents PUT 이 **0회** 여야 한다."""
        c = _client(private=False)

        ok = await _run(c)

        assert ok is False, "공개 리포인데 성공을 반환했다 — 호출부가 설치됐다고 믿는다"
        assert c.put.await_count == 0, (
            f"공개 리포에 {c.put.await_count}회 커밋했다 — hook_token 이 공개된다"
        )

    async def test_public_repo_token_never_appears_in_any_request(self):
        """대조군 — PUT 이 0회여도 토큰이 다른 요청에 실리지 않았는지 본다."""
        c = _client(private=False)

        await _run(c)

        assert "SECRET_HOOK_TOKEN" not in _put_bodies(c)


class TestPrivateRepoStillWorks:
    """비공개 리포의 기존 동작을 깨지 않는다."""

    async def test_private_repo_still_commits(self):
        c = _client(private=True)

        ok = await _run(c)

        assert ok is True, "비공개 리포인데 쓰지 않았다 — 기능이 죽었다"
        assert c.put.await_count >= 1, "비공개인데 커밋이 0회다"

    async def test_private_repo_config_carries_the_token(self):
        """🔴 대조군 — 이 축이 없으면 「아무것도 안 쓰는」 구현이 위 전부를 통과한다."""
        c = _client(private=True)

        await _run(c)

        import base64  # pylint: disable=import-outside-toplevel
        blob = _put_bodies(c)
        decoded = ""
        for token in blob.replace("'", " ").replace('"', " ").split():
            try:
                decoded += base64.b64decode(token).decode("utf-8", "replace")
            except (ValueError, UnicodeDecodeError):
                continue
        assert "SECRET_HOOK_TOKEN" in decoded, (
            "비공개 리포 config.json 에 토큰이 없다 — 훅이 인증하지 못한다"
        )


class TestVisibilityLookupFailsClosed:
    """조회에 실패하면 **쓰지 않는다** — 모르면 안 쓴다."""

    @pytest.mark.parametrize("exc", [
        httpx.HTTPError("boom"),
        httpx.TimeoutException("slow"),
    ])
    async def test_lookup_failure_writes_nothing(self, exc):
        """🔴 fail-open 이면 GitHub 이 흔들릴 때마다 토큰이 나간다."""
        c = _client(private=None, get_raises=exc)

        ok = await _run(c)

        assert ok is False
        assert c.put.await_count == 0, "visibility 를 모르는데 커밋했다"

    async def test_missing_private_field_is_treated_as_public(self):
        """🔴 응답에 `private` 가 없으면 **공개로 간주**한다 — 모호할 때 안전한 쪽."""
        c = _client(private=None)                       # private 키 없음

        ok = await _run(c)

        assert ok is False
        assert c.put.await_count == 0


def test_install_script_never_embeds_the_token():
    """대조군 — 토큰이 들어가는 커밋 산출물은 `config.json` 하나뿐이다 (Grok K4)."""
    script = repos_mod._INSTALL_HOOK_SH  # pylint: disable=protected-access

    assert "hook_token" not in script
    assert "{token}" not in script
    assert "d['token']" in script, "스크립트가 config.json 에서 토큰을 읽는 계약이 바뀌었다"


# ── 호출부: 거부를 성공으로 표시하지 않는다 (Grok `01a024b5` K2) ────────────


def test_add_repo_only_claims_installed_when_the_commit_succeeded():
    """🔴 구판은 반환값을 **무시**하고 항상 `?hook_installed=1` 로 보냈다.

    공개 리포는 이제 의도적으로 거부되므로, 그 거부가 성공으로 보이면 사용자는
    훅이 도는 줄 알고 기다린다 — 조용한 거짓이다.
    """
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    src = Path(__file__).resolve().parents[3] / "src" / "ui" / "routes" / "add_repo.py"
    text = src.read_text(encoding="utf-8")

    assert "hook_committed = await commit_scamanager_files(" in text, (
        "add_repo 가 커밋 결과를 받지 않는다 — 거부를 성공으로 표시한다"
    )
    assert '"?hook_installed=1" if hook_committed else ""' in text, (
        "설치 배너가 커밋 성공 여부와 무관하게 붙는다"
    )
