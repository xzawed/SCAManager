"""판정할 «코드» — 템플릿·JS 에서 주석을 지운 본문.

주석이 코드를 인용하면(`// if (typeof Chart === 'undefined') return;` 처럼 주석 처리된 가드) 원문의
substring 검사는 그 주석으로 통과한다. 지우는 것은 엔진이 읽지 않는 것뿐이다 — Jinja `{# #}`,
HTML `<!-- -->`, `<script>` 안의 JS 주석, `<style>` 안의 CSS 주석. 지운 자리엔 줄바꿈만 남겨
보고하는 줄이 파일의 줄과 맞는다. JS 블록 주석은 공백으로 바꿔 앞뒤 토큰이 붙지 않게 한다.

쓰는 법 — 있어야 할 것(`in` · 개수 하한)은 이 본문에서 찾는다. 없어야 할 것(`not in`)은 원문에서
찾는다: 주석 속 언급까지 빨갛게 하는 쪽이 안전하다.

🔴 JS 정규식 리터럴은 모른다 — `/\\/\\//` 의 `//` 를 주석으로 읽어 그 줄 끝을 지운다. 지우는
   쪽으로만 틀리므로 있어야 할 것이 사라지는 거짓 빨강은 나도 거짓 초록은 안 난다.
Comment-free views of templates and JS: assert presence on the view, absence on the raw text.
"""
from __future__ import annotations

import re

from ._contrast import strip_css_comments

# Jinja 는 HTML 보다 먼저 읽는다 — `{# #}` 는 `<script>` 안에 있어도 주석이다(안 닫히면 끝까지).
# Jinja reads first: `{# #}` is a comment even inside <script>; an unclosed one runs to the end.
_JINJA_COMMENT = re.compile(r"\{#.*?(?:#\}|\Z)", re.S)
# HTML 주석 · `<script>`/`<style>` 원시 텍스트 — 왼쪽부터 먼저 만난 것이 이긴다. 그래서 주석 속
# `<script>` 는 주석과 함께 지워지고, `<script>` 안의 `<!--` 는 JS 본문으로 남는다.
# Leftmost wins: a <script> inside a comment goes with it; a `<!--` inside a script stays JS.
_HTML_PART = re.compile(
    r"<!--.*?(?:-->|\Z)"
    r"|(?P<open><(?P<tag>script|style)\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>)"
    r"(?P<body>.*?)(?P<close></(?P=tag)\s*>|\Z)",
    re.S | re.I)
# JS 주석과 문자열 — 문자열·템플릿 리터럴 안의 `//`·`/*` 는 주석이 아니다.
# JS comments and strings: `//` and `/*` inside strings or template literals are not comments.
_JS_TOKEN = re.compile(
    r"//[^\n]*"
    r"|/\*.*?(?:\*/|\Z)"
    r'|"(?:\\.|[^"\\\n])*"?'
    r"|'(?:\\.|[^'\\\n])*'?"
    r"|`(?:\\.|[^`\\])*`?",
    re.S)


def _newlines(text: str) -> str:
    return "\n" * text.count("\n")


def js_code(src: str) -> str:
    """JS 본문에서 주석을 지운다 — 줄 주석은 그 줄 끝까지, 블록 주석은 공백(또는 품었던 줄바꿈)으로."""
    def keep(m: re.Match) -> str:
        s = m.group(0)
        if s.startswith("//"):
            return ""
        if s.startswith("/*"):
            return _newlines(s) or " "
        return s
    return _JS_TOKEN.sub(keep, src)


def template_code(html: str) -> str:
    """템플릿 원문 → 주석을 지운 본문(Jinja · HTML · `<script>` 의 JS · `<style>` 의 CSS)."""
    text = _JINJA_COMMENT.sub(lambda m: _newlines(m.group(0)), html)

    def part(m: re.Match) -> str:
        if m.group("tag") is None:
            return _newlines(m.group(0))
        body = m.group("body")
        body = js_code(body) if m.group("tag").lower() == "script" else strip_css_comments(body)
        return m.group("open") + body + m.group("close")
    return _HTML_PART.sub(part, text)
