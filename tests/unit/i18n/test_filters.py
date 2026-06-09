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


def test_i18n_args_render_escapes_html_in_str_kwarg():
    """autoescape 렌더 시 str kwarg 의 HTML 이 이스케이프됨 — XSS 방어 (Jinja2 autoescape).
    Under autoescape, HTML in a str kwarg is escaped by Jinja2 at render — XSS defence."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    register_i18n_filters(env)
    tmpl = env.from_string('{{ "header.welcome" | i18n_args("en", name=name) }}')
    result = tmpl.render(name="<script>alert(1)</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_i18n_args_filter_passes_kwargs_raw_no_escape():
    """필터는 kwarg 를 raw 치환만 — escape 안 함(Markup·일반 str 모두). escape 는 render 시 autoescape (#34).

    The filter substitutes kwargs raw without escaping (Markup and plain str alike); escaping is
    deferred to Jinja2 autoescape at render. `| safe` 컨텍스트의 의도적 HTML(Markup) 은 그대로 렌더된다.
    """
    from markupsafe import Markup
    # Markup HTML 그대로 통과 (의도적 HTML — | safe 컨텍스트에서 렌더)
    # Markup HTML passes through (intentional HTML — rendered in | safe contexts)
    result_markup = i18n_args_filter("header.welcome", "en", name=Markup("<b>Alice</b>"))
    assert "<b>Alice</b>" in result_markup
    # 일반 str 도 raw — 필터는 escape 안 함 (autoescape 가 render 시 처리)
    # Plain str is also raw — the filter does not escape (autoescape handles it at render)
    result_str = i18n_args_filter("header.welcome", "en", name="<i>x</i>")
    assert "<i>x</i>" in result_str
    assert "&lt;" not in result_str


def test_i18n_args_filter_normal_str_no_html():
    """HTML 없는 일반 str은 그대로 치환 — 이스케이프 부작용 없음.
    Plain str without HTML is substituted as-is — no escape side-effects."""
    result = i18n_args_filter("header.welcome", "en", name="World")
    assert "World" in result


def test_i18n_args_render_no_double_escape():
    """autoescape 렌더 시 str kwarg 는 1회만 이스케이프 — 이중 이스케이프 회귀 차단 (#34).

    Under autoescape, a str kwarg is escaped exactly once — guards against the double-escape
    bug (#34). 필터가 직접 escape 하면 Jinja2 가 재escape 해 'Tom & Jerry' → 'Tom &amp;amp; Jerry'
    로 깨졌다. 필터는 raw 치환만 하고 escape 는 autoescape 가 1회 수행한다.
    """
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    register_i18n_filters(env)
    tmpl = env.from_string('{{ "header.welcome" | i18n_args("en", name=name) }}')
    result = tmpl.render(name="Tom & Jerry")
    # 1회 이스케이프: & → &amp; (정상 표시)
    assert "Tom &amp; Jerry" in result
    # 이중 이스케이프 부재: &amp;amp; 금지
    assert "&amp;amp;" not in result
