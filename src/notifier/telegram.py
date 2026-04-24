"""Telegram notifier — sends HTML-formatted analysis results via Bot API."""
from html import escape

import httpx
from src.constants import GRADE_EMOJI, TELEGRAM_MAX_MESSAGE_LENGTH, NOTIFIER_MAX_ISSUES_SHORT
from src.shared.http_client import get_http_client
from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult
from src.notifier._common import format_ref, get_all_issues, truncate_message, truncate_issue_msg


async def telegram_post_message(bot_token: str, chat_id: str, payload: dict) -> None:
    """Telegram Bot API sendMessage 엔드포인트에 JSON 페이로드를 POST한다.

    Args:
        bot_token: Telegram Bot API 토큰
        chat_id:   대상 채팅 ID (사용자·그룹·채널)
        payload:   sendMessage JSON 페이로드 (text, parse_mode 등)
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    client = get_http_client()  # 싱글톤
    r = await client.post(url, json={"chat_id": chat_id, **payload})
    r.raise_for_status()


def _build_message(  # pylint: disable=too-many-positional-arguments
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> str:
    ref = format_ref(commit_sha, pr_number)
    all_issues = get_all_issues(analysis_results)
    top_issues = [
        f"- [{escape(i.tool)}] {escape(truncate_issue_msg(i.message))}"
        for i in all_issues[:NOTIFIER_MAX_ISSUES_SHORT]
    ]

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
            f"<b>정적 분석 이슈:</b> {len(all_issues)}건",
            issues_text,
        ]

    return truncate_message("\n".join(lines), TELEGRAM_MAX_MESSAGE_LENGTH)


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


# ---------------------------------------------------------------------------
# Notifier Protocol 구현체 (Phase S.3-E) — pipeline.py 에서 이관
# ---------------------------------------------------------------------------
from src.config import settings  # noqa: E402  pylint: disable=wrong-import-position
from src.notifier.registry import NotifyContext, register  # noqa: E402  pylint: disable=wrong-import-position


class _TelegramNotifier:
    """Telegram 알림 채널 — 항상 활성 (global fallback chat_id 사용)."""

    name = "telegram"

    def is_enabled(self, ctx: NotifyContext) -> bool:  # pylint: disable=unused-argument
        """채널 활성화 여부를 반환한다."""
        return True

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다."""
        chat_id = (ctx.config.notify_chat_id if ctx.config else None) or settings.telegram_chat_id
        await send_analysis_result(
            bot_token=settings.telegram_bot_token,
            chat_id=chat_id,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
        )


register(_TelegramNotifier())
