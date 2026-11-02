"""마우스를 올려야만 드러나는 것에는 키보드 짝이 있어야 한다 (WCAG 2.1.1 Keyboard).

회고 2026-09-16 P2-70 은 `:hover` 와 `:focus-visible` 의 개수 차이(그때 93 대 13)를 짚었다.
개수 차이 자체는 결함이 아니다 — 포커스 «표시» 는 전역 `*:focus-visible` 링이 모든 포커스
대상에 주고, 그 링이 보이는지·3:1 인지는 e2e 포커스 스윕이 잰다. 개수를 맞추라고 하면
들어 올림·광택 같은 장식까지 복제하게 된다.

키보드 사용자가 실제로 잃는 것은 «마우스를 올려야만 나타나는 것» 이다. 이 파일은 그 모양만 본다:

- `:hover` 뒤에 결합자가 와서 «다른 요소» 의 드러냄 속성(`_REVEAL`)을 바꾸거나,
- 의사요소(`::before`·`::after`)의 드러냄 속성을 바꾸는데 그 의사요소의 `content` 가 글자를
  담는다(빈 `content` 는 장식이다),

그런데 같은 파일에 `:hover` 를 `:focus-within`·`:focus-visible`·`:focus` 로 바꾼 선택자가
그 속성을 같은 값으로 주지 않는 규칙.

🔴 일부러 안 보는 것:
- `transform` — 지금 `:hover` 의 transform 은 전부 들어 올림·확대·화살표 이동이다. 화면 밖에서
  미끄러져 들어오는 패널이 생기면 이 판정은 못 본다.
- 요소 «자신» 의 드러냄 변화(`.btn:hover{opacity:.9}`) — 요소는 이미 보인다. 평상시 대비는
  대비 가드의 몫이다.
🔴 `:hover` 가 괄호(`:is()`·`:has()`·`:not()`) 안에만 있거나 의사요소의 `content` 를 못 찾으면
   대상을 가를 수 없다 — «안 잰 것» 이라 red 다.

Hover-only reveals of another element (or of a text-bearing pseudo-element) need a keyboard twin.
"""
from __future__ import annotations

import re

import pytest

from ._contrast import css_sources, declarations, style_text

_REVEAL = frozenset({"display", "visibility", "opacity", "max-height", "height",
                     "clip-path", "pointer-events"})
_KEYBOARD = (":focus-within", ":focus-visible", ":focus")
_HOVER = ":hover"
_DECORATIVE_CONTENT = frozenset({"''", '""', "none", "normal"})
_PSEUDO_ELEMENT = re.compile(r"::?(?:before|after)\b")
# `:hover` 와 같은 복합 선택자에 붙은 단순 선택자 — 의사클래스(괄호 포함) · 속성 · 클래스 · id.
# 옛 한 콜론 의사요소(`:before`·`:after`)는 의사클래스로 걷지 않는다.
# Simple selectors glued to the same compound; legacy single-colon pseudo-elements excluded.
_SAME_COMPOUND = re.compile(
    r"(?::(?!:)(?!(?:before|after)\b)[\w-]+(?:\((?:[^()]|\([^()]*\))*\))?"
    r"|\[[^\]]*\]|\.[\w-]+|#[\w-]+)*")

Rule = tuple[str, dict[str, str]]


def _split_selectors(group: str) -> list[str]:
    """선택자 목록을 «최상위» 쉼표에서만 자른다 — `:not(a, b)` 안의 쉼표는 자르지 않는다."""
    out, depth, cur = [], 0, []
    for ch in group:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [" ".join(s.split()) for s in out if s.strip()]


def _rules(css: str) -> list[Rule]:
    """(선택자 하나, 선언) — 규칙마다, 목록은 풀어서. `@media` 안의 규칙도 나온다."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        decls = declarations(m.group(2))
        out += [(sel, decls) for sel in _split_selectors(m.group(1))]
    return out


def _hover_at(sel: str) -> int | None:
    """괄호 밖 첫 `:hover` 의 위치. 없으면 -1, 괄호 안에만 있으면 None(가를 수 없음)."""
    depth, nested = 0, False
    for i, ch in enumerate(sel):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ":" and sel.startswith(_HOVER, i) and sel[i - 1:i] != ":":
            if depth == 0:
                return i
            nested = True
    return None if nested else -1


def _target(sel: str, at: int) -> str:
    """`:hover` 가 바꾸는 대상 — "self"(그 요소) · "other"(다른 요소) · "pseudo"(의사요소)."""
    rest = sel[at + len(_HOVER):]
    rest = rest[_SAME_COMPOUND.match(rest).end():]
    if _PSEUDO_ELEMENT.search(rest):
        return "pseudo"
    return "other" if rest.strip() else "self"


def _content_of(selector: str, index: list[Rule]) -> str | None:
    """의사요소 선택자의 `content` — 정확한 선택자로, 없으면 마지막 복합 선택자로 찾는다."""
    last = re.split(r"\s*[>+~]\s*|\s+", selector)[-1]
    for key in (selector, last):
        found = [d["content"] for s, d in index if s == key and "content" in d]
        if found:
            return found[-1]
    return None


def _without_hover(sel: str, at: int, swap: str = "") -> str:
    return " ".join((sel[:at] + swap + sel[at + len(_HOVER):]).split())


def _hover_only_reveals(css: str, index: list[Rule]) -> tuple[int, list[str], list[str]]:
    """(본 `:hover` 선택자 수, 짝 없는 드러냄, 가르지 못한 선택자).

    `index` 는 의사요소 `content` 를 찾을 규칙 전부다 — 장식 `content` 가 다른 파일에
    적혀 있을 수 있어 파일 하나로 좁히지 않는다.
    """
    rules = _rules(css)
    seen, bad, unmeasured = 0, [], []
    for sel, decls in rules:
        at = _hover_at(sel)
        if at == -1:
            continue
        if at is None:
            unmeasured.append(f"`{sel}` — `:hover` 가 괄호 안에만 있다")
            continue
        seen += 1
        reveal = {p: v for p, v in decls.items() if p in _REVEAL}
        kind = _target(sel, at)
        if not reveal or kind == "self":
            continue
        if kind == "pseudo":
            content = decls.get("content") or _content_of(_without_hover(sel, at), index)
            if content is None:
                unmeasured.append(f"`{sel}` — 의사요소의 `content` 를 못 찾았다")
                continue
            if content in _DECORATIVE_CONTENT:
                continue
        twins = {_without_hover(sel, at, kb) for kb in _KEYBOARD}
        missing = sorted(p for p, v in reveal.items()
                         if not any(s in twins and d.get(p) == v for s, d in rules))
        if missing:
            bad.append(f"`{sel}` 가 {missing} 를 마우스로만 바꾼다")
    return seen, bad, unmeasured


def _all_rules() -> list[Rule]:
    return [rule for rel in css_sources() for rule in _rules(style_text(rel))]


def test_nothing_is_revealed_by_hover_alone():
    """🔴 마우스를 올려야만 드러나는 «다른 요소» 가 없어야 한다 — 있으면 키보드 짝을 준다.

    처방은 같은 규칙에 키보드 선택자를 더하는 것이다:
    `.row:hover .actions, .row:focus-within .actions { display: flex }`.
    """
    files = css_sources()
    assert files, "CSS 를 담는 파일을 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    index = _all_rules()
    seen, bad, unmeasured = 0, [], []
    for rel in files:
        n, b, u = _hover_only_reveals(style_text(rel), index)
        seen += n
        bad += [f"{rel}: {x}" for x in b]
        unmeasured += [f"{rel}: {x}" for x in u]
    assert seen, "`:hover` 선택자를 0개 봤다 — 판정이 공허하다"
    assert not unmeasured, (
        "대상을 가르지 못한 `:hover` 규칙 — 안 잰 것은 통과가 아니다:\n  "
        + "\n  ".join(unmeasured))
    assert not bad, (
        "마우스를 올려야만 드러나는 것이 있다 (WCAG 2.1.1 Level A):\n  " + "\n  ".join(bad))


# 계기 뒤집기(verify.md 「판정식을 쓸 때」 4) — 두 «싼 과정» 에서 하나씩 심는다.
#   cheap-A(회고가 쓴 지표): 파일마다 `:focus` 가 `:hover` 이상이면 통과
#     → 개수가 맞는 파일의 드러냄을 놓친다. 아래 CAUGHT 는 `:hover` 2 · `:focus` 2 다.
#   cheap-B: 드러냄 속성을 가진 `:hover` 규칙을 전부 잡는다
#     → 장식 의사요소 · 요소 자신 · 이미 짝이 있는 규칙까지 잡는다(아래 IGNORED 셋).
_PLANT_CAUGHT = (
    ".pr:hover .pact{display:flex}"
    ".pt::after{content:attr(data-tip);opacity:0}.pt:hover::after{opacity:1}"
    ".pz:focus-visible{outline:2px solid}.py:focus{outline:2px solid}"
)
_PLANT_IGNORED = (
    ".pk::after{content:'';opacity:0}.pk:hover::after{opacity:1}"
    ".pb:hover{opacity:.9}"
    ".pq:hover .pw, .pq:focus-within .pw{display:block}"
)


@pytest.mark.parametrize("host", ["", "src/static/css/components.css"])
def test_hover_reveal_instrument_flips_on_both_plants(host):
    """심은 드러냄 둘은 잡히고, 장식·자기 자신·짝 있는 규칙은 무시돼야 한다.

    `host` 가 있으면 손대지 않은 운영 스타일시트에 끼워 넣어 같은 뒤집힘을 요구한다.
    """
    base = style_text(host) if host else ""
    index = _all_rules()
    _, before, unmeasured = _hover_only_reveals(base, index)
    assert not before and not unmeasured, f"심기 전부터 걸린다 — 뒤집기를 잴 수 없다: {before}{unmeasured}"
    _, caught, _ = _hover_only_reveals(base + _PLANT_CAUGHT, index + _rules(_PLANT_CAUGHT))
    assert len(caught) == 2, caught
    assert any("`.pr:hover .pact`" in c for c in caught), caught
    assert any("`.pt:hover::after`" in c for c in caught), caught
    _, ignored, unmeasured = _hover_only_reveals(
        base + _PLANT_IGNORED, index + _rules(_PLANT_IGNORED))
    assert not ignored and not unmeasured, f"무시해야 할 규칙을 잡았다: {ignored}{unmeasured}"
