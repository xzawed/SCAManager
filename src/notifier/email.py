"""Email notifier — sends HTML analysis reports via SMTP.

Phase 3 PR-10 (사이클 84) — i18n: language 인자 + 3-layer fallback + RFC 2047 base64 일본어 호환.
Phase 3 PR-10 (Cycle 84) — i18n: language arg + 3-layer fallback + RFC 2047 base64 (Japanese-safe).
"""
import logging
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import aiosmtplib

from src.i18n.loader import get_text
from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult
from src.constants import GRADE_COLOR_HTML, HTTP_CLIENT_TIMEOUT, NOTIFIER_MAX_ISSUES_LONG
from src.notifier._common import format_ref, get_all_issues, resolve_ai_summary, truncate_issue_msg

logger = logging.getLogger(__name__)

# implicit TLS(SMTPS) 전용 포트 — 이 포트만 연결 즉시 TLS 핸드셰이크를 한다.
# 나머지(587 제출 포트 · 25 등)는 평문으로 열고 STARTTLS 로 승격한다.
# 사용처 1곳이라 constants.py 로 올리지 않고 모듈 상수로 둔다(정책 16 최소 추상화).
# The only implicit-TLS (SMTPS) port — TLS handshake starts immediately on connect.
# All others (587 submission, 25, …) open in plaintext and upgrade via STARTTLS.
# Kept module-local rather than in constants.py: single use site (Policy 16, minimal abstraction).
SMTP_IMPLICIT_TLS_PORT = 465


def _build_html_body(  # pylint: disable=too-many-positional-arguments,too-many-locals
    repo_name: str,
    commit_sha: str,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    pr_number: int | None,
    ai_review: AiReviewResult | None = None,
    language: str = "en",
) -> str:
    ref = format_ref(commit_sha, pr_number, language)
    bd = score_result.breakdown
    color = GRADE_COLOR_HTML.get(score_result.grade, "#6366f1")

    rows = "".join(
        f"<tr><td style='padding:4px 8px'>{escape(name)}</td>"
        f"<td style='padding:4px 8px;text-align:right'><b>{bd.get(key, '-')}</b>/{mx}</td></tr>"
        for name, key, mx in [
            (get_text("notifier.email.row_quality", language), "code_quality", 25),
            (get_text("notifier.email.row_security", language), "security", 20),
            (get_text("notifier.email.row_commit", language), "commit_message", 15),
            (get_text("notifier.email.row_direction", language), "ai_review", 25),
            (get_text("notifier.email.row_test", language), "test_coverage", 15),
        ]
    )

    ai_section = ""
    ai_summary = resolve_ai_summary(ai_review, language)
    if ai_summary:
        ai_label = get_text("notifier.email.ai_summary", language)
        ai_section = f"<p><b>{escape(ai_label)}</b> {escape(ai_summary)}</p>"

    issues_section = ""
    all_issues = get_all_issues(analysis_results)
    if all_issues:
        issue_items = "".join(
            f"<li>[{escape(i.tool)}] {escape(truncate_issue_msg(i.message))}</li>"
            for i in all_issues[:NOTIFIER_MAX_ISSUES_LONG]
        )
        issues_header = get_text(
            "notifier.email.issues_header", language, count=len(all_issues),
        )
        issues_section = f"<p><b>{escape(issues_header)}</b></p><ul>{issue_items}</ul>"

    title = get_text("notifier.email.title", language, repo=escape(repo_name))
    total_label = get_text("notifier.email.total", language, total=score_result.total)
    grade_label = get_text("notifier.email.grade", language, grade=score_result.grade)
    th_item = get_text("notifier.email.th_item", language)
    th_score = get_text("notifier.email.th_score", language)

    return f"""\
<div style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:{color};color:#fff;padding:16px 20px;border-radius:8px 8px 0 0">
    <h2 style="margin:0;font-size:18px">{title}</h2>
    <p style="margin:4px 0 0;opacity:0.9">{escape(ref)}</p>
  </div>
  <div style="border:1px solid #e2e8f0;border-top:none;padding:20px;border-radius:0 0 8px 8px">
    <p style="font-size:20px;margin:0 0 16px"><b>{total_label}</b> ({grade_label})</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead><tr style="background:#f8fafc">
        <th style="padding:4px 8px;text-align:left">{escape(th_item)}</th>
        <th style="padding:4px 8px;text-align:right">{escape(th_score)}</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    {ai_section}
    {issues_section}
  </div>
</div>"""


async def send_email_notification(  # pylint: disable=too-many-arguments,too-many-locals
    # too-many-locals (16/15): TLS 모드 판정용 implicit_tls 지역변수 1개 추가 — 기존 함수 확장
    # 사례. use_tls/start_tls 에 `smtp_port == PORT` / `!= PORT` 를 각각 인라인하면 두 표현이
    # 갈라질 수 있어(한쪽만 수정) 명명 변수로 단일 출처 유지 (testing.md R0914 결정 트리:
    # 기존 함수 확장 → inline disable + 사유).
    # too-many-locals (16/15): one added local (implicit_tls) for the TLS-mode decision — an
    # extension of an existing function. Inlining `smtp_port == PORT` / `!= PORT` separately into
    # use_tls/start_tls would let the two drift apart, so a named local keeps a single source
    # (testing.md R0914 decision tree: extending an existing function → inline disable + reason).
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
    language: str = "en",
) -> None:
    """SMTP를 통해 HTML 분석 리포트 이메일을 전송한다 (Phase 3 PR-10 — i18n + RFC 2047)."""
    if not recipients or not smtp_host:
        return

    html = _build_html_body(
        repo_name, commit_sha, score_result, analysis_results, pr_number, ai_review,
        language=language,
    )

    msg = MIMEMultipart("alternative")
    # Phase 3 PR-10 — RFC 2047 base64 인코딩 (Header 사용 — 일본어/한국어 등 비-ASCII subject 호환)
    # Phase 3 PR-10 — RFC 2047 base64 (Header used — supports non-ASCII subjects like ja/ko)
    # 직접 string 할당 시 Python email 모듈은 ASCII 외 문자에 raw bytes 또는 SMTP 거부 발생 위험.
    # Direct string assignment risks raw bytes or SMTP rejection for non-ASCII chars.
    subject_text = get_text(
        "notifier.email.subject", language,
        repo=repo_name, total=score_result.total, grade=score_result.grade,
    )
    msg["Subject"] = Header(subject_text, "utf-8")
    msg["From"] = smtp_user or "sca@localhost"
    # 🔴 헤더 인젝션 차단 — recipients(repo 설정 email_recipients)의 CR/LF 제거 후 To 헤더 설정.
    # email 모듈은 raw string 헤더에 개행을 그대로 넣어 추가 헤더 주입이 가능하므로 명시 제거.
    # Strip CR/LF from recipients (repo email_recipients config) — the email module would otherwise
    # let embedded newlines inject extra headers (To-header injection).
    msg["To"] = recipients.replace("\r", "").replace("\n", "")
    msg.attach(MIMEText(html, "html"))

    # 🔴 TLS 모드는 포트로 결정한다 — 465 만 implicit TLS, 나머지(587 제출 포트 등)는 STARTTLS.
    # 이전엔 use_tls=True 고정이라 기본 포트 587 에 바이트 0 부터 ClientHello 를 보냈고, 587 은
    # 평문 배너(220 ...)로 응답하므로 핸드셰이크가 깨져 **이메일이 100% 실패**했다.
    # aiosmtplib 의 자동 STARTTLS 폴백(smtp.py:551-556)은 `not use_tls` 뒤라 실행되지 않았다.
    # start_tls=True 는 명시적 fail-closed — start_tls=None(기본)이면 STARTTLS 미지원 서버에
    # 자격증명과 리포트를 **평문으로 조용히** 보낸다. use_tls 와 start_tls 동시 True 는
    # aiosmtplib 이 ValueError 로 거부하므로(smtp.py:304-305) 둘은 항상 배타.
    # 🔴 Pick the TLS mode from the port — only 465 is implicit TLS; everything else (e.g. the 587
    # submission port) uses STARTTLS. The previous hardcoded use_tls=True sent a ClientHello at byte
    # 0 to port 587, which answers with a plaintext banner → handshake failure → 100% of emails
    # failed. aiosmtplib's auto-STARTTLS fallback is gated behind `not use_tls` and never ran.
    # start_tls=True is an explicit fail-closed: with start_tls=None (the default) aiosmtplib would
    # silently send credentials and the report in PLAINTEXT to a non-STARTTLS server. The two flags
    # are mutually exclusive — aiosmtplib raises ValueError if both are True (smtp.py:304-305).
    implicit_tls = smtp_port == SMTP_IMPLICIT_TLS_PORT

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
        use_tls=implicit_tls,
        start_tls=not implicit_tls,
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
        """알림을 전송한다 (Phase 3 PR-10 — 3-layer fallback)."""
        from src.database import WorkerSessionLocal as SessionLocal  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        from src.notifier._language import resolve_notification_language  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        with SessionLocal() as db:
            language = resolve_notification_language(db, config=ctx.config)
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
            language=language,
        )


register(_EmailNotifier())
