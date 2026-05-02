"""analytics_service 폐기 함수 회귀 가드.
Regression guard for deprecated analytics_service functions.

Phase 1 PR 1 (top_issues 폐기) 시점부터 추가. 향후 PR 2 (author_trend),
PR 3 (repo_comparison + leaderboard) 폐기 시 동일 패턴으로 가드 항목 추가.

원칙:
- 폐기된 함수는 모듈에서 import 불가 — 실수 부활 차단
- /insights/me, /insights compare 라우트의 호출처가 함께 정리되어 있음을 검증

Background:
Phase 1 cleanup of analytics_service follows the user-approved deprecation plan
(see docs/design/2026-05-02-insight-dashboard-rework.md §6.3). This module is
the single source of regression guards for those removals.
"""
from __future__ import annotations

import importlib

import pytest


# ─── PR 1: top_issues 폐기 ──────────────────────────────────────────────────


def test_top_issues_function_removed() -> None:
    """analytics_service.top_issues 가 모듈에서 제거되었음을 검증.

    실수로 함수가 다시 추가되거나 git revert 로 부활하면 본 테스트가 차단.
    """
    import src.services.analytics_service as svc  # pylint: disable=import-outside-toplevel

    assert not hasattr(svc, "top_issues"), (
        "top_issues 는 Phase 1 PR 1 에서 폐기됨 — "
        "재도입 금지. 부활 필요 시 사용자 결정 (2026-05-02 폐기 확정) 재논의."
    )


def test_top_issues_import_raises() -> None:
    """deprecated symbol 접근 시 실패하는지 검증.

    호출처가 새로 추가되는 것을 import/attribute 접근 단계에서 차단.
    """
    with pytest.raises(AttributeError):
        svc = importlib.import_module("src.services.analytics_service")
        _ = svc.top_issues


# ─── PR 2: author_trend + /insights/me 페이지 + GET /api/insights/authors/.../trend 폐기 ──


def test_author_trend_function_removed() -> None:
    """analytics_service.author_trend 가 모듈에서 제거되었음을 검증.

    /insights/me 페이지 (개인 추세) + REST API 엔드포인트 모두 폐기 — 부활 차단.
    """
    import src.services.analytics_service as svc  # pylint: disable=import-outside-toplevel

    assert not hasattr(svc, "author_trend"), (
        "author_trend 는 Phase 1 PR 2 에서 폐기됨 — "
        "재도입 금지. 신규 dashboard (/dashboard, PR 4) 와 시그니처 다름."
    )


def test_author_trend_import_raises() -> None:
    """deprecated symbol 접근 시 실패하는지 검증."""
    with pytest.raises(AttributeError):
        svc = importlib.import_module("src.services.analytics_service")
        _ = svc.author_trend


def test_insights_me_route_removed() -> None:
    """GET /insights/me 라우트가 폐기되어 404 응답을 반환해야 한다.

    페이지 자체와 라우트 함수 (`insights_me`) + 헬퍼 (`_compute_kpi`) 폐기.
    `/dashboard` (PR 4) 가 후속.
    """
    # pylint: disable=import-outside-toplevel
    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app)
    response = client.get("/insights/me")
    assert response.status_code == 404, (
        f"/insights/me 라우트는 폐기됨 — 404 기대, 실제: {response.status_code}"
    )


def test_get_author_trend_api_removed() -> None:
    """GET /api/insights/authors/{login}/trend 엔드포인트가 폐기되어야 한다.

    require_api_key 인증 거치기 전 라우트 자체가 없으므로 404 (또는 401 — 인증 우선 확인).
    핵심: 200 이 아니면 OK (엔드포인트 부재).
    """
    # pylint: disable=import-outside-toplevel
    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app)
    # API key 없이 호출 — 라우트 자체가 폐기되어 401 또는 404 반환되어야 함
    response = client.get("/api/insights/authors/alice/trend")
    assert response.status_code != 200, (
        f"/api/insights/authors/{{login}}/trend 라우트는 폐기됨 — "
        f"non-200 기대, 실제: {response.status_code}"
    )
