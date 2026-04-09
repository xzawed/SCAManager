"""Telegram notifier — sends HTML-formatted analysis results via Bot API."""
from html import escape

import httpx
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult

GRADE_EMOJI = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🟠", "F": "🔴"}
_TELEGRAM_MAX_LEN = 4096


def _build_message(
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> str:
    ref = f"PR #{pr_number}" if pr_number else f"커밋 {commit_sha[:7]}"
    total_issues = sum(len(r.issues) for r in analysis_results)
    top_issues = [
        f"- [{escape(i.tool)}] {escape(i.message[:80])}"
        for r in analysis_results
        for i in r.issues
    ][:5]

    grade_emoji = GRADE_EMOJI.get(score_result.grade, "⚪")
    issues_text = "\n".join(top_issues) if top_issues else "이슈 없음"
    bd = score_result.breakdown

    lines = [
        f"{grade_emoji} <b>SCA 분석 결과</b>",
        f"📁 <code>{escape(repo_name)}</code> — {escape(ref)}",
        "",
        f"<b>총점:</b> {score_result.total}/100  (등급 {score_result.grade})",
        "",
        "<b>점수 상세:</b>",
        f"  커밋 메시지: {bd.get('commit_message', '-')}/15",
        f"  코드 품질: {bd.get('code_quality', '-')}/25",
        f"  보안: {bd.get('security', '-')}/20",
        f"  구현 방향성: {bd.get('ai_review', '-')}/25",
        f"  테스트: {bd.get('test_coverage', '-')}/15",
    ]

    if ai_review and ai_review.summary:
        lines += ["", f"<b>AI 요약:</b> {escape(ai_review.summary)}"]

    if ai_review and ai_review.suggestions:
        lines += ["", "<b>개선 제안:</b>"]
        for s in ai_review.suggestions:
            lines.append(f"- {escape(s)}")

    if top_issues:
        lines += [
            "",
            f"<b>정적 분석 이슈:</b> {total_issues}건",
            issues_text,
        ]

    msg = "\n".join(lines)
    if len(msg) > _TELEGRAM_MAX_LEN:
        msg = msg[:_TELEGRAM_MAX_LEN - 3] + "..."
    return msg


async def send_analysis_result(
    bot_token: str,
    chat_id: str,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
) -> None:
    text = _build_message(repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review=ai_review)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        })
        r.raise_for_status()
