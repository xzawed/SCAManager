r"""CSS 구조 스캐너 — 저자가 쓴 블록 구조를 엄격하게 읽고, 깨진 자리를 돌려준다.

🔴 «파서를 통과시킨다» 는 아무것도 재지 않는다. CSS 파서는 오류를 **복구**한다 — 깨진 자리 뒤의
   규칙을 조용히 버리거나 앞 규칙 안으로 옮긴다(Chromium: `}` 하나가 빠지면 뒤 규칙이 중첩
   규칙이 돼 화면에서 사라진다). 실측 — 깨짐 9모양을 `components.css` 에 하나씩 심으면
   lightningcss 엄격 모드는 7개, postcss(stylelint 의 파서)는 6개를 잡고, 둘 다 «주석이 다음
   주석까지 삼킨» 모양을 못 본다. 복구하는 파서는 자기가 복구한 결과를 정상으로 읽는다.

이 스캐너는 복구하지 않는다. 저자의 의도 — 괄호 짝 · 줄 안에서 닫히는 문자열 · 주석 경계 ·
규칙 사이엔 `;` 가 없다 · 선언 자리엔 블록이 없다(이 리포는 CSS 중첩을 쓰지 않는다) — 를 엄격히
읽어 어긋난 자리를 결함으로 내고, 블록 목록(문서 순서)을 돌려준다.

판정자는 둘이다. 단위 시험(`tests/unit/ui/test_css_structure.py`)은 이 스캐너의 결함 목록을,
e2e(`e2e/test_stylesheet_integrity.py`)는 이 블록 목록을 Chromium CSSOM 과 맞댄다. 스캐너가
못 그린 깨짐은 브라우저가 규칙을 잃는 것으로, 브라우저가 «적법» 하게 복구한 깨짐은 스캐너의
결함으로 드러난다.

🔴 템플릿의 `<style>` 은 정규식이 아니라 HTML 파서로 뽑는다(`style_blocks`). `base.html` 의 HTML
   주석이 `<style>` 이라는 글자를 품고 있어, `<style[^>]*>(.*?)</style>` 는 주석 한가운데서
   시작해 `-->`·`<link …>` 까지 CSS 로 읽는다 — 첫 규칙의 셀렉터가 쓰레기가 된다(실측: Chromium
   CSSOM 대조가 그 규칙 하나를 «버려졌다» 로 냈다).

Strict reader of authored CSS structure: reports where the author's structure breaks and
returns the block list (document order) that the e2e compares with Chromium's CSSOM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_CSS_DIR = ROOT / "src" / "static" / "css"
_TEMPLATES = ROOT / "src" / "templates"

STRAY_TERMINATOR = "주석 밖 `*/`"
UNTERMINATED_COMMENT = "닫히지 않은 `/*`"
NESTED_OPENER = "주석 안의 `/*` — 앞 주석이 다음 주석까지 삼켰다"
UNTERMINATED_STRING = "줄 안에서 닫히지 않은 문자열"
UNTERMINATED_URL = "닫히지 않은 `url(`"
MISMATCHED_CLOSE = "짝이 안 맞는 닫는 괄호"
BLOCK_IN_BRACKET = "`(`·`[` 안에서 열린 `{`"
UNCLOSED = "파일 끝까지 안 닫힌 괄호"
STRAY_CLOSE = "여는 짝 없는 `}`"
STRAY_SEMICOLON = "규칙 사이의 `;`"
EMPTY_PRELUDE = "셀렉터 없는 블록"
TRAILING_PRELUDE = "블록 없이 끝난 셀렉터"
NESTED_RULE = "선언 자리에 열린 블록(CSS 중첩) — 앞 `}` 가 빠졌을 때의 모양"
MALFORMED_DECLARATION = "속성 이름이 아닌 선언"

# 몸체가 «규칙 목록» 인 at-rule · «선언 목록» 인 at-rule. 나머지(모르는 것)는 둘 다 받는다.
# At-rules whose body is a rule list / a declaration list; unknown ones accept both.
_RULE_LIST_AT = frozenset({"media", "supports", "layer", "container", "document",
                           "-moz-document", "scope", "starting-style"})
_DECL_LIST_AT = frozenset({"font-face", "property", "counter-style", "font-palette-values",
                           "view-transition", "position-try"})
# 문장형 at-rule 이 CSSOM 에서 갖는 종류 — `@charset` 은 CSSOM 에 규칙으로 남지 않는다.
# CSSOM kind of statement at-rules; @charset leaves no rule in the CSSOM.
_STATEMENT_KIND = {"import": "import", "layer": "layer-statement", "namespace": "namespace"}

_PROP_NAME = re.compile(r"--[\w-]+|-?[A-Za-z_][\w-]*")
_AT_NAME = re.compile(r"@([\w-]+)")
# 다른 엔진 전용 접두사 — Chromium 은 이 셀렉터·at-rule 을 «적법하게» 버린다.
# Other-engine vendor prefixes: Chromium legitimately drops these selectors and at-rules.
_OTHER_ENGINE_SELECTOR = re.compile(r"::?-(?:moz|ms|o)-")
_OTHER_ENGINE_AT = re.compile(r"@-(?:moz|ms|o)-")


@dataclass(frozen=True)
class Block:
    """블록 하나 — 문서 순서. `kind` 는 CSSOM 의 규칙 종류와 같은 이름을 쓴다.

    `span` = (여는 `{` 의 위치, 닫는 `}` 의 위치) — 안 닫혔거나 문장형 at-rule 이면 -1.
    """
    depth: int
    kind: str
    prelude: str
    line: int
    decls: tuple[tuple[str, str], ...] = ()
    span: tuple[int, int] = (-1, -1)


@dataclass
class Scan:
    blocks: list[Block] = field(default_factory=list)
    defects: list[tuple[int, str]] = field(default_factory=list)


def _trim(raw: str) -> str:
    """앞뒤 공백을 깎되 이스케이프된 공백(`\\ `)은 남긴다 — 그것은 이름의 일부다.

    🔴 `" ".join(raw.split())` 로 접으면 `.a\\ ` 가 `.a\\` 가 돼 뜻이 바뀐다(실측: 백슬래시 변이 퍼즈).
    Trim surrounding whitespace but keep an escaped one, which belongs to the identifier.
    """
    s = raw.lstrip()
    end = len(s.rstrip())
    if end < len(s):
        k = end - 1
        while k >= 0 and s[k] == "\\":
            k -= 1
        if (end - 1 - k) % 2:
            end += 1
    return s[:end]


def _at_kind(name: str) -> tuple[str, str]:
    """at-rule 이름 → (CSSOM 종류, 몸체 문법)."""
    if name.endswith("keyframes"):
        return "keyframes", "keyframes"
    if name in _RULE_LIST_AT:
        return name.removeprefix("-moz-"), "rules"
    if name in _DECL_LIST_AT:
        return name, "decls"
    if name == "page":
        return "page", "mixed"
    return f"at:{name}", "mixed"


class _Scanner:
    def __init__(self, src: str) -> None:
        self.s, self.n, self.i, self.line = src, len(src), 0, 1
        self.out = Scan()

    # ── 결함 · 낮은 층 ────────────────────────────────────────────────
    def defect(self, kind: str, line: int | None = None) -> None:
        self.out.defects.append((self.line if line is None else line, kind))

    def skip_comment(self) -> None:
        """`/*` 에서 짝 `*/` 다음으로. 몸체에 `/*` 가 있으면 앞 주석이 다음 주석을 삼킨 것이다."""
        start_line, end = self.line, self.s.find("*/", self.i + 2)
        if end < 0:
            self.defect(UNTERMINATED_COMMENT, start_line)
            self.line += self.s.count("\n", self.i)
            self.i = self.n
            return
        inner = self.s.find("/*", self.i + 2, end)
        if inner >= 0:
            self.defect(NESTED_OPENER, start_line + self.s.count("\n", self.i, inner))
        self.line += self.s.count("\n", self.i, end)
        self.i = end + 2

    def skip_string(self) -> None:
        """여는 따옴표에서 닫는 따옴표 다음으로. 날 줄바꿈이 먼저 오면 결함이고 거기서 멈춘다."""
        quote, j = self.s[self.i], self.i + 1
        while j < self.n:
            c = self.s[j]
            if c == "\\":
                if j + 1 < self.n and self.s[j + 1] == "\n":
                    self.line += 1
                j += 2
            elif c == quote:
                self.i = j + 1
                return
            elif c == "\n":
                break
            else:
                j += 1
        self.defect(UNTERMINATED_STRING)
        self.i = j

    def at_unquoted_url(self) -> bool:
        """`url(` + 따옴표 아닌 첫 글자 — 통째로 한 토큰이다(그 안의 `*/`·`/*`·`;` 는 문법이 아니다)."""
        if self.s[self.i:self.i + 4].lower() != "url(":
            return False
        if self.i and (self.s[self.i - 1].isalnum() or self.s[self.i - 1] in "-_\\"):
            return False
        k = self.i + 4
        while k < self.n and self.s[k] in " \t\r\n\f":
            k += 1
        return k < self.n and self.s[k] not in "\"')"

    def skip_url(self) -> None:
        close = self.s.find(")", self.i + 4)
        if close < 0:
            self.defect(UNTERMINATED_URL)
            self.line += self.s.count("\n", self.i)
            self.i = self.n
            return
        self.line += self.s.count("\n", self.i, close)
        self.i = close + 1

    def skip_ws_and_comments(self) -> None:
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\n":
                self.line += 1
                self.i += 1
            elif c in " \t\r\f":
                self.i += 1
            elif self.s.startswith("/*", self.i):
                self.skip_comment()
            else:
                return

    def read_until(self, stops: str, braces: str, custom: bool = False) -> tuple[str, str | None]:
        """괄호 깊이 0 에서 `stops` 의 글자를 만날 때까지 읽는다 → (원문, 멈춘 글자 | None=끝).

        braces — `{` 를 만났을 때: "stop"(블록 시작) · "nest"(값 안의 블록, 커스텀 속성) ·
        "error"(값 자리의 블록 = 결함, 멈춘다). 🔴 커스텀 속성 값(`custom`)은 거의 모든 토큰을
        담는다 — 그 안의 `*/` 는 적법하다(Chromium: `.a{--x:*/;}` 는 규칙 둘이 다 산다).
        """
        # 🔴 돌려주는 원문엔 주석을 넣지 않는다 — 셀렉터 목록 사이의 주석 글자(`.68`)가
        #    셀렉터로 읽히면 표지가 Chromium 과 어긋난다(실측: admin.css).
        # Comments are left out of the returned text; they are not part of a selector or value.
        parts: list[str] = []
        seg, stack = self.i, []

        def text() -> str:
            return "".join(parts) + self.s[seg:self.i]

        while self.i < self.n:
            c = self.s[self.i]
            if self.s.startswith("/*", self.i):
                parts.append(self.s[seg:self.i] + " ")
                self.skip_comment()
                seg = self.i
                continue
            if self.s.startswith("*/", self.i) and not custom:
                self.defect(STRAY_TERMINATOR)
                self.i += 2
                continue
            if c in "\"'":
                self.skip_string()
                continue
            if c == "\\":
                if self.i + 1 < self.n and self.s[self.i + 1] == "\n":
                    self.line += 1
                self.i += 2
                continue
            if c == "\n":
                self.line += 1
                self.i += 1
                continue
            if c in "uU" and self.at_unquoted_url():
                self.skip_url()
                continue
            if c in "([":
                stack.append((c, self.line))
            elif c in ")]":
                want = "(" if c == ")" else "["
                if stack and stack[-1][0] == want:
                    stack.pop()
                else:
                    self.defect(MISMATCHED_CLOSE)
                    if any(o == want for o, _ in stack):
                        while stack[-1][0] != want:
                            stack.pop()
                        stack.pop()
            elif c == "{":
                if stack and stack[-1][0] in "([":
                    self.defect(BLOCK_IN_BRACKET)
                    stack = [x for x in stack if x[0] == "{"]
                if stack or braces == "nest":
                    stack.append(("{", self.line))
                elif "{" in stops:
                    return text(), "{"
                else:
                    self.defect(NESTED_RULE)
                    return text(), "{"
            elif c == "}":
                if stack and stack[-1][0] in "([":
                    self.defect(MISMATCHED_CLOSE)
                    stack = [x for x in stack if x[0] == "{"]
                if stack:
                    stack.pop()
                elif "}" in stops:
                    return text(), "}"
            elif c in stops and not stack:
                return text(), c
            self.i += 1
        for _opener, opened_at in stack:
            self.defect(UNCLOSED, opened_at)
        return text(), None

    # ── 블록 · 목록 ───────────────────────────────────────────────────
    def open_block(self, prelude: str, depth: int, line: int, *, keyframe: bool = False) -> None:
        if keyframe:
            kind, body = "keyframe", "decls"
        elif prelude.startswith("@"):
            m = _AT_NAME.match(prelude)
            kind, body = _at_kind(m.group(1).lower()) if m else ("at:", "mixed")
        else:
            kind, body = "style", "decls"
        slot, opened = len(self.out.blocks), self.i - 1  # 부르는 쪽이 `{` 를 막 넘겼다
        self.out.blocks.append(Block(depth, kind, prelude, line))  # 자리 — 문서 순서를 지킨다
        decls: list[tuple[str, str]] = []
        if body == "rules":
            closed = self.parse_rules(depth + 1, top=False)
        elif body == "keyframes":
            closed = self.parse_rules(depth + 1, top=False, keyframes=True)
        else:
            closed = self.parse_decls(depth + 1, decls, mixed=body == "mixed")
        self.out.blocks[slot] = Block(depth, kind, prelude, line, tuple(decls),
                                      (opened, self.i - 1 if closed else -1))
        if not closed:
            self.defect(UNCLOSED, line)

    def statement(self, prelude: str, depth: int, line: int) -> None:
        m = _AT_NAME.match(prelude)
        name = m.group(1).lower() if m else ""
        if name == "charset":
            return
        self.out.blocks.append(Block(depth, _STATEMENT_KIND.get(name, f"at:{name};"), prelude, line))

    def parse_rules(self, depth: int, *, top: bool, keyframes: bool = False) -> bool:
        """규칙 목록 — 닫는 `}` 를 만나면 True, 파일 끝이면 False."""
        while True:
            self.skip_ws_and_comments()
            if self.i >= self.n:
                return False
            if self.s[self.i] == "}":
                self.i += 1
                if top:
                    self.defect(STRAY_CLOSE)
                    continue
                return True
            line = self.line
            raw, stop = self.read_until(";{}", braces="stop")
            prelude = _trim(raw)
            if stop == "{":
                self.i += 1
                if not prelude:
                    self.defect(EMPTY_PRELUDE, line)
                self.open_block(prelude, depth, line, keyframe=keyframes)
            elif stop == ";":
                self.i += 1
                if prelude.startswith("@") and not keyframes:
                    self.statement(prelude, depth, line)
                else:
                    self.defect(STRAY_SEMICOLON, line)
            elif prelude:
                self.defect(TRAILING_PRELUDE, line)
            if stop is None:
                return False

    def parse_decls(self, depth: int, decls: list[tuple[str, str]], *, mixed: bool) -> bool:
        """선언 목록 — 닫는 `}` 를 만나면 True, 파일 끝이면 False. `mixed` 면 블록도 받는다."""
        while True:
            self.skip_ws_and_comments()
            if self.i >= self.n:
                return False
            c = self.s[self.i]
            if c == "}":
                self.i += 1
                return True
            if c == ";":
                self.i += 1
                continue
            line = self.line
            if c == "@":
                raw, stop = self.read_until(";{}", braces="stop")
                if stop == "{":
                    if not mixed:
                        self.defect(NESTED_RULE, line)
                    self.i += 1
                    self.open_block(_trim(raw), depth, line)
                elif stop == ";":
                    self.i += 1
                elif stop is None:
                    return False
                continue
            raw, stop = self.read_until(":;{}", braces="stop")
            if stop == ":":
                self.i += 1
                name = raw.strip()
                custom = name.startswith("--")
                if not _PROP_NAME.fullmatch(name):
                    self.defect(MALFORMED_DECLARATION, line)
                value, vstop = self.read_until(";}", braces="nest" if custom else "error",
                                               custom=custom)
                if vstop == "{":
                    # 값 자리의 블록 — 앞 규칙의 `}` 가 빠져 다음 규칙이 선언으로 읽혔다.
                    # A block where a value belongs: the previous rule lost its `}`.
                    self.i += 1
                    self.open_block(_trim(f"{raw}:{value}"), depth, line)
                    continue
                decls.append((name if custom else name.lower(), " ".join(value.split())))
                if vstop == ";":
                    self.i += 1
                elif vstop is None:
                    return False
                continue
            if stop == "{":
                if not mixed:
                    self.defect(NESTED_RULE, line)
                self.i += 1
                self.open_block(_trim(raw), depth, line)
                continue
            if raw.strip():
                self.defect(MALFORMED_DECLARATION, line)
            if stop == ";":
                self.i += 1
            elif stop is None:
                return False


def scan(src: str) -> Scan:
    """원문을 엄격히 읽는다 → 블록 목록(문서 순서) + 결함 (줄, 종류)."""
    sc = _Scanner(src)
    sc.parse_rules(0, top=True)
    return sc.out


_HEX_ESCAPE = r"\\[0-9a-fA-F]{1,6}[ \t\r\n\f]?"
# 이름 글자 = 영숫자·`_`·`-`·비ASCII 전부(CSS Syntax «ident code point») — `\w` 는 비ASCII 일부를 뺀다.
# Ident code points: ASCII alnum, `_`, `-` and every non-ASCII code point.
_CLASS_OR_ID = re.compile(rf"[.#](?:{_HEX_ESCAPE}|\\.|[A-Za-z0-9_\-\u0080-\U0010FFFF])+", re.S)
_ESCAPE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})[ \t\r\n\f]?|(.))", re.S)


def _unescape(token: str) -> str:
    """CSS 이스케이프를 푼다 — `\\-`·`\\31 ` 는 같은 이름이다(CSS Syntax 4.3.7)."""
    def one(m: re.Match) -> str:
        if m.group(2) is not None:
            return m.group(2)
        code = int(m.group(1), 16)
        return chr(code) if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else "�"
    return _ESCAPE.sub(one, token)


def selector_signature(kind: str, selector: str) -> str:
    """규칙을 가리키는 표지 — 스타일 규칙은 셀렉터의 클래스·id 집합(이스케이프를 푼 이름), 나머지는 빈 문자열.

    🔴 셀렉터 «문자열» 을 비교하지 않는다 — Chromium 은 직렬화하며 공백·따옴표·`*`·`::`·불필요한
       이스케이프를 바꾼다(`*:focus-visible` → `:focus-visible`, `.a\\-b` → `.a-b`). 이스케이프를 푼
       클래스·id 이름은 바꾸지 않는다(실측: 변이 퍼즈에서 이스케이프를 안 풀면 오탐).
    Class/id set (escapes decoded) of a style rule's selector — serialization-stable.
    """
    if kind != "style":
        return ""
    return " ".join(sorted({_unescape(t) for t in _CLASS_OR_ID.findall(selector)}))


def chromium_kept(blocks: list[Block]) -> list[Block]:
    """Chromium 이 들고 있어야 할 블록 — 문서 순서.

    다른 엔진 전용 셀렉터(`::-moz-range-thumb`)·at-rule(`@-moz-document`)은 Chromium 이 «적법하게»
    버리므로 그 블록과 자손을 뺀다. 판정은 원문에서 파생한다 — 손 목록이 아니다.
    """
    out: list[Block] = []
    skip_below: int | None = None
    for b in blocks:
        if skip_below is not None:
            if b.depth > skip_below:
                continue
            skip_below = None
        foreign = (_OTHER_ENGINE_AT.match(b.prelude) if b.prelude.startswith("@")
                   else b.kind == "style" and _OTHER_ENGINE_SELECTOR.search(b.prelude))
        if foreign:
            skip_below = b.depth
            continue
        out.append(b)
    return out


def chromium_expected(blocks: list[Block]) -> list[tuple[int, str, str]]:
    """`chromium_kept` 의 (깊이, 종류, 표지) — CSSOM 쪽과 같은 모양으로 맞댄다."""
    return [(b.depth, b.kind, selector_signature(b.kind, b.prelude)) for b in chromium_kept(blocks)]


# ── 원문 — 어디의 CSS 를 판정하는가 ─────────────────────────────────────
class _StyleAndLinks(HTMLParser):
    """`<style>` 몸체(시작 줄과 함께)와 `<link rel=stylesheet>` 의 href 를 모은다.

    HTML 주석·`<script>` 안의 `<style>` 글자는 태그가 아니다 — 브라우저와 같다.
    """

    def __init__(self) -> None:
        super().__init__()
        self.styles: list[tuple[int, str]] = []
        self.hrefs: list[str] = []
        self._buf: list[str] | None = None
        self._line = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "style":
            # CSS 는 여는 태그가 «끝난» 줄에서 시작한다 — 속성이 여러 줄이면 그만큼 내려간다.
            # The CSS starts on the line where the start tag ends.
            self._buf = []
            self._line = self.getpos()[0] + (self.get_starttag_text() or "").count("\n")
        elif tag == "link" and "stylesheet" in (a.get("rel") or "").split() and a.get("href"):
            self.hrefs.append(a["href"])

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "style" and self._buf is not None:
            self.styles.append((self._line, "".join(self._buf)))
            self._buf = None


def _parse_html(text: str) -> _StyleAndLinks:
    p = _StyleAndLinks()
    p.feed(text)
    p.close()
    return p


def style_blocks(html: str) -> list[tuple[int, str]]:
    """템플릿 원문의 `<style>` 몸체 → [(파일 안에서 `<style>` 태그가 있는 줄, CSS)]."""
    return _parse_html(html).styles


@dataclass(frozen=True)
class Source:
    """판정할 CSS 한 덩어리. `line` = 그 덩어리의 1행이 파일에서 몇 번째 줄인가."""
    path: str
    line: int
    text: str
    served: bool  # 브라우저가 실제로 받는가 — 템플릿이 링크하는 파일 · 템플릿 `<style>`


def authored_sources() -> list[Source]:
    """저자가 쓴 CSS 전부 — 정적 파일(빌드 산출물 `dist/` 제외) + 템플릿 `<style>`.

    `served` 는 템플릿이 링크하는가로 파생한다 — Tailwind 입력(`main.css`)은 브라우저가 받지
    않는다(빌드가 `dist/` 로 바꾼다). 손 목록이 아니다.
    """
    linked: set[str] = set()
    templates: list[tuple[str, str]] = []
    for f in sorted(_TEMPLATES.rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        templates.append((f.relative_to(ROOT).as_posix(), text))
        linked |= {h.split("?")[0] for h in _parse_html(text).hrefs}
    out = [Source(f.relative_to(ROOT).as_posix(), 1, f.read_text(encoding="utf-8"),
                  f"/static/css/{f.name}" in linked)
           for f in sorted(_CSS_DIR.glob("*.css"))]
    for rel, text in templates:
        out += [Source(rel, line, css, True) for line, css in style_blocks(text)]
    return out


def template_links() -> dict[str, tuple[str | None, frozenset[str]]]:
    """템플릿 이름마다 (상속하는 부모 템플릿 | None, `<link rel=stylesheet>` href 집합 — 쿼리 제외).

    상속은 Jinja 파서로 본다 — `{% extends` 글자 검사는 주석 속 글자에도 맞는다.
    Per template name: the parent it extends (Jinja AST) and the stylesheet hrefs it links.
    """
    import jinja2  # pylint: disable=import-outside-toplevel
    # 파싱만 한다(렌더 안 함) — CodeQL `py/jinja2/autoescape-false` 는 시험 코드에도 뜬다.
    # Parse only (never rendered); CodeQL flags autoescape=False even in test code.
    env = jinja2.Environment(autoescape=True)
    out: dict[str, tuple[str | None, frozenset[str]]] = {}
    for f in sorted(_TEMPLATES.rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        node = next(env.parse(text).find_all(jinja2.nodes.Extends), None)
        parent = (node.template.value
                  if node is not None and isinstance(node.template, jinja2.nodes.Const) else None)
        out[f.relative_to(_TEMPLATES).as_posix()] = (
            parent, frozenset(h.split("?")[0] for h in _parse_html(text).hrefs))
    return out


def linked_stylesheets() -> set[str]:
    """템플릿이 `<link rel=stylesheet>` 로 거는 href(쿼리 제외) 전부."""
    return {h for _, hrefs in template_links().values() for h in hrefs}
