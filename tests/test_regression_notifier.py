"""Phase 3-B Red — src/notifier/telegram.py 의 send_regression_alert 함수 테스트.

async def send_regression_alert(*, bot_token, chat_id, repo_name, commit_sha,
                                 current_score, regression_info) -> None
- telegram_post_message 공용 헬퍼 사용 (httpx 직접 금지)
- HTML parse_mode, ⚠️📉 이모지로 일반 알림과 구분
- type=="drop" → "급락", type=="f_entry" → "F등급"
현재 send_regression_alert 함수가 존재하지 않으므로 import/attr 단계에서 Red.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch

# conftest와 동일한 env setdefault
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")


async def test_send_regression_alert_uses_telegram_post_message():
    # telegram_post_message 공용 헬퍼가 호출되는지 확인 (httpx 직접 호출 금지)
    from src.notifier.telegram import send_regression_alert

    with patch("src.notifier.telegram.telegram_post_message",
               new_callable=AsyncMock) as mock_post:
        await send_regression_alert(
            bot_token="123:ABC",
            chat_id="-100123",
            repo_name="owner/repo",
            commit_sha="abc1234def",
            current_score=60,
            regression_info={"type": "drop", "delta": 20, "baseline": 85.0},
        )
    mock_post.assert_called_once()


async def test_send_regression_alert_drop_message():
    # type=="drop"이면 메시지에 "급락"·"20"·"85.0" 포함
    from src.notifier.telegram import send_regression_alert

    captured = {}

    async def fake_post(bot_token, chat_id, payload):
        captured["payload"] = payload

    with patch("src.notifier.telegram.telegram_post_message", side_effect=fake_post):
        await send_regression_alert(
            bot_token="123:ABC",
            chat_id="-100123",
            repo_name="owner/repo",
            commit_sha="abc1234def",
            current_score=65,
            regression_info={"type": "drop", "delta": 20, "baseline": 85.0},
        )

    text = captured["payload"]["text"]
    assert "급락" in text
    assert "20" in text
    assert "85.0" in text
    # HTML parse_mode 필수
    assert captured["payload"].get("parse_mode") == "HTML"


async def test_send_regression_alert_f_entry_message():
    # type=="f_entry" 이면 메시지에 "F등급" 문구 포함
    from src.notifier.telegram import send_regression_alert

    captured = {}

    async def fake_post(bot_token, chat_id, payload):
        captured["payload"] = payload

    with patch("src.notifier.telegram.telegram_post_message", side_effect=fake_post):
        await send_regression_alert(
            bot_token="123:ABC",
            chat_id="-100123",
            repo_name="owner/repo",
            commit_sha="abc1234def",
            current_score=40,
            regression_info={"type": "f_entry", "delta": 8, "baseline": 48.0},
        )

    text = captured["payload"]["text"]
    assert "F등급" in text


async def test_send_regression_alert_includes_repo_and_sha():
    # 메시지에 repo_name과 commit_sha 앞 7자 포함
    from src.notifier.telegram import send_regression_alert

    captured = {}

    async def fake_post(bot_token, chat_id, payload):
        captured["payload"] = payload

    with patch("src.notifier.telegram.telegram_post_message", side_effect=fake_post):
        await send_regression_alert(
            bot_token="123:ABC",
            chat_id="-100123",
            repo_name="owner/repo",
            commit_sha="abc1234def9999",
            current_score=50,
            regression_info={"type": "drop", "delta": 25, "baseline": 75.0},
        )

    text = captured["payload"]["text"]
    assert "owner/repo" in text
    # 앞 7자 포함, 8자 이후는 포함되지 않도록 느슨히 검증 (7자는 반드시 존재)
    assert "abc1234" in text


async def test_send_regression_alert_html_escapes_repo():
    # repo_name에 악의적 HTML 태그가 들어와도 이스케이프되어 원문 태그는 메시지에 나타나지 않는다
    from src.notifier.telegram import send_regression_alert

    captured = {}

    async def fake_post(bot_token, chat_id, payload):
        captured["payload"] = payload

    with patch("src.notifier.telegram.telegram_post_message", side_effect=fake_post):
        await send_regression_alert(
            bot_token="123:ABC",
            chat_id="-100123",
            repo_name="owner/<script>alert(1)</script>",
            commit_sha="abc1234",
            current_score=50,
            regression_info={"type": "drop", "delta": 25, "baseline": 75.0},
        )

    text = captured["payload"]["text"]
    # 이스케이프된 결과: "&lt;script&gt;" 가 보여야 하고, 원본 "<script>" 는 없어야 함
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


async def test_send_regression_alert_keyword_only():
    # positional 호출 시 TypeError — keyword-only 강제 검증
    from src.notifier.telegram import send_regression_alert

    with pytest.raises(TypeError):
        await send_regression_alert(
            "123:ABC", "-100123", "owner/repo", "abc1234", 60,
            {"type": "drop", "delta": 20, "baseline": 85.0},
        )
