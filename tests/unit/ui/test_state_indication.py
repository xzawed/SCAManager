"""상태를 «색만으로» 나르는 자리들 — 1.4.1(A) · 1.4.11(AA) · 4.1.2(A).

실측(브라우저·4테마):

| 자리 | 실측 | 무엇이 문제인가 |
|---|---|---|
| `.conn-dot` (채널 설정됨/아님) | on↔off 가 **색 말고 다른 차이 0** · off 가 light 2.51 · pastel 2.72 | 1.4.1 + 1.4.11 |
| 언어 메뉴 선택 항목 | active 와 비활성의 **계산 스타일이 전부 동일**, `aria-checked` 없음 | 1.3.1 / 4.1.2 |
| 토글 OFF | 트랙이 카드와 **1.00~1.07**, light·pastel 은 손잡이마저 **1.00 / 1.04** | 1.4.11 |
| 정렬 방향 글리프 | 1.71~2.97 — `.sort-icon{opacity:.5}` 가 `::after{opacity:1}` 과 **곱해져** 저자 의도가 죽었다 | 1.4.11 |

이 파일은 계산이고, 「칠해진 결과」는 e2e 가 본다.
"""
from __future__ import annotations

import re

from ._contrast import (
    THEMES, decl, over, parse_color, ratio, read, resolve, strip_css_comments, theme_block,
)

NON_TEXT = 3.0

_SETTINGS = "src/templates/settings.html"
_BASE = "src/templates/base.html"
_REPO_DETAIL = "src/templates/repo_detail.html"


def _rule(src: str, selector: str) -> str | None:
    """선택자 목록에 그 선택자가 «포함된» 규칙의 본문. 주석은 미리 지운다.

    🔴 처음엔 `re.escape(selector)` 를 썼는데 인자를 이미 정규식으로 넘기고 있어
    역슬래시가 «두 번» 이스케이프됐다 — 어떤 규칙도 못 찾고 전부 「규칙 부재」로 red 가 났다.
    결함이 아니라 계기 때문에 빨간 것은 초록만큼 위험하다.
    묶인 선택자(`.a, .b { … }`)도 찾아야 하므로 «단독» 이 아니라 «포함» 으로 본다.
    """
    clean = strip_css_comments(src)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean):
        for one in m.group(1).split(","):
            if re.fullmatch(r"\s*" + selector + r"\s*", one):
                return m.group(2)
    return None


# ── A. conn-dot — 채널이 설정됐는지를 8px 점 «색» 하나로 ────────────────────

def test_conn_dot_state_is_not_conveyed_by_color_alone():
    """🔴 on/off 가 색 외의 것으로도 갈려야 한다 (WCAG 1.4.1 Use of Color, Level A).

    실측: 두 상태의 `width`·`height`·`border-radius`·`text`·`title`·`aria-label`·`role`·
    `border`·`box-shadow` 가 **전부 같았다** — 차이는 `background` 와 `opacity` 뿐.
    """
    src = read(_SETTINGS)
    on = _rule(src, r"\.conn-dot\.is-on")
    off = _rule(src, r"\.conn-dot\.is-off")
    assert on and off, "`.conn-dot.is-on/.is-off` 규칙 부재 — 테스트가 늙었다"

    def shape(body: str) -> dict[str, str]:
        """색·투명도가 아닌 «형태» 선언 — 이름이 아니라 «값» 까지 본다.

        🔴 이름만 비교하면 `border: 0` 과 `border: 1.5px solid …` 가 같아 보인다.
        모양이 갈리는지는 값이 말한다.
        """
        out: dict[str, str] = {}
        for part in body.split(";"):
            if ":" not in part:
                continue
            name, _, value = part.partition(":")
            name = name.strip()
            if name in ("background", "background-color", "opacity", "color"):
                continue
            out[name] = " ".join(value.split())
        return out

    diff = {k for k in set(shape(on)) | set(shape(off))
            if shape(on).get(k) != shape(off).get(k)}
    assert diff, (
        "`.conn-dot` 의 on/off 가 색(그리고 투명도)으로만 갈린다 — "
        "테두리·모양 등 색 아닌 차이를 하나 둘 것 (WCAG 1.4.1 Level A).\n"
        f"  is-on  형태 선언: {sorted(shape(on))}\n"
        f"  is-off 형태 선언: {sorted(shape(off))}"
    )


def test_conn_dot_state_is_exposed_to_assistive_tech():
    """🔴 점의 상태가 보조기술에 노출돼야 한다.

    실측: `role`·`aria-label`·`title`·글자 어느 것도 없었다. 스크린리더에게 이 점은
    존재하지 않고, 「설정됨/아님」은 어디에도 없다.
    """
    src = read(_SETTINGS)
    dots = re.findall(r"<span[^>]*class=\"conn-dot[^\"]*\"[^>]*>", src)
    assert dots, "`.conn-dot` 마크업 부재 — 테스트가 늙었다"
    naked = [d for d in dots
             if "aria-label" not in d and "title" not in d and "role=" not in d]
    assert not naked, (
        f"`.conn-dot` {len(naked)}/{len(dots)} 개가 상태를 보조기술에 알리지 않는다 "
        "(role + aria-label 또는 곁의 글자):\n  " + "\n  ".join(naked[:3])
    )


def test_conn_dot_off_meets_non_text_contrast():
    """꺼진 점도 카드 위에서 3:1 이상이어야 한다 — 실측 light 2.51 · pastel 2.72."""
    css = read("src/static/css/tokens.css")
    settings = strip_css_comments(read(_SETTINGS))
    off = _rule(read(_SETTINGS), r"\.conn-dot\.is-off")
    assert off, "`.conn-dot.is-off` 규칙 부재"
    om = re.search(r"opacity\s*:\s*([\d.]+)", off)
    alpha = float(om.group(1)) if om else 1.0
    token = re.search(r"(?:background|border(?:-\w+)?)\s*:[^;]*var\(\s*(--[\w-]+)", off)
    assert token, f"`.conn-dot.is-off` 가 토큰을 쓰지 않는다 — {off.strip()[:60]!r}"
    bad = []
    for theme in THEMES:
        block = theme_block(css, theme)
        fg = parse_color(resolve(block, decl(block, token.group(1))))
        card = parse_color(resolve(block, decl(block, "--bg-card")))
        painted = over((fg[0], fg[1], fg[2], fg[3] * alpha), card)
        r = ratio(painted, card)
        if r < NON_TEXT:
            bad.append(f"{theme}: conn-dot(off) on --bg-card = {r:.2f} (< {NON_TEXT})")
    assert not bad, "꺼진 연결 점이 카드에서 안 보인다:\n  " + "\n  ".join(bad)
    assert "conn-dot" in settings


# ── B. 메뉴 선택 상태 — 언어 메뉴는 «아무 표시도» 없었다 ────────────────────

def test_language_menu_marks_the_selected_item_visually():
    """🔴 선택된 언어가 «보여야» 한다.

    실측: JS 가 `.active` 를 붙이는데 `.lang-option.active` CSS 규칙이 **어디에도 없어서**,
    네 테마 전부 활성/비활성의 `color`·`background`·`font-weight`·`::before`·`::after` 가
    완전히 같았다. 색이 정보를 나르는 것조차 아니다 — 아무것도 안 나른다.
    """
    body = _rule(read(_BASE), r"\.lang-option\.active")
    assert body, (
        "`.lang-option.active` CSS 규칙이 없다 — JS 가 붙이는 `active` 가 화면에 아무 효과도 "
        "내지 않는다 (WCAG 1.3.1 / 4.1.2)"
    )
    props = {p.split(":")[0].strip() for p in body.split(";") if p.strip()}
    assert props & {"color", "background", "background-color", "font-weight"}, (
        f"`.lang-option.active` 가 눈에 보이는 차이를 만들지 않는다 — {body.strip()[:60]!r}")


def test_language_menu_selection_is_exposed_to_assistive_tech():
    """선택 상태가 `aria-checked` 로 노출돼야 한다 — `role=\"menuitem\"` 만으로는 못 알린다."""
    src = read(_BASE)
    opts = re.findall(r"<div[^>]*class=\"lang-option\"[^>]*>", src)
    assert len(opts) >= 3, f"`.lang-option` 마크업 {len(opts)}개 — 테스트가 늙었다"
    bad = [o for o in opts if 'role="menuitemradio"' not in o or "aria-checked" not in o]
    assert not bad, (
        "언어 메뉴 항목이 선택 상태를 보조기술에 알리지 않는다 "
        '(`role="menuitemradio"` + `aria-checked` 필요):\n  ' + "\n  ".join(bad[:2])
    )


def test_theme_menu_selection_is_exposed_to_assistive_tech():
    """테마 메뉴는 `✓` 로 «보이기» 는 한다 — 보조기술에는 여전히 안 보였다."""
    src = read(_BASE)
    opts = re.findall(r"<div[^>]*class=\"theme-option\"[^>]*>", src)
    assert len(opts) >= 4, f"`.theme-option` 마크업 {len(opts)}개 — 테스트가 늙었다"
    bad = [o for o in opts if 'role="menuitemradio"' not in o or "aria-checked" not in o]
    assert not bad, (
        "테마 메뉴 항목이 선택 상태를 보조기술에 알리지 않는다:\n  " + "\n  ".join(bad[:2])
    )


def test_menu_scripts_keep_aria_checked_in_sync():
    """`.active` 를 토글하는 곳마다 `aria-checked` 도 같이 바뀌어야 한다.

    🔴 마크업에만 넣으면 첫 렌더 이후로 굳는다 — 사용자가 언어·테마를 바꾸면 어긋난다.
    """
    src = strip_css_comments(read(_BASE))
    for cls in ("lang-option", "theme-option"):
        blocks = re.findall(
            rf"querySelectorAll\('\.{cls}'\)[\s\S]{{0,400}}?\}}\);", src)
        assert blocks, f"`{cls}` 를 토글하는 스크립트를 찾지 못했다 — 테스트가 늙었다"
        toggling = [b for b in blocks if "classList.toggle('active'" in b
                    or "classList.add('active'" in b or "classList.remove('active'" in b]
        assert toggling, f"`{cls}` 의 active 토글 지점을 찾지 못했다"
        missing = [b for b in toggling if "aria-checked" not in b]
        assert not missing, (
            f"`{cls}` 의 active 를 바꾸면서 `aria-checked` 를 갱신하지 않는 자리가 "
            f"{len(missing)}곳 있다")


# ── C. 토글 스위치 — OFF 상태가 아예 안 보였다 ─────────────────────────────

def test_toggle_off_state_is_visible_against_the_card():
    """🔴 꺼진 스위치도 «보여야» 한다.

    실측(4테마): OFF 트랙이 카드와 1.00~1.07, 테두리 1.13~1.28.
    light·pastel 은 흰 손잡이가 흰 트랙 위라 **1.00 / 1.04** — 스위치가 있다는 사실조차
    안 보인다. 트랙 테두리·손잡이 셋 중 하나는 3:1 을 넘어야 한다.
    """
    css = read("src/static/css/tokens.css")
    src = read(_SETTINGS)
    track = _rule(src, r"\.toggle-switch \.toggle-track")
    knob = _rule(src, r"\.toggle-switch \.toggle-track::after")
    assert track and knob, "토글 규칙 부재 — 테스트가 늙었다"

    def token_of(body: str, prop: str) -> str | None:
        m = re.search(rf"{prop}\s*:[^;]*var\(\s*(--[\w-]+)", body)
        return m.group(1) if m else None

    def literal_of(body: str, prop: str) -> str | None:
        m = re.search(rf"{prop}\s*:\s*(#[0-9a-fA-F]{{3,6}})", body)
        return m.group(1) if m else None

    bad = []
    for theme in THEMES:
        block = theme_block(css, theme)
        card = parse_color(resolve(block, decl(block, "--bg-card")))

        def paint(body: str, props: tuple[str, ...], ground: tuple) -> float:
            best = 0.0
            for prop in props:
                tok = token_of(body, prop)
                lit = literal_of(body, prop)
                if tok:
                    c = parse_color(resolve(block, decl(block, tok)))
                elif lit:
                    c = parse_color(lit)
                else:
                    continue
                best = max(best, ratio(over(c, ground), ground))
            return best

        track_fill = paint(track, ("background", "background-color"), card)
        track_bd = paint(track, ("border", "border-color"), card)
        # 손잡이는 «트랙 위» 에 앉는다
        tok = token_of(track, "background") or token_of(track, "background-color")
        track_c = (parse_color(resolve(block, decl(block, tok))) if tok else card)
        track_painted = over(track_c, card)
        knob_r = paint(knob, ("background", "background-color", "border", "border-color"),
                       track_painted)
        best = max(track_fill, track_bd, knob_r)
        if best < NON_TEXT:
            bad.append(f"{theme}: 트랙 {track_fill:.2f} · 테두리 {track_bd:.2f} · "
                       f"손잡이 {knob_r:.2f} — 최댓값 {best:.2f} (< {NON_TEXT})")
    assert not bad, "꺼진 스위치가 보이지 않는다:\n  " + "\n  ".join(bad)


# ── D. 정렬 방향 글리프 — opacity 가 «곱해져» 저자 의도가 죽었다 ────────────

def test_sort_indicator_opacity_does_not_compound():
    """🔴 `.sort-icon { opacity }` 는 `::after { opacity: 1 }` 로 되돌릴 수 없다.

    CSS `opacity` 는 «곱해진다». 저자는 정렬된 열의 화살표를 또렷하게 하려고
    `::after { opacity: 1 }` 을 적었지만, 부모의 `.5` 가 그대로 남아 실제로는 0.5 다 —
    실측 1.71~2.97 로 네 테마 전부 3:1 미만.

    처방: 부모에서 흐림을 걷고, «정렬 안 된» 상태에만 흐림을 준다.
    """
    src = strip_css_comments(read(_REPO_DETAIL))
    parent = _rule(read(_REPO_DETAIL), r"\.sort-icon")
    assert parent is not None, "`.sort-icon` 규칙 부재 — 테스트가 늙었다"
    parent_op = re.search(r"opacity\s*:\s*([\d.]+)", parent)
    child_overrides = re.findall(
        r"\.sort-icon::after\s*\{([^}]*opacity\s*:\s*1\b[^}]*)\}", src)
    assert not (parent_op and float(parent_op.group(1)) < 1 and child_overrides), (
        f"`.sort-icon` 이 opacity {parent_op.group(1) if parent_op else '?'} 를 걸어 두고 "
        f"`::after` 가 `opacity: 1` 로 되돌리려 한다 ({len(child_overrides)}곳) — "
        "opacity 는 곱해지므로 그 되돌림은 «작동하지 않는다»"
    )
