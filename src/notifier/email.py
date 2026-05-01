"""Email notifier — sends HTML analysis reports via SMTP."""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import aiosmtplib

from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult
from src.constants import GRADE_COLOR_HTML, HTTP_CLIENT_TIMEOUT, NOTIFIER_MAX_ISSUES_LONG
from src.notifier._common import format_ref, get_all_issues, truncate_issue_msg

logger = logging.getLogger(__name__)


def _build_html_body(  # pylint: disable=too-many-positional-arguments
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> str:
    ref = format_ref(commit_sha, pr_number)
    bd = score_result.breakdown
    color = GRADE_COLOR_HTML.get(score_result.grade, "#6366f1")

    rows = "".join(
        f"<tr><td style='padding:4px 8px'>{name}</td>"
        f"<td style='padding:4px 8px;text-align:right'><b>{bd.get(key, '-')}</b>/{mx}</td></tr>"
        for name, key, mx in [
            ("코드 품질", "code_quality", 25),
            ("보안", "security", 20),
            ("커밋 메시지", "commit_message", 15),
            ("구현 방향성", "ai_review", 25),
            ("테스트", "test_coverage", 15),
        ]
    )

    ai_section = ""
    if ai_review and ai_review.summary:
        ai_section = f"<p><b>AI 요약:</b> {escape(ai_review.summary)}</p>"

    issues_section = ""
    all_issues = get_all_issues(analysis_results)
    if all_issues:
        issue_items = "".join(
            f"<li>[{escape(i.tool)}] {escape(truncate_issue_msg(i.message))}</li>"
            for i in all_issues[:NOTIFIER_MAX_ISSUES_LONG]
        )
        issues_section = f"<p><b>정적 분석 이슈 ({len(all_issues)}건):</b></p><ul>{issue_items}</ul>"

    return f"""\
<div style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:{color};color:#fff;padding:16px 20px;border-radius:8px 8px 0 0">
    <h2 style="margin:0;font-size:18px">📊 SCA 분석 결과 — {escape(repo_name)}</h2>
    <p style="margin:4px 0 0;opacity:0.9">{escape(ref)}</p>
  </div>
  <div style="border:1px solid #e2e8f0;border-top:none;padding:20px;border-radius:0 0 8px 8px">
    <p style="font-size:20px;margin:0 0 16px"><b>총점: {score_result.total}/100</b> (등급 {score_result.grade})</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead><tr style="background:#f8fafc"><th style="padding:4px 8px;text-align:left">항목</th><th style="padding:4px 8px;text-align:right">점수</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    {ai_section}
    {issues_section}
  </div>
</div>"""


async def send_email_notification(  # pylint: disable=too-many-arguments
    *,
    recipients: str | None,
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None = None,
    ai_review: AiReviewResult | None = None,
    smtp_host: str | None = None,
    smtp_port: int = 587,
    smtp_user: str | None = None,
    smtp_pass: str | None = None,
) -> None:
    """SMTP를 통해 HTML 분석 리포트 이메일을 전송한다."""
    if not recipients or not smtp_host:
        return

    html = _build_html_body(repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[SCA] {repo_name} — {score_result.total}점 ({score_result.grade})"
    msg["From"] = smtp_user or "sca@localhost"
    msg["To"] = recipients
    msg.attach(MIMEText(html, "html"))

    # SMTP hang 방어: aiosmtplib 기본 timeout=60s 가 길어 운영 hang 시
    # BackgroundTask 슬롯 점유 위험. HTTP_CLIENT_TIMEOUT(=10s) 과 동일 정책.
    # SMTP hang guard: aiosmtplib's default 60s timeout is too long; align to
    # HTTP_CLIENT_TIMEOUT to avoid BackgroundTask slot exhaustion.
    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_pass,
        use_tls=True,
        timeout=HTTP_CLIENT_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# Notifier Protocol 구현체 (Phase S.3-E) — pipeline.py 에서 이관
# ---------------------------------------------------------------------------
from src.config import settings  # noqa: E402  pylint: disable=wrong-import-position
from src.notifier.registry import NotifyContext, register  # noqa: E402  pylint: disable=wrong-import-position


class _EmailNotifier:
    """SMTP 이메일 알림 채널 — email_recipients + SMTP 설정 시 활성."""

    name = "email"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        """채널 활성화 여부를 반환한다."""
        return bool(ctx.config and ctx.config.email_recipients and settings.smtp_host)

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다."""
        await send_email_notification(
            recipients=ctx.config.email_recipients,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_pass=settings.smtp_pass,
        )


register(_EmailNotifier())
