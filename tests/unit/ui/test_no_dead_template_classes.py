"""템플릿 마크업의 정적 클래스는 «읽혀야» 한다 — 규칙도 읽는 곳도 없는 클래스는 0 (회고 원장 R-13).

분석 상세의 이슈 등록 모달 «취소» 는 CSS 어디에도 규칙이 없는 Bootstrap 이름을 달아 여섯 달 동안 맨 글자로
그려졌고, «등록» 은 기본 `.btn` 없이 변형만 달아 색만 칠해졌다. 렌더 시험 · 정적 시험 모두 초록이었다.
Template classes must be read by something; a class nothing reads drew a bare-text button for six months.

판정 1 — 죽은 클래스. 템플릿 마크업(`<script>` · `<style>` · 주석 밖)의 정적 클래스 토큰마다 셋 중 하나가 있어야 한다.
  · 저자가 쓴 CSS(정적 파일 + 템플릿 `<style>` — `_css_structure.authored_sources`)의 셀렉터에 그 클래스가 있다.
  · 제품 쪽 코드가 그 이름을 쓴다 — 템플릿 `<script>` · `src/static/js` · 마크업의 다른 속성(`onclick` · `hx-target` …).
  · 시험 코드의 문자열이 그 이름을 «셀렉터 꼴»(`.이름`)이나 `class="… 이름 …"` 꼴로 쓴다.
  🔴 산문은 읽기가 아니다 — 독스트링 · 주석이 이름을 적었다고 클래스가 살아나지 않는다(`test_no_dead_design_tokens`
     와 같은 원칙). 그래서 시험 쪽은 AST 의 문자열 상수만 보고, 문장 자리에 홀로 선 문자열(독스트링)은 뺀다. 이 파일
     자신도 뺀다 — 이 독스트링과 대조군이 예로 드는 이름이 그 클래스를 살린다.
판정 2 — btn 변형은 `.btn` 과 함께. 변형 규칙은 색만 갖고 여백 · 모서리 · 테두리는 `.btn` 이 준다. 변형은 CSS 에서
  파생한다(손 목록이 아니다): `btn--*` · 셀렉터 목록에서 `btn--*` 와 묶인 옛 `btn-*` 이름(`.btn-primary, .btn--primary`) ·
  모든 규칙이 `.btn` 과 같은 복합 셀렉터에만 나오는 이름(`.btn.btn-sm`).

알려진 한계(의도): 셀렉터가 맥락(자손 · 형제)에서 실제로 맞는지는 보지 않는다 · Jinja 문자열 리터럴이나 런타임 JS 가
만드는 클래스는 보지 않는다 · Tailwind 빌드만이 정의하는 유틸리티는 지금 0개라 빌드 산출물(`dist/`, 추적 안 됨)을 읽지
않는다 — 템플릿에 그런 유틸리티를 쓰게 되면 이 판정이 막으므로, 그때 빌드 산출물을 판정에 넣는다.
Known limits: context of a matched selector, classes built in Jinja literals or at runtime, Tailwind-only utilities (none today).
"""
from __future__ import annotations

import ast
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from ._css_structure import ROOT, authored_sources, scan, selector_signature

_TEMPLATES = ROOT / "src" / "templates"
_STATIC_JS = ROOT / "src" / "static" / "js"
_TEST_DIRS = (ROOT / "tests", ROOT / "e2e")
_SELF = Path(__file__).resolve()

_JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.S)
_JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
_TOKEN = re.compile(r"-?[A-Za-z_][\w-]*")
_GROUP = re.compile(r"\([^()]*\)|\[[^\[\]]*\]|\"[^\"]*\"|'[^']*'")  # 가장 안쪽 묶음 / innermost group
# CSS 이스케이프 — 16진(뒤 공백 하나까지 이스케이프의 일부)을 먼저, 그다음 글자 하나(CSS Syntax 4.3.7)
# CSS escapes: hex first (one trailing whitespace belongs to it), then any single escaped character.
_HEX_ESCAPE = re.compile(r"\\[0-9a-fA-F]{1,6}[ \t\r\n\f]?")
_CHAR_ESCAPE = re.compile(r"\\.", re.S)
_COMMA = re.compile(r",")
_COMBINATOR = re.compile(r"\s*[>+~]\s*|\s+")
_VARIANT_PREFIX = "btn--"
_BASE = "btn"


class _Markup(HTMLParser):
    """마크업의 class 속성(줄 번호와 함께) · 그 밖의 속성값 · `<script>` 몸체를 모은다.

    `<script>` · `<style>` 안은 HTML 파서가 태그로 읽지 않는다 — 브라우저와 같다.
    Collects class attributes, other attribute values and script bodies; script/style content is not markup.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.classes: list[tuple[int, str]] = []
        self.other_attrs: list[str] = []
        self.scripts: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        self._attrs(attrs)
        self._in_script = tag == "script"

    def handle_startendtag(self, tag, attrs):
        self._attrs(attrs)

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            self.scripts.append(data)

    def _attrs(self, attrs) -> None:
        for key, value in attrs:
            if value is None:
                continue
            if key == "class":
                self.classes.append((self.getpos()[0], value))
            elif key != "style":
                self.other_attrs.append(value)


def _blank_jinja_comments(text: str) -> str:
    """Jinja 주석을 같은 길이의 공백으로 — 주석 안의 태그는 마크업이 아니고, 줄 번호는 그대로."""
    return _JINJA_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)


def static_tokens(raw: str) -> list[str]:
    """class 값에서 Jinja 식 · 태그를 지우고 남은 정적 토큰. `-` 로 끝나는 것은 Jinja 로 이어 붙인 이름의 앞부분이라 뺀다
    (`issue__sev--{{ sev }}`). Static tokens left after deleting Jinja; a '-'-ending token is a concatenation prefix."""
    return [t for t in _JINJA.sub(" ", raw).split() if _TOKEN.fullmatch(t) and not t.endswith("-")]


def parse_markup(text: str) -> _Markup:
    parser = _Markup()
    parser.feed(_blank_jinja_comments(text))
    parser.close()
    return parser


def _templates() -> dict[str, _Markup]:
    files = sorted(_TEMPLATES.rglob("*.html"))
    assert files, f"템플릿을 못 찾았다 — 경로가 바뀌었다: {_TEMPLATES}"
    return {f.relative_to(ROOT).as_posix(): parse_markup(f.read_text(encoding="utf-8")) for f in files}


def _style_preludes() -> list[str]:
    """저자가 쓴 스타일 규칙의 셀렉터 목록들. 🔴 깨진 원문에서는 판정하지 않는다 — 블록 목록을 믿을 수 없다."""
    out = []
    for src in authored_sources():
        res = scan(src.text)
        assert not res.defects, (
            f"전제 깨짐 — {src.path}:{src.line} 에 CSS 구조 결함 {res.defects[:3]} — "
            "`tests/unit/ui/test_css_structure.py` 를 먼저 고친다.")
        out += [b.prelude for b in res.blocks if b.kind == "style"]
    assert out, "저자가 쓴 스타일 규칙이 0개다 — 원문을 못 읽었다"
    return out


def _split_top(text: str, separator: re.Pattern) -> list[str]:
    """괄호 · 대괄호 · 따옴표 밖의 구분자로 자른다(`:is(.a, .b)` 안의 쉼표는 그대로).

    이스케이프와 안쪽 묶음부터 같은 길이의 NUL 로 가린 뒤, 가려지지 않은 자리에서만 구분자를 찾아 원문을 그 자리에서 자른다.
    Mask escapes and groups (innermost first) with same-length NULs, then cut the original where the mask has a separator.
    """
    def blank(m: re.Match) -> str:
        return "\0" * len(m.group())

    masked = _CHAR_ESCAPE.sub(blank, _HEX_ESCAPE.sub(blank, text))
    while (unmasked := _GROUP.sub(blank, masked)) != masked:
        masked = unmasked
    parts, start = [], 0
    for m in separator.finditer(masked):
        parts.append(text[start:m.start()])
        start = m.end()
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def _class_names(selector: str) -> set[str]:
    return {n[1:] for n in selector_signature("style", selector).split() if n.startswith(".")}


def ruled_classes(preludes: list[str]) -> set[str]:
    return set().union(*(_class_names(p) for p in preludes))


def btn_variants(preludes: list[str]) -> set[str]:
    """`.btn` 없이는 뜻이 없는 클래스 — CSS 에서 파생한다(모듈 독스트링 «판정 2»)."""
    variants: set[str] = set()
    alone: set[str] = set()      # `.btn` 없는 복합 셀렉터에 한 번이라도 나온 이름
    with_base: set[str] = set()  # `.btn` 과 같은 복합 셀렉터에 나온 이름
    for prelude in preludes:
        selectors = _split_top(prelude, _COMMA)
        # 셀렉터마다 주어(맨 오른쪽 복합)의 클래스 — `.btn--primary:hover .btn-arrow` 의 주어는 `.btn-arrow` 다
        # Subject (rightmost compound) classes per selector; an ancestor's modifier says nothing about the subject.
        subjects = [_class_names(_split_top(s, _COMBINATOR)[-1]) for s in selectors]
        variants |= {n for cls in subjects for n in cls if n.startswith(_VARIANT_PREFIX)}
        if any(n.startswith(_VARIANT_PREFIX) for cls in subjects for n in cls):
            variants |= {n for cls in subjects for n in cls if n.startswith(_BASE + "-")}
        for selector in selectors:
            for compound in _split_top(selector, _COMBINATOR):
                cls = _class_names(compound)
                (with_base if _BASE in cls else alone).update(cls - {_BASE})
    return variants | (with_base - alone)


def _test_strings() -> str:
    """시험 코드가 «쓰는» 문자열 상수를 잇는다 — 문장 자리에 홀로 선 문자열(독스트링)과 주석은 산문이라 뺀다.

    Joins the string constants test code uses; a string standing alone as a statement (a docstring) is prose.
    """
    chunks = []
    for root in _TEST_DIRS:
        for f in sorted(root.rglob("*.py")):
            if f.resolve() == _SELF:
                continue
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            prose = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}
            chunks += [n.value for n in ast.walk(tree)
                       if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in prose]
    assert chunks, "시험 문자열을 하나도 못 읽었다 — 경로가 바뀌었다"
    return "\n".join(chunks)


def _bounded(name: str) -> str:
    return r"(?<![\w-])" + re.escape(name) + r"(?![\w-])"


def product_reads(name: str, code: str) -> bool:
    return re.search(_bounded(name), code) is not None


def read_by_tests(name: str, strings: str) -> bool:
    return (re.search(r"(?<![\w-])\." + re.escape(name) + r"(?![\w-])", strings) is not None
            or re.search(r"class=[\"'][^\"'\n]*" + _bounded(name), strings) is not None)


def dead_classes(templates: dict[str, _Markup], ruled: set[str], product_code: str, strings: str) -> dict:
    uses: dict[str, set[str]] = {}
    for path, markup in templates.items():
        for _, raw in markup.classes:
            for token in static_tokens(raw):
                uses.setdefault(token, set()).add(path)
    assert uses, "템플릿에서 클래스를 하나도 못 읽었다 — 판정이 공허하다"
    return {name: sorted(paths) for name, paths in sorted(uses.items())
            if name not in ruled and not product_reads(name, product_code) and not read_by_tests(name, strings)}


def variants_without_base(templates: dict[str, _Markup], variants: set[str]) -> list[tuple[str, int, str]]:
    out = []
    for path, markup in templates.items():
        for line, raw in markup.classes:
            tokens = set(static_tokens(raw))
            if tokens & variants and _BASE not in tokens and re.search(_bounded(_BASE), _JINJA.sub(" ", raw)) is None:
                out.append((path, line, raw.strip()))
    return out


def _product_code(templates: dict[str, _Markup]) -> str:
    code = [s for m in templates.values() for s in m.scripts + m.other_attrs]
    code += [f.read_text(encoding="utf-8") for f in sorted(_STATIC_JS.rglob("*.js"))]
    return "\n".join(code)


def test_every_static_template_class_is_styled_or_read():
    """규칙도 읽는 곳도 없는 클래스 = 0. 걸리면: 규칙을 쓰거나(의도한 모양이 있었다면) 클래스를 지운다."""
    templates = _templates()
    dead = dead_classes(templates, ruled_classes(_style_preludes()), _product_code(templates), _test_strings())
    assert not dead, (
        "규칙도 읽는 곳도 없는 클래스가 템플릿에 있다 — 화면에 아무 일도 하지 않는다. 의도한 모양이 있었다면 규칙이 없는 "
        "것이고(R-13 «취소» 버튼), 아니면 지운다 / classes nothing styles or reads: "
        + "; ".join(f"{name} ({', '.join(paths)})" for name, paths in dead.items()))


def test_btn_variants_carry_the_base_btn_class():
    """btn 변형만 단 요소 = 0 — 색만 칠해지고 여백 · 모서리 · 테두리가 0 이 된다(R-13 «등록» 버튼)."""
    preludes = _style_preludes()
    variants = btn_variants(preludes)
    assert {"btn--primary", "btn--ghost"} <= variants, f"변형을 CSS 에서 못 읽었다 — 판정이 공허하다: {sorted(variants)}"
    missing = variants_without_base(_templates(), variants)
    assert not missing, (
        "btn 변형을 달았는데 같은 요소에 `btn` 이 없다 / variant without the base .btn: "
        + "; ".join(f"{p}:{line} class=\"{raw}\"" for p, line, raw in missing))


def test_the_judges_catch_the_r13_markup():
    """🔴 행동 대조군 — 고치기 전(#1893 직전) 모달 마크업을 두 판정에 넣으면 둘 다 잡아야 한다.

    셀렉터 목록 · 복합 셀렉터 파생도 함께 잰다: 옛 이름은 `btn--*` 와 묶여서, `btn-sm` 은 `.btn.btn-sm` 에만 나와서 변형이다.
    """
    markup = {"old/analysis_detail.html": parse_markup(
        '<div class="issue-modal-actions">'
        '<button type="button" class="btn-secondary" id="issueModalCancel">취소</button>'
        '<button type="button" class="btn-primary" id="issueModalSubmit">등록</button></div>')}
    preludes = [".btn", ".btn-primary, .btn--primary", ".btn-primary:hover, .btn--primary:hover",
                ".btn.btn-sm", ".issue-modal-actions"]
    dead = dead_classes(markup, ruled_classes(preludes), product_code="", strings="")
    assert dead == {"btn-secondary": ["old/analysis_detail.html"]}, dead
    variants = btn_variants(preludes)
    assert {"btn--primary", "btn-primary", "btn-sm"} <= variants and "btn" not in variants, sorted(variants)
    assert [raw for _, _, raw in variants_without_base(markup, variants)] == ["btn-primary"]
    # 같은 요소에 `btn` 이 있으면 통과 — 고친 뒤의 마크업 / passes once the base class is there
    fixed = {"new.html": parse_markup('<button class="btn btn--ghost">취소</button><button class="btn btn--primary">등록</button>')}
    assert variants_without_base(fixed, variants) == []


# witness-corpus: CSS 명세(Selectors 4 · Syntax 3)의 예에서 옮긴, 쉼표 · 결합자 글자가 구분자가 아닌 자리 — 묶음 정규식에서 뽑지 않았다
_INNER_SEPARATORS = (
    (":is(section, article) > h1, .b", ",", [":is(section, article) > h1", ".b"]),
    ("a[title='x, y'], .c", ",", ["a[title='x, y']", ".c"]),
    (r".a\,b, .c", ",", [r".a\,b", ".c"]),
    (r".\31 0, .d", ",", [r".\31 0", ".d"]),
    ("li:nth-child(2n+1) ~ li", " ", ["li:nth-child(2n+1)", "li"]),
    ('a[href~="x y"] > .b', " ", ['a[href~="x y"]', ".b"]),
    (r".a\>b .c", " ", [r".a\>b", ".c"]),
    (r".\31 0 .d", " ", [r".\31 0", ".d"]),
)


@pytest.mark.parametrize(("text", "kind", "expected"), _INNER_SEPARATORS)
def test_selectors_split_only_at_real_separators(text, kind, expected):
    """묶음(괄호 · 대괄호 · 따옴표) 안과 이스케이프된 글자는 구분자가 아니다 — 변형 파생(판정 2)이 주어 복합을 잘못 고르지 않게.

    Separators inside groups or escaped are not separators, so the variant derivation picks the right subject compound.
    """
    assert _split_top(text, _COMMA if kind == "," else _COMBINATOR) == expected
