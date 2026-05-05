"""Phase 3 PR-10 회귀 가드 — Discord + Slack + Email 다국어 + RFC 2047 base64.

Phase 3 PR-10 regression guards — Discord + Slack + Email i18n + RFC 2047 base64.

검증 범위 (Coverage):
1. Discord _build_embed — title / summary_line / fields 5 / ai_summary / issues_header (en/ko/ja)
2. Slack _build_payload — header / fallback / pretext / fields 5 / issues_header (en/ko/ja)
3. Email _build_html_body — title / total / grade / rows 5 / ai_summary / issues (en/ko/ja)
4. Email subject RFC 2047 base64 — Header(text, 'utf-8') 일본어 호환 검증
5. language='en' default fallback
"""
from __future__ import annotations

from email.header import Header, decode_header
from unittest.mock import MagicMock, patch

from src.notifier.discord import _build_embed
from src.notifier.email import _build_html_body
from src.notifier.slack import _build_payload as _build_slack_payload


def _score_result(grade: str = "B", total: int = 80):
    return MagicMock(
        total=total,
        grade=grade,
        breakdown={
            "code_quality": 22, "security": 18, "commit_message": 13,
            "ai_review": 22, "test_coverage": 12,
        },
    )


def _ai_review(summary: str = "Good code.", suggestions=None):
    return MagicMock(summary=summary, suggestions=suggestions or [])


# ── Discord _build_embed ────────────────────────────────────────────────────


def test_discord_embed_korean():
    embed = _build_embed(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(), analysis_results=[],
        pr_number=42, ai_review=_ai_review(), language="ko",
    )
    assert "📊 SCA 분석 — owner/repo" == embed["title"]
    assert "총점: 80/100" in embed["description"]
    assert "등급 B" in embed["description"]
    assert "AI 요약" in embed["description"]
    field_names = [f["name"] for f in embed["fields"]]
    assert field_names == ["코드 품질", "보안", "커밋 메시지", "구현 방향성", "테스트"]


def test_discord_embed_english():
    embed = _build_embed(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(grade="A", total=92), analysis_results=[],
        pr_number=None, ai_review=None, language="en",
    )
    assert "📊 SCA Analysis — owner/repo" == embed["title"]
    assert "Total: 92/100" in embed["description"]
    assert "(Grade A)" in embed["description"]
    field_names = [f["name"] for f in embed["fields"]]
    assert field_names == [
        "Code quality", "Security", "Commit message",
        "Implementation direction", "Tests",
    ]


def test_discord_embed_japanese():
    embed = _build_embed(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(), analysis_results=[],
        pr_number=42, ai_review=_ai_review(), language="ja",
    )
    assert "📊 SCA 分析 — owner/repo" == embed["title"]
    assert "合計: 80/100" in embed["description"]
    assert "(グレード B)" in embed["description"]
    field_names = [f["name"] for f in embed["fields"]]
    assert field_names == [
        "コード品質", "セキュリティ", "コミットメッセージ",
        "実装方向性", "テスト",
    ]


def test_discord_embed_default_language_falls_to_en():
    embed = _build_embed(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(), analysis_results=[],
        pr_number=None,
    )
    assert "SCA Analysis" in embed["title"]


# ── Slack _build_payload ────────────────────────────────────────────────────


def test_slack_payload_korean():
    payload = _build_slack_payload(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(), analysis_results=[],
        pr_number=42, ai_review=_ai_review(), language="ko",
    )
    assert "*SCA 분석 — owner/repo*" in payload["text"]
    attachment = payload["attachments"][0]
    assert "SCA: owner/repo" in attachment["fallback"]
    assert "*총점: 80/100*" in attachment["pretext"]
    assert "(등급 B)" in attachment["pretext"]
    field_titles = [f["title"] for f in attachment["fields"]]
    assert field_titles == ["코드 품질", "보안", "커밋 메시지", "구현 방향성", "테스트"]


def test_slack_payload_english():
    payload = _build_slack_payload(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(grade="A", total=92), analysis_results=[],
        pr_number=None, ai_review=None, language="en",
    )
    assert "*SCA Analysis — owner/repo*" in payload["text"]
    attachment = payload["attachments"][0]
    assert "*Total: 92/100*" in attachment["pretext"]
    assert "(Grade A)" in attachment["pretext"]
    field_titles = [f["title"] for f in attachment["fields"]]
    assert "Code quality" in field_titles
    assert "Tests" in field_titles


def test_slack_payload_japanese():
    payload = _build_slack_payload(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(), analysis_results=[],
        pr_number=42, ai_review=_ai_review(), language="ja",
    )
    assert "*SCA 分析 — owner/repo*" in payload["text"]
    attachment = payload["attachments"][0]
    assert "*合計: 80/100*" in attachment["pretext"]
    field_titles = [f["title"] for f in attachment["fields"]]
    assert "コード品質" in field_titles
    assert "テスト" in field_titles


# ── Email _build_html_body ─────────────────────────────────────────────────


def test_email_html_korean():
    html = _build_html_body(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(), analysis_results=[],
        pr_number=42, ai_review=_ai_review(), language="ko",
    )
    assert "📊 SCA 분석 결과 — owner/repo" in html
    assert "<b>총점: 80/100</b>" in html
    assert "(등급 B)" in html
    assert ">항목</th>" in html
    assert "코드 품질" in html
    assert "AI 요약:" in html


def test_email_html_english():
    html = _build_html_body(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(grade="A", total=92), analysis_results=[],
        pr_number=None, ai_review=None, language="en",
    )
    assert "📊 SCA Analysis Result — owner/repo" in html
    assert "<b>Total: 92/100</b>" in html
    assert "(Grade A)" in html
    assert "Code quality" in html
    assert "Implementation direction" in html


def test_email_html_japanese():
    html = _build_html_body(
        repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score_result(), analysis_results=[],
        pr_number=42, ai_review=_ai_review(), language="ja",
    )
    assert "📊 SCA 分析結果 — owner/repo" in html
    assert "<b>合計: 80/100</b>" in html
    assert "(グレード B)" in html
    assert "コード品質" in html
    assert "AI 要約:" in html


# ── Email subject RFC 2047 base64 (Japanese-safe) ───────────────────────────


def test_email_subject_japanese_rfc2047_encodable():
    """Email subject 일본어 — Header(text, 'utf-8') 가 RFC 2047 base64 로 인코딩 가능해야 한다.

    Phase 3 PR-10 — 직접 string 할당 시 ASCII 외 문자는 SMTP 거부 또는 raw bytes 위험.
    Header(text, 'utf-8') 사용으로 RFC 2047 base64 인코딩 + 받는 클라이언트 호환 보장.
    """
    from email.mime.multipart import MIMEMultipart

    from src.i18n.loader import get_text

    msg = MIMEMultipart("alternative")
    subject_ja = get_text(
        "notifier.email.subject", "ja", repo="owner/repo", total=80, grade="B",
    )
    msg["Subject"] = Header(subject_ja, "utf-8")

    # Subject 헤더 직렬화 시 RFC 2047 base64 = `=?utf-8?b?...?=` 형식
    raw_header = str(msg["Subject"])
    # 직접 비교 — Header 클래스가 base64/quoted-printable 자동 인코딩
    decoded = decode_header(raw_header)
    decoded_text = decoded[0][0]
    if isinstance(decoded_text, bytes):
        decoded_text = decoded_text.decode("utf-8")
    assert "owner/repo" in decoded_text
    assert "80点" in decoded_text  # 일본어 "점" 보존
    assert "(B)" in decoded_text


def test_email_subject_korean_rfc2047_encodable():
    """Email subject 한국어 — Header(text, 'utf-8') 인코딩 검증."""
    from email.mime.multipart import MIMEMultipart

    from src.i18n.loader import get_text

    msg = MIMEMultipart("alternative")
    subject_ko = get_text(
        "notifier.email.subject", "ko", repo="owner/repo", total=80, grade="B",
    )
    msg["Subject"] = Header(subject_ko, "utf-8")

    raw_header = str(msg["Subject"])
    decoded = decode_header(raw_header)
    decoded_text = decoded[0][0]
    if isinstance(decoded_text, bytes):
        decoded_text = decoded_text.decode("utf-8")
    assert "owner/repo" in decoded_text
    assert "80점" in decoded_text  # 한국어 "점" 보존


def test_email_subject_english_ascii_only():
    """Email subject 영문 — ASCII 영역, RFC 2047 인코딩 불필요 (본질 invariant)."""
    from email.mime.multipart import MIMEMultipart

    from src.i18n.loader import get_text

    msg = MIMEMultipart("alternative")
    subject_en = get_text(
        "notifier.email.subject", "en", repo="owner/repo", total=80, grade="B",
    )
    msg["Subject"] = Header(subject_en, "utf-8")

    raw_header = str(msg["Subject"])
    # 영문은 인코딩 불필요 — direct
    assert "[SCA] owner/repo" in raw_header
    assert "80/100" in raw_header
