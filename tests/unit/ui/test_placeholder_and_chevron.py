"""여태 «구조적으로» 못 보던 두 표면 — `::placeholder` 와 SVG 안에 박힌 색.

## placeholder (WCAG 1.4.3, AA)

`::placeholder` 는 의사요소라 **DOM 텍스트 노드를 걷는 감사는 원리적으로 못 본다** —
canvas 글자와 같은 부류의 사각지대다. 실측(4테마 × 3런, 8개 전수):

    color: var(--text-2); opacity: .7
    → dark 4.48 · light 3.43 · pastel 3.88 · catppuccin 4.34   (기준 4.5)

`--text-2` 자체는 7.05~8.64 로 여유롭다 — **`.7` 곱셈이 원인 전부**다. 정렬 글리프와
같은 형태의 결함이다(부모/의사요소 투명도가 이미 보정된 토큰을 다시 깎는다).

🔴 Blink/WebKit 은 `.7` 을 «지우기만» 하면 UA 기본 placeholder 투명도를 다시 적용한다 —
`opacity: 1` 을 명시해야 한다(Grok 지적).

## 드롭다운 셰브론 (WCAG 1.4.11, AA)

`add_repo.html` 의 `.form-select` 는 `appearance: none` 으로 기본 화살표를 지우고
SVG 데이터 URI 로 다시 그리는데, 그 stroke 가 `#73737c` 로 **박혀 있어 테마를 안 탄다**.
실측: dark 4.06 · light 4.70 · pastel 4.62 · **catppuccin 2.68**(기준 3.0).

Understanding 1.4.11 Figures 24–25 는 이 화살표를 「드롭다운 기능이 있다는 것을 이해하는
데 필요한」 그래픽으로 명시한다. `appearance:none` + 저자 SVG 는 «사용자 에이전트가 정한
모양» 면제를 소진시킨다.
"""
from __future__ import annotations

import re

from ._contrast import (
    THEMES, decl, over, parse_color, ratio, read, resolve, strip_css_comments, theme_block,
)

AA_TEXT = 4.5
NON_TEXT = 3.0

# `::placeholder` 를 선언하는 모든 자리. 새 자리가 생기면 여기가 비지 않게 된다.
_PLACEHOLDER_FILES = ("src/templates/repo_detail.html", "src/templates/settings.html")


def _placeholder_rules() -> list[tuple[str, str, str]]:
    """(파일, 선택자, 본문) — 주석을 지운 뒤 `::placeholder` 규칙 전부."""
    out = []
    for rel in _PLACEHOLDER_FILES:
        clean = strip_css_comments(read(rel))
        for m in re.finditer(r"([^{}]*::placeholder[^{}]*)\{([^{}]*)\}", clean):
            out.append((rel, m.group(1).strip(), m.group(2)))
    return out


def test_placeholder_rules_are_all_found():
    """관측 하한 — 규칙을 못 찾으면 아래 시험들이 조용히 공허해진다."""
    rules = _placeholder_rules()
    assert len(rules) >= 2, (
        f"`::placeholder` 규칙을 {len(rules)}개만 찾았다 — 테스트가 늙었거나 형식이 바뀌었다")


def test_placeholder_is_not_dimmed_by_opacity():
    """🔴 placeholder 를 `opacity` 로 깎지 않는다.

    실측: `--text-2` 는 7.05~8.64 인데 `.7` 을 곱하면 3.43~4.48 로 AA 아래로 떨어진다.
    색은 토큰으로 정하고, 투명도는 «명시적으로 1» 로 둔다 — 지우기만 하면 UA 기본값이
    다시 적용된다.
    """
    offenders = []
    for rel, sel, body in _placeholder_rules():
        m = re.search(r"opacity\s*:\s*([\d.]+)", body)
        if m is None:
            offenders.append(f"{rel}: `{sel}` 이 `opacity: 1` 을 «명시» 하지 않는다 — "
                             "UA 기본 placeholder 투명도가 되살아난다")
        elif float(m.group(1)) < 1:
            offenders.append(f"{rel}: `{sel}` 이 opacity {m.group(1)} 로 깎는다")
    assert not offenders, (
        "placeholder 가 투명도로 흐려진다 (WCAG 1.4.3):\n  " + "\n  ".join(offenders))


def test_placeholder_color_meets_aa_in_every_theme():
    """placeholder 색이 네 테마에서 4.5:1 이상이어야 한다.

    🔴 바탕이 자리마다 다르다 — `.field-input` 은 `--bg-input`, `.filter-search` 는
    투명이라 `.filter-bar` 의 `--bg-elevated` 다. 둘 다 본다(Grok 지적: dark 의
    `--bg-elevated` 는 여유가 0.03 뿐이라 한쪽만 보면 놓친다).
    """
    css = read("src/static/css/tokens.css")
    bad = []
    for rel, sel, body in _placeholder_rules():
        m = re.search(r"color\s*:\s*var\(\s*(--[\w-]+)", body)
        assert m, f"{rel}: `{sel}` 이 색 토큰을 쓰지 않는다 — {body.strip()[:60]!r}"
        for theme in THEMES:
            block = theme_block(css, theme)
            fg = parse_color(resolve(block, decl(block, m.group(1))))
            for ground_name in ("--bg-input", "--bg-elevated"):
                ground = parse_color(resolve(block, decl(block, ground_name)))
                r = ratio(over(fg, ground), ground)
                if r < AA_TEXT:
                    bad.append(f"{theme}: `{sel}` {m.group(1)} on {ground_name} = "
                               f"{r:.2f} (< {AA_TEXT})")
    assert not bad, "placeholder 가 AA 미달이다:\n  " + "\n  ".join(bad)


# ── 드롭다운 셰브론 ─────────────────────────────────────────────────────────

_SELECT_FILE = "src/templates/add_repo.html"


def test_dropdown_chevron_color_is_not_hardcoded():
    """🔴 SVG 데이터 URI 안에 색을 박지 않는다 — 테마를 못 탄다.

    실측: `#73737c` 가 catppuccin 에서 2.68(기준 3.0). 나머지 셋은 4.06~4.70 이라
    «세 테마에서 통과» 가 결함을 가려 왔다.
    """
    src = strip_css_comments(read(_SELECT_FILE))
    # 🔴 `[^"')]*` 로 끊으면 안 된다 — SVG 안의 `stroke='...'` 첫 따옴표에서 잘려
    #    정작 찾으려는 색 앞에서 멈춘다(이 시험이 처음에 그래서 거짓 초록이었다).
    #    `url(` 부터 «닫는 괄호» 까지를 통째로 본다.
    # 🔴 `mask-image` 안의 색은 «알파» 로만 쓰이므로 무해하다 — 보이는 색은 별도의
    #    `background-color` 가 정한다. 문제는 `background-image` 로 «그려지는» 색이다.
    #    이 구분을 안 하면 올바른 처방(마스크)까지 red 가 난다.
    hits = re.findall(
        r"(?<!-)background(?:-image)?\s*:[^;]*url\(\s*[\"']?data:image/svg\+xml[^;]*",
        src, re.DOTALL)
    assert re.search(r"data:image/svg\+xml", src), (
        "SVG 데이터 URI 를 찾지 못했다 — 못 재면 초록이 아니라 red 다")
    offenders = [h[:110] for h in hits
                 if re.search(r"(?:stroke|fill)=(?:'|%27|\")?%23[0-9a-fA-F]{3,6}", h)]
    assert not offenders, (
        "SVG 데이터 URI 안에 색이 박혀 있다 — 테마 토큰이 닿지 않는다:\n  "
        + "\n  ".join(offenders))


def test_dropdown_chevron_uses_a_theme_token():
    """셰브론이 «토큰» 으로 칠해져야 한다 — 그리고 그 토큰이 3:1 을 넘어야 한다."""
    src = strip_css_comments(read(_SELECT_FILE))
    m = re.search(r"\.form-select-wrap::after\s*\{([^}]*)\}", src)
    assert m, (
        "`.form-select-wrap::after` 규칙 부재 — `<select>` 는 의사요소를 가질 수 없으므로 "
        "감싸는 요소에 셰브론을 그려야 한다")
    body = m.group(1)
    tok = re.search(r"background-color\s*:\s*var\(\s*(--[\w-]+)", body)
    assert tok, f"셰브론이 토큰으로 칠해지지 않는다 — {body.strip()[:70]!r}"
    assert "mask" in body, (
        "셰브론이 `mask-image` 로 그려지지 않는다 — 색을 토큰으로 두려면 마스크가 필요하다")

    css = read("src/static/css/tokens.css")
    bad = []
    for theme in THEMES:
        block = theme_block(css, theme)
        fg = parse_color(resolve(block, decl(block, tok.group(1))))
        for ground_name in ("--bg-input", "--bg-elevated"):
            ground = parse_color(resolve(block, decl(block, ground_name)))
            r = ratio(over(fg, ground), ground)
            if r < NON_TEXT:
                bad.append(f"{theme}: 셰브론 {tok.group(1)} on {ground_name} = "
                           f"{r:.2f} (< {NON_TEXT})")
    assert not bad, "드롭다운 셰브론이 안 보인다:\n  " + "\n  ".join(bad)
