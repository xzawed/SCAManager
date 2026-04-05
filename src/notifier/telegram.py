import httpx
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult

GRADE_EMOJI = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🟠", "F": "🔴"}


def _build_message(
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
) -> str:
    ref = f"PR #{pr_number}" if pr_number else f"커밋 {commit_sha[:7]}"
    total_issues = sum(len(r.issues) for r in analysis_results)
    top_issues = [
        f"- [{i.tool}] {i.message[:80]}"
        for r in analysis_results
        for i in r.issues
    ][:5]

    grade_emoji = GRADE_EMOJI.get(score_result.grade, "⚪")
    issues_text = "\n".join(top_issues) if top_issues else "이슈 없음"

    return (
        f"{grade_emoji} *SCA 분석 결과*\n"
        f"📁 `{repo_name}` — {ref}\n\n"
        f"*점수:* {score_result.total}/100  (등급 {score_result.grade})\n"
        f"*이슈 수:* {total_issues}건\n\n"
        f"*주요 이슈:*\n{issues_text}"
    )


async def send_analysis_result(
    bot_token: str,
    chat_id: str,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
) -> None:
    text = _build_message(repo_name, commit_sha, score_result, analysis_results, pr_number)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        })
        r.raise_for_status()
