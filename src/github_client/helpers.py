"""Shared helpers for GitHub API client modules."""
from urllib.parse import quote, unquote


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
