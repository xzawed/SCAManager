"""OAuth redirect_uri 정합성 회귀 가드 — P0 사고 (2026-05-02) 후속.

본 사고: SCAManager 측 코드/환경변수 정상 + GitHub OAuth App callback URL mismatch.
근본 회고: OAuth flow 종단간 회귀 가드 0건 → 사고 가시화 부재.

본 모듈 = 정책 11 강화 (인증 flow 검증 추가) + 정책 13 (smoke check 의무) 의 자동화 가드.

검증:
- APP_BASE_URL 설정 시 redirect_uri 정확성 (https + /auth/callback + trailing slash 없음)
- APP_BASE_URL 미설정 시 fallback 동작 (request.url_for)
- redirect_uri URL 인코딩 정합성 (& 분할 가능)
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """conftest.py 의 client fixture 와 별개 — env 격리."""
    from src.main import app  # pylint: disable=import-outside-toplevel
    return TestClient(app, follow_redirects=False)


# ─── APP_BASE_URL 설정 시 redirect_uri 정확성 ─────────────────────────


class TestRedirectUriCorrectness:
    """SCAManager 가 GitHub 으로 보내는 redirect_uri 정확성 검증.

    P0 사고 (2026-05-02) 의 직접 회귀 가드 — APP_BASE_URL 변경 또는 라우트
    이름 (`auth_callback`) 변경 시 즉시 fail.
    """

    def test_redirect_uri_uses_app_base_url_when_set(self, client):
        """APP_BASE_URL 설정 시 redirect_uri = APP_BASE_URL + /auth/callback."""
        with patch("src.auth.github.settings") as mock_settings, \
             patch("src.auth.github.oauth.github.authorize_redirect", new_callable=AsyncMock) as mock_redirect:
            mock_settings.app_base_url = "https://scamanager-production.up.railway.app"
            from fastapi.responses import RedirectResponse  # pylint: disable=import-outside-toplevel
            mock_redirect.return_value = RedirectResponse(url="https://github.com/login/oauth/authorize?...", status_code=302)
            client.get("/auth/github")

        mock_redirect.assert_called_once()
        # authorize_redirect(request, redirect_uri) — 두 번째 인자 검증
        args = mock_redirect.call_args[0]
        assert len(args) >= 2
        redirect_uri = args[1]
        assert redirect_uri == "https://scamanager-production.up.railway.app/auth/callback", (
            f"P0 회귀 — redirect_uri 잘못됨: {redirect_uri}"
        )

    def test_redirect_uri_strips_trailing_slash_from_app_base_url(self, client):
        """APP_BASE_URL 에 trailing slash 가 있어도 정상 처리 (/auth/callback 한 번만)."""
        with patch("src.auth.github.settings") as mock_settings, \
             patch("src.auth.github.oauth.github.authorize_redirect", new_callable=AsyncMock) as mock_redirect:
            mock_settings.app_base_url = "https://scamanager-production.up.railway.app/"
            from fastapi.responses import RedirectResponse  # pylint: disable=import-outside-toplevel
            mock_redirect.return_value = RedirectResponse(url="https://...", status_code=302)
            client.get("/auth/github")

        redirect_uri = mock_redirect.call_args[0][1]
        # trailing slash 정규화 → /auth/callback 1번만 (// 없음)
        assert redirect_uri == "https://scamanager-production.up.railway.app/auth/callback"
        assert "//auth" not in redirect_uri, (
            f"trailing slash 처리 회귀 — double slash 발생: {redirect_uri}"
        )

    def test_redirect_uri_falls_back_to_url_for_when_app_base_url_empty(self, client):
        """APP_BASE_URL 미설정 시 request.url_for('auth_callback') fallback.

        주의: fallback 은 http:// 가능 — Railway 환경에서는 APP_BASE_URL 필수
        (CLAUDE.md L298 명시).
        """
        with patch("src.auth.github.settings") as mock_settings, \
             patch("src.auth.github.oauth.github.authorize_redirect", new_callable=AsyncMock) as mock_redirect:
            mock_settings.app_base_url = ""  # 미설정
            from fastapi.responses import RedirectResponse  # pylint: disable=import-outside-toplevel
            mock_redirect.return_value = RedirectResponse(url="https://...", status_code=302)
            client.get("/auth/github")

        redirect_uri = mock_redirect.call_args[0][1]
        # fallback = request.url_for("auth_callback") — TestClient 기준 http://testserver/auth/callback
        assert "/auth/callback" in redirect_uri
        # APP_BASE_URL 부재 시 url_for 사용 → testserver 또는 http:// 가능
        # (Railway 운영에서는 APP_BASE_URL 필수 — 본 테스트는 fallback 동작만 검증)


# ─── redirect_uri 라우트명 (auth_callback) 회귀 가드 ──────────────────


def test_auth_callback_route_name_unchanged():
    """`@router.get("/auth/callback", name="auth_callback")` name 변경 시 url_for fallback 깨짐.

    P0 회귀 가드 — 라우트 함수 rename 또는 name 인자 변경 시 즉시 fail.
    """
    from src.main import app  # pylint: disable=import-outside-toplevel

    callback_routes = [
        r for r in app.routes
        if hasattr(r, "name") and r.name == "auth_callback"
    ]
    assert len(callback_routes) == 1, (
        f"auth_callback 라우트 name 변경됨 — url_for fallback 깨짐. "
        f"발견된 라우트: {[r.name for r in app.routes if hasattr(r, 'name')]}"
    )
    # 경로도 검증
    assert callback_routes[0].path == "/auth/callback", (
        f"auth_callback 경로 변경됨: {callback_routes[0].path} (기대: /auth/callback)"
    )
