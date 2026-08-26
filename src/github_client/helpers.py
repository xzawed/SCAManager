"""Shared helpers for GitHub API client modules."""
import re
from urllib.parse import quote

# GitHub 소유자·저장소 이름에 허용되는 문자 — 화이트리스트.
# 슬래시는 정확히 하나이고, `%`·공백·`?`·`#`·`@` 는 들어올 수 없다.
#
# 🔴 수량자는 **바운드여야 한다**(`+` 금지). 무한 `+` 두 개는 CodeQL
# `py/polynomial-redos` 이고, 실측으로도 비앵커 형태에서 n² 이다
# (20k 자 입력 572.8 ms vs 바운드 5.7 ms). 상한은 GitHub 실제 한계다:
# 소유자 39자 · 저장소 100자.
#
# GitHub owner/repo charset; exactly one slash, no URL-structural characters,
# and bounded quantifiers (unbounded `+` is polynomial — measured).
REPO_FULL_NAME_RE = re.compile(r"[A-Za-z0-9._-]{1,39}/[A-Za-z0-9._-]{1,100}")


def repo_path(full_name: str) -> str:
    """owner/repo 를 **검증**한다 — github_client URL 빌드 단일 출처.
    Validate owner/repo before it is interpolated into an API URL — single source for
    github_client URL builds.

    🔴 **인코딩은 방어가 아니다.** 예전 docstring 은 「방어적 인코딩으로 path injection
    을 차단한다」고 적었지만 거짓이었다(실측). `quote(..., safe="/")` 는 슬래시를 남기고
    `.` 은 애초에 unreserved 라 인코딩되지 않는다. `../` 가 그대로 통과했고, httpx 가
    RFC 3986 대로 dot-segment 를 **정규화**해 다른 엔드포인트로 요청이 나갔다:

        "../../../user/repos"  ->  GET /user/repos/hooks
        "owner/.."             ->  GET /repos/hooks

    호스트는 항상 `api.github.com` 이라 호스트 탈출은 못 하지만, 그 요청에는
    `Authorization: Bearer <토큰>` 이 실린다 — `/user/repos` 는 그 토큰으로 접근 가능한
    **모든 저장소 목록**이다. CodeQL `py/partial-ssrf`(alert #598)가 옳았다.

    그래서 방어는 **두 검사**다: ① owner/repo 화이트리스트, ② `.`/`..` 세그먼트.
    ② 는 ① 을 통과하는 `owner/..` 를 잡으므로 둘 다 필요하다.

    마지막 `quote(..., safe="/")` 는 **통과 입력에 대해 항등**이다 — ① 이 허용하는
    문자 65개가 전부 unreserved 다(실측). 방어가 아니라 경계에서의 관용구로 남긴다.

    Encoding is not the defence; the two checks are. The trailing quote() is identity for
    every input that gets past check ①.
    """
    # ① 화이트리스트 — 허용 문자 밖은 전부 거부한다.
    # `re.fullmatch` 가드여야 한다: 정적 분석이 barrier 로 읽는 형태가 이것뿐이다(실측).
    # Whitelist first; must be a `re.fullmatch` guard so analyzers treat it as a barrier.
    if not REPO_FULL_NAME_RE.fullmatch(full_name):
        raise ValueError(
            "repo path charset - "
            f"저장소 이름이 owner/repo 형식이 아니다: {full_name!r}"
        )

    # ② `.`/`..` 세그먼트 — 화이트리스트를 통과해도 `owner/..` 는 여전히 가능하다.
    #
    # 원문을 그대로 쪼갠다. 퍼센트 디코드는 하지 않는다 — ① 이 `%` 를 이미 거부했고
    # (허용 문자 65개에 없다), `unquote` 는 `'%' not in string` 이면 그대로 반환하므로
    # 여기서 부르면 **항상 항등**이었다(실측: 지워도 죽는 테스트 0건).
    # 그 불변식은 `test_percent_cannot_pass_the_whitelist` 가 잡는다 — 문자 집합을
    # 넓히면 거기가 먼저 red 가 되고, 그때 디코드를 되살려야 한다.
    #
    # No percent-decoding: guard ① already rejects '%', so unquote() was always identity.
    for segment in full_name.split("/"):
        if segment in (".", ".."):
            raise ValueError(
                "repo path segment traversal - "
                f"저장소 이름에 경로 이동 세그먼트가 있다: {segment!r}"
            )
    return quote(full_name, safe="/")


def github_api_headers(token: str) -> dict:
    """Return standard GitHub REST API authentication headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
