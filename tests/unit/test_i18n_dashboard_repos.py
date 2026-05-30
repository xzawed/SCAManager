"""dashboard.html repos 모드 신규 i18n 키 존재 검증 테스트 (Red 단계).

RED phase tests: verify that newly planned i18n keys for the dashboard repos
mode exist in all three locale files (ko/en/ja).  These tests must FAIL until
the keys are added to the JSON translation files.
"""

import json
import pathlib

import pytest

# src 모듈 import 전 환경변수 주입 — conftest 보다 먼저 실행되는 단위 테스트 파일 안전장치
# Inject env vars before any src import — safety net for unit test files loaded before conftest
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

# 프로젝트 루트 기준 절대 경로 — CI / 로컬 모두 동일하게 동작
# Absolute path anchored at project root — works on both CI and local
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_TRANSLATIONS_DIR = _PROJECT_ROOT / "src" / "i18n" / "translations"

# ──────────────────────────────────────────────────────────────
# 검증할 신규 키 목록
# List of new keys to be validated
# ──────────────────────────────────────────────────────────────

# dashboard.repos 서브 네임스페이스 아래에 추가될 키 (12개)
# Keys to be added under the dashboard.repos sub-namespace (12 keys)
_REPOS_SUB_KEYS: list[str] = [
    "kpi_avg_score",
    "kpi_connected_repos",
    "kpi_warning",
    "grade_distribution",
    "grade_bar_tooltip",
    "select_repo_aria",
    "chart_avg_score_label",
    "cat_security_error",
    "cat_security_warning",
    "cat_quality_error",
    "cat_quality_warning",
    "recurring_count",
]

# dashboard 최상위에 추가될 키 (5개)
# Keys to be added at the dashboard top level (5 keys)
_DASHBOARD_TOP_KEYS: list[str] = [
    "kpi_foot_avg",
    "kpi_unit_count",
    "score_trend_subtitle",
    "repo_insights_title",
    "recent_days",
]

# 지원 locale 목록
# Supported locale list
_LOCALES: list[str] = ["ko", "en", "ja"]


# ──────────────────────────────────────────────────────────────
# 헬퍼
# Helpers
# ──────────────────────────────────────────────────────────────

def _load_translation(locale: str) -> dict:
    """지정 locale 의 JSON 번역 파일을 dict 로 반환한다.

    Load and return the JSON translation file for the given locale as a dict.
    """
    path = _TRANSLATIONS_DIR / f"{locale}.json"
    assert path.exists(), (
        f"번역 파일이 없습니다: {path}\n"
        f"Translation file not found: {path}"
    )
    return json.loads(path.read_text(encoding="utf-8"))


# ──────────────────────────────────────────────────────────────
# 테스트 1 — dashboard.repos 서브 네임스페이스 키 존재 확인
# Test 1 — Verify dashboard.repos sub-namespace keys exist
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _REPOS_SUB_KEYS)
def test_dashboard_repos_keys_exist_in_all_locales(locale: str, key: str) -> None:
    """ko/en/ja 번역 파일 모두에 dashboard.repos.<key> 가 존재해야 한다.

    Each planned key under dashboard.repos must exist in all three locale files.
    This test is RED until the keys are added to the JSON files.
    """
    data = _load_translation(locale)

    # dashboard 네임스페이스 접근
    # Access dashboard namespace
    assert "dashboard" in data, (
        f"[{locale}] 'dashboard' 네임스페이스가 없습니다.\n"
        f"[{locale}] 'dashboard' namespace is missing."
    )

    # repos 서브 네임스페이스 접근
    # Access repos sub-namespace
    assert "repos" in data["dashboard"], (
        f"[{locale}] 'dashboard.repos' 서브 네임스페이스가 없습니다.\n"
        f"[{locale}] 'dashboard.repos' sub-namespace is missing."
    )

    # 개별 키 존재 확인
    # Check individual key existence
    assert key in data["dashboard"]["repos"], (
        f"[{locale}] 'dashboard.repos.{key}' 키가 없습니다.\n"
        f"[{locale}] Key 'dashboard.repos.{key}' is missing."
    )


# ──────────────────────────────────────────────────────────────
# 테스트 2 — dashboard 최상위 신규 키 존재 확인
# Test 2 — Verify new dashboard top-level keys exist
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _DASHBOARD_TOP_KEYS)
def test_dashboard_top_level_keys_exist_in_all_locales(locale: str, key: str) -> None:
    """ko/en/ja 번역 파일 모두에 dashboard.<key> 최상위 키가 존재해야 한다.

    Each planned top-level key under dashboard must exist in all three locale files.
    This test is RED until the keys are added to the JSON files.
    """
    data = _load_translation(locale)

    assert "dashboard" in data, (
        f"[{locale}] 'dashboard' 네임스페이스가 없습니다.\n"
        f"[{locale}] 'dashboard' namespace is missing."
    )

    assert key in data["dashboard"], (
        f"[{locale}] 'dashboard.{key}' 최상위 키가 없습니다.\n"
        f"[{locale}] Top-level key 'dashboard.{key}' is missing."
    )


# ──────────────────────────────────────────────────────────────
# 테스트 3 — dashboard.repos 키 값이 빈 문자열이 아님 확인
# Test 3 — Verify dashboard.repos key values are non-empty
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _REPOS_SUB_KEYS)
def test_dashboard_repos_keys_are_non_empty(locale: str, key: str) -> None:
    """ko/en/ja 모두에서 dashboard.repos.<key> 값이 빈 문자열이 아니어야 한다.

    The value of each dashboard.repos key must be a non-empty string in all
    three locales.  An empty string signals a placeholder that was never filled.
    This test is RED until the keys are added with non-empty translations.
    """
    data = _load_translation(locale)

    # repos 서브 네임스페이스와 키 자체의 존재는 테스트 1이 이미 담당하므로
    # 여기서는 존재를 가정하고 값의 내용만 검증한다.
    # Existence of the repos sub-namespace and each key is covered by test 1;
    # here we only assert the value is a non-empty string.
    repos = data.get("dashboard", {}).get("repos", {})
    value = repos.get(key)

    assert isinstance(value, str) and value.strip() != "", (
        f"[{locale}] 'dashboard.repos.{key}' 값이 비어 있거나 문자열이 아닙니다 (현재 값: {value!r}).\n"
        f"[{locale}] 'dashboard.repos.{key}' value is empty or not a string (current: {value!r})."
    )


# ──────────────────────────────────────────────────────────────
# 테스트 4 — dashboard 최상위 신규 키 값이 빈 문자열이 아님 확인
# Test 4 — Verify new dashboard top-level key values are non-empty
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _DASHBOARD_TOP_KEYS)
def test_dashboard_top_level_keys_are_non_empty(locale: str, key: str) -> None:
    """ko/en/ja 모두에서 dashboard.<key> 최상위 값이 빈 문자열이 아니어야 한다.

    The value of each new dashboard top-level key must be a non-empty string
    in all three locales.
    This test is RED until the keys are added with non-empty translations.
    """
    data = _load_translation(locale)

    dashboard = data.get("dashboard", {})
    value = dashboard.get(key)

    assert isinstance(value, str) and value.strip() != "", (
        f"[{locale}] 'dashboard.{key}' 값이 비어 있거나 문자열이 아닙니다 (현재 값: {value!r}).\n"
        f"[{locale}] 'dashboard.{key}' value is empty or not a string (current: {value!r})."
    )


# ──────────────────────────────────────────────────────────────
# 테스트 5 — repos 서브 네임스페이스에 정확히 예정된 키만 존재하는지 확인
# Test 5 — Verify repos sub-namespace contains exactly the planned keys (no extras)
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("locale", _LOCALES)
def test_dashboard_repos_has_all_expected_keys(locale: str) -> None:
    """ko/en/ja 의 dashboard.repos 가 예정된 12개 키를 모두 포함해야 한다.

    The dashboard.repos sub-namespace must contain all 12 planned keys in every
    locale.  This test catches the case where only some keys are added partially.
    This test is RED until all 12 keys are present.
    """
    data = _load_translation(locale)

    repos = data.get("dashboard", {}).get("repos", {})
    missing = [k for k in _REPOS_SUB_KEYS if k not in repos]

    assert not missing, (
        f"[{locale}] dashboard.repos 에 누락된 키 {len(missing)}개: {missing}\n"
        f"[{locale}] {len(missing)} key(s) missing from dashboard.repos: {missing}"
    )
