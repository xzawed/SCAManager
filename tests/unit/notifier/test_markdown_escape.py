"""감사 D — 아웃바운드 markdown 인젝션 escape 테스트 (Option A: issue.message 만 escape).

Outbound markdown injection escape tests (option A: escape only untrusted static-tool
issue.message on github/discord/slack; AI 요약/피드백은 Claude 의도 프로즈라 보존 — 정책 16).
telegram 은 이미 전 동적 값 html.escape(HTML mode) 라 본 PR 범위 외.
"""
import json

from src.analyzer.io.ai_review import AiReviewResult
from src.analyzer.io.static import AnalysisIssue, StaticAnalysisResult
from src.notifier._common import escape_markdown, escape_slack_mrkdwn
from src.notifier.discord import _build_embed
from src.notifier.github_comment import _static_issues_lines
from src.notifier.slack import _build_payload
from src.scorer.calculator import ScoreResult


def _score() -> ScoreResult:
    return ScoreResult(
        total=82, grade="B", code_quality_score=22, security_score=18,
        breakdown={"code_quality": 22, "security": 18, "commit_message": 14,
                   "ai_review": 21, "test_coverage": 7},
    )


def _analysis(message: str) -> list[StaticAnalysisResult]:
    r = StaticAnalysisResult(filename="app.py")
    r.issues = [AnalysisIssue(tool="semgrep", severity="error", message=message, line=3)]
    return [r]


# ── escape_markdown 단위 (GitHub·Discord — GFM backslash) ──

def test_escape_markdown_neutralizes_link():
    assert escape_markdown("[evil](http://x)") == "\\[evil\\]\\(http://x\\)"


def test_escape_markdown_neutralizes_image_and_code():
    assert escape_markdown("![i](u)") == "\\!\\[i\\]\\(u\\)"
    assert escape_markdown("`code`") == "\\`code\\`"


def test_escape_markdown_escapes_backslash_first():
    assert escape_markdown("a\\b") == "a\\\\b"


def test_escape_markdown_plain_text_unchanged():
    assert escape_markdown("undefined variable x") == "undefined variable x"


# ── escape_slack_mrkdwn 단위 (Slack — & < > 엔티티) ──

def test_escape_slack_neutralizes_link_and_mention():
    assert escape_slack_mrkdwn("<http://x|evil>") == "&lt;http://x|evil&gt;"
    assert escape_slack_mrkdwn("<!channel>") == "&lt;!channel&gt;"


def test_escape_slack_amp_first_no_double_escape():
    # & 를 먼저 치환해야 엔티티의 & 가 이중 이스케이프되지 않음
    assert escape_slack_mrkdwn("a & <b>") == "a &amp; &lt;b&gt;"


def test_escape_slack_plain_text_unchanged():
    assert escape_slack_mrkdwn("undefined variable x") == "undefined variable x"


# ── 채널 통합: untrusted issue.message escape ──

def test_discord_escapes_issue_message():
    embed = _build_embed("owner/repo", "abc1234", _score(), _analysis("[evil](http://x)"), None)
    assert "\\[evil\\]\\(http://x\\)" in embed["description"]
    assert "[evil](http://x)" not in embed["description"]


def test_slack_escapes_issue_message():
    payload = _build_payload("owner/repo", "abc1234", _score(), _analysis("<http://x|evil>"), None)
    blob = json.dumps(payload)
    assert "&lt;http://x|evil&gt;" in blob
    assert "<http://x|evil>" not in blob


def test_github_escapes_issue_message():
    lines = _static_issues_lines(
        {"issues": [{"tool": "semgrep", "message": "[evil](http://x)", "line": 1}]}, "en",
    )
    blob = "\n".join(lines)
    assert "\\[evil\\]\\(http://x\\)" in blob
    assert "[evil](http://x)" not in blob


# ── Option A 경계: ai_summary 는 escape 안 함 (Claude markdown 프로즈 보존, 정책 16) ──

def test_discord_preserves_ai_summary_markdown():
    ai = AiReviewResult(
        commit_score=17, ai_score=15, test_score=10,
        summary="**굵게** 그리고 [링크](http://ok)", suggestions=[],
    )
    embed = _build_embed("owner/repo", "abc1234", _score(), _analysis("x"), None, ai_review=ai)
    # AI 요약의 markdown 은 보존(escape 안 됨) — 렌더링 품질 유지
    assert "**굵게**" in embed["description"]
    assert "[링크](http://ok)" in embed["description"]
