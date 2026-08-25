"""Shared helpers for GitHub API client modules."""
import re
from urllib.parse import quote, unquote

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
    """owner/repo 를 URL 안전하게 인코딩 (슬래시는 유지) — github_client URL 빌드 단일 출처.
    URL-encode owner/repo defensively while preserving the path slash — single source for
    github_client URL builds.

    🔴 **인코딩만으로는 path injection 이 안 막힌다** — 예전 docstring 이 막는다고
    적었지만 거짓이었다(실측). `quote(..., safe="/")` 는 슬래시를 남기고 `.` 은 애초에
    unreserved 라 인코딩되지 않는다. 즉 `../` 가 그대로 통과하고, httpx 가 RFC 3986 대로
    dot-segment 를 **정규화**해 다른 엔드포인트로 요청이 나간다:

        "../../../user/repos"  ->  GET /user/repos/hooks
        "o/r/../../admin"      ->  GET /repos/admin/hooks

    호스트는 항상 `api.github.com` 이라 호스트 탈출은 못 하지만, 그 요청에는
    `Authorization: Bearer <토큰>` 이 실린다 — `/user/repos` 는 그 토큰으로 접근 가능한
    **모든 저장소 목록**이다. CodeQL `py/partial-ssrf`(PR #1514 alert #598)가 옳았다.

    🔴 그래서 **세그먼트를 검사한다.** 정상 저장소 이름은 `.` 으로 시작할 수 있고
    (`owner/.github`) 점을 포함할 수 있으므로(`owner/repo.js`), 막는 것은 **`.`/`..`
    세그먼트 자체**와 그 인코딩 형태뿐이다.

    Encoding alone does not block path injection: `.` is unreserved and `/` is kept, so `../`
    survives and httpx normalizes it into a different endpoint reached with our token.
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
    # 이미 인코딩된 형태(%2e)도 디코드해서 본다 — 서버가 디코드하면 같은 결과다.
    # Decode first: a pre-encoded %2e would otherwise slip through.
    decoded = unquote(full_name)
    for segment in decoded.split("/"):
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
