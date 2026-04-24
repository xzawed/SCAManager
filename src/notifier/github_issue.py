"""GitHub Issue 자동 생성 — 낮은 점수/보안 HIGH 커밋에 대한 알림."""
import logging

import httpx

from src.config import settings
from src.constants import GITHUB_API
from src.github_client.helpers import github_api_headers
from src.shared.http_client import get_http_client

logger = logging.getLogger(__name__)


def _bandit_high_issues(result: dict) -> list[dict]:
    """result["issues"]에서 bandit HIGH severity 이슈만 추출한다."""
    issues = result.get("issues") or []
    return [i for i in issues if i.get("tool") == "bandit" and i.get("severity") == "HIGH"]


def _build_issue_body(
    repo_name: str,
    commit_sha: str,
    analysis_id: int,
    result: dict,
    high_issues: list[dict],
) -> str:
    """Issue body — AI 요약, 보안 HIGH 이슈, 분석 상세 링크."""
    score = result.get("score", 0)
    grade = result.get("grade", "F")
    base_url = (settings.app_base_url or "").rstrip("/")
    link_path = f"/repos/{repo_name}/analyses/{analysis_id}"
    full_link = f"{base_url}{link_path}" if base_url else link_path

    lines = [
        f"## SCAManager 분석 결과 — 커밋 `{commit_sha[:7]}`",
        "",
        f"- **점수**: {score}/100 (등급 {grade})",
        f"- **상세 분석**: {full_link}",
    ]

    summary = result.get("ai_summary")
    if summary:
        lines += ["", "### 요약", summary]

    if high_issues:
        lines += ["", "### 보안 이슈 (HIGH)"]
        for issue in high_issues[:10]:
            lines.append(
                f"- {issue.get('message', '')} (line {issue.get('line', '?')})"
            )

    suggestions = result.get("ai_suggestions") or []
    if suggestions:
        lines += ["", "### 개선 제안"]
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
) -> int | None:
    """낮은 점수 또는 보안 HIGH 커밋에 대한 GitHub Issue를 생성한다.

    Returns:
        생성된 Issue 번호, 실패 시 None.
    """
    score = result.get("score", 0)
    high_issues = _bandit_high_issues(result)
    labels = ["scamanager", "code-quality"]
    if high_issues:
        labels.append("security")

    title = f"[SCAManager] 점수 낮은 커밋: {commit_sha[:7]} ({score}점)"
    body = _build_issue_body(repo_name, commit_sha, analysis_id, result, high_issues)

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
        logger.warning("create_low_score_issue 실패 (%s@%s): %s", repo_name, commit_sha, exc)
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
        is_bot_pr = ctx.pr_head_ref and ctx.pr_head_ref.startswith("claude-fix/")
        if is_bot_pr:
            return False
        has_bandit_high = any(
            i.get("severity") == "HIGH" and i.get("tool") == "bandit"
            for i in (ctx.result_dict.get("issues") or [])
        )
        return ctx.score_result.total < ctx.config.reject_threshold or has_bandit_high

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다."""
        await create_low_score_issue(
            github_token=ctx.owner_token,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            analysis_id=ctx.analysis_id,
            result=ctx.result_dict,
        )


register(_IssueNotifier())
