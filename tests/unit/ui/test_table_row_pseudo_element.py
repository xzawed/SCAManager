r"""표의 행에 ::before/::after 를 달지 않는다 — Chromium 은 그것을 «열 하나» 로 센다.

🔴 무엇을 막는가

    .x tbody tr::before   { content: ""; position: absolute; left: 0; width: 3px; }
    .analysis-row::before { content: ""; ... }   ← `<tr class="analysis-row">` 의 클래스

   headless Chromium 153 실측 — `position: absolute` 여도 행의 가상 요소가 첫 열 자리를
   차지해, 본문 행의 `td` 가 머리글 `th` 보다 **한 칸씩 오른쪽** 에 그려진다
   (가상 요소 없음 → th x == td x · `tr::before` absolute/static → 어긋남 ·
   `td:first-child::before` + `td:first-child { position: relative }` → 일치).
   행 강조선은 첫 칸에 단다 — `tr:hover td:first-child::before`.

🔴 «행» 의 정의 — 가상 요소를 **직접** 단 복합 셀렉터가
   · 타입 `tr` 이거나(대소문자 무시) `:is()`·`:where()` 인자의 주어가 행이거나,
   · 「행 클래스」 `.cls` 나 「행 id」 `#id` 를 가지거나(`:not()` 등 함수 안은 세지 않는다),
   · 타입 없는 복합이면서 최상위 `:has(…)` 인자에 `td`/`th` 가 있거나(`:not()` 안은 제외),
   · 타입 없는 복합이 결합만으로 행을 고른다 — `tbody|thead|tfoot > 그것`(행 그룹의 자식은 `tr`
     뿐이라 `.x` 도) · `tbody|thead|tfoot|table 그것`(자손 — 클래스·id 없는 `*`·`:…`·`[…]` 만) ·
     `행 + 그것`·`행 ~ 그것`(행의 형제는 행 · `thead + *` 는 행 그룹이라 아니다).
     맨 앞 `:is(…)`/`:where(…)` 는 인자의 주어로 읽는다 — `:is(td, th)` 는 타입 있는 셀,
     `:is(tbody, tfoot) > *` 는 행 그룹의 자식.
   행 클래스·id = git 추적 `src/templates/**/*.html`(본문·`<script>` 문자열 전부)과
   `src/static/js/**/*.js` 에서 `<tr … class="a b" id="c">` 로 붙은 것(속성값 속 `>` 를 건너뛴다) +
   `document.createElement('tr')` 를 받은 변수나 그 체인에 `.className =`/`+=`·`.classList(?.)add(`
   ·`.id =` 로 붙은 것. Jinja·JS 보간(`{{ }}`·`{% %}`·`{# #}`·`${}`·`' + x + '`)과 HTML 주석은 걷어 낸다.
   `.analysis-row td:first-child::before` 는 가상 요소가 `td` 복합에 있으므로 행이 아니다.

🔴 계기를 뒤집어 봤다(`docs/workflow/verify.md` 「판정식을 쓸 때」 4).
   타입 `tr`
     claimed: `tr:hover::before` · `tr.row::after` · `tr:not(:nth-child(2))::before`(괄호
       중첩) · `tr:not(:is(.a, .b) .c)::before`(두 겹 괄호 속 공백 — 한 겹만 가리면 놓친다) ·
       `TR::Before` · `:is(tr)::before` · 정적 CSS 와 템플릿 `<style>` 양쪽 · 주석 속 언급은 제외
     cheap(부분문자열 `tr::before`): 주석 · `.tr::before` · `.str::before` 를 잡고
       `tr:hover::before` · `tr:before` · `TR::Before` 를 놓친다
   행 클래스 — 첫 출력 「repo_detail.html 의 `.analysis-row::before` 두 줄」
     claimed: `<tr class="{% if x %}hot{% endif %}">` 의 `hot` · JS 문자열
       `'<tr class="x y">'` 의 x·y · `createElement('tr')` 변수의 `className`·`classList.add`
     cheap(이름에 `row` 가 든 클래스 + 가상 요소): `li` 의 `.issue-row::before` 를 잡고
       `hot`·`x`·`y` 를 놓친다
   claimed\cheap → 반드시 잡혀야(`test_catches_…`·`test_collects_…`) · cheap\claimed →
   반드시 무시돼야(`test_ignores_…`·`test_does_not_collect_…`) — 둘째로 싼 과정
   (`<tr[^>]*class="…"`)이 넘어질 `<td class>`·`<track class>`·`data-class=`·주석 속
   `<tr class>` 도 거기 둔다. 같은 심음을 손대지 않은 운영 파일에 끼워 넣고도 같은 뒤집힘을
   요구한다(`test_plants_…`).

🔴 이 계기가 **못 보는** 것 — 여기 걸리지 않아도 안전하다는 뜻이 아니다.
   · CSS 중첩 `tr { &::before {} }` — 이 리포 CSS 는 중첩을 쓰지 않는다(`&` 는 `main.css`
     의 `@custom-variant` 에만 있다 — 실측).
   · 속성으로 고른 행(`[class~="x"]::before` — 행 그룹 바로 아래가 아닐 때) · `thead`/`tbody`
     자신의 가상 요소(`table > *`) · `display: table-row` 를 준 비-`tr` 요소 ·
     CSS 이스케이프로 쓴 타입(`\74 r`) · 셀렉터 속성 문자열 안의 `{`(`tr[data-x="{"]` —
     셀렉터 머리가 `{` 에서 끊긴다) · 결합으로만 행이 되는 복합의 다음 형제(`tbody > * + *`).
   · 변수로 이어 붙인 클래스(`'<tr' + rowCls + '>'` — `settings.html` 의 `pt-row-same`),
     실행 중 아무 요소에나 붙는 클래스(`.reveal` 에 붙는 `visible`), `setAttribute('class')`
     · `classList.toggle`.
   · 과잉 수집·판정(시끄러운 red 쪽): JS 주석 속 `<tr class>`, `createElement('tr')` 변수 이름을
     같은 파일에서 다른 요소에 다시 쓴 경우(변수는 파일 안 «이름» 으로 따라간다),
     `table :not(tr)::before`(행을 뺀 `:not` 도 타입 없는 자손으로 센다).
   · JS 가 주입하는 스타일, gitignore 된 `dist/tailwind.css`, `src/static/mockup-polar.html`.

Table rows must not carry ::before/::after: Chromium lays the row pseudo-element out as an
extra first column, shifting every body cell one column right of its header. A row is the `tr`
type (also inside `:is()`/`:where()`), a class or id the templates/JS put on a `tr`, a typeless
`:has(td)`, or a typeless compound whose combinator context makes it a row (`tbody > *`,
`table *`, `tr + *`); the pseudo must sit on that compound itself
(`.row td:first-child::before` is a cell). Not covered: CSS nesting, attribute-selected rows
outside a row group, row-group pseudos, CSS escapes, classes spliced in through a variable or
added at runtime to generic elements.
"""
from __future__ import annotations

import functools
import re
import subprocess  # nosec B404

import pytest

from ._contrast import ROOT

# `{` 앞의 셀렉터 머리 — 직전 `{` · `}` · `;` 뒤부터 `{` 까지.
# A rule prelude: the text between the previous `{`/`}`/`;` and the next `{`.
_PRELUDE = re.compile(r"([^{};]*)\{")
_STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)

# 가상 요소(구식 한 콜론 포함) · 타입 `tr` · 클래스 · `:is(`/`:where(` — 전부 «가린» 문자열에 쓴다.
# Pseudo-element / `tr` type / class / :is( :where( — all applied to the masked compound.
_PSEUDO_EL = re.compile(r"::?(?:before|after)(?![\w-])", re.I)
_TYPE_TR = re.compile(r"tr(?![\w-])", re.I)
_CLASS = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")
_ID = re.compile(r"#(-?[_a-zA-Z][\w-]*)")
_IS_WHERE = re.compile(r":(?:is|where)\(", re.I)
# 타입이 없는 복합(`*`·`:nth-child()`·`[x]` 로 시작)이 행 그룹 바로 아래면 행을 고른다.
# A typeless compound right under a row group selects rows (`tbody > *`, `tbody :nth-child(odd)`).
_ROW_GROUP = re.compile(r"(?:tbody|thead|tfoot)(?![\w-])", re.I)
_TYPELESS = re.compile(r"[*:\[.#]")
_HAS = re.compile(r":has\(", re.I)
_CELL_TYPE = re.compile(r"(?<![\w-])(?:td|th)(?![\w-])", re.I)
# 행 그룹 — `>` 자식이면 tbody·thead·tfoot, 자손이면 table 도(그 안의 `*` 는 행을 포함한다).
_ROW_GROUP_OR_TABLE = re.compile(r"(?:tbody|thead|tfoot|table)(?![\w-])", re.I)

# 행 클래스 수집. `<tr` 다음 글자가 공백·`>`·`/` 여야 `<track` · `<tref` 가 빠진다.
# 속성값 안의 `>`(`title="HP > 50"`)에서 끊기지 않게 따옴표를 건너뛰고, 따옴표가 짝이 안 맞으면
# 옛 형태(`[^>]*`)로 물러선다. Quote-aware, falling back to the plain form on unbalanced quotes.
_TR_TAG = re.compile(r"<tr(?=[\s>/])(?:((?:[^>\"']|\"[^\"]*\"|'[^']*')*)|([^>]*))>", re.I)
_CLASS_ATTR = re.compile(r"(?<![\w-])class\s*=\s*(?:(\\?[\"'])(.*?)\1|([\w-]+))", re.I | re.S)
_ID_ATTR = re.compile(r"(?<![\w-])id\s*=\s*(?:(\\?[\"'])(.*?)\1|([\w-]+))", re.I | re.S)
_CREATE_TR = re.compile(r"([A-Za-z_$][\w$]*)\s*=\s*document\.createElement\(\s*([\"'`])(?i:tr)\2\s*\)")
_CREATE_TR_CHAIN = r"document\.createElement\(\s*([\"'`])(?i:tr)\1\s*\)"
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.S)
_JS_INTERP = re.compile(r"\$\{[^}]*\}|([\"'`])\s*\+.*?\+\s*\1", re.S)
_IDENT = re.compile(r"-?[_a-zA-Z][\w-]*")


def _strip_comments(src: str) -> str:
    r"""주석을 지우되 줄바꿈 수는 남긴다 — 보고하는 줄이 파일의 줄과 맞도록.

    `re.sub(r"/\*.*?\*/", "", src, flags=re.S)` 관용구 그대로, 지운 자리에 그 주석이 품었던
    줄바꿈만 되돌려 둔다. 주석 안에서 규칙을 인용해도(`/* tbody tr::before */`) 걸리지 않는다.
    Strip comments (repo idiom) but keep their newlines so reported lines match the file.
    """
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)


def _mask(sel: str) -> str:
    r"""괄호·대괄호·따옴표 «안» 을 `\0` 으로 가린다(길이 보존) — 최상위만 읽도록.

    `tr:not(:nth-child(2))::before` → `tr:not(\0…\0)::before`. 중첩 괄호도 바깥 한 쌍만 남는다.
    Mask everything nested (length-preserving) so combinators, commas and pseudos are read at
    the top level only; nested parentheses collapse into the outer pair.
    """
    out: list[str] = []
    depth, quote = 0, ""
    for ch in sel:
        if quote:
            out.append("\0")
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            out.append("\0")
        elif ch in "([":
            out.append("\0" if depth else ch)
            depth += 1
        elif ch in ")]" and depth:
            depth -= 1
            out.append("\0" if depth else ch)
        else:
            out.append("\0" if depth else ch)
    return "".join(out)


def _spans(sel: str, pattern: str) -> list[tuple[int, str]]:
    """가린 문자열에서 `pattern` 구간을 찾아 원문 조각을 (시작, 원문) 으로.
    Top-level pieces of `sel` (found on the masked text, returned as original slices)."""
    return [(m.start(), sel[m.start():m.end()]) for m in re.finditer(pattern, _mask(sel))]


def _compounds(sel: str) -> list[tuple[int, str]]:
    """복합 셀렉터들 — 최상위 공백·`>`·`+`·`~` 가 가른다. Compounds split on top-level combinators."""
    return _spans(sel, r"[^\s>+~]+")


def _row_reason(compound: str, row_classes: frozenset[str]) -> str | None:
    """이 복합 셀렉터가 표의 행을 고르면 그 근거(`tr` · `.cls` · `:is(…)`), 아니면 None.
    Why this compound selects a table row (`tr`, `.cls`, `:is(...)`), or None."""
    masked = _mask(compound)
    if _TYPE_TR.match(masked):
        return "tr"
    for cls in _CLASS.findall(masked):
        if cls in row_classes:
            return "." + cls
    for ident in _ID.findall(masked):
        if "#" + ident in row_classes:
            return "#" + ident
    if _TYPELESS.match(compound) and _has_cell(compound, masked):
        return ":has(td)"
    for fn in _IS_WHERE.finditer(masked):
        close = masked.find(")", fn.end())
        if close < 0:
            continue
        for _, arg in _spans(compound[fn.end():close], r"[^,]+"):
            parts = _compounds(arg)
            inner = _row_reason(parts[-1][1], row_classes) if parts else None
            if inner:
                return f":is({inner})"
    return None


def _has_cell(compound: str, masked: str) -> bool:
    """최상위 `:has(…)` 인자에 `td`/`th` 가 있는가 — 셀을 품은 요소는 행이거나 행을 포함한다.
    `:not(:has(> td))` 처럼 다른 함수 안의 `:has` 는 세지 않는다.
    A top-level `:has(...)` mentioning `td`/`th`; a `:has` nested in `:not()` does not count."""
    for fn in _HAS.finditer(masked):
        close = masked.find(")", fn.end())
        if close >= 0 and _CELL_TYPE.search(compound[fn.end():close]):
            return True
    return False


def _by_context(masked_sel: str, spans: list[tuple[int, str]], i: int,
                row_classes: frozenset[str]) -> str | None:
    """타입 없는 복합(`*`·`:…`·`[…]`·`.x`·`#x`)이 앞 복합과의 관계만으로 행을 고르는가.
    · `tbody|thead|tfoot > 그것` — 행 그룹의 자식은 `tr` 뿐이다.
    · `tbody|thead|tfoot|table 그것`(자손) — 클래스·id 없는 `*`·`:…`·`[…]` 는 행도 고른다.
    · `행 + 그것` · `행 ~ 그것` — 행의 형제는 행이다. `thead + *` 는 행 그룹이라 아니다.
    Whether a typeless compound selects rows through its combinator context alone."""
    prev_start, prev = spans[i - 1]
    start, comp = spans[i]
    subjects = _subjects(comp)
    # `:is(td, th)` 처럼 인자가 전부 행 아닌 타입이면 타입 있는 복합이다(Grok 3차 거짓 red).
    if not _TYPELESS.match(comp) or all(
            _IDENT.match(s) and not _TYPE_TR.match(_mask(s)) for s in subjects):
        return None
    gap = masked_sel[prev_start + len(prev):start]
    if "+" in gap or "~" in gap:
        reason = _row_reason(prev, row_classes)
        return f"{reason} {'+' if '+' in gap else '~'} *" if reason else None
    prev_subjects = [_mask(s) for s in _subjects(prev)]
    if ">" in gap:
        return prev.lower() + " > *" if any(_ROW_GROUP.match(s) for s in prev_subjects) else None
    classed = any(_CLASS.search(_mask(s)) or _ID.search(_mask(s)) for s in subjects)
    if any(_ROW_GROUP_OR_TABLE.match(s) for s in prev_subjects) and not classed:
        return prev.lower() + " *"
    return None


def _subjects(compound: str) -> list[str]:
    """복합이 `:is(`/`:where(` 로 시작하면 그 인자들의 주어 복합, 아니면 복합 자신.
    The subject compounds of a leading `:is()`/`:where()`, else the compound itself."""
    masked = _mask(compound)
    fn = _IS_WHERE.match(masked)
    close = masked.find(")", fn.end()) if fn else -1
    if close < 0:
        return [compound]
    out = []
    for _, arg in _spans(compound[fn.end():close], r"[^,]+"):
        parts = _compounds(arg)
        if parts:
            out.append(parts[-1][1].strip())
    return out or [compound]


def row_compounds(css: str, row_classes: frozenset[str] = frozenset()
                  ) -> list[tuple[int, str, str, bool]]:
    """행을 고르는 복합 셀렉터마다 (조각 안 줄, 셀렉터, 근거, 그 복합에 가상 요소가 있는가).
    Every compound that selects a table row: (line, selector, reason, carries a pseudo)."""
    text = _strip_comments(css)
    found: list[tuple[int, str, str, bool]] = []
    for pm in _PRELUDE.finditer(text):
        prelude = pm.group(1)
        if prelude.lstrip().startswith("@"):
            continue
        for off, sel in _spans(prelude, r"[^,]+"):
            lead = len(sel) - len(sel.lstrip())
            line = text.count("\n", 0, pm.start(1) + off + lead) + 1
            spans = _compounds(sel)
            masked_sel = _mask(sel)
            for i, (_, comp) in enumerate(spans):
                reason = _row_reason(comp, row_classes) or (
                    _by_context(masked_sel, spans, i, row_classes) if i else None)
                if reason:
                    found.append((line, " ".join(sel.split()), reason,
                                  bool(_PSEUDO_EL.search(_mask(comp)))))
    return found


def row_pseudo_selectors(css: str, row_classes: frozenset[str] = frozenset()
                         ) -> list[tuple[int, str]]:
    """행에 가상 요소를 다는 셀렉터를 (조각 안 줄번호, 셀렉터) 로 돌려준다.
    Return (line within the snippet, offending selector) for each row pseudo-element."""
    return [(ln, sel) for ln, sel, _, pseudo in row_compounds(css, row_classes) if pseudo]


def _class_tokens(value: str) -> set[str]:
    """class 값에서 보간을 걷어 내고 식별자만. Class tokens with interpolation removed."""
    return {t for t in _JS_INTERP.sub(" ", value).split() if _IDENT.fullmatch(t)}


def _attr_value(m: re.Match) -> str:
    return m.group(2) if m.group(2) is not None else m.group(3)


def row_classes_in(text: str) -> set[str]:
    """템플릿·JS 원문에서 표의 행(`tr`)에 붙는 클래스 이름과 `#id` 를 모은다.
    Class names (and `#id`s) this template/JS text puts on table rows."""
    text = _JINJA.sub(" ", _HTML_COMMENT.sub(" ", text))
    out: set[str] = set()
    for tag in _TR_TAG.finditer(text):
        attrs = tag.group(1) if tag.group(1) is not None else tag.group(2)
        for attr in _CLASS_ATTR.finditer(attrs):
            out |= _class_tokens(_attr_value(attr))
        for attr in _ID_ATTR.finditer(attrs):
            out |= {"#" + t for t in _class_tokens(_attr_value(attr))}
    # 변수로 받은 `createElement('tr')` 와, 받지 않고 바로 이어 쓴 체인 둘 다.
    # Both a bound `createElement('tr')` variable and an unbound chain.
    targets = [rf"(?<![\w$.]){re.escape(m.group(1))}" for m in _CREATE_TR.finditer(text)]
    targets.append(_CREATE_TR_CHAIN)
    for target in dict.fromkeys(targets):
        for m in re.finditer(rf"{target}\.className\s*\+?=\s*(?P<q>[\"'`])(?P<v>.*?)(?P=q)", text):
            out |= _class_tokens(m.group("v"))
        for m in re.finditer(rf"{target}\.classList\??\.add\((?P<args>[^)]*)\)", text):
            for lit in re.finditer(r"([\"'`])(.*?)\1", m.group("args")):
                out |= _class_tokens(lit.group(2))
        for m in re.finditer(rf"{target}\.id\s*=\s*(?P<q>[\"'`])(?P<v>.*?)(?P=q)", text):
            out |= {"#" + t for t in _class_tokens(m.group("v"))}
    return out


def style_blocks(html: str) -> list[tuple[int, str]]:
    """템플릿의 `<style>` 내용을 (파일 안 시작 줄, 원문) 으로.
    The template's `<style>` contents with their file-relative start line."""
    return [(html.count("\n", 0, m.start(1)) + 1, m.group(1)) for m in _STYLE.finditer(html)]


def _tracked(under: str, suffix: str) -> list[str]:
    """git 추적 파일만, 한 번씩. `git ls-files` 는 충돌 중인 경로를 stage 마다 되풀이한다.
    Git-tracked files only, deduped (a conflicted path is listed once per stage)."""
    out = subprocess.run(  # nosec B603 B607
        ["git", "ls-files", "-z", "--", under], cwd=str(ROOT),
        capture_output=True, check=True,
    ).stdout.decode("utf-8").split("\0")
    return list(dict.fromkeys(
        p for p in out if p.endswith(suffix) and (ROOT / p).is_file()))


def _sources() -> list[tuple[str, int, str]]:
    """검사 대상을 (경로, 그 조각이 시작하는 파일 안의 줄, 원문) 으로 연다."""
    out: list[tuple[str, int, str]] = []
    for rel in _tracked("src/static/css", ".css"):
        out.append((rel, 1, (ROOT / rel).read_text(encoding="utf-8")))
    for rel in _tracked("src/templates", ".html"):
        for start, block in style_blocks((ROOT / rel).read_text(encoding="utf-8")):
            out.append((rel, start, block))
    return out


@functools.lru_cache(maxsize=1)
def _row_classes() -> frozenset[str]:
    """운영 트리의 행 클래스 — 템플릿 전문 + 정적 JS. Row classes of the real tree."""
    rels = _tracked("src/templates", ".html") + _tracked("src/static/js", ".js")
    return frozenset().union(
        *(row_classes_in((ROOT / rel).read_text(encoding="utf-8")) for rel in rels))


_ROWS = frozenset({"row-accent", "analysis-row", "#special-row"})


@pytest.mark.parametrize("css", [
    ".x tbody tr::before { content: ''; }",
    ".x tbody tr:hover::before { transform: scaleY(1); }",
    ".x tr.row::after { content: ''; }",
    ".x tbody tr:nth-child(2n)::before { content: ''; }",
    ".x tbody tr:not(:nth-child(2))::before { content: ''; }",
    ".x tr:not(:is(.a, .b) .c)::before { content: ''; }",
    "tr:before { content: ''; }",
    ".x TBODY TR::Before { content: ''; }",
    ".x :is(tr)::before { content: ''; }",
    ".x tbody :where(.y > tr, li)::after { content: ''; }",
    ".a,\n.x tbody > tr::after { content: ''; }",
    "@media (prefers-reduced-motion: reduce) {\n  .x tbody tr::before { transition: none; }\n}",
    ".row-accent::before { content: ''; }",
    ".x tbody > .analysis-row:hover::before { transform: scaleY(1); }",
    ".row-accent.reveal:not(.x)::after { content: ''; }",
    # Grok claim-review `06606bf6` 반례 — 행 그룹 아래 타입 없는 복합 · 셀을 자식으로 가진 요소 · 행 id
    "tbody > *::before { content: ''; }",
    ".x tbody > :nth-child(odd)::before { content: ''; }",
    ".x tbody *::after { content: ''; }",
    ".x tbody > .anything::before { content: ''; }",
    ":has(> td)::before { content: ''; }",
    "#special-row::before { content: ''; }",
    # Grok claim-review `06606bf6` 2차 반례 — 행의 형제 · `table` 아래 자손 · `>` 없는 `:has(td)`
    "tr + *::before { content: ''; }",
    ".x tr ~ *::after { content: ''; }",
    "tbody > tr + *::before { content: ''; }",
    ".analysis-row + .any::before { content: ''; }",
    ".x table *::before { content: ''; }",
    ":has(td)::before { content: ''; }",
    ":is(tbody, tfoot) > *::before { content: ''; }",
])
def test_catches_every_row_pseudo_form(css):
    r"""claimed\cheap 포함 — 부분문자열 `tr::before` 와 1차 정규식(괄호 한 겹)은 여럿을 놓친다."""
    assert len(row_pseudo_selectors(css, _ROWS)) == 1, css


@pytest.mark.parametrize("css", [
    ".x th::before { content: ''; }",
    ".x td::before { content: ''; }",
    ".x tbody tr:hover td:first-child::before { transform: scaleY(1); }",
    ".analysis-row td:first-child::before { content: ''; }",
    ".analysis-row:hover td:first-child::before { transform: scaleY(1); }",
    ".x:not(.analysis-row)::before { content: ''; }",
    ".x :not(tr)::before { content: ''; }",
    "table:has(tr)::before { content: ''; }",
    ".analysis-rows::before { content: ''; }",
    ".issue-row::before { content: ''; }",
    ".tr-x::before { content: ''; }",
    ".tr::before { content: ''; }",
    ".str::before { content: ''; }",
    "[data-tr]::before { content: ''; }",
    "/* tbody tr::before */\n.x td { color: red; }",
    ".x tbody tr { position: relative; }",
    ".analysis-row { transition: background 0.15s; }",
    ".x tbody td *::before { content: ''; }",
    ".x tbody .cell::before { content: ''; }",
    ".x tbody tr > *::before { content: ''; }",
    "#special-cell::before { content: ''; }",
    ".x td:has(> span)::before { content: ''; }",
    "thead + *::before { content: ''; }",
    ":not(:has(> td))::before { content: ''; }",
    ".x td + *::before { content: ''; }",
    "table > *::before { content: ''; }",
    ".x table .caption::before { content: ''; }",
    "tbody > tr > td::before { content: ''; }",
    "tbody:hover::after { content: ''; }",
    # Grok 3차 — `:is()` 인자가 셀 타입이면 셀이다(인자를 가려 `*` 로 읽던 거짓 red)
    "tbody :is(td, th):first-child::before { content: ''; }",
    ".admin-table tbody :is(td, th):first-child::before { content: ''; }",
    "table :is(td, th)::before { content: ''; }",
    ".x tbody :is(.num, .date)::before { content: ''; }",
])
def test_ignores_cells_classes_and_comments(css):
    r"""cheap\claimed 포함 — `row` 가 든 이름(`.issue-row`)은 행 클래스가 아니다."""
    assert row_pseudo_selectors(css, _ROWS) == [], css


def test_row_class_needs_a_tr_that_carries_it():
    """🔴 같은 CSS 가 «그 클래스를 단 `tr` 이 있을 때만» 걸린다 — 판정이 이름이 아니라 수집에 기댄다."""
    css = ".row-accent::before { content: ''; }"
    with_tr = row_classes_in('<table><tr class="row-accent"><td>1</td></tr></table>')
    without_tr = row_classes_in('<div class="row-accent"></div><td class="row-accent"></td>')
    assert with_tr == {"row-accent"}
    assert without_tr == set()
    assert row_pseudo_selectors(css, frozenset(with_tr)) == [(1, ".row-accent::before")]
    assert row_pseudo_selectors(css, frozenset(without_tr)) == []


@pytest.mark.parametrize("text, expected", [
    ("return '<tr class=\"x y\">' + cells + '</tr>';", {"x", "y"}),
    ('html += "<tr class=\\"esc\\">";', {"esc"}),
    ("<tr\n  class='multi'\n  data-id=\"1\">", {"multi"}),
    ('<tr class="{% if x %}hot{% endif %} base {{ extra }}">', {"hot", "base"}),
    ("return '<tr class=\"lead ' + dyn + ' tail\">';", {"lead", "tail"}),
    ("row = `<tr class=\"t-a ${cls}\">`;", {"t-a"}),
    ("const r = document.createElement('tr');\nr.className = 'made-row';\n"
     "r.classList.add('added', \"also\");\n"
     "const td = document.createElement('td');\ntd.className = 'cell-only';", {"made-row", "added", "also"}),
    # Grok claim-review `06606bf6` 반례 — 속성값 속 `>` · 행 id · 받지 않은 체인 · `?.`·`+=`
    ('<tr title="HP > 50" class="hot">', {"hot"}),
    ("return '<tr data-label=\"Score > 80\" class=\"analysis-row\">';", {"analysis-row"}),
    ("<tr class=\"ok\" data-x='oops>", {"ok"}),
    ('<tr id="special-row" class="a">', {"a", "#special-row"}),
    ("document.createElement('tr').className = 'chain-row';", {"chain-row"}),
    ("const r = document.createElement('tr');\nr.classList?.add('opt');\n"
     "r.className += ' plus';\nr.id = 'made-id';", {"opt", "plus", "#made-id"}),
])
def test_collects_row_classes_from_markup_and_scripts(text, expected):
    r"""claimed\cheap — 이름에 `row` 가 없어도, JS 문자열·보간 사이에 있어도 모은다."""
    assert row_classes_in(text) == expected, text


@pytest.mark.parametrize("text", [
    '<td class="cell-c">x</td>',
    '<track class="trk" src="a.vtt">',
    '<tr data-class="dc"><td class="in-td"></td></tr>',
    '<!-- <tr class="commented"> -->',
    '{# <tr class="jinja-comment"> #}',
    "const td = document.createElement('td');\ntd.className = 'filter-empty';",
    "const row = document.createElement('tr');\nrow.appendChild(cell);",
    "html += '<tr' + rowCls + '>';",
    "const c = document.createElement('td');\nc.id = 'cell-id';\nc.classList?.add('cell-opt');",
    '<td id="td-id" title="a > b" class="td-cls"></td>',
])
def test_does_not_collect_non_row_classes(text):
    r"""cheap\claimed — 둘째로 싼 과정(`<tr[^>]*class="…"`)이 넘어질 자리들."""
    assert row_classes_in(text) == set(), text


def test_style_blocks_read_only_the_style_element():
    """템플릿에서는 `<style>` 안만 CSS 다 — 본문 텍스트의 같은 글자는 셀렉터가 아니다."""
    html = ("<p>tbody tr::before {</p>\n<style>\n  .a { color: red; }\n"
            "  .x tbody tr::after { content: ''; }\n</style>")
    blocks = style_blocks(html)
    assert [start for start, _ in blocks] == [2]
    assert [(start + ln - 1, sel) for start, b in blocks
            for ln, sel in row_pseudo_selectors(b)] == [(4, ".x tbody tr::after")]


def _insert_mid(src: str, snippet: str) -> str:
    cut = src.index("}\n", len(src) // 2) + 2
    return src[:cut] + snippet + src[cut:]


def test_plants_flip_inside_an_untouched_stylesheet():
    """🔴 같은 심음 쌍을 이 수정이 건드리지 않은 운영 파일에 끼운다 — 합성 조각에서만
    맞는 계기가 아닌지 본다. 심은 셀렉터만 비교하므로 운영 파일에 진짜 위반이 있어도 흔들리지 않는다."""
    src = (ROOT / "src/static/css/components.css").read_text(encoding="utf-8")
    bad = _insert_mid(src, ".plant tbody tr:not(:nth-child(2)):hover::before { content: ''; }\n")
    ok = _insert_mid(src, "/* .plant tbody tr::before */\n"
                          ".plant tbody tr:hover td:first-child::before { content: ''; }\n")
    assert [s for _, s in row_pseudo_selectors(bad) if ".plant" in s] == [
        ".plant tbody tr:not(:nth-child(2)):hover::before"]
    assert [s for _, s in row_pseudo_selectors(ok) if ".plant" in s] == []


def test_plants_row_class_flip_inside_untouched_template_and_stylesheet():
    """🔴 행 클래스 경로도 운영 파일에서 뒤집는다 — 손대지 않은 템플릿(`overview.html`)에
    `<tr class="plant-live">` 와 `<td class="plant-dead">`·주석 속 `<tr class="plant-comment">` 를
    심고, 손대지 않은 `components.css` 에 셋의 `::before` 와 `.plant-live td:first-child::before`
    를 심는다. `.plant-live::before` 하나만 걸려야 한다."""
    html = (ROOT / "src/templates/overview.html").read_text(encoding="utf-8")
    cut = html.index("<tbody>") + len("<tbody>")
    html = (html[:cut] + '\n<tr class="plant-live"><td class="plant-dead">x</td></tr>'
            '\n<!-- <tr class="plant-comment"><td></td></tr> -->' + html[cut:])
    rows = frozenset(row_classes_in(html))
    assert {"plant-live"} <= rows and not {"plant-dead", "plant-comment"} & rows
    css = _insert_mid((ROOT / "src/static/css/components.css").read_text(encoding="utf-8"),
                      ".plant-live::before { content: ''; }\n"
                      ".plant-dead::before { content: ''; }\n"
                      ".plant-comment::before { content: ''; }\n"
                      ".plant-live td:first-child::before { content: ''; }\n")
    assert [s for _, s in row_pseudo_selectors(css, rows) if ".plant" in s] == [".plant-live::before"]


def test_the_scan_actually_reaches_both_stylesheets_and_template_styles():
    """🔴 공허화 방어 — 「위반 0」과 「아무것도 안 읽었다」를 가른다."""
    sources = _sources()
    names = {n for n, _, _ in sources}
    assert "src/static/css/repo_insights.css" in names
    assert "src/static/css/admin.css" in names
    assert "src/templates/repo_detail.html" in names, "템플릿 `<style>` 을 안 읽었다"
    rows = _row_classes()
    assert rows, "행 클래스를 하나도 못 모았다 — 수집이 죽었다"
    assert "analysis-row" in rows, "`<script>` 문자열 속 `<tr class=…>` 를 못 읽었다"
    assert "filter-empty" not in rows, "`td.className` 을 행 클래스로 셌다"
    # 판정 대상인 «행을 고르는 복합» 을 두 경로 모두 실제로 만났는가 — 못 만나면 초록이 공허하다.
    reasons = {reason for _, _, text in sources for _, _, reason, _ in row_compounds(text, rows)}
    assert "tr" in reasons, "셀렉터 머리에서 `tr` 을 하나도 못 봤다"
    assert ".analysis-row" in reasons, "셀렉터 머리에서 행 클래스를 하나도 못 봤다"


def test_no_table_row_gets_a_pseudo_element():
    rows = _row_classes()
    bad = [(name, start + line - 1, sel)
           for name, start, text in _sources()
           for line, sel in row_pseudo_selectors(text, rows)]
    assert not bad, (
        "표의 행에 ::before/::after 가 달렸다 — Chromium 이 그것을 열 하나로 세어 본문 행이 "
        "머리글보다 한 칸 밀린다. `td:first-child::before` 로 옮긴다:\n  "
        + "\n  ".join(f"{n}:{ln}  {s}" for n, ln, s in bad))
