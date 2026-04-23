"""Slack notifier — sends analysis results as attachment messages via incoming webhook."""
import logging

from src.notifier._http import build_safe_client, validate_external_url
from src.constants import GRADE_COLOR_HTML, NOTIFIER_MAX_ISSUES_SHORT
from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult
from src.notifier._common import format_ref, get_all_issues, truncate_issue_msg

logger = logging.getLogger(__name__)

# Slack attachment color = hex string (GRADE_COLOR_HTML 재사용)
# Slack emoji는 Slack 고유 텍스트 형식(:large_green_circle:)이라 별도 정의
_SLACK_GRADE_EMOJI = {
    "A": ":large_green_circle:", "B": ":large_blue_circle:",
    "C": ":large_yellow_circle:", "D": ":large_orange_circle:",
    "F": ":red_circle:",
}


def _build_payload(  # pylint: disable=too-many-positional-arguments,too-many-locals
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> dict:
    grade_emoji = _SLACK_GRADE_EMOJI.get(score_result.grade, ":white_circle:")
    ref = format_ref(commit_sha, pr_number)
    bd = score_result.breakdown

    text = f"{grade_emoji} *SCA 분석 — {repo_name}* ({ref})"
    fallback = f"SCA: {repo_name} — {score_result.total}/100 ({score_result.grade})"
    pretext = f"*총점: {score_result.total}/100* (등급 {score_result.grade})"

    blocks = []
    if ai_review and ai_review.summary:
        blocks.append(ai_review.summary)

    all_issues = get_all_issues(analysis_results)
    if all_issues:
        blocks.append(f"*정적 분석 이슈:* {len(all_issues)}건")
        for issue in all_issues[:NOTIFIER_MAX_ISSUES_SHORT]:
            blocks.append(f"• [{issue.tool}] {truncate_issue_msg(issue.message)}")

    footer_text = "\n".join(blocks) if blocks else ""

    fields = [
        {"title": "코드 품질", "value": f"{bd.get('code_quality', '-')}/25", "short": True},
        {"title": "보안", "value": f"{bd.get('security', '-')}/20", "short": True},
        {"title": "커밋 메시지", "value": f"{bd.get('commit_message', '-')}/15", "short": True},
        {"title": "구현 방향성", "value": f"{bd.get('ai_review', '-')}/25", "short": True},
        {"title": "테스트", "value": f"{bd.get('test_coverage', '-')}/15", "short": True},
    ]

    attachment = {
        "fallback": fallback,
        "color": GRADE_COLOR_HTML.get(score_result.grade, "#6366f1"),
        "pretext": pretext,
        "fields": fields,
    }
    if footer_text:
        attachment["text"] = footer_text

    return {"text": text, "attachments": [attachment]}


async def send_slack_notification(
    *,
    webhook_url: str | None,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
) -> None:
    """Slack Incoming Webhook으로 분석 결과 메시지를 전송한다."""
    if not webhook_url:
        return
    if not validate_external_url(webhook_url):
        logger.warning("send_slack_notification: blocked unsafe URL '%s'", webhook_url)
        return
    payload = _build_payload(repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review)
    async with build_safe_client() as client:
        r = await client.post(webhook_url, json=payload)
        r.raise_for_status()


# ---------------------------------------------------------------------------
# Notifier Protocol 구현체 (Phase S.3-E) — pipeline.py 에서 이관
# ---------------------------------------------------------------------------
from src.notifier.registry import NotifyContext, register  # noqa: E402  pylint: disable=wrong-import-position


class _SlackNotifier:
    """Slack webhook 알림 채널 — slack_webhook_url 설정 시 활성."""

    name = "slack"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        """채널 활성화 여부를 반환한다."""
        return bool(ctx.config and ctx.config.slack_webhook_url)

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다."""
        await send_slack_notification(
            webhook_url=ctx.config.slack_webhook_url,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
        )


register(_SlackNotifier())
