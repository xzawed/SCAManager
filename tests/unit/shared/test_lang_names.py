"""src/shared/lang_names.py 모듈 및 서비스 DRY 통합 검증.

Verifies that the shared LANG_NAMES constant exists with correct values,
and that both services import from the shared module rather than defining
their own duplicate dictionaries.
"""
from __future__ import annotations

import pytest


# ─── LANG_NAMES 상수 기본 검증 ──────────────────────────────────────────────


def test_lang_names_importable_from_shared():
    """from src.shared.lang_names import LANG_NAMES가 ImportError 없이 성공해야 함.

    The import must succeed without ImportError — the module does not yet exist (Red).
    """
    from src.shared.lang_names import LANG_NAMES  # noqa: F401


def test_lang_names_has_three_languages():
    """LANG_NAMES에 'ko', 'en', 'ja' 세 키가 모두 존재해야 함.

    LANG_NAMES must contain exactly the three language keys: 'ko', 'en', 'ja'.
    """
    from src.shared.lang_names import LANG_NAMES

    assert "ko" in LANG_NAMES
    assert "en" in LANG_NAMES
    assert "ja" in LANG_NAMES


def test_lang_names_values():
    """각 키의 값이 'Korean', 'English', 'Japanese'여야 함.

    Each key must map to the correct English language name.
    """
    from src.shared.lang_names import LANG_NAMES

    assert LANG_NAMES["ko"] == "Korean"
    assert LANG_NAMES["en"] == "English"
    assert LANG_NAMES["ja"] == "Japanese"


def test_lang_names_is_dict():
    """LANG_NAMES가 dict 타입이어야 함.

    LANG_NAMES must be a plain dict (not a subclass or other mapping).
    """
    from src.shared.lang_names import LANG_NAMES

    assert isinstance(LANG_NAMES, dict)


# ─── repo_insight_service DRY 검증 ─────────────────────────────────────────


def test_repo_insight_service_uses_shared_lang_names():
    """repo_insight_service에 _LANG_NAMES 직접 정의가 없고 shared LANG_NAMES를 사용해야 함.

    After the refactor, _LANG_NAMES must not be a module-level attribute;
    LANG_NAMES (imported from shared) must be present instead.
    """
    import src.services.repo_insight_service as m

    # 구현 전(Red): _LANG_NAMES 직접 정의 존재 → hasattr True → 테스트 실패 예상
    # Pre-implementation (Red): _LANG_NAMES defined directly → test fails.
    assert not hasattr(m, "_LANG_NAMES"), (
        "repo_insight_service still defines _LANG_NAMES directly. "
        "Replace with `from src.shared.lang_names import LANG_NAMES`."
    )

    # 구현 후(Green): shared에서 import한 LANG_NAMES가 모듈 네임스페이스에 있어야 함
    # Post-implementation (Green): LANG_NAMES imported from shared must be present.
    assert hasattr(m, "LANG_NAMES"), (
        "repo_insight_service must import LANG_NAMES from src.shared.lang_names."
    )


def test_repo_insight_service_lang_names_values_match_shared():
    """repo_insight_service의 LANG_NAMES가 shared 모듈과 동일 객체여야 함.

    The LANG_NAMES in repo_insight_service must be the exact same object
    imported from src.shared.lang_names (not a copy with different content).
    """
    import src.services.repo_insight_service as m
    from src.shared.lang_names import LANG_NAMES

    assert m.LANG_NAMES is LANG_NAMES, (
        "repo_insight_service.LANG_NAMES must be the same object as "
        "src.shared.lang_names.LANG_NAMES (identity check)."
    )


# ─── dashboard_service DRY 검증 ────────────────────────────────────────────


def test_dashboard_service_uses_shared_lang_names():
    """dashboard_service에 _DASHBOARD_LANG_NAMES 직접 정의가 없고 shared LANG_NAMES를 사용해야 함.

    After the refactor, _DASHBOARD_LANG_NAMES must not be a module-level attribute;
    LANG_NAMES (imported from shared) must be present instead.
    """
    import src.services.dashboard_service as m

    # 구현 전(Red): _DASHBOARD_LANG_NAMES 직접 정의 존재 → hasattr True → 테스트 실패 예상
    # Pre-implementation (Red): _DASHBOARD_LANG_NAMES defined directly → test fails.
    assert not hasattr(m, "_DASHBOARD_LANG_NAMES"), (
        "dashboard_service still defines _DASHBOARD_LANG_NAMES directly. "
        "Replace with `from src.shared.lang_names import LANG_NAMES`."
    )

    # 구현 후(Green): shared에서 import한 LANG_NAMES가 모듈 네임스페이스에 있어야 함
    # Post-implementation (Green): LANG_NAMES imported from shared must be present.
    assert hasattr(m, "LANG_NAMES"), (
        "dashboard_service must import LANG_NAMES from src.shared.lang_names."
    )


def test_dashboard_service_lang_names_values_match_shared():
    """dashboard_service의 LANG_NAMES가 shared 모듈과 동일 객체여야 함.

    The LANG_NAMES in dashboard_service must be the exact same object
    imported from src.shared.lang_names (not a locally-defined copy).
    """
    import src.services.dashboard_service as m
    from src.shared.lang_names import LANG_NAMES

    assert m.LANG_NAMES is LANG_NAMES, (
        "dashboard_service.LANG_NAMES must be the same object as "
        "src.shared.lang_names.LANG_NAMES (identity check)."
    )
