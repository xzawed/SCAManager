"""Phase 3 PR-9 회귀 가드 — Telegram + telegram_commands 다국어 + 3-layer fallback.

Phase 3 PR-9 regression guards — Telegram + telegram_commands i18n + 3-layer fallback.

검증 범위 (Coverage):
1. resolve_notification_language — 3-layer 우선순위 (User → RepoConfig → settings.default_locale)
2. _build_message — en/ko/ja 3 언어 분기 (title / breakdown / AI summary / issues / no_issues)
3. handle_message_command — User.preferred_language 기반 응답 언어 결정
4. _handle_connect — 미연결 사용자 = settings.default_locale, 성공 시 user lang
5. _handle_stats / _handle_settings — language 인자 기반 응답
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.notifier._language import resolve_notification_language
from src.notifier.telegram import _build_message
from src.notifier.telegram_commands import (
    _handle_settings,
    _handle_stats,
    _resolve_user_language,
    handle_message_command,
)


# ── ScoreResult / AiReviewResult fixtures ────────────────────────────────────


def _score_result(grade: str = "B", total: int = 80):
    """Lightweight ScoreResult-like mock."""
    return MagicMock(
        total=total,
        grade=grade,
        breakdown={
            "code_quality": 22,
            "security": 18,
            "commit_message": 13,
            "ai_review": 22,
            "test_coverage": 12,
        },
    )


def _ai_review(summary: str = "Good code.", suggestions=None):
    return MagicMock(summary=summary, suggestions=suggestions or [])


# ── resolve_notification_language ───────────────────────────────────────────


def test_resolve_language_layer1_user_preferred(monkeypatch):
    """Layer 1 — User.preferred_language 우선."""
    db = MagicMock()
    user = MagicMock(preferred_language="ja")

    monkeypatch.setattr(
        "src.repositories.user_repo.find_by_telegram_user_id",
        lambda db, tid: user,
    )

    result = resolve_notification_language(db, telegram_user_id="123")
    assert result == "ja"


def test_resolve_language_layer1_user_no_preferred_falls_through(monkeypatch):
    """Layer 1 — preferred_language 빈 값 → Layer 2 fallthrough."""
    db = MagicMock()
    user = MagicMock(preferred_language="")
    config = MagicMock(notification_language="ko")

    monkeypatch.setattr(
        "src.repositories.user_repo.find_by_telegram_user_id",
        lambda db, tid: user,
    )

    result = resolve_notification_language(db, telegram_user_id="123", config=config)
    assert result == "ko"


def test_resolve_language_layer2_repo_config():
    """Layer 2 — RepoConfig.notification_language (Telegram 미연결 영역)."""
    config = MagicMock(notification_language="ja")
    result = resolve_notification_language(config=config)
    assert result == "ja"


def test_resolve_language_layer3_default_locale():
    """Layer 3 — settings.default_locale fallback (모든 layer 부재)."""
    result = resolve_notification_language()
    # default_locale = 'en' (config.py default)
    assert result in ("en", "ko", "ja")


def test_resolve_language_layer1_exception_falls_through(monkeypatch):
    """Layer 1 raise 시 Layer 2 fallthrough (graceful degradation)."""
    db = MagicMock()

    def _raise(*args, **kwargs):
        raise RuntimeError("DB connection lost")

    monkeypatch.setattr(
        "src.repositories.user_repo.find_by_telegram_user_id",
        _raise,
    )
    config = MagicMock(notification_language="ja")
    result = resolve_notification_language(db, telegram_user_id="123", config=config)
    assert result == "ja"  # Layer 2 fallthrough


# ── _build_message — 3 languages ────────────────────────────────────────────


def test_build_message_korean():
    """Telegram message — 한국어."""
    out = _build_message(
        repo_name="owner/repo",
        commit_sha="abc1234",
        score_result=_score_result(),
        analysis_results=[],
        pr_number=42,
        ai_review=_ai_review(suggestions=["Improve tests"]),
        language="ko",
    )
    assert "<b>SCA 분석 결과</b>" in out
    assert "<b>총점:</b> 80/100" in out
    assert "등급 B" in out
    assert "<b>점수 상세:</b>" in out
    assert "  커밋 메시지: 13/15" in out
    assert "  코드 품질: 22/25" in out
    assert "  보안: 18/20" in out
    assert "<b>AI 요약:</b>" in out
    assert "<b>개선 제안:</b>" in out


def test_build_message_english():
    """Telegram message — 영문."""
    out = _build_message(
        repo_name="owner/repo",
        commit_sha="abc1234",
        score_result=_score_result(grade="A", total=92),
        analysis_results=[],
        pr_number=None,
        ai_review=None,
        language="en",
    )
    assert "<b>SCA Analysis Result</b>" in out
    assert "<b>Total:</b> 92/100" in out
    assert "(Grade A)" in out
    assert "<b>Score breakdown:</b>" in out
    assert "  Commit message: 13/15" in out
    assert "  Code quality: 22/25" in out
    assert "  Security: 18/20" in out


def test_build_message_japanese():
    """Telegram message — 일본어."""
    out = _build_message(
        repo_name="owner/repo",
        commit_sha="abc1234",
        score_result=_score_result(),
        analysis_results=[],
        pr_number=42,
        ai_review=_ai_review(),
        language="ja",
    )
    assert "<b>SCA 分析結果</b>" in out
    assert "<b>合計:</b> 80/100" in out
    assert "(グレード B)" in out
    assert "<b>スコア詳細:</b>" in out
    assert "  コミットメッセージ: 13/15" in out
    assert "<b>AI 要約:</b>" in out


def test_build_message_no_ai_no_issues_korean():
    """ai_review None + no issues → 한국어."""
    out = _build_message(
        repo_name="owner/repo",
        commit_sha="abc1234",
        score_result=_score_result(),
        analysis_results=[],
        pr_number=None,
        ai_review=None,
        language="ko",
    )
    assert "AI 요약" not in out  # ai_review is None
    assert "개선 제안" not in out
    assert "정적 분석 이슈" not in out


def test_build_message_default_language_falls_to_en():
    """language 인자 default = 'en' → 영문 응답."""
    out = _build_message(
        repo_name="owner/repo",
        commit_sha="abc1234",
        score_result=_score_result(),
        analysis_results=[],
        pr_number=None,
    )
    assert "SCA Analysis Result" in out


# ── telegram_commands ──────────────────────────────────────────────────────


def test_resolve_user_language_with_user():
    """_resolve_user_language — User 있으면 preferred_language 반환."""
    user = MagicMock(preferred_language="ja")
    assert _resolve_user_language(user) == "ja"


def test_resolve_user_language_user_none():
    """_resolve_user_language — User None → settings.default_locale."""
    result = _resolve_user_language(None)
    assert result in ("en", "ko", "ja")


def test_handle_message_unlinked_user_returns_default_locale_message(monkeypatch):
    """미연결 사용자 → not_connected 메시지 (settings.default_locale)."""
    monkeypatch.setattr(
        "src.notifier.telegram_commands.user_repo.find_by_telegram_user_id",
        lambda db, tid: None,
    )
    db = MagicMock()
    out = handle_message_command(db, "tg_user_123", "/stats owner/repo")
    # default_locale = 'en' or 'ko' or 'ja' — multilingual default
    assert ("Connect your account first" in out) or ("계정을 연결" in out) or ("連携してください" in out)


def test_handle_message_unknown_command_uses_user_language(monkeypatch):
    """연결된 사용자 — 알 수 없는 명령 시 User.preferred_language 기반 응답."""
    user = MagicMock(preferred_language="ja", display_name="Tanaka")
    monkeypatch.setattr(
        "src.notifier.telegram_commands.user_repo.find_by_telegram_user_id",
        lambda db, tid: user,
    )
    db = MagicMock()
    out = handle_message_command(db, "tg_user_123", "/unknown_cmd")
    assert "対応していないコマンド" in out


def test_handle_stats_no_repo_uses_language():
    """_handle_stats — repo 미입력 시 사용법 안내 (한국어)."""
    db = MagicMock()
    user = MagicMock(id=1)
    out = _handle_stats(db, user, repo_name="", language="ko")
    assert "사용법: /stats" in out


def test_handle_stats_repo_not_found_japanese(monkeypatch):
    """_handle_stats — 리포 미존재 시 일본어 응답."""
    monkeypatch.setattr(
        "src.notifier.telegram_commands.repository_repo.find_by_full_name",
        lambda db, name: None,
    )
    db = MagicMock()
    user = MagicMock(id=1)
    out = _handle_stats(db, user, repo_name="missing/repo", language="ja")
    assert "リポジトリが見つかりません" in out
    assert "missing/repo" in out


def test_handle_stats_no_data_korean(monkeypatch):
    """_handle_stats — 7일 데이터 부재 시 한국어 응답."""
    repo = MagicMock(id=10, user_id=1)
    monkeypatch.setattr(
        "src.notifier.telegram_commands.repository_repo.find_by_full_name",
        lambda db, name: repo,
    )
    monkeypatch.setattr(
        "src.notifier.telegram_commands.weekly_summary",
        lambda db, repo_id, week_start, now: None,
    )
    db = MagicMock()
    user = MagicMock(id=1)
    out = _handle_stats(db, user, repo_name="owner/repo", language="ko")
    assert "최근 7일간 분석 데이터가 없습니다" in out


def test_handle_stats_summary_english(monkeypatch):
    """_handle_stats — summary 영문 + trend."""
    repo = MagicMock(id=10, user_id=1)
    monkeypatch.setattr(
        "src.notifier.telegram_commands.repository_repo.find_by_full_name",
        lambda db, name: repo,
    )
    monkeypatch.setattr(
        "src.notifier.telegram_commands.weekly_summary",
        lambda db, repo_id, week_start, now: {
            "avg_score": 80.5, "count": 5, "min_score": 65, "max_score": 92,
        },
    )
    monkeypatch.setattr(
        "src.notifier.telegram_commands.moving_average",
        lambda db, repo_id, now: 75.0,
    )
    db = MagicMock()
    user = MagicMock(id=1)
    out = _handle_stats(db, user, repo_name="owner/repo", language="en")
    assert "Analyses (7d): 5" in out
    assert "Average score: 80.5" in out
    assert "vs 7d moving avg" in out


def test_handle_settings_no_repos_korean():
    """_handle_settings — 리포 0개 시 한국어 응답."""
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    user = MagicMock(id=1)
    out = _handle_settings(db, user, language="ko")
    assert "등록된 리포지토리가 없습니다" in out


def test_handle_settings_with_repos_japanese():
    """_handle_settings — 리포 N개 시 일본어 헤더 + 리스트."""
    db = MagicMock()
    repo1 = MagicMock(full_name="owner/repo1")
    repo2 = MagicMock(full_name="owner/repo2")
    db.scalars.return_value.all.return_value = [repo1, repo2]
    user = MagicMock(id=1)
    out = _handle_settings(db, user, language="ja")
    assert "登録されたリポジトリ" in out
    assert "owner/repo1" in out
    assert "owner/repo2" in out


def test_handle_connect_no_otp_default_locale(monkeypatch):
    """_handle_connect — OTP 빈 값 시 default_locale 사용법."""
    from src.notifier.telegram_commands import _handle_connect
    db = MagicMock()
    out = _handle_connect(db, "tg_user_123", "")
    # default_locale = 'en' or 'ko' or 'ja'
    assert ("Usage:" in out) or ("사용법:" in out) or ("使い方:" in out)


def test_handle_connect_invalid_otp(monkeypatch):
    """_handle_connect — OTP 잘못/만료 시 default_locale 응답."""
    from src.notifier.telegram_commands import _handle_connect
    monkeypatch.setattr(
        "src.notifier.telegram_commands.user_repo.find_by_otp",
        lambda db, otp: None,
    )
    db = MagicMock()
    out = _handle_connect(db, "tg_user_123", "123456")
    assert ("Invalid or expired OTP" in out) or ("OTP가 잘못" in out) or ("OTP が無効" in out)


def test_handle_connect_success_uses_user_language(monkeypatch):
    """_handle_connect — 성공 시 연결 User.preferred_language 사용 (즉시 다국어 활성화)."""
    from src.notifier.telegram_commands import _handle_connect
    user = MagicMock(
        id=42, preferred_language="ja",
        display_name="Tanaka", github_login="tanaka",
    )
    monkeypatch.setattr(
        "src.notifier.telegram_commands.user_repo.find_by_otp",
        lambda db, otp: user,
    )
    monkeypatch.setattr(
        "src.notifier.telegram_commands.user_repo.set_telegram_user_id",
        lambda db, user_id, tid: None,
    )
    db = MagicMock()
    out = _handle_connect(db, "tg_user_123", "123456")
    assert "Tanaka さんのアカウントが連携されました" in out
