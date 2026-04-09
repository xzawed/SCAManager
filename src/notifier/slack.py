"""Slack notifier — sends analysis results as attachment messages via incoming webhook."""
import httpx
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult

GRADE_COLORS = {
    "A": "#10b981",
    "B": "#3b82f6",
    "C": "#f59e0b",
    "D": "#f97316",
    "F": "#ef4444",
}
GRADE_EMOJI = {"A": ":large_green_circle:", "B": ":large_blue_circle:",
               "C": ":large_yellow_circle:", "D": ":large_orange_circle:",
               "F": ":red_circle:"}


def _build_payload(
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> dict:
    grade_emoji = GRADE_EMOJI.get(score_result.grade, ":white_circle:")
    ref = f"PR #{pr_number}" if pr_number else f"커밋 {commit_sha[:7]}"
    bd = score_result.breakdown

    text = f"{grade_emoji} *SCA 분석 — {repo_name}* ({ref})"

    fallback = f"SCA: {repo_name} — {score_result.total}/100 ({score_result.grade})"

    pretext = f"*총점: {score_result.total}/100* (등급 {score_result.grade})"

    blocks = []
    if ai_review and ai_review.summary:
        blocks.append(ai_review.summary)

    all_issues = [i for r in analysis_results for i in r.issues]
    if all_issues:
        blocks.append(f"*정적 분석 이슈:* {len(all_issues)}건")
        for issue in all_issues[:5]:
            blocks.append(f"• [{issue.tool}] {issue.message[:80]}")

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
        "color": GRADE_COLORS.get(score_result.grade, "#6366f1"),
        "pretext": pretext,
        "fields": fields,
    }
    if footer_text:
        attachment["text"] = footer_text

    return {"text": text, "attachments": [attachment]}


async def send_slack_notification(
    webhook_url: str | None,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
) -> None:
    if not webhook_url:
        return
    payload = _build_payload(repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review)
    async with httpx.AsyncClient() as client:
        r = await client.post(webhook_url, json=payload)
        r.raise_for_status()
