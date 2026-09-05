"""포커스 표시 — 「보이는가」와 「3:1 인가」.

실측(픽셀·Tab 으로 실제 도달): `repo_detail.html` 의 점수 범위 슬라이더 둘은 Tab 으로
포커스를 받아도 **4386px 중 0px** 이 바뀐다 — 네 테마 전부. 원인은
`.dual-slider-track input[type=range] { outline: none }` 이 전역
`*:focus-visible { outline: 2px solid var(--accent) }` 를 특이도로 이기고 **대체가 없는 것**.
WCAG 2.4.7 Focus Visible(Level A).

색 쪽은 pastel 이 미달이었다 — `--accent`(#8c82d2)를 링으로 쓰는데 페이지 바탕에서
실측 2.77~2.88(기준 3.0). 링 역할을 `--focus-ring` 으로 떼어 낸다.
"""
import re

from ._contrast import (
    ROOT, THEMES, decl, over, parse_color, ratio, read, resolve,
    strip_css_comments, theme_block,
)

NON_TEXT = 3.0


def test_focus_ring_token_meets_non_text_contrast_in_every_theme():
    """🔴 포커스 링은 그것이 얹히는 두 바탕(페이지·카드) 위에서 3:1 이상이어야 한다.

    실측(픽셀·5화면): pastel 의 링이 페이지 바탕에서 2.77 이었다. 카드 위만 재면
    통과하므로 **두 바탕을 다 본다** — 실제로 미달한 9건은 전부 페이지 바탕 위였다.
    """
    src = read("src/static/css/tokens.css")
    bad = []
    for theme in THEMES:
        block = theme_block(src, theme)
        ring = parse_color(resolve(block, decl(block, "--focus-ring")))
        for ground_name in ("--bg-base", "--bg-card"):
            ground = parse_color(resolve(block, decl(block, ground_name)))
            r = ratio(over(ring, ground), ground)
            if r < NON_TEXT:
                bad.append(f"{theme}: --focus-ring on {ground_name} = {r:.2f} (< {NON_TEXT})")
    assert not bad, "포커스 링이 바탕에서 안 보인다:\n  " + "\n  ".join(bad)


def test_global_focus_ring_uses_the_focus_ring_token():
    """전역 `*:focus-visible` 은 링 전용 토큰을 쓴다 — 면 색(`--accent`)이 아니라.

    🔴 값-매칭이 아니라 «구조» 를 본다. `--accent` 로 되돌리면 e2e 대비 가드도 잡지만,
    그 가드는 조상 사슬로 바탕을 계산해 형제 orb 를 못 보므로 후하게 나온다(#1617).
    """
    base = strip_css_comments(read("src/templates/base.html"))
    m = re.search(r"\*:focus-visible\s*\{([^}]*)\}", base)
    assert m, "`*:focus-visible` 규칙 부재 — 테스트가 늙었다"
    body = m.group(1)
    outline = re.search(r"outline\s*:\s*([^;]+);", body)
    assert outline, "`*:focus-visible` 이 outline 을 선언하지 않는다"
    assert "var(--focus-ring)" in outline.group(1), (
        f"전역 포커스 링이 `--focus-ring` 을 쓰지 않는다 — {outline.group(1).strip()!r}")


# 🔴 포커스를 «지우는» 규칙은 같은 선택자에 대체 표시를 반드시 짝지어야 한다.
#    현재 리포에서 `outline:none` 을 «포커스 상태에» 쓰는 자리를 모두 적는다.
#    새 자리가 생기면 이 목록이 비어 있지 않게 되어 red 가 된다.
_FOCUS_KILLERS = (
    ("src/templates/repo_detail.html", r"\.dual-slider-track input\[type=range\]"),
    ("src/templates/settings.html", r"input:focus, select:focus, textarea:focus"),
    ("src/templates/analysis_detail.html", r"\.issue-modal-input:focus"),
)


def _rules(src: str):
    """(선택자, 본문) 쌍 — 주석을 지운 뒤."""
    clean = strip_css_comments(src)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", clean)


def test_outline_none_is_always_paired_with_a_replacement_indicator():
    """🔴 `outline: none` 을 쓰는 규칙마다 «대체 표시» 가 같은 파일에 있어야 한다.

    실측: 슬라이더는 대체가 없어 Tab 도달 시 픽셀이 0개 바뀐다. 대체로 인정하는 것은
    같은 요소를 겨냥한 `:focus`/`:focus-visible` 규칙이 `outline`(none 아님) ·
    `box-shadow` · `border-color` 중 하나를 선언하는 것.
    """
    offenders = []
    checked = 0
    for rel in sorted({p for p, _ in _FOCUS_KILLERS}):
        src = read(rel)
        rules = _rules(src)
        killers = [(s.strip(), b) for s, b in rules
                   if re.search(r"outline\s*:\s*(none|0)\b", b)]
        for sel, _body in killers:
            checked += 1
            key = sel.split(":")[0].split("::")[0].strip().rstrip(",").strip()
            if not key:
                continue
            repl = [
                (s, b) for s, b in rules
                if key in s and re.search(r":focus(-visible)?", s)
                and (re.search(r"outline\s*:\s*(?!none|0\b)", b)
                     or "box-shadow" in b or "border-color" in b
                     or re.search(r"\bborder\s*:", b))
            ]
            if not repl:
                offenders.append(f"{rel}: `{sel[:70]}` 이 outline 을 지우고 대체가 없다")
    assert checked >= 3, (
        f"`outline:none` 규칙을 {checked}건만 봤다 — 못 재면 초록이 아니라 red 다")
    assert not offenders, (
        "포커스 표시가 사라지는 자리가 있다 (WCAG 2.4.7 Level A):\n  "
        + "\n  ".join(offenders))


def test_range_slider_has_a_thumb_focus_ring():
    """점수 범위 슬라이더는 «손잡이» 에 링을 준다.

    트랙 전체를 두르면 두 손잡이가 같은 트랙을 공유해 «어느 쪽이 포커스인지» 를 못 알린다.
    webkit·moz 두 의사요소를 다 적는다 — 한쪽만 적으면 다른 엔진에서 그대로 사라진다.
    """
    src = strip_css_comments(read("src/templates/repo_detail.html"))
    missing = [
        pseudo for pseudo in ("::-webkit-slider-thumb", "::-moz-range-thumb")
        if not re.search(
            r"input\[type=range\]:focus-visible" + re.escape(pseudo) + r"\s*\{([^}]*)\}", src)
    ]
    assert not missing, f"슬라이더 손잡이 포커스 링 부재: {missing}"
    for pseudo in ("::-webkit-slider-thumb", "::-moz-range-thumb"):
        m = re.search(
            r"input\[type=range\]:focus-visible" + re.escape(pseudo) + r"\s*\{([^}]*)\}", src)
        assert "var(--focus-ring)" in m.group(1), (
            f"{pseudo} 링이 `--focus-ring` 을 쓰지 않는다 — {m.group(1).strip()[:60]!r}")


def test_focus_ring_token_is_defined_in_every_theme():
    """네 테마 전부에 정의돼야 한다 — 한 테마만 빠지면 그 테마에서 링이 사라진다."""
    src = read("src/static/css/tokens.css")
    for theme in THEMES:
        decl(theme_block(src, theme), "--focus-ring")
    assert (ROOT / "src/static/css/tokens.css").exists()
