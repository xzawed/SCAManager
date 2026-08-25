"""`repo_path` 가 path traversal 을 막지 못한다 — docstring 이 거짓이다.

🔴 실측. `src/github_client/helpers.py::repo_path` docstring:

    「GitHub 저장소 이름은 신뢰 입력이지만 **방어적 인코딩으로 path injection 을 차단**한다.」

구현은 `quote(full_name, safe="/")` 다. `safe="/"` 가 슬래시를 남기고, `.` 은 애초에
`quote` 의 unreserved 문자라 인코딩되지 않는다. 즉 **`../` 가 그대로 통과한다.**

그리고 httpx 는 RFC 3986 대로 dot-segment 를 **정규화한다**(실측):

| 입력 | 조립된 URL | 실제 요청 경로 |
|---|---|---|
| `../../../user/repos` | `.../repos/../../../user/repos/hooks` | **`/user/repos/hooks`** |
| `o/r/../../admin` | `.../repos/o/r/../../admin/hooks` | **`/repos/admin/hooks`** |

호스트는 항상 `api.github.com` 이라 **호스트 탈출은 불가능**하다. 그러나 **다른
엔드포인트**에 우리 `Authorization: Bearer <토큰>` 이 실려 나간다 — 예를 들어
`/user/repos` 는 그 토큰으로 접근 가능한 **모든 저장소 목록**이다.

🔴 `repo_path` 는 `github_client` URL 빌드의 **단일 출처**이고 이 파일 안에서만
5곳이 쓴다(`create_webhook` · `list_webhooks` · `delete_webhook` ·
`update_webhook_events` · contents API). 한 곳을 고치면 전부 고쳐진다.

발견 경위: PR #1514 의 CodeQL `py/partial-ssrf`(alert #598). 처음엔 「기존 패턴이
새 alert 로 잡힌 것」이라 여겼으나, 재보니 **지적이 옳았다.**

`quote(..., safe="/")` leaves both `/` and `.`, so `../` survives; httpx then normalizes
the dot-segments and the request reaches a different GitHub API endpoint with our token.
"""
from __future__ import annotations

import httpx
import pytest

from src.constants import GITHUB_API
from src.github_client.helpers import repo_path


def _final_path(full_name: str) -> str:
    """호출부와 같은 방식으로 URL 을 조립했을 때 **실제로 요청되는 경로**."""
    url = f"{GITHUB_API}/repos/{repo_path(full_name)}/hooks"
    return httpx.Request("GET", url).url.path


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_httpx_really_normalizes_dot_segments():
    """🔴 전제 확인 — httpx 가 `..` 를 정규화하지 않는다면 이 파일 전체가 공허하다."""
    normalized = httpx.Request(
        "GET", "https://api.github.com/repos/../../../user/repos/hooks"
    ).url.path
    assert normalized == "/user/repos/hooks", (
        f"httpx 가 dot-segment 를 정규화하지 않는다 — 전제가 바뀌었다: {normalized}"
    )


def test_normal_repo_names_still_work():
    """대조군 — 정상 이름은 그대로 통과한다 (수정이 과잉이 되지 않는다)."""
    assert _final_path("owner/repo") == "/repos/owner/repo/hooks"
    # 점이 들어간 정상 이름 — `..` 세그먼트가 아니면 막지 않는다
    assert _final_path("owner/repo.js") == "/repos/owner/repo.js/hooks"
    assert _final_path("owner/.github") == "/repos/owner/.github/hooks"


# ─── 결함 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("attack,reached", [
    ("../../../user/repos", "/user/repos/hooks"),
    ("o/r/../../admin", "/repos/admin/hooks"),
    ("o/../../../user/repos", "/user/repos/hooks"),
])
def test_traversal_is_rejected(attack, reached):
    """🔴 `../` 로 다른 엔드포인트에 도달하지 못한다.

    막지 않으면 그 요청에 `Authorization: Bearer <토큰>` 이 실려
    `{reached}` 같은 **다른 API** 로 나간다.
    """
    with pytest.raises(ValueError, match="path"):
        repo_path(attack)


def test_single_dot_segment_is_also_rejected():
    """`.` 세그먼트도 막는다 — 정규화 대상이고 정상 저장소 이름이 아니다."""
    with pytest.raises(ValueError, match="path"):
        repo_path("owner/./repo")


def test_encoded_traversal_is_rejected_too():
    """🔴 인코딩된 형태(`%2e%2e`)도 막는다 — 서버가 디코드하면 같은 결과다.

    `quote` 는 이미 인코딩된 문자열을 다시 인코딩하지 않으므로(`%` 는 남는다)
    이 형태가 그대로 흘러갈 수 있다.
    """
    for encoded in ("owner/%2e%2e/admin", "owner/%2E%2E/admin"):
        with pytest.raises(ValueError, match="path"):
            repo_path(encoded)


# ─── 화이트리스트 검증 ───────────────────────────────────────────────────────
#
# 🔴 `..` 세그먼트만 막는 것은 **블랙리스트**다. 실측으로 확인한 CodeQL
# `py/partial-ssrf` 는 이 형태를 sanitizer 로 인정하지 않는다 — 인정하는 것은
# `re.match`/`re.fullmatch` 가드와 `str.isalnum()` 계열뿐이다
# (`ServerSideRequestForgeryCustomizations.qll::stringRestriction`, 실측).
#
# 게이트를 통과시키려고 넣는 것이 아니라, 화이트리스트가 실제로 더 강하기
# 때문에 넣는다 — 블랙리스트는 다음 우회 문자를 매번 쫓아가야 한다.
#
# Whitelist validation: GitHub owner/repo names are `[A-Za-z0-9._-]+`.


@pytest.mark.parametrize("bad", [
    "owner/re po",          # 공백
    "owner/repo?x=1",       # 쿼리 문자 — URL 구조를 바꾼다
    "owner/repo#frag",      # fragment
    "owner/repo/extra",     # 슬래시 2개 — owner/repo 형태가 아니다
    "owner",                # 슬래시 없음
    "owner/re%2Fpo",        # 인코딩된 슬래시
    "owner/repo@host",      # authority 처럼 보이는 문자
    "",                     # 빈 문자열
])
def test_names_outside_the_whitelist_are_rejected(bad):
    """🔴 `owner/repo` 화이트리스트 밖의 이름은 전부 거부한다."""
    with pytest.raises(ValueError):
        repo_path(bad)


def test_whitelist_uses_a_modeled_guard():
    """🔴 검증이 `re.fullmatch` 가드로 이뤄진다 — 정적 분석이 읽는 형태다.

    이 단언은 「어떤 API 로 검증하는가」를 고정한다. `..` in-check 로 되돌리면
    동작은 같아 보여도 CodeQL 이 taint 를 못 끊어 alert 이 되살아난다(실측).
    """
    import re as _re

    from src.github_client import helpers

    pattern = getattr(helpers, "REPO_FULL_NAME_RE", None)
    assert isinstance(pattern, _re.Pattern), (
        "helpers.REPO_FULL_NAME_RE 가 컴파일된 정규식이 아니다 — "
        f"{pattern!r}. re.fullmatch 가드가 없으면 CodeQL barrier 가 성립하지 않는다."
    )
    assert pattern.fullmatch("owner/repo"), f"정상 이름을 거부한다: {pattern.pattern}"
    assert not pattern.fullmatch("owner/repo/extra"), "슬래시 2개를 통과시킨다"
