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


# Phase 5 PR-17 (사이클 84) — i18n fallback 메모리 카운터.
# Phase 5 PR-17 (Cycle 84) — i18n fallback in-memory counters.
# 운영 KPI = i18n_fallback_rate 산출 인프라 (process restart 시 reset).
# Operations KPI = infrastructure for computing i18n_fallback_rate (resets on process restart).
# 정책 16 5번 원칙 페어 — 메모리 카운터 (DB persist X — Phase 6 영역, 정책 16 4번 원칙 사용처 ≥3 도달 시).
# Policy 16 #5 pair — in-memory only (no DB persist — Phase 6 area when usage ≥3 per Policy 16 #4).
_i18n_metrics: dict[str, int] = {
    "lookups_total": 0,        # 총 get_text 호출 횟수
    "lookups_hit": 0,          # 대상 locale 에서 직접 발견 (hit)
    "lookups_fallback": 0,     # 영문 fallback 으로 해결 (target → en)
    "lookups_missing": 0,      # 영문 fallback 도 실패 (key 자체 반환)
}


def get_i18n_metrics() -> dict[str, int | float]:
    """i18n 사용 메트릭 + fallback rate 반환 (Phase 5 PR-17 — admin operations KPI).

    Return i18n usage metrics + fallback rate (Phase 5 PR-17 — admin operations KPI).

    Returns:
        dict with keys: lookups_total / lookups_hit / lookups_fallback / lookups_missing
        + fallback_rate_pct (영문 fallback 또는 missing 비율 — 0~100)

    process restart 시 reset (memory_only). Phase 6 영역 = DB persist.
    Resets on process restart (memory only). Phase 6 area = DB persist.
    """
    total = int(_i18n_metrics.get("lookups_total") or 0)
    fallback = int(_i18n_metrics.get("lookups_fallback") or 0)
    missing = int(_i18n_metrics.get("lookups_missing") or 0)
    rate = ((fallback + missing) / total * 100) if total > 0 else 0.0
    return {
        "lookups_total": total,
        "lookups_hit": int(_i18n_metrics.get("lookups_hit") or 0),
        "lookups_fallback": fallback,
        "lookups_missing": missing,
        "fallback_rate_pct": round(rate, 2),
    }


def reset_i18n_metrics() -> None:
    """i18n 메트릭 리셋 (단위 테스트 + admin manual reset).

    Reset i18n metrics (unit tests + admin manual reset).
    """
    for key in _i18n_metrics:
        _i18n_metrics[key] = 0


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

    # Phase 5 PR-17 — 메트릭 카운터 (operations KPI — i18n_fallback_rate 산출).
    # Phase 5 PR-17 — metric counter (operations KPI — i18n_fallback_rate computation).
    _i18n_metrics["lookups_total"] += 1

    # 1. 대상 locale 시도
    # 1. Try target locale
    value = _lookup_key(load_translations(target_locale), key)
    if value is not None:
        _i18n_metrics["lookups_hit"] += 1

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
        if value is not None:
            _i18n_metrics["lookups_fallback"] += 1

    # 3. 최종 fallback = key 자체 반환 + WARNING
    # 3. Final fallback = return key itself + WARNING
    if value is None:
        logger.warning(
            "Translation key '%s' not found in any locale — returning key as-is",
            key,
        )
        _i18n_metrics["lookups_missing"] += 1
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
