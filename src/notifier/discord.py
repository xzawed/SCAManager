"""Discord notifier — sends analysis results as embed messages via webhook."""
import logging

from src.notifier._http import build_safe_client, validate_external_url
from src.constants import (
    GRADE_EMOJI, GRADE_COLOR_DISCORD,
    DISCORD_EMBED_DESC_MAX_LENGTH, NOTIFIER_MAX_ISSUES_SHORT,
)
from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult
from src.notifier._common import format_ref, get_all_issues, truncate_message, truncate_issue_msg

logger = logging.getLogger(__name__)


def _build_embed(  # pylint: disable=too-many-positional-arguments
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> dict:
    grade_emoji = GRADE_EMOJI.get(score_result.grade, "⚪")
    ref = format_ref(commit_sha, pr_number)
    bd = score_result.breakdown

    lines = [
        f"{grade_emoji} **총점: {score_result.total}/100** (등급 {score_result.grade}) — {ref}",
    ]

    if ai_review and ai_review.summary:
        lines.append(f"\n**AI 요약:** {ai_review.summary}")

    all_issues = get_all_issues(analysis_results)
    if all_issues:
        lines.append(f"\n**정적 분석 이슈:** {len(all_issues)}건")
        for issue in all_issues[:NOTIFIER_MAX_ISSUES_SHORT]:
            lines.append(f"- [{issue.tool}] {truncate_issue_msg(issue.message)}")

    desc = truncate_message("\n".join(lines), DISCORD_EMBED_DESC_MAX_LENGTH)

    fields = [
        {"name": "코드 품질", "value": f"{bd.get('code_quality', '-')}/25", "inline": True},
        {"name": "보안", "value": f"{bd.get('security', '-')}/20", "inline": True},
        {"name": "커밋 메시지", "value": f"{bd.get('commit_message', '-')}/15", "inline": True},
        {"name": "구현 방향성", "value": f"{bd.get('ai_review', '-')}/25", "inline": True},
        {"name": "테스트", "value": f"{bd.get('test_coverage', '-')}/15", "inline": True},
    ]

    return {
        "title": f"📊 SCA 분석 — {repo_name}",
        "description": desc,
        "color": GRADE_COLOR_DISCORD.get(score_result.grade, 0x6366F1),
        "fields": fields,
    }


async def send_discord_notification(
    *,
    webhook_url: str | None,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
) -> None:
    """Discord Embed 메시지를 Webhook URL로 전송한다."""
    if not webhook_url:
        return
    if not validate_external_url(webhook_url):
        logger.warning("send_discord_notification: blocked unsafe URL '%s'", webhook_url)
        return
    embed = _build_embed(repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review)
    async with build_safe_client() as client:
        r = await client.post(webhook_url, json={"embeds": [embed]})
        r.raise_for_status()


# ---------------------------------------------------------------------------
# Notifier Protocol 구현체 (Phase S.3-E) — pipeline.py 에서 이관
# ---------------------------------------------------------------------------
from src.notifier.registry import NotifyContext, register  # noqa: E402  pylint: disable=wrong-import-position


class _DiscordNotifier:
    """Discord webhook 알림 채널 — discord_webhook_url 설정 시 활성."""

    name = "discord"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        """채널 활성화 여부를 반환한다."""
        return bool(ctx.config and ctx.config.discord_webhook_url)

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다."""
        await send_discord_notification(
            webhook_url=ctx.config.discord_webhook_url,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
        )


register(_DiscordNotifier())
