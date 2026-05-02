"""OAuth flow + 운영 endpoint smoke check 통합 테스트 — 정책 13 자동화.

P0 OAuth 사고 (2026-05-02) 후속 + 정책 13 (운영 endpoint smoke check 의무) 자동화.

unit 레벨 (`tests/unit/auth/test_oauth_redirect_uri_smoke.py`) 가드는 mock 기반.
본 통합 테스트는 실제 FastAPI app + TestClient 기반으로 운영 endpoint smoke check 패턴 검증.

검증 범위:
- /health → 200 (liveness)
- /auth/github → 302 + Location 헤더의 redirect_uri 정합성
- /auth/callback → state 검증 거부 (직접 호출 시 401 또는 4xx)
- /webhooks/github → 서명 누락 401
- /insights → /dashboard 301 redirect
- /insights/me → /dashboard 301 redirect
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from urllib.parse import urlparse, parse_qs

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """conftest 의 client fixture 와 별개 — env 격리 + redirect 미추적."""
    from src.main import app  # pylint: disable=import-outside-toplevel
    return TestClient(app, follow_redirects=False)


@pytest.fixture()
def client_follow():
    """301/302 redirect 추적용 client."""
    from src.main import app  # pylint: disable=import-outside-toplevel
    return TestClient(app, follow_redirects=True)


# ─── 정책 13 — 3-endpoint smoke check ──────────────────────────────────


class TestSmokeCheckMinimal:
    """매 사이클 종료 시 의무 3-endpoint smoke check (정책 13)."""

    def test_health_returns_200(self, client):
        """GET /health → 200 (liveness probe)."""
        response = client.get("/health")
        assert response.status_code == 200, (
            f"/health 5xx — SCAManager 프로세스 자체 문제 위험. status={response.status_code}"
        )

    def test_auth_github_returns_302(self, client):
        """GET /auth/github → 302 (GitHub OAuth 동의 화면 redirect)."""
        response = client.get("/auth/github")
        assert response.status_code == 302, (
            f"/auth/github 302 기대, 실제: {response.status_code}. "
            "OAuth flow 깨짐 — P0 사고 위험."
        )

    def test_login_page_returns_200_or_302(self, client):
        """GET /login → 200 (페이지 표시) 또는 302 (로그인 상태에서 / 로 redirect).

        둘 다 정상 — 5xx 만 P0.
        """
        response = client.get("/login")
        assert response.status_code in (200, 302), (
            f"/login 5xx: {response.status_code}"
        )


# ─── 정책 11 강화 — 인증 flow 4 endpoint ────────────────────────────────


class TestAuthFlowEndpoints:
    """인증 flow 4 endpoint 종단간 검증 (정책 11 강화)."""

    def test_auth_github_redirect_uri_matches_app_base_url(self, client):
        """GET /auth/github 의 Location 헤더 redirect_uri 정합성.

        P0 OAuth 사고 (2026-05-02) 직접 회귀 가드 — APP_BASE_URL 변경 또는
        라우트 name 변경 시 즉시 fail.
        """
        response = client.get("/auth/github")
        location = response.headers.get("location", "")
        assert "github.com/login/oauth/authorize" in location, (
            f"GitHub OAuth URL 미검출: {location}"
        )

        # redirect_uri 파라미터 추출
        parsed = urlparse(location)
        query = parse_qs(parsed.query)
        redirect_uri_list = query.get("redirect_uri", [])
        assert len(redirect_uri_list) == 1, "redirect_uri 파라미터 부재 또는 중복"
        redirect_uri = redirect_uri_list[0]

        # /auth/callback 으로 끝나는지 (정확한 도메인은 환경 의존)
        assert redirect_uri.endswith("/auth/callback"), (
            f"redirect_uri /auth/callback 미종료: {redirect_uri}"
        )
        # https:// 또는 http://testserver — 둘 다 허용 (테스트 환경)
        assert redirect_uri.startswith(("http://", "https://")), (
            f"redirect_uri scheme 누락: {redirect_uri}"
        )

    def test_auth_callback_rejects_direct_call(self):
        """GET /auth/callback 직접 호출 시 거부 (state 검증 실패).

        4xx / 5xx / authlib MismatchingStateError exception 모두 정상 거부 — 200 만 P0
        (인증 우회 위험). raise_server_exceptions=False 로 exception 도 5xx 응답으로 변환.
        """
        # pylint: disable=import-outside-toplevel
        from src.main import app
        client = TestClient(app, follow_redirects=False, raise_server_exceptions=False)
        response = client.get("/auth/callback")
        assert response.status_code != 200, (
            f"/auth/callback 직접 호출 200 = 인증 우회 위험. status={response.status_code}"
        )
        # 정상 거부: 4xx (state 검증 실패) 또는 5xx (Authlib MismatchingStateError 처리되지 않음)
        assert response.status_code >= 400, (
            f"4xx/5xx 거부 기대, 실제: {response.status_code}"
        )

    def test_webhooks_github_rejects_missing_signature(self, client):
        """POST /webhooks/github 서명 헤더 누락 시 401 (HMAC 검증)."""
        response = client.post(
            "/webhooks/github",
            content=b'{"test": "no-sig"}',
            headers={"Content-Type": "application/json", "X-GitHub-Event": "push"},
        )
        assert response.status_code == 401, (
            f"서명 누락 시 401 기대 (정상 거부), 실제: {response.status_code}"
        )


# ─── /insights → /dashboard 301 redirect (Phase 1 PR 5) ──────────────


class TestInsightsRedirect:
    """폐기된 /insights* 라우트의 301 redirect 정합성 (Phase 1 PR 5)."""

    def test_insights_redirects_to_dashboard(self, client):
        """GET /insights → 301 + Location: /dashboard."""
        response = client.get("/insights")
        assert response.status_code == 301
        assert response.headers.get("location") == "/dashboard"

    def test_insights_me_redirects_to_dashboard(self, client):
        """GET /insights/me → 301 + Location: /dashboard."""
        response = client.get("/insights/me")
        assert response.status_code == 301
        assert response.headers.get("location") == "/dashboard"

    def test_insights_query_params_preserved(self, client):
        """GET /insights?days=30 → /dashboard?days=30 (쿼리 파라미터 보존)."""
        response = client.get("/insights?days=30")
        location = response.headers.get("location", "")
        assert location.startswith("/dashboard")
        assert "days=30" in location, f"쿼리 파라미터 손실: {location}"


# ─── 정책 13 강화 후속 (P1 권장) ─────────────────────────────────────


class TestPolicyThirteenAutomation:
    """정책 13 (운영 endpoint smoke check) 의 자동화 검증 메타-테스트.

    회고 P0 #5 검증 환류 갭 해소 — Phase 종료 시 본 모듈 실행으로 운영 정합성 자동 확인.
    """

    def test_all_critical_endpoints_under_3_seconds(self, client):
        """3-endpoint smoke check 가 3초 이내 완료 (성능 상한)."""
        import time  # pylint: disable=import-outside-toplevel
        start = time.monotonic()
        for endpoint in ("/health", "/auth/github", "/login"):
            client.get(endpoint)
        elapsed = time.monotonic() - start
        assert elapsed < 3.0, (
            f"3-endpoint smoke check {elapsed:.2f}s — 운영 응답 성능 회귀"
        )
