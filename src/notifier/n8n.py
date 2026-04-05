import httpx
from src.scorer.calculator import ScoreResult


async def notify_n8n(
    webhook_url: str | None,
    repo_full_name: str,
    commit_sha: str,
    pr_number: int | None,
    score_result: ScoreResult,
) -> None:
    if not webhook_url:
        return
    payload = {
        "repo": repo_full_name,
        "commit_sha": commit_sha,
        "pr_number": pr_number,
        "score": score_result.total,
        "grade": score_result.grade,
        "breakdown": score_result.breakdown,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(webhook_url, json=payload)
        r.raise_for_status()
