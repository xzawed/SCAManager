"""LocaleMiddleware 단위 테스트 (Phase 1 PR-1b).

5단계 locale 감지 우선순위 + kill-switch + websocket scope passthrough 검증.
"""
from unittest.mock import patch, AsyncMock

import pytest

from src.middleware.locale import LocaleMiddleware


async def _noop_app(scope, receive, send):
    """ASGI no-op app for middleware testing."""


def _make_scope(headers: list | None = None, scope_type: str = "http") -> dict:
    """Test scope builder."""
    return {
        "type": scope_type,
        "headers": headers or [],
    }


@pytest.fixture
def middleware():
    """LocaleMiddleware instance with no-op app."""
    return LocaleMiddleware(_noop_app)


@pytest.mark.asyncio
async def test_cookie_locale_priority(middleware):
    """1순위: Cookie `preferred_language=ja` → ja 감지."""
    scope = _make_scope([(b"cookie", b"preferred_language=ja")])
    await middleware(scope, AsyncMock(), AsyncMock())
    assert scope["state"]["locale"] == "ja"


@pytest.mark.asyncio
async def test_cookie_unsupported_falls_through(middleware):
    """Cookie 미지원 locale (예: zh) → Accept-Language 또는 default fallback."""
    scope = _make_scope([
        (b"cookie", b"preferred_language=zh"),  # 미지원
        (b"accept-language", b"ko,en;q=0.9"),
    ])
    await middleware(scope, AsyncMock(), AsyncMock())
    # Cookie skip → Accept-Language → ko
    assert scope["state"]["locale"] == "ko"


@pytest.mark.asyncio
async def test_accept_language_q_weight_parsing(middleware):
    """2순위: Accept-Language q-weight 파싱 (ko;q=0.9 > en;q=0.8 > ja;q=0.7)."""
    scope = _make_scope([(b"accept-language", b"ja;q=0.7,ko;q=0.9,en;q=0.8")])
    await middleware(scope, AsyncMock(), AsyncMock())
    # ko (0.9) > en (0.8) > ja (0.7)
    assert scope["state"]["locale"] == "ko"


@pytest.mark.asyncio
async def test_accept_language_normalization(middleware):
    """Accept-Language `ko-KR` → `ko` 정규화."""
    scope = _make_scope([(b"accept-language", b"ko-KR")])
    await middleware(scope, AsyncMock(), AsyncMock())
    assert scope["state"]["locale"] == "ko"


@pytest.mark.asyncio
async def test_default_locale_when_no_signals(middleware):
    """3순위: 헤더 부재 시 default_locale (en) 적용."""
    scope = _make_scope([])
    await middleware(scope, AsyncMock(), AsyncMock())
    assert scope["state"]["locale"] == "en"


@pytest.mark.asyncio
async def test_websocket_scope_passthrough(middleware):
    """WebSocket scope → state 미주입 (HTTP 만 처리)."""
    scope = _make_scope([(b"cookie", b"preferred_language=ja")], scope_type="websocket")
    await middleware(scope, AsyncMock(), AsyncMock())
    assert "state" not in scope or "locale" not in scope.get("state", {})


@pytest.mark.asyncio
async def test_kill_switch_disables_detection(middleware):
    """kill-switch (`I18N_DISABLED=1`) → locale_fallback (en) 강제."""
    scope = _make_scope([(b"cookie", b"preferred_language=ja")])
    with patch("src.middleware.locale.is_disabled", return_value=True):
        await middleware(scope, AsyncMock(), AsyncMock())
    # Cookie ja 무시 → fallback en 강제
    assert scope["state"]["locale"] == "en"


@pytest.mark.asyncio
async def test_unsupported_accept_language_fallback(middleware):
    """Accept-Language 미지원 locale (zh) → default fallback."""
    scope = _make_scope([(b"accept-language", b"zh-CN,fr;q=0.9")])
    await middleware(scope, AsyncMock(), AsyncMock())
    # zh, fr 모두 미지원 → default_locale "en"
    assert scope["state"]["locale"] == "en"


@pytest.mark.asyncio
async def test_cookie_priority_over_accept_language(middleware):
    """Cookie 가 Accept-Language 보다 우선."""
    scope = _make_scope([
        (b"cookie", b"preferred_language=ja"),
        (b"accept-language", b"ko,en;q=0.9"),
    ])
    await middleware(scope, AsyncMock(), AsyncMock())
    # Cookie ja 우선
    assert scope["state"]["locale"] == "ja"


@pytest.mark.asyncio
async def test_multiple_cookies_correct_extraction(middleware):
    """다중 Cookie 중 preferred_language 만 정확 추출."""
    scope = _make_scope([
        (b"cookie", b"session=abc123; preferred_language=ko; other=xyz")
    ])
    await middleware(scope, AsyncMock(), AsyncMock())
    assert scope["state"]["locale"] == "ko"


@pytest.mark.asyncio
async def test_malformed_accept_language_graceful(middleware):
    """잘못된 q-weight 포맷 → graceful skip."""
    scope = _make_scope([(b"accept-language", b"ko;q=invalid,en;q=0.9")])
    await middleware(scope, AsyncMock(), AsyncMock())
    # ko q=invalid → q=0.0 / en q=0.9 → en 우선
    assert scope["state"]["locale"] == "en"


@pytest.mark.asyncio
async def test_lifespan_scope_passthrough(middleware):
    """Lifespan scope → state 미주입 (HTTP 만 처리)."""
    scope = _make_scope([], scope_type="lifespan")
    await middleware(scope, AsyncMock(), AsyncMock())
    assert "state" not in scope or "locale" not in scope.get("state", {})
