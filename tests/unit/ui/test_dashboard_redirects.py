"""Phase 1 PR 5 — /insights → /dashboard 301 redirect 회귀 가드.

이전 URL (`/insights`, `/insights/me`) 북마크 사용자 보호를 위해 영구 리다이렉트.
Permanent redirect (301) preserves bookmarks of users who saved /insights URLs.

검증:
- GET /insights → 301 Location: /dashboard
- GET /insights/me → 301 Location: /dashboard
- 쿼리 파라미터 (예: /insights?days=30) 도 보존되어 redirect

base.html nav 링크 갱신 별도 테스트 (test_router.py 통합).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app


def test_insights_redirects_to_dashboard():
    """GET /insights → 301 Location /dashboard."""
    client = TestClient(app, follow_redirects=False)
    response = client.get("/insights")
    assert response.status_code == 301, (
        f"301 영구 리다이렉트 기대, 실제: {response.status_code}"
    )
    assert response.headers.get("location") == "/dashboard", (
        f"Location 헤더 /dashboard 기대, 실제: {response.headers.get('location')}"
    )


def test_insights_me_redirects_to_dashboard():
    """GET /insights/me → 301 Location /dashboard."""
    client = TestClient(app, follow_redirects=False)
    response = client.get("/insights/me")
    assert response.status_code == 301, (
        f"301 영구 리다이렉트 기대, 실제: {response.status_code}"
    )
    assert response.headers.get("location") == "/dashboard", (
        f"Location 헤더 /dashboard 기대, 실제: {response.headers.get('location')}"
    )


def test_insights_preserves_days_query_param():
    """GET /insights?days=30 → 301 Location /dashboard?days=30 (쿼리 파라미터 보존).

    북마크 사용자가 days=30 으로 저장한 URL 도 새 페이지에서 동일 days 적용.
    """
    client = TestClient(app, follow_redirects=False)
    response = client.get("/insights?days=30")
    assert response.status_code == 301
    location = response.headers.get("location", "")
    assert location.startswith("/dashboard"), (
        f"Location /dashboard 시작 기대, 실제: {location}"
    )
    # 쿼리 파라미터 보존
    assert "days=30" in location, f"days=30 보존 실패, 실제: {location}"
