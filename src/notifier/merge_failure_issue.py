"""Auto-merge 실패 시 GitHub Issue 자동 생성 — Phase F.3.

Phase 3 PR-11 (사이클 84) — i18n: language 인자 + 3-layer fallback. Title prefix 영문 고정.
Phase 3 PR-11 (Cycle 84) — i18n: language arg + 3-layer fallback. Title prefix English-fixed.
"""
import logging
import httpx
from src.constants import GITHUB_API
from src.github_client.helpers import github_api_headers
from src.i18n.loader import get_text
from src.shared.http_client import get_http_client

logger = logging.getLogger(__name__)

ISSUE_LABELS = ["scamanager", "auto-merge-failure"]


def _build_issue_body(
    *,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,
    advice: str,
    language: str = "en",
) -> str:
    """Auto-merge 실패 Issue 본문을 조립한다 (Phase 3 PR-11 — i18n).

    Build auto-merge failure Issue body (Phase 3 PR-11 — i18n).
    """
    marker = f"<!-- scamanager-auto-merge-pr:{pr_number} -->"
    pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
    return "\n".join([
        marker,
        "",
        get_text("notifier.merge_failure_issue.header", language),
        "",
        get_text("notifier.merge_failure_issue.repo_label", language, repo=repo_name),
        get_text(
            "notifier.merge_failure_issue.pr_label", language,
            pr_number=pr_number, url=pr_url,
        ),
        get_text(
            "notifier.merge_failure_issue.score_label", language,
            score=score, threshold=threshold,
        ),
        get_text("notifier.merge_failure_issue.reason_label", language, reason=reason),
        "",
        get_text("notifier.merge_failure_issue.advice_header", language),
        "",
        advice,
        "",
        "---",
        get_text("notifier.merge_failure_issue.footer", language),
    ])


async def create_merge_failure_issue(  # pylint: disable=too-many-locals
    *,
    github_token: str,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,
    advice: str,
    language: str = "en",
) -> int | None:
    """24h 내 중복 체크 후 Issue 생성. 이미 존재하면 None, 생성 성공 시 Issue number.

    Phase 3 PR-11 (사이클 84) — i18n: title prefix 영문 고정 (검색 호환), body 다국어.
    Phase 3 PR-11 (Cycle 84) — i18n: title prefix English-fixed (search compat), body multilingual.
    """
    dedup_marker = f"scamanager-auto-merge-pr:{pr_number}"
    # Title prefix = 영문 고정 (검색 호환). i18n key 자체가 영문 고정 — 모든 locale 동일 출력.
    # Title prefix = English-fixed (search compat). i18n key is English-fixed across all locales.
    reason_short = reason.split(":")[0].strip()
    title = get_text(
        "notifier.merge_failure_issue.title_prefix", language,
        pr_number=pr_number, reason_short=reason_short,
    )
    body = _build_issue_body(
        repo_name=repo_name,
        pr_number=pr_number,
        score=score,
        threshold=threshold,
        reason=reason,
        advice=advice,
        language=language,
    )
    headers = github_api_headers(github_token)

    try:
        client = get_http_client()
        search_resp = await client.get(
            f"{GITHUB_API}/search/issues",
            params={
                "q": (
                    f'repo:{repo_name} "{dedup_marker}" in:body '
                    f"label:auto-merge-failure is:open"
                )
            },
            headers=headers,
        )
        search_resp.raise_for_status()
        if search_resp.json().get("total_count", 0) > 0:
            logger.info("Auto-merge failure Issue 이미 존재 (pr=%d)", pr_number)
            return None

        create_resp = await client.post(
            f"{GITHUB_API}/repos/{repo_name}/issues",
            json={"title": title, "body": body, "labels": ISSUE_LABELS},
            headers=headers,
        )
        create_resp.raise_for_status()
        number = create_resp.json().get("number")
        logger.info("Auto-merge failure Issue 생성 완료 #%s (pr=%d)", number, pr_number)
        return number
    except httpx.HTTPError:
        # Phase H PR-6A: logger.exception 으로 stack trace 보존
        logger.exception(
            "create_merge_failure_issue 실패 (%s, pr=%d)", repo_name, pr_number,
        )
        return None
