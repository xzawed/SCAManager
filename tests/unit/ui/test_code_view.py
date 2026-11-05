"""`_code_view` 자기검증 — 주석을 지운 본문이 주석만 지우는가.

이 본문으로 «있어야 할 코드» 를 판정하는 시험이 여럿이다. 이 계기가 코드를 지우면 거짓 빨강,
주석을 남기면 거짓 초록이다 — 양쪽을 따로 심어 본다.
Calibrates the comment-free view: comments go, code stays, line numbers keep.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ._code_view import js_code, template_code

_TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "templates"
_GUARD = "if (typeof Chart === 'undefined') return;"


@pytest.mark.parametrize("commented", [
    f"// {_GUARD}\n",
    f"/* {_GUARD} */\n",
    f"/*\n * {_GUARD}\n */\n",
], ids=["line", "block", "multiline-block"])
def test_js_comment_hides_the_code_it_quotes(commented):
    """🔴 주석 처리된 가드는 원문 substring 으로는 «있다» 지만 본문에서는 없다 — 이 계기가 존재하는 이유."""
    src = "function build() {\n" + commented + "  new Chart(el, cfg);\n}\n"
    assert _GUARD in src
    assert _GUARD not in js_code(src)


@pytest.mark.parametrize("live", [
    "var u = 'https://example.com/a';",
    'var u = "http://x//y";',
    "var t = `a // b /* c */`;",
    "var s = 'it\\'s // not a comment';",
], ids=["single-quoted-url", "double-quoted", "template-literal", "escaped-quote"])
def test_js_strings_keep_their_comment_lookalikes(live):
    """대조군 — 문자열·템플릿 리터럴 안의 `//`·`/*` 는 코드다. 지우면 있어야 할 것이 사라진다."""
    assert js_code(live + "\n") == live + "\n"


def test_js_block_comment_does_not_glue_tokens():
    """블록 주석 자리는 공백이다 — `a/**/b` 가 `ab` 가 되면 없던 이름이 생긴다."""
    assert js_code("return a/**/b;") == "return a b;"


def test_js_view_keeps_every_line():
    """보고하는 줄 번호가 파일과 맞는다 — 지운 주석이 품었던 줄바꿈은 남긴다."""
    src = "a();\n/* one\ntwo\nthree */\nb(); // tail\nc();\n"
    view = js_code(src)
    assert view.count("\n") == src.count("\n")
    assert view.splitlines()[5] == "c();"


@pytest.mark.parametrize("commented", [
    "{# <script>GUARD</script> #}",
    "<!-- <script>GUARD</script> -->",
    "<script>// GUARD\n</script>",
    "<script>/* GUARD */</script>",
    "<style>/* GUARD */</style>",
    "{# 안 닫힌 주석 GUARD",
], ids=["jinja", "html", "script-line", "script-block", "style", "unclosed-jinja"])
def test_template_comments_hide_the_code_they_quote(commented):
    """🔴 Jinja · HTML · 스크립트 · 스타일 주석 속 글자는 본문에 없다."""
    html = "<body>\n" + commented + "\n</body>\n"
    assert "GUARD" in html
    assert "GUARD" not in template_code(html)


@pytest.mark.parametrize("live", [
    '<a href="https://example.com/x">x</a>',
    "<script>var u = 'https://example.com';</script>",
    "<script>var s = '<!-- not html -->';</script>",
    "<style>a { background: url(https://example.com/a.png); }</style>",
    '<script src="/static/vendor/chart.umd.min.js" onload="if(document._x)document._x()"></script>',
    "<p>{{ value }} {% if x %}y{% endif %}</p>",
], ids=["href", "script-string", "script-html-comment-string", "css-url", "script-attrs", "jinja-expr"])
def test_template_code_outside_comments_survives(live):
    """대조군 — 스크립트 밖의 `//` · 스크립트 안 문자열 · CSS `url()` · Jinja 식은 그대로 남는다."""
    html = "<body>\n" + live + "\n</body>\n"
    assert template_code(html) == html


@pytest.mark.parametrize("path", sorted(_TEMPLATES.rglob("*.html")), ids=lambda p: p.name)
def test_real_templates_keep_their_line_count(path):
    """실제 템플릿 전부 — 본문의 줄 수가 원문과 같다(시험이 보고하는 줄 = 파일의 줄)."""
    raw = path.read_text(encoding="utf-8")
    assert template_code(raw).count("\n") == raw.count("\n")


def test_real_templates_have_comments_to_strip():
    """바닥 — 실제 템플릿에서 지울 주석이 있어야 위 «줄 수 같음» 이 공허하지 않다."""
    changed = [p.name for p in sorted(_TEMPLATES.rglob("*.html"))
               if template_code(p.read_text(encoding="utf-8")) != p.read_text(encoding="utf-8")]
    assert changed, "어느 템플릿에서도 지운 것이 없다 — 계기가 아무 일도 안 한다"
