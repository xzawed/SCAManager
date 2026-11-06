"""가장자리에서 띄워 둔 `position: fixed` 요소는 그 가장자리의 safe-area 를 피한다.

노치 · 펀치홀 · 홈 표시줄 기기(`viewport-fit=cover`)에서는 `bottom: 1.5rem` 으로 띄운 토스트가 홈 표시줄
밑에, `right: 1.5rem` 이 가로 모드 노치 밑에 깔린다. 띄운 거리는 안전 영역의 가장자리에서 재야 한다 —
그 쪽 `env(safe-area-inset-<쪽>)` 를 값에 넣는다.

판정은 손 목록이 아니라 CSS 에서 파생한다 — 브라우저가 받는 CSS(정적 파일 · 템플릿 `<style>`)에서
`position: fixed` 를 선언한 선택자를 모으고, 그 선택자가 나오는 **모든** 블록(폭 분기의 덮어쓰기 포함)의
`top`·`right`·`bottom`·`left`·`inset` 을 본다. 띄운 거리가 아닌 값은 뺀다 — `0` · `auto` · 퍼센트
(`left: 50%` 가운데 맞춤) · nav 높이(nav 밑에 붙인 패널은 nav 와 같은 기준을 쓴다).
Floating fixed elements must offset from the safe-area edge; derived from every served stylesheet.
"""
from __future__ import annotations

import re

import pytest

from ._contrast import split_selectors
from ._css_structure import authored_sources, scan

_SIDES = ("top", "right", "bottom", "left")
_INSET = {side: re.compile(rf"env\(\s*safe-area-inset-{side}\b", re.I) for side in _SIDES}
# 0 은 단위 · 부호 · `calc()` 를 가리지 않는다 — `0dvh` · `0pt` · `calc(0px)` · `-0.0rem`.
# Zero regardless of unit, sign or a calc() wrapper.
_ZERO = re.compile(r"^(?:calc\(\s*)?[-+]?0*\.?0+(?:[a-z%]+)?(?:\s*\))?$", re.I)
_IMPORTANT = re.compile(r"!\s*important", re.I)


def _split_values(value: str) -> list[str]:
    """괄호 밖 공백에서만 자른다 — `calc(1rem + env(…))` 는 한 값이다."""
    parts, depth, cur = [], 0, ""
    for ch in value:
        depth += (ch == "(") - (ch == ")")
        if ch.isspace() and depth == 0:
            if cur:
                parts.append(cur)
            cur = ""
        else:
            cur += ch
    return [*parts, cur] if cur else parts


def _inset_sides(value: str) -> list[tuple[str, str]]:
    """`inset` 단축(1~4 값) → [(쪽, 값)] — CSS 의 위 · 오른쪽 · 아래 · 왼쪽 순서."""
    vals = _split_values(value)
    if len(vals) == 1:
        vals = vals * 4
    elif len(vals) == 2:
        vals = vals * 2
    elif len(vals) == 3:
        vals = [*vals, vals[1]]
    return list(zip(_SIDES, vals[:4]))


def _winning(block) -> dict[str, str]:
    """블록 안 선언을 CSS 우선순위대로 편다 — 뒤에 온 선언이 이기되, 일반 선언은 앞의 `!important` 를 못 이긴다.

    `inset` 단축은 그 자리에서 네 쪽으로 펼친다 — 개별 속성보다 뒤에 오면 그것을 덮는다(Grok O1 반례).
    Resolve a block's declarations in cascade order: later wins, except a normal one never beats !important.
    """
    won: dict[str, tuple[str, bool]] = {}

    def put(prop: str, value: str, important: bool) -> None:
        prev = won.get(prop)
        if prev is None or important or not prev[1]:
            won[prop] = (value, important)

    for raw_prop, raw_value in block.decls:
        prop = raw_prop.strip().lower()
        important = bool(_IMPORTANT.search(raw_value))
        value = " ".join(_IMPORTANT.sub("", raw_value).split())
        for side, v in (_inset_sides(value) if prop == "inset" else [(prop, value)]):
            put(side, v, important)
    return {prop: value for prop, (value, _) in won.items()}


def _is_gap(value: str, nav_height: str) -> bool:
    """가장자리에서 띄운 거리인가 — 0 · auto · 퍼센트 · nav 높이는 아니다."""
    return not (_ZERO.match(value) or value.lower() == "auto" or value.endswith("%") or value == nav_height)


def floating_offsets_without_inset(sources: list[tuple[str, str, int]], nav_height: str) -> tuple[int, list[str]]:
    """(띄운 거리 선언 수, safe-area 를 안 쓰는 곳) — `sources` = [(이름, CSS 본문, 그 본문 1행의 파일 줄)]."""
    blocks = [(name, first, b) for name, text, first in sources for b in scan(text).blocks if b.kind == "style"]
    fixed = {sel for _, _, b in blocks if _winning(b).get("position") == "fixed" for sel in split_selectors(b.prelude)}
    seen, wrong = 0, []
    for name, first, b in blocks:
        selectors = [s for s in split_selectors(b.prelude) if s in fixed]
        if not selectors:
            continue
        won = _winning(b)
        for side, value in ((side, won[side]) for side in _SIDES if side in won):
            if not _is_gap(value, nav_height):
                continue
            seen += 1
            if not _INSET[side].search(value):
                wrong.append(f"{name}:{first + b.line - 1} {', '.join(selectors)} {{ {side}: {value} }}")
    return seen, wrong


def _nav_height() -> str:
    """nav 의 높이 — `base.html` 의 `nav { height: … }` 에서 읽는다(nav 밑에 붙인 패널의 `top`)."""
    for source in authored_sources():
        if source.path.endswith("templates/base.html"):
            for block in scan(source.text).blocks:
                if block.kind == "style" and "nav" in split_selectors(block.prelude) and _winning(block).get("height"):
                    return _winning(block)["height"]
    raise AssertionError("base.html 에서 nav 높이를 못 읽었다 — nav 밑 패널을 가를 수 없다")


# ── 계기 자기검증 — 이 판정기가 틀리면 아래 전수 검사가 공허하다 ──────────────

@pytest.mark.parametrize("css,expected", [
    (".t{position:fixed;bottom:1.5rem;right:1.5rem}", ["bottom", "right"]),
    (".t{position:fixed;right:calc(1rem + env(safe-area-inset-left))}", ["right"]),
    (".t{position:fixed;inset:auto 1rem 1rem auto}", ["right", "bottom"]),
    (".t{position:fixed;bottom:calc(1rem + env(safe-area-inset-bottom))}"
     + "@media (max-width:480px){.t{bottom:1rem}}", ["bottom"]),
    (".a,.t{position:fixed}.t{left:16px}", ["left"]),
    (".t{position:fixed;top:0;right:0;bottom:0;left:0;inset:1.5rem}", ["top", "right", "bottom", "left"]),
    (".t{position:fixed;bottom:1rem !important;bottom:0}", ["bottom"]),
], ids=["plain-gaps", "swapped-side", "inset-shorthand", "media-override", "selector-list",
        "shorthand-after-longhands", "important-wins"])
def test_the_check_catches_a_floating_offset_without_its_inset(css, expected):
    """🔴 띄운 거리에 그 쪽 inset 이 없으면 잡는다 — 다른 쪽 inset · 단축 속성 · 폭 분기의 덮어쓰기도."""
    seen, wrong = floating_offsets_without_inset([("t.css", css, 1)], "56px")
    assert seen >= len(expected)
    assert sorted(w.split("{ ")[1].split(":")[0] for w in wrong) == sorted(expected), wrong


@pytest.mark.parametrize("css", [
    ".t{position:fixed;inset:0}",
    ".t{position:fixed;top:0;left:50%;transform:translateX(-50%)}",
    ".t{position:fixed;top:56px;left:0;right:0}",
    ".t{position:fixed;bottom:calc(1.5rem + env(safe-area-inset-bottom, 0px));"
    + "right:max(1rem, env(safe-area-inset-right))}",
    ".t{position:absolute;bottom:1rem}",
    ".t{position:fixed}/* .t{bottom:1rem} */",
    ".t{position:fixed;top:0dvh;left:0pt;bottom:calc(0px);right:-0.0rem}",
    ".t{position:fixed;bottom:1rem;bottom:calc(1rem + env(safe-area-inset-bottom))}",
], ids=["full-bleed", "centred", "under-the-nav", "clears-the-inset", "not-fixed", "commented",
        "zero-in-other-units", "later-declaration-wins"])
def test_the_check_ignores_what_is_not_a_bare_floating_offset(css):
    """대조군 — 화면을 덮는 0 · 가운데 맞춤 퍼센트 · nav 밑 · inset 을 쓴 값 · fixed 아님 · 주석은 위반이 아니다."""
    assert floating_offsets_without_inset([("t.css", css, 1)], "56px")[1] == []


# ── 전수 검사 ────────────────────────────────────────────────────────────

def test_floating_fixed_elements_clear_the_safe_area():
    """🔴 브라우저가 받는 CSS 전부 — 띄운 fixed 요소의 거리는 안전 영역 가장자리에서 잰다."""
    seen, wrong = floating_offsets_without_inset(_served(), _nav_height())
    assert seen, "띄운 fixed 요소를 하나도 못 찾았다 — 이 검사가 공허하다"
    assert not wrong, "safe-area 를 안 쓰는 띄운 거리(노치 · 홈 표시줄 밑에 깔린다):\n  " + "\n  ".join(wrong)


def _served() -> list[tuple[str, str, int]]:
    return [(s.path, s.text, s.line) for s in authored_sources() if s.served]
