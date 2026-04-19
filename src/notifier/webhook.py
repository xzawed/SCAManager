"""Generic webhook notifier — sends analysis results as a JSON POST request."""
import logging
from datetime import datetime, timezone

from src.notifier._http import build_safe_client, validate_external_url
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult

logger = logging.getLogger(__name__)


def _build_payload(  # pylint: disable=too-many-positional-arguments
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> dict:
    all_issues = [i for r in analysis_results for i in r.issues]
    return {
        "event": "analysis_complete",
        "repo": repo_name,
        "commit_sha": commit_sha,
        "pr_number": pr_number,
        "score": {
            "total": score_result.total,
            "grade": score_result.grade,
            "breakdown": score_result.breakdown,
        },
        "ai_summary": ai_review.summary if ai_review else "",
        "ai_suggestions": list(ai_review.suggestions) if ai_review else [],
        "issues_count": len(all_issues),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def send_webhook_notification(
    *,
    webhook_url: str | None,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
) -> None:
    """범용 Webhook URL로 분석 결과 JSON을 POST한다."""
    if not webhook_url:
        return
    if not validate_external_url(webhook_url):
        logger.warning("send_webhook_notification: blocked unsafe URL '%s'", webhook_url)
        return
    payload = _build_payload(repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review)
    async with build_safe_client() as client:
        r = await client.post(webhook_url, json=payload)
        r.raise_for_status()
