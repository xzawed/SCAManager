"""Discord notifier — sends analysis results as embed messages via webhook."""
import logging

from src.notifier._http import build_safe_client, validate_external_url
from src.constants import GRADE_EMOJI, GRADE_COLOR_DISCORD
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult

logger = logging.getLogger(__name__)
_EMBED_DESC_MAX = 4096


def _build_embed(
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> dict:
    grade_emoji = GRADE_EMOJI.get(score_result.grade, "⚪")
    ref = f"PR #{pr_number}" if pr_number else f"커밋 {commit_sha[:7]}"
    bd = score_result.breakdown

    lines = [
        f"{grade_emoji} **총점: {score_result.total}/100** (등급 {score_result.grade}) — {ref}",
    ]

    if ai_review and ai_review.summary:
        lines.append(f"\n**AI 요약:** {ai_review.summary}")

    all_issues = [i for r in analysis_results for i in r.issues]
    if all_issues:
        lines.append(f"\n**정적 분석 이슈:** {len(all_issues)}건")
        for issue in all_issues[:5]:
            lines.append(f"- [{issue.tool}] {issue.message[:80]}")

    desc = "\n".join(lines)
    if len(desc) > _EMBED_DESC_MAX:
        desc = desc[:_EMBED_DESC_MAX - 3] + "..."

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
