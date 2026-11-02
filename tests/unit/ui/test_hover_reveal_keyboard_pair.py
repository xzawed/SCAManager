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

from ._contrast import css_sources, declarations, split_selectors, style_text

_REVEAL = frozenset({"display", "visibility", "opacity", "max-height", "height",
                     "clip-path", "pointer-events"})
_KEYBOARD = (":focus-within", ":focus-visible", ":focus")
_HOVER = ":hover"
_DECORATIVE_CONTENT = frozenset({"''", '""', "none", "normal"})
# 의사클래스·의사요소 이름은 ASCII 대소문자를 가리지 않는다(`:HOVER` · `:BEFORE`).
# Pseudo-class and pseudo-element names are ASCII case-insensitive.
_PSEUDO_ELEMENT = re.compile(r"::?(?:before|after)\b", re.I)
_SIMPLE_NAME = re.compile(r"[\w-]+")

Rule = tuple[str, dict[str, str]]


def _compound_end(rest: str) -> int:
    """`:hover` 바로 뒤에 «같은 복합 선택자» 로 붙은 단순 선택자들의 끝 위치.

    의사클래스(괄호는 깊이를 세어 끝까지 — `:not(:has(:is(.a)))`) · 속성 · 클래스 · id 를 건넌다.
    옛 한 콜론 의사요소(`:before`·`:after`)는 의사클래스가 아니므로 멈춘다.
    🔴 정규식으로 괄호 한 겹만 받던 판은 세 겹 중첩에서 «다른 요소» 로 잘못 갈랐다
       (Grok `eb82a090` BROKEN).
    End of the simple selectors glued to the hovered compound (balanced parentheses).
    """
    i = 0
    while i < len(rest):
        ch = rest[i]
        if ch == ":" and rest[i + 1:i + 2] != ":":
            name = _SIMPLE_NAME.match(rest, i + 1)
            if name is None or name.group(0).lower() in ("before", "after"):
                return i
            i = name.end()
            if rest[i:i + 1] == "(":
                depth = 0
                while i < len(rest):
                    depth += {"(": 1, ")": -1}.get(rest[i], 0)
                    i += 1
                    if depth == 0:
                        break
        elif ch == "[":
            close = rest.find("]", i)
            i = len(rest) if close < 0 else close + 1
        elif ch in ".#" and _SIMPLE_NAME.match(rest, i + 1):
            i = _SIMPLE_NAME.match(rest, i + 1).end()
        else:
            return i
    return i


def _rules(css: str) -> list[Rule]:
    """(선택자 하나, 선언) — 규칙마다, 목록은 풀어서. `@media` 안의 규칙도 나온다."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        decls = declarations(m.group(2))
        out += [(sel, decls) for sel in split_selectors(m.group(1))]
    return out


def _hover_at(sel: str) -> int | None:
    """괄호 밖 첫 `:hover` 의 위치. 없으면 -1, 괄호 안에만 있으면 None(가를 수 없음).

    대괄호·따옴표 안(`[title=":hover"]`)은 선택자가 아니라 값이라 건너뛴다.
    """
    parens, brackets, quote, nested = 0, 0, "", False
    for i, ch in enumerate(sel):
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch in "[]":
            brackets += 1 if ch == "[" else -1
        elif ch in "()":
            parens += 1 if ch == "(" else -1
        elif (ch == ":" and not brackets and sel[i:i + len(_HOVER)].lower() == _HOVER
              and sel[i - 1:i] != ":" and not re.match(r"[\w-]", sel[i + len(_HOVER):][:1])):
            if not parens:
                return i
            nested = True
    return None if nested else -1


def _target(sel: str, at: int) -> str:
    """`:hover` 가 바꾸는 대상 — "self"(그 요소) · "other"(다른 요소) · "pseudo"(의사요소)."""
    rest = sel[at + len(_HOVER):]
    rest = rest[_compound_end(rest):]
    if _PSEUDO_ELEMENT.search(rest):
        return "pseudo"
    return "other" if rest.strip() else "self"


def _canon_pseudo(sel: str) -> str:
    """`:before`·`::BEFORE` 를 `::before` 로 — 같은 의사요소의 철자 차이를 지운다."""
    return _PSEUDO_ELEMENT.sub(lambda m: "::" + m.group(0).lstrip(":").lower(), sel)


_COMPOUND_PART = re.compile(r"\.[\w-]+|#[\w-]+|\[[^\]]*\]")


def _last_compound(sel: str) -> tuple[str, str, frozenset]:
    """마지막 복합 선택자 → (의사요소, 타입 이름, 클래스·id·속성 집합). 의사클래스는 뺀다."""
    last = re.split(r"\s*[>+~]\s*|\s+", _canon_pseudo(sel))[-1]
    pseudo = m.group(0) if (m := _PSEUDO_ELEMENT.search(last)) else ""
    head = _PSEUDO_ELEMENT.sub("", last)
    tag = m.group(0).lower() if (m := re.match(r"[a-zA-Z][\w-]*", head)) else ""
    return pseudo, tag, frozenset(_COMPOUND_PART.findall(head))


def _contents_of(selector: str, index: list[Rule]) -> list[str]:
    """그 의사요소에 «적용될 수 있는» 규칙들의 `content` 전부.

    🔴 캐스케이드는 정적으로 못 푼다. 그래서 «가장 그럴듯한 하나» 를 고르지 않고, 마지막 복합
       선택자의 타입·클래스·id·속성이 대상의 부분집합인 규칙(조상 조건은 무시 — 어느 조상이든
       맞을 수 있다)을 모두 후보로 삼는다. 덜 구체적인 `a::before{content:none}` 하나를 골라
       `#n a::before{content:"Menu"}` 를 놓쳤다(Grok `5f893727` 재판정 BROKEN).
    Every rule whose last compound could match the target; ancestors are ignored on purpose.
    """
    pseudo, tag, parts = _last_compound(selector)
    out = []
    for s, d in index:
        if "content" not in d:
            continue
        p2, tag2, parts2 = _last_compound(s)
        if p2 == pseudo and tag2 in ("", tag) and parts2 <= parts:
            out.append(d["content"])
    return out


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
            # 올렸을 때 자기 `content` 를 주면 그것이 이긴다(같은 대상 · 더 구체적).
            contents = ([decls["content"]] if "content" in decls
                        else _contents_of(_without_hover(sel, at), index))
            if not contents:
                unmeasured.append(f"`{sel}` — 의사요소의 `content` 를 못 찾았다")
                continue
            if all(c in _DECORATIVE_CONTENT for c in contents):
                continue
        # 🔴 키보드 선택자 «하나» 가 드러냄 속성을 전부 줘야 한다. 여러 선택자에서 나눠 받으면
        #    `:focus-within` 과 `:focus` 가 섞여 실제로는 함께 성립하지 않는다(Grok `5f893727`).
        #    One keyboard selector must carry every reveal property.
        missing = sorted(reveal)
        for kb in _KEYBOARD:
            twin = _without_hover(sel, at, kb)
            merged: dict[str, str] = {}
            for s, d in rules:
                if s == twin:
                    merged.update(d)
            gaps = sorted(p for p, v in reveal.items() if merged.get(p) != v)
            missing = gaps if len(gaps) < len(missing) else missing
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


@pytest.mark.parametrize("css,flagged", [
    # Grok `eb82a090`: 세 겹 중첩 의사클래스 — 요소 «자신» 이다(정규식 판은 «다른 요소» 로 갈랐다).
    (".x:hover:not(:has(:is(.a))){display:block}", []),
    (".x:hover:not(:has(:is(.a))) .y{display:block}", [".x:hover:not(:has(:is(.a))) .y"]),
    # Grok `5f893727`: 드러냄 속성을 두 키보드 선택자에서 나눠 받는다 — 함께 성립하지 않는다.
    (".m:hover .p{opacity:1;visibility:visible}"
     ".m:focus .p{opacity:1}.m:focus-visible .p{visibility:visible}", [".m:hover .p"]),
    (".m:hover .p{opacity:1;visibility:visible}"
     ".m:focus-visible .p{opacity:1}.m:focus-visible .p{visibility:visible}", []),
    # Grok `eb82a090` 재판정: 이름은 대소문자를 가리지 않는다 — `:BEFORE` 는 의사요소다.
    (".t::before{content:attr(title)}.t:hover:BEFORE{opacity:1}", [".t:hover:BEFORE"]),
    (".t:HOVER .u{display:block}", [".t:HOVER .u"]),
    # Grok `5f893727` 재판정: 덜 구체적인 장식 규칙만 보고 실제 글자 `content` 를 놓쳤다.
    ('a::before{content:none}#n a::before{content:"Menu"}#n>a:hover::before{opacity:1}',
     ["#n>a:hover::before"]),
])
def test_hover_guard_survives_the_claim_review_counterexamples(css, flagged):
    """claim-review 반례를 그대로 심는다 — 고치기 전 판은 일곱 중 다섯을 틀렸다."""
    _, bad, unmeasured = _hover_only_reveals(css, _rules(css))
    assert not unmeasured, unmeasured
    assert [re.search(r"`([^`]+)`", b).group(1) for b in bad] == flagged, bad


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
