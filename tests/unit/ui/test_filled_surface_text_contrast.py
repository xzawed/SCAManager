"""채운 면 «위» 의 글자 — 한 규칙이 면과 글자를 함께 정하면 네 테마 전부 AA 여야 한다.

## 무엇이 문제였나 (2026-09-16 회고 P1-8 · P1-26)

- `dashboard.html::.repos-rec-high`·`-error` 가 `background: var(--danger)` 위에 리터럴 `#fff`,
  `.repos-rec-warning` 이 `var(--warning)` 위에 `#000` 을 얹었다. 면은 테마마다 바뀌는데 글자는
  고정이라 dark 2.77 · catppuccin 2.32 · light 4.18 이다. 그 팔(repos 리포트의 «개선 권장»)은
  어떤 스윕도 렌더한 적이 없었다.
- `repo_detail.html::.filter-btn[data-source="pr"].active` 가 `--grade-b` 면 위에 accent 용
  on-토큰(`--btn-on-accent`)을 빌려 써 pastel 3.57 이다. #1643 은 세 형제 중 push 만 고쳤다.

둘 다 «그 면에 맞춘 글자색» 이 아니라 남의 것을 빌렸고, 둘 다 «같은 규칙 안» 에서 면과 글자를
함께 정한다 — 규칙 단위로 계산하면 렌더하지 않고도 잡힌다.

## 🔴 이 가드가 판정하지 «못하는» 것

1. **반투명 면**(틴트·워시) — 실제 바탕이 그 아래 무엇이냐에 달려 정적으로 모른다. 카드 위로
   가정하면 nav 위 알약처럼 틀린 값이 나온다(실측). 그래서 판정하지 않고 따로 센다.
2. 면과 글자가 **다른 규칙** 에서 오는 쌍(`.btn` 이 글자, `.btn--x` 가 면).
3. JS 가 조립하는 인라인 색(`repo_detail.html::renderSourceBadge`).

셋 다 «칠해진 결과» 를 재는 e2e 전체 글자 감사(`e2e/test_theme_mobile_guards.py`)가 맡는다.

Text on an opaque fill declared in the same rule must clear AA in every theme.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ._contrast import (AA, ROOT, THEMES, Unmeasurable, over, paint_colours, ratio, read,
                        strip_css_comments, token_scope)

_TOKENS = read("src/static/css/tokens.css")
_SCOPES = {t: token_scope(_TOKENS, t) for t in THEMES}

# `background`·`background-color`·`background-image` — 마지막 선언이 이긴다.
_FILL = re.compile(r"(?<![\w-])background(?:-color|-image)?\s*:\s*([^;]+)")
# `color:` 만 — `border-color`·`outline-color` 는 글자색이 아니다.
_TEXT = re.compile(r"(?<![\w-])color\s*:\s*([^;]+)")
# 그라디언트 «글자» — 면이 글자 모양으로 잘려 `color` 는 투명이다. 면 위 글자가 아니다.
_CLIP_TEXT = re.compile(r"(?<![\w-])(?:-webkit-)?background-clip\s*:\s*text")
_JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.S)


@dataclass(frozen=True)
class Pair:
    where: str
    selector: str
    fill: str
    text: str


def pairs_in(src: str, where: str) -> list[Pair]:
    """CSS 원문에서 «같은 규칙이 면과 글자를 함께 정하는» 쌍을 뽑는다."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", strip_css_comments(_JINJA.sub("", src))):
        fills, texts = _FILL.findall(m.group(2)), _TEXT.findall(m.group(2))
        if fills and texts and not _CLIP_TEXT.search(m.group(2)):
            out.append(Pair(where, " ".join(m.group(1).split()), fills[-1].strip(),
                            texts[-1].strip()))
    return out


def _all_pairs() -> list[Pair]:
    out = []
    for f in sorted((ROOT / "src" / "static" / "css").glob("*.css")):
        out += pairs_in(f.read_text(encoding="utf-8"), f.relative_to(ROOT).as_posix())
    for f in sorted((ROOT / "src" / "templates").rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(ROOT).as_posix()
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", text, re.S | re.I):
            out += pairs_in(m.group(1), rel)
        # 인라인 `style=""` 도 한 규칙이다.
        for m in re.finditer(r'\bstyle="([^"]*)"', text):
            line = text.count("\n", 0, m.start()) + 1
            out += pairs_in(f"[style@{line}] {{{m.group(1)}}}", rel)
    return out


def judge(pair: Pair, theme: str) -> float | str:
    """그 테마에서 최악 stop 의 대비비. 반투명이면 'translucent', 못 풀면 'unmeasured'."""
    scope = _SCOPES[theme]
    try:
        fills = paint_colours(scope, pair.fill)
        texts = paint_colours(scope, pair.text)
    except Unmeasurable:
        return "unmeasured"
    if len(texts) != 1:
        return "unmeasured"
    if any(c[3] < 1 for c in fills):
        return "translucent"
    return min(ratio(over(texts[0], c), c) for c in fills)


def _verdicts() -> dict[Pair, dict[str, float | str]]:
    return {p: {t: judge(p, t) for t in THEMES} for p in _all_pairs()}


def test_text_on_every_opaque_fill_meets_aa_in_every_theme():
    """🔴 채운 면 위 글자는 «그 면에 맞춘» 색이어야 한다 — 빌린 on-토큰·리터럴은 테마마다
    우연히 맞거나 틀린다."""
    bad = sorted(f"{p.where}  {p.selector[:60]}  [{t}] {v:.2f} < {AA}  "
                 f"(면 {p.fill[:40]} · 글자 {p.text[:30]})"
                 for p, vs in _verdicts().items() for t, v in vs.items()
                 if isinstance(v, float) and v < AA)
    assert not bad, "채운 면 위 글자가 AA 미달이다:\n  " + "\n  ".join(bad)


def test_the_scan_measures_known_opaque_pairs_in_every_theme():
    """🔴 공허화 방어 — 「위반 0」과 「아무것도 못 쟀다」를 가른다.

    accent 로 채운 두 컨트롤은 네 테마 모두 불투명 면이라 반드시 «재져야» 한다.
    """
    verdicts = _verdicts()
    measured = {p.selector for p, vs in verdicts.items()
                if all(isinstance(v, float) for v in vs.values())}
    for sel in (".filter-btn.active", ".nav-btn:hover"):
        assert sel in measured, f"`{sel}` 를 네 테마에서 재지 못했다 — 스캔이 늙었다"


def test_a_literal_text_colour_on_a_token_fill_is_judged():
    r"""claimed\cheap — «둘 다 토큰인 쌍만» 재는 싼 과정은 리터럴 글자를 지나친다(P1-8 의 모양)."""
    [pair] = pairs_in(".p { background: var(--danger); color: #fff; }", "plant")
    assert judge(pair, "catppuccin") < AA


def test_every_gradient_stop_is_judged():
    r"""claimed\cheap — 첫 stop 만 보는 과정은 light 의 두 번째 stop(`--accent-2`)을 놓친다."""
    [pair] = pairs_in(".p { background: linear-gradient(135deg, var(--accent), var(--accent-2));"
                      " color: var(--accent-text-on); }", "plant")
    assert judge(pair, "light") < AA


def test_a_fallback_is_used_only_when_the_token_is_missing():
    r"""🔴 두 번째 싼 과정 — `var(--x, #fff)` 의 대체값을 집으면 pastel 이 5.3 으로 «통과» 한다.

    `--btn-on-accent` 는 네 테마 모두 정의돼 있으므로 대체값 `#fff` 는 칠해지지 않는다.
    """
    [pair] = pairs_in('.p { background: var(--grade-b); color: var(--btn-on-accent, #fff); }',
                      "plant")
    assert judge(pair, "pastel") < AA


def test_a_translucent_fill_is_not_judged_here():
    r"""cheap\claimed — 틴트 면은 그 아래 바탕을 모르면 대비가 정해지지 않는다."""
    [pair] = pairs_in(".p { background: var(--grade-f-bg); color: var(--grade-f); }", "plant")
    assert judge(pair, "dark") == "translucent"


def test_a_border_colour_is_not_a_text_colour():
    r"""cheap\claimed — `border-color` 를 글자색으로 읽으면 없는 쌍을 만든다."""
    assert pairs_in(".p { background: var(--danger); border-color: #fff; }", "plant") == []


def test_gradient_text_is_not_text_on_a_fill():
    r"""cheap\claimed — `background-clip: text` 는 면이 곧 글자다. `color: transparent` 를
    «면 위 투명 글자» 로 읽으면 대비 1.00 이라는 없는 결함을 만든다(실측 13건)."""
    assert pairs_in(".p { background: var(--accent-grad); -webkit-background-clip: text;"
                    " background-clip: text; color: transparent; }", "plant") == []
