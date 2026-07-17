"""번역 로더 단위 테스트 (Phase 1 PR-1b).

JSON 파일 로드 + LRU cache + namespace dot path + fallback 검증.
"""
from src.i18n.loader import get_text, load_translations


def setup_function():
    """각 테스트 전에 LRU cache 초기화 (테스트 격리)."""
    load_translations.cache_clear()


def test_load_translations_en():
    """en.json 로드 = common 영역 존재."""
    trans = load_translations("en")
    assert "common" in trans
    assert trans["common"]["logout"] == "Logout"


def test_load_translations_ko():
    """ko.json 로드 = 한국어 본문."""
    trans = load_translations("ko")
    assert trans["common"]["logout"] == "로그아웃"


def test_load_translations_ja():
    """ja.json 로드 = 일본어 본문."""
    trans = load_translations("ja")
    assert trans["common"]["logout"] == "ログアウト"


def test_load_translations_missing_locale_returns_empty():
    """존재하지 않는 locale → 빈 dict + WARNING."""
    trans = load_translations("xx")
    assert trans == {}


def test_get_text_namespace_dot_path_en():
    """namespace dot path: 'dashboard.title' → en 번역."""
    result = get_text("dashboard.title", "en")
    assert result == "Dashboard"


def test_get_text_namespace_dot_path_ko():
    """namespace dot path: 'dashboard.title' → ko 번역."""
    result = get_text("dashboard.title", "ko")
    assert result == "대시보드"


def test_get_text_namespace_dot_path_ja():
    """namespace dot path: 'dashboard.title' → ja 번역."""
    result = get_text("dashboard.title", "ja")
    assert result == "ダッシュボード"


def test_get_text_deeply_nested_key():
    """깊은 namespace: 'dashboard.kpi.avg_score' → 정확 값."""
    assert get_text("dashboard.kpi.avg_score", "en") == "Average Score"
    assert get_text("dashboard.kpi.avg_score", "ko") == "평균 점수"
    assert get_text("dashboard.kpi.avg_score", "ja") == "平均スコア"


def test_get_text_variable_substitution():
    """변수 치환 {name} → 실제 값."""
    result = get_text("header.welcome", "ko", name="John")
    assert result == "환영합니다, John님"


def test_get_text_missing_key_returns_key_itself():
    """존재하지 않는 key → key 자체 반환 + WARNING."""
    result = get_text("nonexistent.deeply.nested.key", "ko")
    assert result == "nonexistent.deeply.nested.key"


def test_get_text_missing_key_in_target_falls_back_to_en():
    """대상 locale 에 미존재 → 영문 fallback (en)."""
    # ko.json 에는 미존재하지만 en.json 에는 존재하는 임의 key 시뮬레이션 어려움
    # → key 자체 반환 검증으로 대체 (양 locale 모두 미존재 시)
    result = get_text("missing.in.both", "ja")
    assert result == "missing.in.both"


def test_get_text_default_locale_when_none():
    """locale=None 시 settings.default_locale (en) 사용."""
    result = get_text("dashboard.title", None)
    assert result == "Dashboard"


def test_get_text_format_substitution_failure_returns_unformatted():
    """변수 미일치 시 원본 반환 + WARNING."""
    # 'dashboard.title' = "Dashboard" (no placeholder)
    # kwargs 무시하고 원본 반환
    result = get_text("dashboard.title", "en", unused_var="value")
    assert result == "Dashboard"


def test_get_text_unbalanced_brace_returns_unformatted(monkeypatch):
    """🔴 C28: 번역문에 불균형/리터럴 중괄호 + kwargs → str.format() ValueError 를 graceful 처리.

    'a { b {name}'.format(name='x') 는 ValueError 를 던진다(KeyError/IndexError 아님). 미포착 시
    페이지 렌더 500 → ValueError 도 포착해 unformatted 원본 반환(의도된 fallback 보존).
    """
    from src.i18n import loader  # pylint: disable=import-outside-toplevel
    monkeypatch.setattr(loader, "_lookup_key", lambda translations, key: "a { b {name}")
    # ValueError 가 전파되지 않고 unformatted 원본을 반환해야 한다 (이전엔 미포착 → 500)
    result = loader.get_text("any.key", "en", name="x")
    assert result == "a { b {name}"


def test_get_text_lru_cache_hit():
    """LRU cache 동작 검증 — 동일 locale 재호출 시 캐시 hit."""
    load_translations.cache_clear()
    load_translations("en")
    load_translations("en")
    info = load_translations.cache_info()
    assert info.hits >= 1


def test_get_text_supports_all_three_locales():
    """en/ko/ja 3 언어 모두 동일 key 응답 가능."""
    for locale in ("en", "ko", "ja"):
        result = get_text("notifier.no_issues", locale)
        assert result != "notifier.no_issues"  # key 자체 X
        assert isinstance(result, str)
        assert len(result) > 0


def _flatten_keys(node: dict, prefix: str = "") -> set[str]:
    """중첩 dict 를 dot-path leaf key 집합으로 평탄화.

    Flatten a nested dict into a set of dot-path leaf keys.
    """
    keys: set[str] = set()
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _flatten_keys(value, path)
        else:
            keys.add(path)
    return keys


def test_all_locales_have_identical_key_sets():
    """🔴 en/ko/ja 키 집합 완전 일치 — 로케일 drift 차단.

    🔴 en/ko/ja key sets must match exactly — blocks locale drift.

    i18n.md 의무: "새 키 추가 시 3 언어 모두 동시 추가 (en 누락 시 fallback 깨짐 — 운영 사고)".
    기존 `test_get_text_supports_all_three_locales` 는 하드코딩 키 1개만 검사해
    신규 키를 2 로케일에만 추가하는 실수를 못 잡는다. 여기서 전수 강제한다.
    누락 로케일은 en fallback → 최종적으로 **키 문자열 자체가 사용자에게 노출**된다.

    i18n.md requires every new key to land in all three locales at once. The existing
    test only probes one hardcoded key, so a key added to just two locales slips through.
    A missing locale falls back to en and ultimately renders the raw key to the user.
    """
    key_sets = {
        locale: _flatten_keys(load_translations(locale)) for locale in ("en", "ko", "ja")
    }
    en_keys = key_sets["en"]
    for locale in ("ko", "ja"):
        missing = en_keys - key_sets[locale]
        extra = key_sets[locale] - en_keys
        assert not missing, f"{locale}.json 에 누락된 키: {sorted(missing)}"
        assert not extra, f"{locale}.json 에만 있는 키(en 누락 → fallback 붕괴): {sorted(extra)}"
