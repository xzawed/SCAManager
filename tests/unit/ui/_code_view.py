"""판정할 «코드» — 템플릿·JS 에서 주석을 지운 본문.

주석이 코드를 인용하면(`// if (typeof Chart === 'undefined') return;` 처럼 주석 처리된 가드) 원문의
substring 검사는 그 주석으로 통과한다. 지우는 것은 엔진이 읽지 않는 것뿐이다 — Jinja `{# #}`,
HTML `<!-- -->`, `<script>` 안의 JS 주석, `<style>` 안의 CSS 주석. 지운 자리엔 줄바꿈만 남겨
보고하는 줄이 파일의 줄과 맞는다. JS 블록 주석은 공백으로 바꿔 앞뒤 토큰이 붙지 않게 한다.

쓰는 법 — 있어야 할 것(`in` · 개수 하한)은 이 본문에서 찾는다. 없어야 할 것(`not in`)은 원문에서
찾는다: 주석 속 언급까지 빨갛게 하는 쪽이 안전하다.

🔴 JS 정규식 리터럴은 바로 앞의 의미 있는 글자로 가린다 — 식이 끝난 자리(이름 · 숫자 · `)` · `]` ·
   문자열) 뒤의 `/` 는 나눗셈, 그 밖은 정규식이다. `if (x) /re/.test(y)` · `a++ / 2` 같은 드문
   꼴은 틀리게 읽는다. 중첩 템플릿 리터럴(`` `${ `x` }` ``)은 모른다.
Comment-free views of templates and JS: assert presence on the view, absence on the raw text.
"""
from __future__ import annotations

import re

from ._contrast import strip_css_comments

# Jinja 는 HTML 보다 먼저 읽는다 — `{# #}` 는 `<script>` 안에 있어도 주석이다(안 닫히면 끝까지).
# 식 `{{ }}` · 문 `{% %}` 안의 `{#` 는 주석이 아니다 — 그것들을 먼저 통째로 건너뛴다.
# Jinja reads first; `{#` inside `{{ }}` / `{% %}` is not a comment, so those are skipped whole.
_JINJA_PART = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?(?:#\}|\Z)", re.S)
# 태그의 속성 — 따옴표 안의 `>` · `<script>` 는 태그를 끝내거나 열지 않는다.
# Tag attributes: a quoted `>` or `<script>` neither ends nor opens a tag.
_ATTRS = r"(?:[^>\"']|\"[^\"]*\"|'[^']*')*"
# HTML 주석 · `<script>`/`<style>` 원시 텍스트 · 그 밖의 여는 태그 — 왼쪽부터 먼저 만난 것이 이긴다.
# 주석 속 `<script>` 는 주석과 함께 지워지고, `<script>` 안의 `<!--` 는 JS 본문으로 남고, 속성값
# 안의 `<script>` 는 그 태그와 함께 건너뛴다.
# Leftmost wins: comments, raw-text bodies, and any other start tag (skipped whole with its attributes).
_HTML_PART = re.compile(
    r"<!--.*?(?:-->|\Z)"
    rf"|(?P<open><(?P<tag>script|style)\b{_ATTRS}>)(?P<body>.*?)(?P<close></(?P=tag)\s*>|\Z)"
    rf"|<[A-Za-z][\w:.-]*{_ATTRS}>",
    re.S | re.I)

# 이 글자 · 키워드 뒤의 `/` 는 정규식 리터럴을 연다(식이 끝나지 않은 자리).
# After these characters or keywords a `/` opens a regex literal (no expression has just ended).
_REGEX_AFTER_CHARS = frozenset("([{},;:=!&|?+-*%<>~^")
_REGEX_AFTER_WORDS = frozenset({"return", "typeof", "case", "do", "else", "in", "of", "instanceof",
                                "new", "delete", "void", "throw", "yield", "await"})


def _newlines(text: str) -> str:
    return "\n" * text.count("\n")


def _is_ident(ch: str) -> bool:
    return ch.isalnum() or ch in "_$"


def _string_end(src: str, i: int) -> int:
    """`src[i]` 의 따옴표로 연 문자열의 끝 다음 위치 — `'`·`"` 는 줄 끝에서도 끝난다(안 닫힌 문자열)."""
    quote, j, n = src[i], i + 1, len(src)
    while j < n:
        ch = src[j]
        if ch == "\\":
            j += 2
            continue
        if ch == quote:
            return j + 1
        if ch == "\n" and quote != "`":
            return j
        j += 1
    return n


def _regex_end(src: str, i: int) -> int | None:
    """`src[i] == "/"` 로 여는 정규식 리터럴의 끝(플래그 포함) — 그 줄 안에서 안 닫히면 None."""
    j, n, in_class = i + 1, len(src), False
    while j < n:
        ch = src[j]
        if ch == "\n":
            return None
        if ch == "\\":
            j += 2
            continue
        if in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
        elif ch == "/":
            j += 1
            while j < n and _is_ident(src[j]):
                j += 1
            return j
        j += 1
    return None


def js_code(src: str) -> str:
    """JS 본문에서 주석을 지운다 — 줄 주석은 그 줄 끝까지, 블록 주석은 공백(또는 품었던 줄바꿈)으로.

    문자열 · 템플릿 리터럴 · 정규식 리터럴 안의 `//` · `/*` 는 그대로 둔다.
    """
    out: list[str] = []
    last, word, prev = "", "", ""  # 마지막 의미 있는 글자 · 그것이 이름이면 그 이름 · 바로 앞 글자
    i, n = 0, len(src)
    while i < n:
        ch, pair = src[i], src[i:i + 2]
        if pair == "//":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if pair == "/*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(_newlines(src[i:j]) or " ")
            i, prev = j, " "
            continue
        if ch in "'\"`":
            j = _string_end(src, i)
            out.append(src[i:j])
            i, last, word, prev = j, '"', "", '"'
            continue
        if ch == "/" and (not last or last in _REGEX_AFTER_CHARS or word in _REGEX_AFTER_WORDS):
            j = _regex_end(src, i)
            if j is not None:
                out.append(src[i:j])
                i, last, word, prev = j, '"', "", '"'
                continue
        out.append(ch)
        if not ch.isspace():
            word = (word + ch if _is_ident(prev) else ch) if _is_ident(ch) else ""
            last = ch
        prev = ch
        i += 1
    return "".join(out)


def template_code(html: str) -> str:
    """템플릿 원문 → 주석을 지운 본문(Jinja · HTML · `<script>` 의 JS · `<style>` 의 CSS)."""
    text = _JINJA_PART.sub(
        lambda m: m.group(0) if m.group(0)[:2] in ("{{", "{%") else _newlines(m.group(0)), html)

    def part(m: re.Match) -> str:
        whole = m.group(0)
        if whole.startswith("<!--"):
            return _newlines(whole)
        if m.group("tag") is None:
            return whole  # 그 밖의 여는 태그 — 속성값 안의 글은 건드리지 않는다
        body = m.group("body")
        body = js_code(body) if m.group("tag").lower() == "script" else strip_css_comments(body)
        return m.group("open") + body + m.group("close")
    return _HTML_PART.sub(part, text)
