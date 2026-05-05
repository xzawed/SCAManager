"""번역 로더 — JSON 기반 + LRU cache + namespace dot path + 영문 fallback.

Translation loader — JSON-based + LRU cache + namespace dot path + English fallback.

Phase 1 PR-1b — i18n 인프라 핵심 영역. 사용처:
- Jinja2 템플릿 필터 (`src/i18n/filters.py`)
- Python 코드 직접 호출 (`get_text(key, locale)`)

Phase 1 PR-1b — i18n infrastructure core. Used by:
- Jinja2 template filters (`src/i18n/filters.py`)
- Direct Python calls (`get_text(key, locale)`)

Fallback 정책:
- locale 파일 미존재 → settings.locale_fallback 사용
- key 미존재 → 영문 (locale_fallback) fallback → 여전히 미존재 시 key 자체 반환 + WARNING

Fallback policy:
- locale file missing → use settings.locale_fallback
- key missing → fallback to English (locale_fallback) → still missing returns key + WARNING
"""
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from src.config import settings

logger = logging.getLogger(__name__)


def _translations_dir() -> Path:
    """번역 파일 디렉토리 경로 — 절대/상대 경로 모두 호환.

    Translation file directory — supports absolute/relative paths.
    """
    raw = settings.i18n_translations_dir
    path = Path(raw)
    if path.is_absolute():
        return path
    # 상대 경로 = project root 기준 (CWD = repo root)
    # Relative path = relative to project root (CWD = repo root)
    return Path.cwd() / raw


@lru_cache(maxsize=8)  # en/ko/ja 3개 + 여유분 (Phase 5 신규 언어 추가 대비)
def load_translations(locale: str) -> Dict[str, Any]:
    """JSON 번역 파일 로드 (LRU cache 적용).

    Load JSON translation file (LRU cache applied).

    Args:
        locale: 언어 코드 ("en", "ko", "ja")

    Returns:
        번역 dict (미존재 시 빈 dict + WARNING)
    """
    file_path = _translations_dir() / f"{locale}.json"
    if not file_path.exists():
        logger.warning(
            "Translation file not found: %s — empty dict returned (fallback expected)",
            file_path,
        )
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:  # pylint: disable=broad-exception-caught
        logger.error(
            "Failed to load translation file %s: %s — empty dict returned",
            file_path,
            exc,
        )
        return {}


def get_text(key: str, locale: str | None = None, **kwargs) -> str:
    """번역 문자열 조회 + 변수 치환.

    Get translated text + variable substitution.

    Args:
        key: namespace dot path (예: "dashboard.kpi.avg_score")
        locale: 언어 코드 (None 시 settings.default_locale 사용)
        **kwargs: 변수 치환 (예: name="John")

    Returns:
        번역된 문자열 (미존재 시 영문 fallback → 여전히 미존재 시 key 반환)

    Example:
        >>> get_text("dashboard.kpi.avg_score", "ko")
        '평균 점수'
        >>> get_text("header.welcome", "en", name="John")
        'Welcome, John'
        >>> get_text("nonexistent.key", "ja")
        'nonexistent.key'  # WARNING 로그 + key 반환
    """
    target_locale = locale or settings.default_locale

    # 1. 대상 locale 시도
    # 1. Try target locale
    value = _lookup_key(load_translations(target_locale), key)

    # 2. 영문 fallback (target_locale != locale_fallback 일 때만)
    # 2. English fallback (only when target_locale != locale_fallback)
    if value is None and target_locale != settings.locale_fallback:
        logger.warning(
            "Translation key '%s' not found in locale '%s' — falling back to '%s'",
            key,
            target_locale,
            settings.locale_fallback,
        )
        value = _lookup_key(load_translations(settings.locale_fallback), key)

    # 3. 최종 fallback = key 자체 반환 + WARNING
    # 3. Final fallback = return key itself + WARNING
    if value is None:
        logger.warning(
            "Translation key '%s' not found in any locale — returning key as-is",
            key,
        )
        return key

    # 4. 변수 치환 (kwargs 비어있으면 원본 반환)
    # 4. Variable substitution (return as-is if kwargs empty)
    if not isinstance(value, str):
        return str(value)

    if not kwargs:
        return value

    try:
        return value.format(**kwargs)
    except (KeyError, IndexError) as exc:
        logger.warning(
            "Format substitution failed for key '%s': %s — returning unformatted",
            key,
            exc,
        )
        return value


def _lookup_key(translations: Dict[str, Any], key: str) -> Any:
    """namespace dot path 순회 후 값 반환 (미존재 시 None).

    Traverse namespace dot path, return value (None if missing).
    """
    keys = key.split(".")
    value: Any = translations
    for k in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(k)
        if value is None:
            return None
    return value
