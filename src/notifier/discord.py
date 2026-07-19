"""Discord notifier — sends analysis results as embed messages via webhook.

Phase 3 PR-10 (사이클 84) — i18n: language 인자 + 3-layer fallback (resolve_notification_language).
Phase 3 PR-10 (Cycle 84) — i18n: language arg + 3-layer fallback.
"""
import logging

from src.notifier._http import build_safe_client, url_host_for_log, validate_external_url
from src.constants import (
    GRADE_EMOJI, GRADE_COLOR_DISCORD,
    DISCORD_EMBED_DESC_MAX_LENGTH, NOTIFIER_MAX_ISSUES_SHORT,
)
from src.i18n.loader import get_text
from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult
from src.notifier._common import (
    escape_markdown, format_ref, get_all_issues, resolve_ai_summary,
    truncate_issue_msg, truncate_message,
)

logger = logging.getLogger(__name__)


def _build_embed(  # pylint: disable=too-many-positional-arguments,too-many-locals
    # ai_summary local 추가로 16개 (사이클 155 — resolve_ai_summary 발신 현지화). 헬퍼 추출 시 embed 응집 깨짐
    # ai_summary local added (Cycle 155); extracting a helper would break embed-build cohesion
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
    language: str = "en",
) -> dict:
    grade_emoji = GRADE_EMOJI.get(score_result.grade, "⚪")
    ref = format_ref(commit_sha, pr_number, language)
    bd = score_result.breakdown

    lines = [
        get_text(
            "notifier.discord.summary_line", language,
            emoji=grade_emoji, total=score_result.total, grade=score_result.grade, ref=ref,
        ),
    ]

    ai_summary = resolve_ai_summary(ai_review, language)
    if ai_summary:
        lines.append("\n" + get_text(
            "notifier.discord.ai_summary", language, summary=ai_summary,
        ))

    all_issues = get_all_issues(analysis_results)
    if all_issues:
        lines.append("\n" + get_text(
            "notifier.discord.issues_header", language, count=len(all_issues),
        ))
        for issue in all_issues[:NOTIFIER_MAX_ISSUES_SHORT]:
            # 감사 D: untrusted 정적 도구 메시지 → markdown 이스케이프 (링크/멘션 인젝션 차단)
            # Audit D: escape untrusted static-tool message for markdown (block link/mention injection)
            lines.append(f"- [{issue.tool}] {escape_markdown(truncate_issue_msg(issue.message))}")

    desc = truncate_message("\n".join(lines), DISCORD_EMBED_DESC_MAX_LENGTH)

    fields = [
        {"name": get_text("notifier.discord.field_quality", language),
         "value": f"{bd.get('code_quality', '-')}/25", "inline": True},
        {"name": get_text("notifier.discord.field_security", language),
         "value": f"{bd.get('security', '-')}/20", "inline": True},
        {"name": get_text("notifier.discord.field_commit", language),
         "value": f"{bd.get('commit_message', '-')}/15", "inline": True},
        {"name": get_text("notifier.discord.field_direction", language),
         "value": f"{bd.get('ai_review', '-')}/25", "inline": True},
        {"name": get_text("notifier.discord.field_test", language),
         "value": f"{bd.get('test_coverage', '-')}/15", "inline": True},
    ]

    return {
        "title": get_text("notifier.discord.title", language, repo=repo_name),
        "description": desc,
        "color": GRADE_COLOR_DISCORD.get(score_result.grade, 0x6366F1),
        "fields": fields,
    }


async def send_discord_notification(
    *,
    webhook_url: str | None,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
    language: str = "en",
) -> None:
    """Discord Embed 메시지를 Webhook URL로 전송한다 (Phase 3 PR-10 — i18n)."""
    if not webhook_url:
        return
    if not await validate_external_url(webhook_url):
        logger.warning("send_discord_notification: blocked unsafe URL (host=%s)", url_host_for_log(webhook_url))
        return
    embed = _build_embed(
        repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review,
        language=language,
    )
    async with build_safe_client() as client:
        r = await client.post(webhook_url, json={"embeds": [embed]})
        r.raise_for_status()


# ---------------------------------------------------------------------------
# Notifier Protocol 구현체 (Phase S.3-E) — pipeline.py 에서 이관
# ---------------------------------------------------------------------------
from src.notifier.registry import NotifyContext, register  # noqa: E402  pylint: disable=wrong-import-position


class _DiscordNotifier:
    """Discord webhook 알림 채널 — discord_webhook_url 설정 시 활성."""

    name = "discord"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        """채널 활성화 여부를 반환한다."""
        return bool(ctx.config and ctx.config.discord_webhook_url)

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다 (Phase 3 PR-10 — 3-layer fallback)."""
        # 지연 import — circular 회피 (notifier._language → repositories → models)
        from src.database import (  # noqa: WPS433  # pylint: disable=import-outside-toplevel
            WorkerSessionLocal as SessionLocal,
        )
        from src.notifier._language import resolve_notification_language  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        with SessionLocal() as db:
            language = resolve_notification_language(db, config=ctx.config)
        await send_discord_notification(
            webhook_url=ctx.config.discord_webhook_url,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
            language=language,
        )


register(_DiscordNotifier())
