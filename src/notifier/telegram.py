"""Telegram notifier — sends HTML-formatted analysis results via Bot API."""
import asyncio
import logging
from html import escape

from src.constants import GRADE_EMOJI, TELEGRAM_MAX_MESSAGE_LENGTH, NOTIFIER_MAX_ISSUES_SHORT
from src.i18n.loader import get_text
from src.shared.http_client import get_http_client
from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult
from src.notifier._common import (
    format_ref, get_all_issues, resolve_ai_summary, truncate_html_message, truncate_issue_msg,
)

logger = logging.getLogger(__name__)

# Phase H PR-2B — Telegram 429 재시도 정책
# 12-에이전트 감사 Critical C4 — Bot API 429 응답의 retry_after 미처리 시
# 봇 그룹 차단(spam) → cron 누적 시 운영 중단. 단일 재시도 + cap 으로 보호.
# Phase H PR-2B — Telegram 429 retry policy: respect retry_after with cap,
# single retry only to avoid infinite loop. Critical C4 from 2026-04-30 audit.
TELEGRAM_RETRY_AFTER_MAX_SECONDS = 30

# Cycle 78 PR 2 — 봇 차단 silent skip + streak guard (5+1 NEW-P0 — 🅒 P0-1).
# Telegram 403 = bot blocked by user / kicked from group → cron 누적 사고 차단.
# silent skip + WARNING (단발) + 5회 연속 시 streak WARNING (운영자 인지).
# Cycle 78 PR 2 — bot blocked silent skip + streak guard (5+1 NEW-P0 — 🅒 P0-1).
TELEGRAM_BOT_BLOCKED_STREAK_THRESHOLD = 5
_telegram_bot_blocked_streak: int = 0  # process restart 시 reset (정책 16 단순화)


async def telegram_post_message(bot_token: str, chat_id: str, payload: dict) -> None:
    """Telegram Bot API sendMessage 엔드포인트에 JSON 페이로드를 POST한다.

    429 Too Many Requests 응답 시 `parameters.retry_after` 만큼 sleep 후 1회 재시도.
    cap 30s — 악의적 응답으로 인한 무기한 sleep 방지.

    403 Forbidden (bot blocked by user / kicked from group) 시 silent skip + WARNING.
    5회 연속 403 시 추가 streak WARNING — 운영자 인지 의무.
    Cycle 78 PR 2 — bot blocked guard (Phase 9 silent fallback streak 패턴 차용).

    Args:
        bot_token: Telegram Bot API 토큰
        chat_id:   대상 채팅 ID (사용자·그룹·채널)
        payload:   sendMessage JSON 페이로드 (text, parse_mode 등)
    """
    global _telegram_bot_blocked_streak  # pylint: disable=global-statement
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    client = get_http_client()  # 싱글톤
    body = {"chat_id": chat_id, **payload}
    r = await client.post(url, json=body)

    # 429 처리 — retry_after 파싱 후 1회 재시도
    # Handle 429 — parse retry_after and retry once
    if r.status_code == 429:
        retry_after = _parse_retry_after(r)
        logger.warning(
            "Telegram 429 received, sleeping %ds before single retry", retry_after,
        )
        await asyncio.sleep(retry_after)
        r = await client.post(url, json=body)

    # defensive int coercion — mock-safety + 정책 16 1번 원칙 정확성
    # (방어적 coercion — mock 안전성 패턴. 근거 메모리는 소실, 교훈은 본문에 보존)
    # defensive int coercion — mock-safety + Policy 16 #1 accuracy
    try:
        status = int(r.status_code or 0)
    except (TypeError, ValueError):
        status = 0

    # 403 봇 차단 silent skip + streak guard (Cycle 78 PR 2 — 🅒 P0-1)
    # 403 bot blocked silent skip + streak guard
    if status == 403:
        _telegram_bot_blocked_streak += 1
        logger.warning(
            "Telegram 403 (bot blocked or kicked) chat_id=%s — silent skip", chat_id,
        )
        if _telegram_bot_blocked_streak >= TELEGRAM_BOT_BLOCKED_STREAK_THRESHOLD:
            logger.warning(
                "Telegram bot_blocked streak=%d — 운영자 검토 의무 (token revoke 또는 chat 정리)",
                _telegram_bot_blocked_streak,
            )
            _telegram_bot_blocked_streak = 0  # reset (재 alert 방지)
        return

    # 정상 응답 — streak reset
    if status and status < 400:
        _telegram_bot_blocked_streak = 0

    r.raise_for_status()


def _parse_retry_after(response) -> int:
    """429 응답에서 retry_after 추출 — cap 적용. 파싱 실패 시 1초 fallback."""
    try:
        retry_after = int(response.json().get("parameters", {}).get("retry_after", 1))
    except (ValueError, KeyError, AttributeError):
        retry_after = 1
    return min(max(retry_after, 1), TELEGRAM_RETRY_AFTER_MAX_SECONDS)


def _build_message(  # pylint: disable=too-many-positional-arguments,too-many-locals
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
    language: str = "en",
) -> str:
    """분석 결과를 Telegram HTML 메시지로 빌드 (Phase 3 PR-9 — 사이클 84 i18n).

    Build Telegram HTML message for analysis result (Phase 3 PR-9 — Cycle 84 i18n).

    Args:
        language: 사용자 언어 ('ko'/'en'/'ja'). 3-layer fallback (resolve_notification_language).
    """
    ref = format_ref(commit_sha, pr_number, language)
    all_issues = get_all_issues(analysis_results)
    top_issues = [
        f"- [{escape(i.tool)}] {escape(truncate_issue_msg(i.message))}"
        for i in all_issues[:NOTIFIER_MAX_ISSUES_SHORT]
    ]

    grade_emoji = GRADE_EMOJI.get(score_result.grade, "⚪")  # type: ignore[union-attr]
    no_issues_text = get_text("notifier.telegram.no_issues", language)
    issues_text = "\n".join(top_issues) if top_issues else no_issues_text
    bd = score_result.breakdown

    lines = [
        get_text("notifier.telegram.title", language, emoji=grade_emoji),
        get_text("notifier.telegram.ref_line", language, repo=escape(repo_name), ref=escape(ref)),
        "",
        get_text(
            "notifier.telegram.total", language,
            total=score_result.total, grade=score_result.grade,
        ),
        "",
        get_text("notifier.telegram.breakdown_header", language),
        get_text("notifier.telegram.breakdown_commit", language, value=bd.get("commit_message", "-")),
        get_text("notifier.telegram.breakdown_quality", language, value=bd.get("code_quality", "-")),
        get_text("notifier.telegram.breakdown_security", language, value=bd.get("security", "-")),
        get_text("notifier.telegram.breakdown_direction", language, value=bd.get("ai_review", "-")),
        get_text("notifier.telegram.breakdown_test", language, value=bd.get("test_coverage", "-")),
    ]

    ai_summary = resolve_ai_summary(ai_review, language)
    if ai_summary:
        lines += ["", get_text(
            "notifier.telegram.ai_summary", language, summary=escape(ai_summary),
        )]

    if ai_review and ai_review.suggestions:
        lines += ["", get_text("notifier.telegram.ai_suggestions_header", language)]
        for s in ai_review.suggestions:
            lines.append(f"- {escape(s)}")

    if top_issues:
        lines += [
            "",
            get_text(
                "notifier.telegram.issues_header", language, count=len(all_issues),
            ),
            issues_text,
        ]

    # 🔴 HTML-safe 절단 (P1-8) — parse_mode=HTML 이므로 부분 엔티티/태그·미닫힌 태그를 남기면
    #   Telegram 400 으로 알림 전량 소실. truncate_html_message 가 엔티티/태그 경계를 존중한다.
    return truncate_html_message("\n".join(lines), TELEGRAM_MAX_MESSAGE_LENGTH)


async def send_analysis_result(  # pylint: disable=too-many-arguments
    *,
    bot_token: str,
    chat_id: str,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
    language: str = "en",
) -> None:
    """분석 결과를 Telegram HTML 메시지로 전송한다 (Phase 3 PR-9 — i18n).

    Send analysis result via Telegram HTML message (Phase 3 PR-9 — i18n).
    """
    text = _build_message(
        repo_name, commit_sha, score_result, analysis_results, pr_number,
        ai_review=ai_review, language=language,
    )
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
        """채널 활성화 여부를 반환한다.

        TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 미설정 시 비활성화.
        Disabled when TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured.
        """
        # 토큰 또는 기본 chat_id 없으면 비활성화 (빈 문자열 허용 안 함)
        # Disable if token or default chat_id is missing (empty string not allowed)
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다 (Phase 3 PR-9 — 사이클 84 i18n 3-layer fallback).

        Send notification (Phase 3 PR-9 — Cycle 84 i18n 3-layer fallback).
        """
        chat_id = (ctx.config.notify_chat_id if ctx.config else None) or settings.telegram_chat_id
        # Phase 3 PR-9 — 3-layer 사용자 언어 결정 (User → RepoConfig → settings.default_locale)
        # Phase 3 PR-9 — 3-layer language resolve (User → RepoConfig → settings.default_locale)
        from src.database import (  # noqa: WPS433  # pylint: disable=import-outside-toplevel
            WorkerSessionLocal as SessionLocal,
        )
        from src.notifier._language import resolve_notification_language  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        with SessionLocal() as db:
            language = resolve_notification_language(db, config=ctx.config)
        await send_analysis_result(
            bot_token=settings.telegram_bot_token,
            chat_id=chat_id,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
            language=language,
        )


register(_TelegramNotifier())
