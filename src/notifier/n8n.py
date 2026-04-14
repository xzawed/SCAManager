"""n8n notifier — sends analysis score payload to an n8n webhook URL."""
import logging

from src.notifier._http import build_safe_client, validate_external_url
from src.scorer.calculator import ScoreResult

logger = logging.getLogger(__name__)


async def notify_n8n(
    *,
    webhook_url: str | None,
    repo_full_name: str,
    commit_sha: str,
    pr_number: int | None,
    score_result: ScoreResult,
) -> None:
    """n8n Webhook으로 분석 점수 페이로드를 POST한다."""
    if not webhook_url:
        return
    if not validate_external_url(webhook_url):
        logger.warning("notify_n8n: blocked unsafe URL '%s'", webhook_url)
        return
    payload = {
        "repo": repo_full_name,
        "commit_sha": commit_sha,
        "pr_number": pr_number,
        "score": score_result.total,
        "grade": score_result.grade,
        "breakdown": score_result.breakdown,
    }
    async with build_safe_client() as client:
        r = await client.post(webhook_url, json=payload)
        r.raise_for_status()
