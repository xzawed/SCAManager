"""http_client — lifespan 싱글톤 테스트."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest

from src.shared import http_client


@pytest.mark.asyncio
async def test_get_http_client_raises_before_init():
    """init_http_client() 전에 get_http_client() 호출 시 RuntimeError."""
    # 사전 상태 보장 — 다른 테스트가 초기화한 상태를 정리
    await http_client.close_http_client()
    with pytest.raises(RuntimeError, match="not initialized"):
        http_client.get_http_client()


@pytest.mark.asyncio
async def test_init_and_get_returns_async_client():
    """init 후 get 이 AsyncClient 를 반환."""
    import httpx
    await http_client.init_http_client()
    try:
        client = http_client.get_http_client()
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed
    finally:
        await http_client.close_http_client()


@pytest.mark.asyncio
async def test_close_http_client_marks_closed():
    """close 후 client 가 is_closed 상태."""
    await http_client.init_http_client()
    client_before = http_client.get_http_client()
    await http_client.close_http_client()
    assert client_before.is_closed
    # close 이후 get 호출은 RuntimeError
    with pytest.raises(RuntimeError):
        http_client.get_http_client()


@pytest.mark.asyncio
async def test_init_idempotent():
    """init 중복 호출 시에도 동일 client 재사용 (is_closed 면 재생성)."""
    await http_client.close_http_client()
    await http_client.init_http_client()
    first = http_client.get_http_client()
    await http_client.init_http_client()  # 이미 open — 재생성 없음
    second = http_client.get_http_client()
    assert first is second
    await http_client.close_http_client()
