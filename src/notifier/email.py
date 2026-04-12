"""Email notifier — sends HTML analysis reports via SMTP."""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import aiosmtplib

from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult

from src.constants import GRADE_COLOR_HTML

logger = logging.getLogger(__name__)


def _build_html_body(
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
) -> str:
    ref = f"PR #{pr_number}" if pr_number else f"커밋 {commit_sha[:7]}"
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
    all_issues = [i for r in analysis_results for i in r.issues]
    if all_issues:
        issue_items = "".join(
            f"<li>[{escape(i.tool)}] {escape(i.message[:80])}</li>"
            for i in all_issues[:10]
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


async def send_email_notification(
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

    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_pass,
        use_tls=True,
    )
