"""«자기 틴트 면 + 같은 토큰 글자» 관용구를 리포 전체에서 금지한다 — #1639 W15 2차.

🔴 무엇을 금지하는가

    background: color-mix(in srgb, var(--X) 15%, transparent);
    color:      var(--X);                       /* ← 면을 만든 그 토큰을 글자로 */

   `--danger`·`--warning`·`--btn-on-accent` 같은 토큰은 «면» 으로 쓰려고 고른 값이다.
   그것을 15% 로 옅게 깔고 **같은 값을 글자로** 쓰면, 밝은 테마에서 글자와 면이 서로
   가까워져 대비가 무너진다. `--text-1/2/3` 만 예외다 — 그것들은 애초에 글자용으로
   골라 카드 위 여유가 있고, 자기 틴트를 깔아도 면이 거의 안 움직인다(실측 5.71~7.23).

🔴 왜 «값» 이 아니라 «관용구» 를 금지하는가: 바탕이 카드인지 그라디언트 헤더인지에 따라
   실제 비율이 달라져, 한 가지 배경 모델로는 정직하게 못 센다. 관용구 금지는 배경과
   무관하게 성립한다. 실제 비율은 e2e 대비 스윕이 «칠해진 픽셀» 로 잰다.

🔴 어떻게 찾았나: 커밋된 e2e 대비 감사는 `--text-2`/`--text-3`/`--accent-text` 로 칠해진
   글자만 판정한다. 그 필터를 떼고 「모든 글자」로 넓혀 스윕을 다시 돌리니(감사 308회 발화)
   예외 범주 밖 336행·고유 20자리가 나왔고 **그중 토큰 감사가 볼 수 있는 것은 0건**이었다.
   렌더 실측과 `tokens.css` 정적 계산이 소수점까지 일치했다 —
   pastel warning **2.44** · pastel error 3.76 · light warning 4.08 · catppuccin error 4.18.

   #1683 이 `.ri-badge-*` 두 곳을 고쳤지만 **같은 관용구의 형제 여섯 곳이 남아 있었다.**
   그것이 이 가드가 선택자 목록이 아니라 «관용구» 를 보는 이유다.

🔴 그리고 그 «관용구» 도 처음엔 한 가지 **표기** 로만 봤다. Grok claim-review `01a0a9e5` 가
   `color-mix(in srgb, transparent, var(--X) 15%)` 를 반례로 냈다 — 뜻은 같은데 인자 순서가
   반대라 빠져나갔다. 리포에 그 형태가 실재하지는 않았다(실측 0건). 실재하지 않는 회피
   경로를 열어 둔 채 「리포 전체에서 금지한다」고 적어 둔 것이 결함이었다.

Forbid painting text with the very token that tints its own background.
"""
from __future__ import annotations

import re

import pytest

from ._css_structure import authored_sources, scan

# 글자용으로 설계된 토큰 — 자기 틴트를 깔아도 면이 거의 안 움직인다.
_TEXT_TOKENS = {"--text-1", "--text-2", "--text-3"}

# `color` 값 «전체» 가 토큰 하나 — `var(--x)` · `var(--x, 대체)` · `!important`.
# The whole `color` value is one token reference.
_COLOR_TOKEN = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,[^()]*)?\)\s*(?:!important)?", re.I)
_VAR = re.compile(r"var\(\s*(--[\w-]+)")


def _tinted_tokens(value: str) -> set[str]:
    """`color-mix(...)` 가 `transparent` 와 함께 섞는 토큰 이름들.

    🔴 인자 «순서» 를 보지 않는다. `color-mix(in srgb, transparent, var(--d) 15%)` 는
       `color-mix(in srgb, var(--d) 15%, transparent)` 와 같은 뜻인데,
       순서를 박아 둔 정규식은 앞쪽만 잡았다 — Grok claim-review `01a0a9e5` 의 반례다.
    Order-independent: color-mix arguments may be written either way round.
    """
    out: set[str] = set()
    for m in re.finditer(r"color-mix\(", value):
        depth, j = 1, m.end()
        while j < len(value) and depth:
            depth += (value[j] == "(") - (value[j] == ")")
            j += 1
        inner = value[m.end():j - 1]
        if "transparent" in inner:
            out |= {v.group(1) for v in _VAR.finditer(inner)}
    return out


def self_tint_sites(css: str) -> list[tuple[int, str, str]]:
    """CSS 원문 하나 → (줄, 셀렉터 끝, 토큰). 규칙마다 «칠해지는» 값으로 판정한다.

    🔴 선언 순서대로 배경 겹을 갱신하고 마지막 값이 이긴다 — `background` 단축 속성은 색·이미지
       겹을 둘 다 덮고, `background-color`·`background-image` 는 제 겹만 덮는다. 정규식으로
       «첫 배경» 을 보던 판정은 세미콜론 없는 마지막 선언 · 두 번째 `background` ·
       `background-image` 를 놓치고(회고 P2-4), 덮여서 칠해지지 않는 틴트는 위반으로 셌다.
    Per rule, judge the values that actually paint: declarations in order, last one wins.
    """
    out = []
    for b in scan(css).blocks:
        if b.kind != "style":
            continue
        color, layers = None, {"color": None, "image": None}
        for prop, value in b.decls:
            if prop == "color":
                color = value
            elif prop == "background":
                layers = {"color": value, "image": value}
            elif prop == "background-color":
                layers["color"] = value
            elif prop == "background-image":
                layers["image"] = value
        m = _COLOR_TOKEN.fullmatch(color or "")
        if m and m.group(1) in set().union(*(_tinted_tokens(v) for v in layers.values() if v)):
            out.append((b.line, " ".join(b.prelude.split())[-60:], m.group(1)))
    return out


def _self_tint_sites() -> list[tuple[str, int, str, str]]:
    """정적 CSS + 템플릿 `<style>` 전부(🔴 둘을 같이 봐야 한다 — 이 관용구의 여섯 곳 중 네 곳이
    템플릿 안에 있었다)."""
    return [(s.path, s.line + ln - 1, sel, tok)
            for s in authored_sources() for ln, sel, tok in self_tint_sites(s.text)]


_TINT = "color-mix(in srgb, var(--danger) 15%, transparent)"


@pytest.mark.parametrize("css", [
    f".x {{ color: var(--danger); background: {_TINT} }}",
    f".x {{ background: var(--bg-card); color: var(--danger); background: {_TINT}; }}",
    f".x {{ background-image: linear-gradient({_TINT}, transparent); color: var(--danger); }}",
], ids=["배경이 세미콜론 없는 마지막 선언", "두 번째 background 가 칠한다", "background-image 겹"])
def test_the_painted_background_decides(css):
    r"""회고 P2-4 의 반례 셋 — 칠해지는 배경은 «처음 적힌 배경» 이 아니다."""
    assert [tok for _, _, tok in self_tint_sites(css)] == ["--danger"], css


@pytest.mark.parametrize("css", [
    f".x {{ background: {_TINT}; background: var(--bg-card); color: var(--danger); }}",
    f".x {{ background-color: {_TINT}; background: var(--bg-card); color: var(--danger); }}",
], ids=["뒤 background 가 덮는다", "단축 속성이 background-color 를 덮는다"])
def test_an_overridden_tint_is_not_what_gets_painted(css):
    r"""cheap\claimed — «첫 배경» 을 보는 판정은 덮여서 칠해지지 않는 틴트를 위반으로 센다."""
    assert self_tint_sites(css) == [], css


def test_the_idiom_is_caught_written_either_way_round():
    """🔴 Grok claim-review `01a0a9e5` 의 반례 — 인자 순서를 뒤집으면 빠져나갔다.

    리포에 그 형태가 실재하지는 않았다(실측 0건). 실재하지 않는 회피 경로를 열어 둔 채
    「리포 전체에서 금지한다」고 적어 둔 것이 결함이다.
    """
    token_first = "color-mix(in srgb, var(--danger) 15%, transparent)"
    transparent_first = "color-mix(in srgb, transparent, var(--danger) 15%)"
    assert _tinted_tokens(token_first) == {"--danger"}
    assert _tinted_tokens(transparent_first) == {"--danger"}
    # 🔴 파생되지 않은 바닥 — `transparent` 가 없으면 자기 틴트가 아니다.
    assert _tinted_tokens("color-mix(in srgb, var(--danger) 15%, var(--bg-1))") == set()


def test_the_scan_actually_reaches_both_static_css_and_template_styles():
    """🔴 공허화 방어 — 「위반 0」과 「아무것도 안 읽었다」를 가른다.

    이 관용구의 실제 사용처가 템플릿에 몰려 있어서, 정적 CSS 만 읽으면 조용히 통과한다.
    """
    srcs = authored_sources()
    assert any(s.path.endswith(".css") for s in srcs), "정적 CSS 를 하나도 안 읽었다"
    assert any(s.path.endswith(".html") for s in srcs), "템플릿 `<style>` 을 하나도 안 읽었다"
    # 규칙을 실제로 파싱했는가 — 이 리포에는 수백 개가 있다.
    assert sum(b.kind == "style" for s in srcs for b in scan(s.text).blocks) > 200


def test_no_rule_paints_text_with_the_token_that_tints_its_own_background():
    bad = [(f, ln, s, t) for f, ln, s, t in _self_tint_sites() if t not in _TEXT_TOKENS]
    assert not bad, (
        "면을 만든 토큰을 글자로도 쓴다 — 면·테두리·글자를 «함께» 고른 잠긴 3종 세트"
        "(`--grade-c`/`--grade-f` 등)로 옮긴다:\n  "
        + "\n  ".join(f"{f}:{ln}: {s}  ({t})" for f, ln, s, t in bad))
