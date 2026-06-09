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
    """Jinja2 필터 — 번역 + 변수 치환 (raw 치환만, escape 는 autoescape 가 수행).

    이스케이프는 Jinja2 autoescape 가 렌더 시점에 1회 수행한다 — 필터는 raw 값을 치환만
    하므로 이중 이스케이프(#34)가 발생하지 않는다. 자동이스케이프가 꺼진 `| safe` 컨텍스트
    (개발자 의도 HTML 번역문)에서는 kwarg 가 escape 되지 않으므로 **사용자 입력을
    `i18n_args(...) | safe` 로 넘기지 말 것** (회귀 가드: tests/unit/i18n/test_i18n_args_safe_contract.py).

    Escaping happens once at Jinja2 render time (autoescape); the filter only substitutes raw
    values, so the double-escape bug (#34) cannot occur. In `| safe` contexts (intentional-HTML
    translations) kwargs are NOT escaped — never pass user input through `i18n_args(...) | safe`.

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
