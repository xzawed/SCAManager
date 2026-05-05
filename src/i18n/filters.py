"""Jinja2 i18n 필터 등록 — 템플릿 다국어 통합 (Phase 1 PR-1b).

Jinja2 i18n filter registration — template multilingual integration (Phase 1 PR-1b).

사용 패턴 (Usage):
    {{ "dashboard.title" | i18n(locale) }}
    {{ "header.welcome" | i18n_args(locale, name=user.display_name) }}

Phase 2 PR-5~8 (UI 다국어) 영역에서 본 필터 사용 default.
Used in Phase 2 PR-5~8 (UI multilingual) scope.
"""
from typing import Any

from jinja2 import Environment

from src.i18n.loader import get_text


def i18n_filter(key: str, locale: str | None = None) -> str:
    """Jinja2 필터 — 단순 번역 조회.

    Jinja2 filter — simple translation lookup.

    Example:
        {{ "dashboard.title" | i18n(locale) }}
    """
    return get_text(key, locale)


def i18n_args_filter(key: str, locale: str | None = None, **kwargs: Any) -> str:
    """Jinja2 필터 — 번역 + 변수 치환.

    Jinja2 filter — translation + variable substitution.

    Example:
        {{ "header.welcome" | i18n_args(locale, name=user.name) }}
    """
    return get_text(key, locale, **kwargs)


def register_i18n_filters(env: Environment) -> None:
    """Jinja2 환경에 i18n 필터 등록.

    Register i18n filters on Jinja2 environment.

    Args:
        env: Jinja2 Environment 인스턴스 (Jinja2Templates.env)

    Example:
        from src.i18n.filters import register_i18n_filters
        templates = Jinja2Templates(directory="src/templates")
        register_i18n_filters(templates.env)
    """
    env.filters["i18n"] = i18n_filter
    env.filters["i18n_args"] = i18n_args_filter
