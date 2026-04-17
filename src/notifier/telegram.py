"""Telegram notifier — sends HTML-formatted analysis results via Bot API."""
from html import escape

import httpx
from src.constants import GRADE_EMOJI
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult

_TELEGRAM_MAX_LEN = 4096


async def telegram_post_message(bot_token: str, chat_id: str, payload: dict) -> None:
    """Telegram Bot API sendMessage 엔드포인트에 JSON 페이로드를 POST한다.

    Args:
        bot_token: Telegram Bot API 토큰
        chat_id:   대상 채팅 ID (사용자·그룹·채널)
        payload:   sendMessage JSON 페이로드 (text, parse_mode 등)
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"chat_id": chat_id, **payload})
        r.raise_for_status()


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

    grade_emoji = GRADE_EMOJI.get(score_result.grade, "⚪")  # type: ignore[union-attr]
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
    *,
    bot_token: str,
    chat_id: str,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
) -> None:
    """분석 결과를 Telegram HTML 메시지로 전송한다."""
    text = _build_message(repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review=ai_review)
    await telegram_post_message(bot_token, chat_id, {"text": text, "parse_mode": "HTML"})


async def send_regression_alert(
    *,
    bot_token: str,
    chat_id: str,
    repo_name: str,
    commit_sha: str,
    current_score: int,
    regression_info: dict,
) -> None:
    """회귀(급락·F 진입) 감지 시 별도 경보를 Telegram HTML 메시지로 전송한다.

    일반 분석 알림과 시각적으로 구분되도록 ⚠️📉 이모지와 "급락"/"F등급" 문구를 사용한다.
    """
    info_type = regression_info.get("type")
    delta = regression_info.get("delta", 0)
    baseline = regression_info.get("baseline", 0.0)

    if info_type == "drop":
        title = "⚠️📉 점수 급락 감지"
        reason = f"직전 평균 대비 {int(delta)}점 급락"
    elif info_type == "f_entry":
        title = "⚠️📉 F등급 진입 감지"
        reason = f"F등급 진입 (직전 평균 {baseline:.1f}점)"
    else:
        title = "⚠️📉 회귀 감지"
        reason = "회귀 조건 충족"

    lines = [
        f"<b>{escape(title)}</b>",
        f"📁 <code>{escape(repo_name)}</code> — 커밋 <code>{escape(commit_sha[:7])}</code>",
        "",
        f"<b>현재 점수:</b> {current_score}/100",
        f"<b>직전 평균:</b> {baseline:.1f}",
        f"<b>사유:</b> {escape(reason)}",
    ]
    if info_type == "drop" and regression_info.get("secondary") == "f_entry":
        lines.append("🔻 F등급 진입 동반")

    text = "\n".join(lines)
    if len(text) > _TELEGRAM_MAX_LEN:
        text = text[:_TELEGRAM_MAX_LEN - 3] + "..."
    await telegram_post_message(bot_token, chat_id, {"text": text, "parse_mode": "HTML"})
