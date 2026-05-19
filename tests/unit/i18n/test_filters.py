"""Jinja2 i18n 필터 단위 테스트 (Phase 1 PR-1b)."""
from jinja2 import Environment, select_autoescape

from src.i18n.filters import i18n_args_filter, i18n_filter, register_i18n_filters


def test_i18n_filter_en():
    """i18n_filter — 영문 번역 조회."""
    assert i18n_filter("dashboard.title", "en") == "Dashboard"


def test_i18n_filter_ko():
    """i18n_filter — 한국어 번역 조회."""
    assert i18n_filter("dashboard.title", "ko") == "대시보드"


def test_i18n_filter_ja():
    """i18n_filter — 일본어 번역 조회."""
    assert i18n_filter("dashboard.title", "ja") == "ダッシュボード"


def test_i18n_args_filter_with_substitution():
    """i18n_args_filter — 변수 치환 포함."""
    result = i18n_args_filter("header.welcome", "ko", name="Alice")
    assert result == "환영합니다, Alice님"


def test_i18n_args_filter_en():
    """i18n_args_filter — 영문 변수 치환."""
    result = i18n_args_filter("header.welcome", "en", name="Bob")
    assert result == "Welcome, Bob"


def test_register_i18n_filters_jinja_env():
    """register_i18n_filters — Jinja2 환경에 필터 등록 확인."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    register_i18n_filters(env)
    assert "i18n" in env.filters
    assert "i18n_args" in env.filters


def test_jinja_template_uses_i18n_filter():
    """실제 Jinja2 템플릿에서 i18n 필터 동작 확인."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    register_i18n_filters(env)
    tmpl = env.from_string('{{ "dashboard.title" | i18n("ko") }}')
    result = tmpl.render()
    assert result == "대시보드"


def test_jinja_template_uses_i18n_args_filter():
    """실제 Jinja2 템플릿에서 i18n_args 필터 + 변수 치환 동작 확인."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    register_i18n_filters(env)
    tmpl = env.from_string('{{ "header.welcome" | i18n_args("ja", name=user_name) }}')
    result = tmpl.render(user_name="Tanaka")
    assert result == "ようこそ、Tanakaさん"


def test_filter_with_default_locale_none():
    """locale=None 시 default_locale (en) 사용."""
    result = i18n_filter("dashboard.title", None)
    assert result == "Dashboard"


def test_i18n_args_filter_escapes_html_in_str_kwarg():
    """str kwarg에 HTML 태그가 있으면 이스케이프됨 — XSS 방어.
    HTML tags in str kwargs are escaped — XSS defence."""
    result = i18n_args_filter("header.welcome", "en", name="<script>alert(1)</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_i18n_args_filter_passes_markup_kwarg_unchanged():
    """Markup 인스턴스는 의도적 HTML로 간주 — 이스케이프하지 않음.
    Markup instances are treated as intentional HTML — not escaped."""
    from markupsafe import Markup
    result = i18n_args_filter("header.welcome", "en", name=Markup("<b>Alice</b>"))
    assert "<b>Alice</b>" in result
    assert "&lt;b&gt;" not in result


def test_i18n_args_filter_normal_str_no_html():
    """HTML 없는 일반 str은 그대로 치환 — 이스케이프 부작용 없음.
    Plain str without HTML is substituted as-is — no escape side-effects."""
    result = i18n_args_filter("header.welcome", "en", name="World")
    assert "World" in result
