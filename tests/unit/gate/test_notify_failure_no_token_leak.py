"""engine._notify_merge_failure 가 실패 로그에 bot-token URL 을 남기지 않는지 검증 (종합감사 P2).

engine._notify_merge_failure must not leak the bot-token URL in its failure log (comprehensive P2).

🔴 계층1 근본통제 (security.md §시크릿-in-URL): httpx 예외 메시지는 요청 URL 전문(`api.telegram.org/
bot<TOKEN>/...`)을 담는다. 형제 notify 함수(_notify_merge_deferred)는 전부 `type(exc).__name__` 만
로깅하는데 _notify_merge_failure 만 raw exc 를 로깅해 계층1 을 위반했다. 계층2 리댁션 필터는 backstop
일 뿐이므로(호출처가 본체) 이 테스트는 필터를 우회하는 caplog 로 **호출처 행동**을 직접 관측한다.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position,protected-access
import logging
from unittest.mock import AsyncMock, patch

import httpx

import src.gate.engine as engine


async def test_notify_merge_failure_logs_type_name_not_token(caplog):
    """telegram_post_message 가 토큰 URL 을 담은 httpx 예외를 던져도 로그엔 타입명만 남는다.
    Even when the send raises an httpx error embedding the token URL, only the type name is logged.
    """
    leak_url = "https://api.telegram.org/botTOKENTAIL777/sendMessage"
    err = httpx.ConnectError(f"Connection failed for url '{leak_url}'")

    with patch.object(engine, "telegram_post_message", new=AsyncMock(side_effect=err)):
        with caplog.at_level(logging.WARNING, logger="src.gate.engine"):
            await engine._notify_merge_failure(
                repo_name="owner/repo", pr_number=7, score=50, threshold=70,
                reason="ci_failed", advice="check CI", chat_id="-100999",
            )

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "TOKENTAIL777" not in logged, (
        f"봇 토큰이 merge-failure 로그에 raw exc 로 남았다 — 계층1 위반.\n로그: {logged!r}"
    )
    assert "ConnectError" in logged, "예외 타입명이 로깅되지 않았다 — 진단 관측 소실"
