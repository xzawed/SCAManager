r"""CSS 가 «브라우저가 통째로 버리는» 구조로 깨지지 않았는가 — 엄격 구조 스캐너로 판정한다.

🔴 무엇을 막는가 — 글자 하나로 뒤 규칙이 조용히 사라지는 모양 9가지(`_shapes`). 각 모양을
   `components.css` 의 앞·중간·뒤 규칙 뒤에 심고 Chromium CSSOM 을 재면, `}` 하나가 빠지거나
   문자열·`(`·`[` 하나가 안 닫혔을 때 규칙의 15~88% 가 사라지고(뒤 규칙이 앞 규칙 안 중첩
   규칙이 된다) 나머지 모양은 1~3개를 잃는다. 단위 스위트는 그동안 그 모양 중 «주석 밖 `*/`»
   하나만 봤다 — CSS 판정이 전부 정규식이었다.

🔴 «진짜 파서에 통과시킨다» 로는 안 된다 — 파서는 오류를 복구하고 복구한 결과를 정상으로 읽는다.
   같은 9모양에서 lightningcss 엄격 모드는 7개, postcss(stylelint 의 파서)는 6개를 잡았고, 둘 다
   «주석이 다음 주석까지 삼킨» 모양(S2)을 못 봤다. 스캐너(`_css_structure.py`)는 복구하지 않고
   저자의 구조를 엄격히 읽는다. 스캐너가 못 그리는 깨짐(셀렉터 오타 등)은 e2e 가 같은 원문을
   Chromium CSSOM 과 맞대 잡는다(`e2e/test_stylesheet_integrity.py`).

🔴 계기를 뒤집어 봤다(`verify.md` 「판정식을 쓸 때」 4). 두 목록을 먼저 적었다.

   claimed(이 계기의 «이름» 이 잡는다고 적은 것) — 9모양 전부 · 정적 CSS · 템플릿 `<style>` ·
     «개수는 맞는» 중첩 주석 시도 `/* a /* b */ c */`
   cheap(첫 출력만 보고 적은 «그 출력을 낼 가장 싼 과정» = 괄호 짝·주석 표시 «개수» 비교)
     개수가 어긋나는 모든 경우 · 🔴 문자열·`url(`·커스텀 속성 값 안의 `}`·`*/` — 개수 세기는
     이것도 위반으로 센다

   claimed\cheap = S5(문자열이 `}` 를 삼킴) · S8(규칙 사이 `;`) · 중첩 주석 시도 → **잡혀야** 한다
   cheap\claimed = 문자열·url·커스텀 속성 값 안의 표시 → **무시돼야** 한다
   같은 심음을 손대지 않은 운영 파일(`components.css`)에도 끼워 같은 뒤집힘을 요구한다.

   두 번째로 싼 과정(`re.sub(r"/\*.*?\*/", "", src)` 뒤 `*/` 찾기)은 중첩 시도는 맞히지만
   문자열 안 종결자를 오탐한다 — 문자열을 아는 것이 이 계기의 구분점이다.

Forbid stylesheet structures that make a browser silently discard or re-parent rules.
"""
from __future__ import annotations

import re

from html.parser import HTMLParser

import pytest

from ._css_structure import (BLOCK_IN_BRACKET, MISMATCHED_CLOSE, NESTED_OPENER,
                             NESTED_RULE, ROOT, STRAY_CLOSE, STRAY_SEMICOLON,
                             STRAY_TERMINATOR, UNTERMINATED_COMMENT, UNTERMINATED_STRING,
                             authored_sources, chromium_expected, linked_stylesheets, scan,
                             selector_signature, style_blocks, style_spans)

_BASE = (
    ".a { color: red; }\n"
    ".b { color: blue; }\n"
    "@media (min-width: 640px) { .c { color: green; } }\n"
    "/* 진짜 주석 */\n"
    ".d { color: black; }\n"
)


def _shapes(src: str, o: int, c: int) -> dict[str, tuple[str, str]]:
    """여는 `{`(o)·닫는 `}`(c) 가 있는 규칙 주변에 모양 하나씩 심는다 → {이름: (원문, 결함)}."""
    a, b = src[: c + 1], src[c + 1:]
    return {
        "S1 주석 밖 */": (a + "\n*/\n" + b, STRAY_TERMINATOR),
        "S2 주석이 다음 주석까지 삼킴": (a + "\n/*\n" + b, NESTED_OPENER),
        "S3 } 하나 빠짐": (src[:c] + src[c + 1:], NESTED_RULE),
        "S4 } 하나 더": (a + "}" + b, STRAY_CLOSE),
        "S5 줄 안에서 안 닫힌 문자열": (a + '\n.zz::before { content: "x; }\n' + b,
                                UNTERMINATED_STRING),
        "S6 ( 미종결": (src[:c] + "\n  color: var(--text-1;\n" + src[c:], MISMATCHED_CLOSE),
        "S7 [ 미종결": (a + '\n.zz[data-x="1" { color: red; }\n' + b, BLOCK_IN_BRACKET),
        "S8 } 뒤 ;": (a + ";" + b, STRAY_SEMICOLON),
        "S9 { 하나 빠짐": (src[:o] + src[o + 1:], STRAY_SEMICOLON),
    }


_SHAPE_NAMES = list(_shapes(_BASE, *scan(_BASE).blocks[0].span))


def _kinds(src: str) -> set[str]:
    return {k for _, k in scan(src).defects}


def _cheap_balanced(src: str) -> bool:
    """«가장 싼 과정» — 괄호 짝·주석 표시의 개수만 맞으면 정상으로 본다(문자열을 모른다)."""
    return all(src.count(x) == src.count(y)
               for x, y in (("{", "}"), ("(", ")"), ("[", "]"), ("/*", "*/")))


def test_every_authored_stylesheet_keeps_its_structure():
    bad = [(s.path, s.line + ln - 1, kind)
           for s in authored_sources() for ln, kind in scan(s.text).defects]
    assert not bad, (
        "CSS 구조가 깨졌다 — 브라우저가 뒤따르는 규칙을 버리거나 앞 규칙 안으로 옮긴다:\n  "
        + "\n  ".join(f"{p}:{ln}  ({k})" for p, ln, k in bad))


def test_the_scan_reaches_every_kind_of_source():
    """🔴 공허화 방어 — 「결함 0」과 「아무것도 안 읽었다」를 가른다."""
    srcs = authored_sources()
    assert any(s.path.endswith(".css") for s in srcs), "정적 CSS 를 하나도 안 읽었다"
    assert any(s.path.endswith(".html") for s in srcs), "템플릿 `<style>` 을 하나도 안 읽었다"
    assert any(s.served for s in srcs) and any(not s.served for s in srcs), (
        "«브라우저가 받는가» 파생이 한쪽으로 쏠렸다 — Tailwind 입력은 받지 않는다")
    assert sum(len(scan(s.text).blocks) for s in srcs) > 1000, "블록을 거의 못 읽었다"
    assert any(s.line > 1 for s in srcs), "템플릿 블록의 시작 줄이 죽었다 — 보고 좌표가 틀린다"


@pytest.mark.parametrize("name", _SHAPE_NAMES)
def test_each_breakage_shape_is_a_defect(name):
    o, c = scan(_BASE).blocks[0].span
    assert _kinds(_BASE) == set(), "심기 전 원문은 깨끗해야 한다"
    css, expected = _shapes(_BASE, o, c)[name]
    assert expected in _kinds(css), (name, scan(css).defects)


@pytest.mark.parametrize("name", _SHAPE_NAMES)
def test_the_same_shapes_are_caught_inside_an_untouched_production_file(name):
    """🔴 운영 파일에서도 뒤집혀야 한다 — 짧은 심음만 맞히는 «두 번째 싼 과정» 을 거른다."""
    src = (ROOT / "src" / "static" / "css" / "components.css").read_text(encoding="utf-8")
    top = [b for b in scan(src).blocks if b.depth == 0 and b.kind == "style"]
    assert len(top) > 50 and _kinds(src) == set(), "운영 원문이 깨끗하고 충분히 커야 심을 수 있다"
    o, c = top[len(top) // 2].span
    css, expected = _shapes(src, o, c)[name]
    assert expected in _kinds(css), (name, scan(css).defects[:3])


def test_claimed_minus_cheap_is_caught():
    r"""claimed\cheap — 개수는 맞는데 구조가 깨졌다. 개수 세기는 이것들을 통과시킨다."""
    o, c = scan(_BASE).blocks[0].span
    shapes = _shapes(_BASE, o, c)
    nested_attempt = ".a { color: red; }\n/* 바깥 /* 안쪽 */ 남은 꼬리 */\n.b { color: blue; }"
    for css, expected in (shapes["S5 줄 안에서 안 닫힌 문자열"], shapes["S8 } 뒤 ;"],
                          (nested_attempt, STRAY_TERMINATOR)):
        assert _cheap_balanced(css), "이 심음은 «개수가 맞는» 것이어야 한다"
        assert expected in _kinds(css), css
    assert NESTED_OPENER in _kinds(nested_attempt), "안쪽 `/*` 도 함께 짚어야 한다"


@pytest.mark.parametrize("css", [
    '.a::before { content: "}"; }\n.b { color: red; }',
    '.a::before { content: "*/"; }\n.b { color: red; }',
    ".a { background: url(data:image/svg+xml;x=*/y); }\n.b { color: red; }",
    ".a { --x: */; }\n.b { color: red; }",
], ids=["문자열 안 }", "문자열 안 */", "따옴표 없는 url 안 */", "커스텀 속성 값 안 */"])
def test_cheap_minus_claimed_is_ignored(css):
    r"""cheap\claimed — 적법한 CSS 다. 개수 세기는 이것을 위반으로 센다.

    🔴 url·커스텀 속성 갈래는 계기가 먼저 거짓말한 자리다 — 적대 스윕과 Grok claim-review
       `01a0a9da` 가 낸 반례를 Chromium 실측으로 «적법» 을 확인한 뒤 열었다
       (`.a{--x:*/;}` 는 규칙 둘이 다 살고, 값 밖의 같은 `*/` 는 뒤 규칙을 죽인다).
    """
    assert not _cheap_balanced(css), "이 심음은 «개수가 어긋나는» 것이어야 한다"
    assert scan(css).defects == []


def test_a_comment_swallowed_up_to_a_terminator_inside_a_string_is_still_caught():
    r"""Grok claim-review `27df99d3` 의 반례 — 끼운 `/*` 가 문자열 속 `*/` 에서 끝나면 주석 몸체엔
    `/*` 가 없다. 남은 `"}` 가 파일 끝까지 안 닫히므로 문자열 결함으로 잡혀야 한다."""
    swallowed = '.a{color:red}\n/*\n.b{content:"*/"}'
    assert scan('.a{color:red}\n.b{content:"*/"}').defects == []
    assert UNTERMINATED_STRING in _kinds(swallowed)
    assert UNTERMINATED_STRING in _kinds(swallowed + "\n")


def test_a_terminator_outside_a_custom_property_value_is_still_caught():
    """🔴 파생되지 않은 바닥 — 값 «밖» 의 같은 종결자는 여전히 결함이어야 한다."""
    assert STRAY_TERMINATOR in _kinds(".a { color: blue; } */ .b { color: red; }")
    assert UNTERMINATED_COMMENT in _kinds(".a { color: blue; }\n/* 끝이 없다\n.b { color: red; }")


def test_legal_css_has_no_defect_and_keeps_its_blocks():
    """적법한 구성 요소 — 문장형 at-rule · 값 안 블록·괄호 속 `;` · 이스케이프 · 값·목록 사이 주석."""
    css = (
        '@charset "utf-8";\n'
        "@import url(base.css) screen;\n"
        "@layer base, components;\n"
        ":root { --x: */; --blk: { a: b; }; --list: [a; b]; }\n"
        '.a::before { content: "}{*/;"; }\n'
        '.b[data-x="{"] { background: url(data:image/svg+xml;x=*/y); }\n'
        ".c\\:hover { color: red !important; }\n"
        "@media (min-width: 640px) and (max-width: 1024px) { .d { color: blue; } }\n"
        "@supports (backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)) {\n"
        "  .e { color: green; }\n}\n"
        "@keyframes spin { from { transform: rotate(0); } 50%, 75% { opacity: .5 }"
        " to { transform: rotate(1turn) } }\n"
        '@font-face { font-family: X; src: url(x.woff2) format("woff2"); unicode-range: U+0-FF; }\n'
        ".f { color: red /* 값 안의 주석 */; margin: 0 }\n"
        ".g, /* 목록 사이 주석 */ .h { color: blue; }\n"
    )
    res = scan(css)
    assert res.defects == []
    assert [(b.depth, b.kind) for b in res.blocks] == [
        (0, "import"), (0, "layer-statement"), (0, "style"), (0, "style"), (0, "style"),
        (0, "style"), (0, "media"), (1, "style"), (0, "supports"), (1, "style"),
        (0, "keyframes"), (1, "keyframe"), (1, "keyframe"), (1, "keyframe"), (0, "font-face"),
        (0, "style"), (0, "style")]
    f, g = res.blocks[-2], res.blocks[-1]
    assert f.decls == (("color", "red"), ("margin", "0")), "값 안 주석이 값으로 읽혔다"
    assert " ".join(g.prelude.split()) == ".g, .h", "목록 사이 주석이 셀렉터로 읽혔다"


def test_an_escaped_space_stays_part_of_the_selector():
    r"""🔴 `.a\ ` 의 끝 공백은 이름의 일부다 — 공백을 접으면 `.a\` 가 돼 다음 `{` 를 이스케이프한다."""
    blocks = scan(".a\\  { color: red; }\n.b\\ c { color: blue; }").blocks
    assert [b.prelude for b in blocks] == [".a\\ ", ".b\\ c"]


@pytest.mark.parametrize("authored, served", [
    (".a\\-b", ".a-b"),             # 불필요한 이스케이프 — Chromium 은 풀어서 직렬화한다
    (".\\31 23", ".\\31 23"),       # 숫자로 시작하는 이름 — 양쪽 다 이스케이프
    (".\\31 23", ".123"),           # 같은 이름의 다른 표기
    (".가-나 > #x", "#x .가-나"),   # 비ASCII 이름 글자 · 순서 무관
], ids=["불필요한 이스케이프", "hex 이스케이프", "hex ↔ 글자", "비ASCII"])
def test_selector_signature_reads_names_as_the_browser_does(authored, served):
    r"""표지는 «같은 이름» 을 같게 본다 — 변이 퍼즈에서 이스케이프를 안 풀었을 때 오탐이 났다."""
    assert selector_signature("style", authored) == selector_signature("style", served)
    assert selector_signature("style", ".a-b") != selector_signature("style", ".a-c"), "바닥 — 다른 이름"


def test_chromium_expected_drops_only_other_engine_rules():
    """다른 엔진 전용 셀렉터·at-rule 은 Chromium 이 «적법하게» 버린다 — 원문에서 파생해 뺀다."""
    css = (".a::-moz-range-thumb { color: red; }\n"
           ".a::-webkit-slider-thumb { color: red; }\n"
           "@-moz-document url-prefix() { .x { color: red; } }\n"
           ".y { color: blue; }\n")
    assert chromium_expected(scan(css).blocks) == [(0, "style", ".a"), (0, "style", ".y")]


def test_style_blocks_are_read_by_an_html_parser_not_a_regex():
    r"""🔴 HTML 주석·`<script>` 안의 `<style>` 글자는 태그가 아니다.

    cheap = `<style[^>]*>(.*?)</style>` — 주석 속 `<style>` 에서 시작해 `-->`·`<link>` 까지를
    CSS 로 읽는다. `base.html` 이 실제로 그 모양이었다(Chromium 대조가 첫 규칙을 «버려짐» 으로 냈다).
    """
    html = ("<!-- 아래 <style> 은 컴포넌트 규칙 -->\n"
            '<link rel="stylesheet" href="/static/css/x.css">\n'
            "<script>const t = '<style>.q{}</style>';</script>\n"
            "<style>\n.real { color: red; }\n</style>\n")
    cheap = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I)
    assert "-->" in cheap[0], "싼 과정이 정말로 주석 속에서 시작하는가"
    assert style_blocks(html) == [(4, "\n.real { color: red; }\n")]


def test_style_spans_point_at_exactly_the_style_bodies():
    """`style_spans` 의 [시작, 끝) 이 `style_blocks` 의 몸체와 글자째 같다 — 원문 치환이 이 자리를 쓴다."""
    seen = 0
    for f in sorted((ROOT / "src" / "templates").rglob("*.html")):
        html = f.read_text(encoding="utf-8")
        spans = style_spans(html)
        assert [html[s:e] for s, e in spans] == [css for _, css in style_blocks(html)], f.name
        seen += len(spans)
    assert seen >= 10, "`<style>` 자리를 거의 못 찾았다"


class _Markup(HTMLParser):
    """CSS 덩어리를 HTML 로 읽었을 때 태그·주석이 나오는가 — 진짜 `<style>` 몸체엔 없다."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.seen.append(f"<{tag}>")

    def handle_endtag(self, tag):
        self.seen.append(f"</{tag}>")

    def handle_comment(self, data):
        self.seen.append("<!--…-->")


def _markup_in(css: str) -> list[str]:
    """구조 스캐너가 읽은 셀렉터·선언에서만 찾는다 — CSS 주석 속 `<style>` 설명은 마크업이 아니다."""
    p = _Markup()
    for b in scan(css).blocks:
        p.feed(" ".join([b.prelude, *(f"{name}:{value}" for name, value in b.decls)]) + "\n")
    p.close()
    return p.seen


def test_no_extracted_style_block_contains_markup():
    """운영 템플릿 바닥 — 진짜 `<style>` 몸체엔 HTML 이 없다(추출이 어긋나면 첫 셀렉터에 `<link>` 등이 든다).

    🔴 정규식으로 태그를 찾지 않는다 — HTML 의 태그·주석 문법은 HTML 파서가 안다(CodeQL
       `py/bad-tag-filter` 가 대문자 태그·`--!>` 를 놓친다고 짚었다).
    """
    assert _markup_in("x --> <LINK rel=stylesheet> .a { color: red; }") == ["<link>"], (
        "바닥 — 셀렉터에 든 대문자 태그도 태그다")
    assert _markup_in("/* 본 <style> 블록 */ .a { color: red; }") == [], "주석 속 글자는 마크업이 아니다"
    leaked = [(s.path, s.line, _markup_in(s.text)) for s in authored_sources()
              if s.path.endswith(".html") and _markup_in(s.text)]
    assert not leaked, leaked


def test_every_linked_stylesheet_exists():
    """템플릿이 거는 `/static/css/*.css` 는 디스크에 있어야 한다(빌드 산출물 `dist/` 는 빌드가 만든다)."""
    hrefs = linked_stylesheets()
    assert any(h.startswith("/static/css/") for h in hrefs), "링크를 하나도 못 읽었다"
    missing = [h for h in hrefs if h.startswith("/static/css/") and "/dist/" not in h
               and not (ROOT / "src" / h.removeprefix("/")).is_file()]
    assert not missing, missing
