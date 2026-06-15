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

from tests.unit._route_helpers import route_name_count


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
    # fastapi 0.137 `_IncludedRouter`(지연 include)로 app.routes 가 평탄화되지 않으므로,
    # (1) name 이 정확히 1개(중복/부재 아님)인지 `route_name_count` 로 확인하고,
    # (2) url_for fallback 이 실제 사용하는 `app.url_path_for` 로 경로를 직접 검증한다.
    # fastapi 0.137 no longer flattens app.routes (lazy `_IncludedRouter`): assert exactly one
    # route owns the name, then assert the path via `app.url_path_for` (what url_for resolves through).
    from src.main import app  # pylint: disable=import-outside-toplevel
    from starlette.routing import NoMatchFound  # pylint: disable=import-outside-toplevel

    count = route_name_count(app, "auth_callback")
    assert count == 1, (
        f"auth_callback name 라우트가 정확히 1개가 아님 (중복/부재) — url_for fallback 위험 (개수: {count})"
    )
    try:
        path = app.url_path_for("auth_callback")
    except NoMatchFound:
        path = None
    assert path == "/auth/callback", (
        f"auth_callback 경로 변경됨 — url_for fallback 깨짐 (현재: {path})"
    )
