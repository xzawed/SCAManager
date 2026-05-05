"""Phase 3 PR-11 회귀 가드 — GitHub PR Comment + Issue + Merge Failure Issue 다국어.

Phase 3 PR-11 regression guards — GitHub PR Comment + Issue + Merge Failure Issue i18n.

검증 범위 (Coverage):
1. _build_comment_from_result — title / total / breakdown table / sections (en/ko/ja)
2. _build_issue_body (low score) — header / score / detail / summary / security / suggestions (en/ko/ja)
3. _build_issue_body (merge failure) — header / repo / pr / score / reason / advice / footer (en/ko/ja)
4. Issue title prefix 영문 고정 — 모든 locale 동일 출력 (검색 호환성)
5. language='en' default fallback
"""
from __future__ import annotations

from src.notifier.github_comment import _build_comment_from_result
from src.notifier.github_issue import _build_issue_body as _build_issue_body_low
from src.notifier.merge_failure_issue import _build_issue_body as _build_issue_body_merge


def _result_dict(**overrides) -> dict:
    base = {
        "score": 80,
        "grade": "B",
        "breakdown": {
            "code_quality": 22, "security": 18, "commit_message": 13,
            "ai_review": 22, "test_coverage": 12,
        },
        "ai_summary": "Good code.",
        "ai_suggestions": ["Improve tests"],
        "issues": [
            {"tool": "pylint", "severity": "warning", "message": "msg", "line": 10},
        ],
    }
    base.update(overrides)
    return base


# ── _build_comment_from_result (PR + Commit Comment) ────────────────────────


def test_pr_comment_korean():
    body = _build_comment_from_result(_result_dict(), language="ko")
    assert "## 🔵 SCAManager 분석 결과" in body
    assert "**총점: 80/100** (등급 B)" in body
    assert "### 점수 상세" in body
    assert "| 항목 | 점수 | 만점 |" in body
    assert "| 커밋 메시지 | 13 | 15 |" in body
    assert "| 코드 품질 | 22 | 25 |" in body
    assert "### AI 요약" in body
    assert "### 개선 제안" in body
    assert "### 정적 분석 이슈 (상위" in body


def test_pr_comment_english():
    body = _build_comment_from_result(_result_dict(grade="A", score=92), language="en")
    assert "## 🟢 SCAManager Analysis Result" in body
    assert "**Total: 92/100** (Grade A)" in body
    assert "### Score Breakdown" in body
    assert "| Item | Score | Max |" in body
    assert "| Code quality | 22 | 25 |" in body
    assert "### AI Summary" in body
    assert "### Suggestions" in body


def test_pr_comment_japanese():
    body = _build_comment_from_result(_result_dict(), language="ja")
    assert "## 🔵 SCAManager 分析結果" in body
    assert "**合計: 80/100** (グレード B)" in body
    assert "### スコア詳細" in body
    assert "| 項目 | スコア | 満点 |" in body
    assert "| コード品質 | 22 | 25 |" in body
    assert "### AI 要約" in body
    assert "### 改善提案" in body


def test_pr_comment_category_feedback_korean():
    body = _build_comment_from_result(
        _result_dict(
            commit_message_feedback="커밋 메시지 양호",
            security_feedback="보안 OK",
        ),
        language="ko",
    )
    assert "### 카테고리별 피드백" in body
    assert "**커밋 메시지**" in body
    assert "**보안**" in body


def test_pr_comment_default_language_falls_to_en():
    body = _build_comment_from_result(_result_dict())
    assert "SCAManager Analysis Result" in body


# ── _build_issue_body (low score Issue) ─────────────────────────────────────


def test_low_score_issue_body_korean():
    body = _build_issue_body_low(
        repo_name="owner/repo",
        commit_sha="abc1234567",
        analysis_id=42,
        result=_result_dict(),
        high_issues=[
            {"message": "Hardcoded password", "line": 100},
        ],
        language="ko",
    )
    assert "## SCAManager 분석 결과 — 커밋 `abc1234`" in body
    assert "- **점수**: 80/100 (등급 B)" in body
    assert "- **상세 분석**:" in body
    assert "### 요약" in body
    assert "### 보안 이슈 (HIGH)" in body
    assert "Hardcoded password" in body
    assert "### 개선 제안" in body


def test_low_score_issue_body_english():
    body = _build_issue_body_low(
        repo_name="owner/repo",
        commit_sha="abc1234567",
        analysis_id=42,
        result=_result_dict(grade="A", score=92),
        high_issues=[],
        language="en",
    )
    assert "## SCAManager Analysis Result — Commit `abc1234`" in body
    assert "- **Score**: 92/100 (Grade A)" in body
    assert "- **Detail**:" in body
    assert "### Summary" in body
    assert "### Suggestions" in body


def test_low_score_issue_body_japanese():
    body = _build_issue_body_low(
        repo_name="owner/repo",
        commit_sha="abc1234567",
        analysis_id=42,
        result=_result_dict(),
        high_issues=[
            {"message": "SQL injection", "line": 200},
        ],
        language="ja",
    )
    assert "## SCAManager 分析結果 — コミット `abc1234`" in body
    assert "- **スコア**: 80/100 (グレード B)" in body
    assert "- **詳細**:" in body
    assert "### 要約" in body
    assert "### セキュリティ問題 (HIGH)" in body
    assert "### 改善提案" in body


# ── _build_issue_body (merge failure Issue) ─────────────────────────────────


def test_merge_failure_body_korean():
    body = _build_issue_body_merge(
        repo_name="owner/repo",
        pr_number=42,
        score=70,
        threshold=80,
        reason="branch_protection_blocked: required check failed",
        advice="Wait for CI completion or unblock branch protection.",
        language="ko",
    )
    assert "<!-- scamanager-auto-merge-pr:42 -->" in body
    assert "## ⚠️ Auto-Merge 실패" in body
    assert "- **리포**: `owner/repo`" in body
    assert "- **PR**: [#42](https://github.com/owner/repo/pull/42)" in body
    assert "- **점수**: 70점 (기준 80점 이상)" in body
    assert "- **실패 사유**: `branch_protection_blocked" in body
    assert "### 권장 조치" in body
    assert "Wait for CI completion" in body
    assert "Auto-generated by SCAManager auto-merge advisor" in body


def test_merge_failure_body_english():
    body = _build_issue_body_merge(
        repo_name="owner/repo",
        pr_number=42,
        score=70,
        threshold=80,
        reason="unstable_ci",
        advice="Investigate CI flakiness.",
        language="en",
    )
    assert "## ⚠️ Auto-Merge Failure" in body
    assert "- **Repo**: `owner/repo`" in body
    assert "- **PR**: [#42]" in body
    assert "- **Score**: 70 (threshold 80+)" in body
    assert "- **Reason**: `unstable_ci`" in body
    assert "### Recommended Action" in body


def test_merge_failure_body_japanese():
    body = _build_issue_body_merge(
        repo_name="owner/repo",
        pr_number=42,
        score=70,
        threshold=80,
        reason="permission_denied",
        advice="Review GitHub token scopes.",
        language="ja",
    )
    assert "## ⚠️ Auto-Merge 失敗" in body
    assert "- **リポ**: `owner/repo`" in body
    assert "- **PR**: [#42]" in body
    assert "- **スコア**: 70点 (基準 80点以上)" in body
    assert "- **失敗理由**: `permission_denied`" in body
    assert "### 推奨アクション" in body


# ── Issue title prefix 영문 고정 검증 ─────────────────────────────────────


def test_low_score_issue_title_prefix_english_fixed_across_locales():
    """[SCAManager] Low score commit: ... — 영문 prefix 모든 locale 동일 (검색 호환)."""
    from src.i18n.loader import get_text
    for lang in ("en", "ko", "ja"):
        title = get_text(
            "notifier.github_issue.title_prefix_low_score", lang,
            sha="abc1234", score=70,
        )
        # 영문 고정 — 모든 locale 동일 출력
        assert title.startswith("[SCAManager] Low score commit:")
        assert "abc1234" in title
        assert "70pt" in title


def test_merge_failure_title_prefix_english_fixed_across_locales():
    """[SCAManager] Auto-Merge failed: ... — 영문 prefix 모든 locale 동일 (검색 호환)."""
    from src.i18n.loader import get_text
    for lang in ("en", "ko", "ja"):
        title = get_text(
            "notifier.merge_failure_issue.title_prefix", lang,
            pr_number=42, reason_short="unstable_ci",
        )
        # 영문 고정 — 모든 locale 동일 출력
        assert title.startswith("[SCAManager] Auto-Merge failed:")
        assert "#42" in title
        assert "unstable_ci" in title
