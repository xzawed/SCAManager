"""GitHub Issue 자동 생성 — 낮은 점수/보안 HIGH 커밋에 대한 알림.

Phase 3 PR-11 (사이클 84) — i18n: language 인자 + 3-layer fallback. Title prefix 영문 고정 (검색 호환).
Phase 3 PR-11 (Cycle 84) — i18n: language arg + 3-layer fallback. Title prefix English-fixed (search-compat).
"""
import logging

import httpx

from src.config import settings
from src.constants import GITHUB_API
from src.github_client.helpers import github_api_headers
from src.i18n.loader import get_text
from src.shared.http_client import get_http_client
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger(__name__)

# 봇 PR 헤드 ref 패턴 — Issue 생성 시 해당 PR은 제외한다
# Bot PR head ref prefixes — skip Issue creation for these automation PRs
_BOT_PR_PREFIXES: tuple[str, ...] = ("claude-fix/", "bot/", "renovate/", "dependabot/")


def _bandit_high_issues(result: dict) -> list[dict]:
    """result["issues"]에서 bandit HIGH severity 이슈만 추출한다."""
    issues = result.get("issues") or []
    return [i for i in issues if i.get("tool") == "bandit" and i.get("severity") == "HIGH"]


def _build_issue_body(  # pylint: disable=too-many-locals,too-many-positional-arguments
    repo_name: str,
    commit_sha: str,
    analysis_id: int,
    result: dict,
    high_issues: list[dict],
    language: str = "en",
) -> str:
    """Issue body — AI 요약, 보안 HIGH 이슈, 분석 상세 링크 (Phase 3 PR-11 — i18n)."""
    score = result.get("score", 0)
    grade = result.get("grade", "F")
    base_url = (settings.app_base_url or "").rstrip("/")
    link_path = f"/repos/{repo_name}/analyses/{analysis_id}"
    full_link = f"{base_url}{link_path}" if base_url else link_path

    lines = [
        get_text("notifier.github_issue.header", language, sha=commit_sha[:7]),
        "",
        get_text("notifier.github_issue.score_line", language, score=score, grade=grade),
        get_text("notifier.github_issue.detail_line", language, link=full_link),
    ]

    summary = result.get("ai_summary")
    if summary:
        lines += [
            "",
            get_text("notifier.github_issue.summary_header", language),
            summary,
        ]

    if high_issues:
        lines += [
            "",
            get_text("notifier.github_issue.security_header", language),
        ]
        for issue in high_issues[:10]:
            lines.append(get_text(
                "notifier.github_issue.security_item", language,
                message=issue.get("message", ""), line=issue.get("line", "?"),
            ))

    suggestions = result.get("ai_suggestions") or []
    if suggestions:
        lines += [
            "",
            get_text("notifier.github_issue.suggestions_header", language),
        ]
        for s in suggestions[:5]:
            lines.append(f"- {s}")

    return "\n".join(lines)


async def create_low_score_issue(
    *,
    github_token: str,
    repo_name: str,
    commit_sha: str,
    analysis_id: int,
    result: dict,
    language: str = "en",
) -> int | None:
    """낮은 점수 또는 보안 HIGH 커밋에 대한 GitHub Issue를 생성한다 (Phase 3 PR-11 — i18n).

    Title prefix 영문 고정 — 운영자 검색 호환성 보장 (`[SCAManager] Low score commit: ...`).
    Body 는 다국어 적용 — 사용자 가시 텍스트.

    Returns:
        생성된 Issue 번호, 실패 시 None.
    """
    score = result.get("score", 0)
    high_issues = _bandit_high_issues(result)
    labels = ["scamanager", "code-quality"]
    if high_issues:
        labels.append("security")

    # Title prefix = 영문 고정 (검색 호환). i18n key 의 본문도 영문 고정.
    # Title prefix = English-fixed (search compat). i18n key body is also English-fixed.
    title = get_text(
        "notifier.github_issue.title_prefix_low_score", language,
        sha=commit_sha[:7], score=score,
    )
    body = _build_issue_body(
        repo_name, commit_sha, analysis_id, result, high_issues, language=language,
    )

    try:
        client = get_http_client()
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo_name}/issues",
            json={"title": title, "body": body, "labels": labels},
            headers=github_api_headers(github_token),
        )
        resp.raise_for_status()
        return resp.json().get("number")
    except httpx.HTTPError as exc:
        logger.warning(
            "create_low_score_issue 실패 (%s@%s): %s",
            sanitize_for_log(repo_name), sanitize_for_log(commit_sha), exc,
        )
        return None


# ---------------------------------------------------------------------------
# Notifier Protocol 구현체 (Phase S.3-E) — pipeline.py 에서 이관
# ---------------------------------------------------------------------------
from src.notifier.registry import NotifyContext, register  # noqa: E402  pylint: disable=wrong-import-position


class _IssueNotifier:
    """GitHub Issue 자동 생성 채널 — 저점 OR bandit HIGH 시 활성. bot PR 제외."""

    name = "create_issue"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        """채널 활성화 여부를 반환한다."""
        if not (ctx.config and ctx.config.create_issue and ctx.result_dict):
            return False
        # 봇 PR 제외 — claude-fix/ 및 기타 자동화 PR 헤드 ref 패턴
        # Exclude bot PRs — claude-fix/ and other automation PR head ref patterns
        is_bot_pr = ctx.pr_head_ref and any(
            ctx.pr_head_ref.startswith(prefix) for prefix in _BOT_PR_PREFIXES
        )
        if is_bot_pr:
            return False
        has_bandit_high = any(
            i.get("severity") == "HIGH" and i.get("tool") == "bandit"
            for i in (ctx.result_dict.get("issues") or [])
        )
        return ctx.score_result.total < ctx.config.reject_threshold or has_bandit_high

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다 (Phase 3 PR-11 — 3-layer fallback)."""
        from src.database import SessionLocal  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        from src.notifier._language import resolve_notification_language  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        with SessionLocal() as db:
            language = resolve_notification_language(db, config=ctx.config)
        await create_low_score_issue(
            github_token=ctx.owner_token,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            analysis_id=ctx.analysis_id,
            result=ctx.result_dict,
            language=language,
        )


register(_IssueNotifier())
