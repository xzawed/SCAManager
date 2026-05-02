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
    """`from src.services.analytics_service import top_issues` 가 ImportError 발생.

    호출처가 새로 추가되는 것을 import 단계에서 차단.
    """
    with pytest.raises(ImportError):
        # pylint: disable=import-outside-toplevel,no-name-in-module,unused-import
        from src.services.analytics_service import top_issues  # noqa: F401  # type: ignore[attr-defined]
