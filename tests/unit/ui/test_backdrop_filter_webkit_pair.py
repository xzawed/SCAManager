r"""`backdrop-filter` 는 같은 값의 `-webkit-backdrop-filter` 와 함께 쓴다.

🔴 왜 짝인가 — Safari 17 이하(iOS 17 이하)는 접두사 판만 읽는다. Chromium 은 접두사 판을 받지
   않는다(실측: `CSS.supports('-webkit-backdrop-filter', 'blur(1px)')` 거짓 → CSSOM 에서 버린다)
   — 짝을 더해도 Chromium·Firefox 화면은 그대로다. 한쪽만 쓰면 그 엔진에서 유리 효과가 조용히
   사라진다. 리포가 28곳 중 5곳에만 짝을 써 왔다(회고 P2-58) — 저자가 필요를 알았다는 증거다.

🔴 «같은 규칙 안의 짝» 을 본다 — 파일마다 개수만 맞추는 판정은 짝이 다른 규칙에 가 있어도,
   값이 달라도(`blur(12px)` ↔ `blur(14px)`) 통과시킨다. 판정은 구조 스캐너가 읽은 선언이다
   (`_css_structure.py`) — 주석 속 `backdrop-filter:` 는 선언이 아니다.

   claimed\cheap = 개수는 맞는데 짝이 다른 규칙 · 값이 다른 짝 → **잡혀야** 한다
   cheap\claimed = 주석 속 글자 → **무시돼야** 한다

Pair every backdrop-filter with an equal -webkit-backdrop-filter in the same rule.
"""
from __future__ import annotations

from ._css_structure import authored_sources, scan

_STD, _WEBKIT = "backdrop-filter", "-webkit-backdrop-filter"


def unpaired(css: str) -> list[tuple[int, str, str | None, str | None]]:
    """(줄, 셀렉터, 표준 값, 접두사 값) — 같은 규칙에서 둘이 같지 않은 자리. 마지막 선언이 이긴다."""
    out = []
    for b in scan(css).blocks:
        last = {p: v for p, v in b.decls if p in (_STD, _WEBKIT)}
        if last and last.get(_STD) != last.get(_WEBKIT):
            out.append((b.line, " ".join(b.prelude.split())[-60:], last.get(_STD), last.get(_WEBKIT)))
    return out


def _cheap_counts_match(css: str) -> bool:
    """«가장 싼 과정» — 원문 글자에서 두 속성 이름의 개수만 맞춘다."""
    webkit = css.count(f"{_WEBKIT}:")
    return css.count(f"{_STD}:") - webkit == webkit


def test_every_backdrop_filter_has_an_equal_webkit_pair():
    bad = [(s.path, s.line + ln - 1, sel, std, webkit)
           for s in authored_sources() for ln, sel, std, webkit in unpaired(s.text)]
    assert not bad, (
        "`backdrop-filter` 와 `-webkit-backdrop-filter` 가 같은 규칙에서 같은 값이 아니다 — "
        "Safari 17 이하에서 유리 효과가 사라진다:\n  "
        + "\n  ".join(f"{p}:{ln}  {sel}  표준={std!r} 접두사={wk!r}" for p, ln, sel, std, wk in bad))


def test_the_scan_reaches_the_backdrop_filters():
    """🔴 공허화 방어 — 판정할 선언을 실제로 만났는가."""
    seen = sum(1 for s in authored_sources() for b in scan(s.text).blocks
               if any(p == _STD for p, _ in b.decls))
    assert seen > 20, f"`backdrop-filter` 를 쓰는 규칙을 {seen} 개만 만났다"


def test_a_pair_in_another_rule_or_with_another_value_is_caught():
    r"""claimed\cheap — 개수는 맞지만 짝이 아니다."""
    moved = (f".a {{ {_STD}: blur(8px); }}\n"
             f".b {{ {_WEBKIT}: blur(8px); }}")
    mismatched = f".a {{ {_WEBKIT}: blur(12px); {_STD}: blur(14px); }}"
    for css in (moved, mismatched):
        assert _cheap_counts_match(css), "이 심음은 «개수가 맞는» 것이어야 한다"
        assert unpaired(css), css
    assert unpaired(f".a {{ {_WEBKIT}: blur(8px); {_STD}: blur(8px); }}") == [], "바닥 — 짝이면 통과"


def test_a_property_named_in_a_comment_is_ignored():
    r"""cheap\claimed — 주석 속 글자는 선언이 아니다. 개수 세기는 이것을 짝 없는 선언으로 센다."""
    css = f"/* {_STD}: blur(8px) 는 아래 규칙이 쓴다 */\n.a {{ color: red; }}"
    assert not _cheap_counts_match(css), "이 심음은 «개수가 어긋나는» 것이어야 한다"
    assert unpaired(css) == []
