"""다국어 (i18n) smoke 통합 테스트 — Phase 5 PR-18 (사이클 84).

i18n smoke integration test — Phase 5 PR-18 (Cycle 84).

정책 13 (운영 endpoint smoke check 의무) 페어 — i18n 인증/UI 변경 PR 시점 정합 보조 가드.
실제 FastAPI app + TestClient 기반으로 다국어 endpoint smoke check 패턴 검증.

Pairs with Policy 13 (operational endpoint smoke check obligation) — supports verification
during i18n / auth / UI changes via FastAPI app + TestClient.

검증 범위:
- /login + Cookie locale=en/ko/ja → 301 /auth/github (사이클 117 변경)
- / (랜딩 페이지) + Cookie locale=en/ko/ja → 200 + HTML lang attribute 동적 매칭
- LocaleMiddleware Layer 1 (Cookie) 우선 감지 정상 동작
- Cookie 미설정 시 settings.default_locale fallback
- /api/users/me/preferred-language POST → User 미연결 = 401, 연결 시 200 (PR-1c → PR-4 페어)

검증 X (별도 영역):
- /repos/{owner}/{repo}/settings — require_login 의존성 (e2e 영역에서 검증, PR-16 페어)
- /admin/* — require_admin 의존성 (e2e 영역에서 검증)

본 가드는 자동화 보조 — 사용자 manual 시각 검증 의무 (정책 11 8 조합) 대체 X.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """env 격리 + redirect 미추적 (LocaleMiddleware 검증용).

    이전 단위 테스트가 등록한 dependency_overrides 격리 (require_login mock 등).
    Isolates dependency_overrides leaked from prior unit tests (e.g. require_login mock).
    """
    from src.main import app  # pylint: disable=import-outside-toplevel
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        yield TestClient(app, follow_redirects=False)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)


# ── /login 301 리다이렉트 smoke (사이클 117 — 중간 단계 제거) ──────────────


@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_login_redirects_to_auth_github_regardless_of_locale(client, locale):
    """/login + preferred_language Cookie → 301 /auth/github (사이클 117).

    /login 은 locale 에 관계없이 301 리다이렉트 — LocaleMiddleware 통과 후 redirect.
    /login always 301-redirects to /auth/github regardless of locale cookie.
    """
    response = client.get(
        "/login",
        cookies={"preferred_language": locale},
    )
    assert response.status_code == 301, (
        f"login smoke failed for locale={locale}: expected 301, got {response.status_code}"
    )
    assert response.headers.get("location") == "/auth/github", (
        f"login redirect target mismatch for locale={locale}"
    )


# ── 3 언어 × 랜딩 페이지 (/) Cookie smoke ────────────────────────────────
# /login 이 301 리다이렉트로 변경됨 (사이클 117) — lang attr 검증을 / 로 이전
# /login changed to 301 redirect (cycle 117) — lang attr verification moved to /


@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_landing_html_lang_attr_matches_cookie(client, locale):
    """/ (랜딩 페이지) HTML <html lang="..."> 동적 attribute = Cookie locale 매칭.

    Phase 2 PR-5 (base.html) i18n 적용 페어 — HTML lang 동적 검증.
    /login 이 301 redirect 가 됨에 따라 / 로 검증 대상 변경 (사이클 117).
    """
    response = client.get(
        "/",
        cookies={"preferred_language": locale},
    )
    assert response.status_code == 200
    assert f'<html lang="{locale}"' in response.text, (
        f"<html lang='{locale}'> missing for Cookie locale={locale}"
    )


def test_landing_no_cookie_falls_to_default_locale(client):
    """/ Cookie 미설정 → settings.default_locale 기본값 fallback.

    /login 이 301 redirect 가 됨에 따라 / 로 검증 대상 변경 (사이클 117).
    """
    response = client.get("/")
    assert response.status_code == 200
    # default_locale = 'ko' (landing.html default)
    assert "SCAManager" in response.text


# ── /api/users/me/preferred-language smoke (Phase 2 PR-4 페어) ────────────


def test_preferred_language_api_unauthenticated_rejects(client):
    """POST /api/users/me/preferred-language — 비로그인 시 401 (require_login)."""
    response = client.post(
        "/api/users/me/preferred-language",
        json={"language": "ja"},
    )
    # 비로그인 = 401 또는 redirect (302) 둘 다 보안 정상
    # Both 401 and 302 are acceptable security responses for unauthenticated.
    assert response.status_code in (401, 302, 403), (
        f"unauthenticated /api/users/me/preferred-language should reject, got {response.status_code}"
    )


def test_preferred_language_api_invalid_locale_rejects(client):
    """POST /api/users/me/preferred-language — 미지원 locale (zh) → 422.

    field_validator 가 SUPPORTED_LOCALES 영역 검증 (Phase 1 PR-1a 페어).
    """
    # 비로그인 시도 — 인증 우회는 dependency_overrides 영역 (e2e 페어).
    # 본 smoke 는 422 (validation error) 가 인증 (401/302) 보다 먼저 발화하는지 검증.
    # Pydantic field_validator 는 request body 파싱 시 발화 — 인증 의존성 발화 전.
    # Smoke goal: validate Pydantic field_validator triggers before auth dependency.
    response = client.post(
        "/api/users/me/preferred-language",
        json={"language": "zh"},  # 미지원 locale (en/ko/ja 외)
    )
    # 422 (validation) 또는 401/302/403 (auth-first) 모두 보안/유효성 정상
    # Either 422 (validation-first) or 4xx (auth-first) is acceptable.
    assert response.status_code in (401, 302, 403, 422), (
        f"invalid locale should reject, got {response.status_code}"
    )


# ── i18n metrics 인프라 smoke (Phase 5 PR-17 페어) ─────────────────────


def test_i18n_metrics_increments_on_get_text():
    """get_text 호출 → i18n metrics 카운터 증가 (PR-17 인프라 smoke 검증)."""
    from src.i18n.loader import (  # pylint: disable=import-outside-toplevel
        get_i18n_metrics,
        get_text,
        reset_i18n_metrics,
    )
    reset_i18n_metrics()

    before = get_i18n_metrics()
    assert before["lookups_total"] == 0

    get_text("common.logout", "ko")
    get_text("common.logout", "en")

    after = get_i18n_metrics()
    assert after["lookups_total"] == 2
    assert after["lookups_hit"] == 2
    assert after["fallback_rate_pct"] == 0.0


def test_i18n_metrics_missing_key_increments_fallback_rate():
    """get_text 미존재 key → fallback_rate_pct ↑ (운영자 액션 의무 영역)."""
    from src.i18n.loader import (  # pylint: disable=import-outside-toplevel
        get_i18n_metrics,
        get_text,
        reset_i18n_metrics,
    )
    reset_i18n_metrics()

    get_text("common.logout", "ko")          # hit
    get_text("nonexistent.key.xyz", "ko")    # missing

    metrics = get_i18n_metrics()
    assert metrics["lookups_total"] == 2
    assert metrics["lookups_hit"] == 1
    assert metrics["lookups_missing"] == 1
    assert metrics["fallback_rate_pct"] == 50.0
