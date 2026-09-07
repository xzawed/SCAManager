"""포커스 표시 — 「보이는가」와 「3:1 인가」.

실측(픽셀·Tab 으로 실제 도달): `repo_detail.html` 의 점수 범위 슬라이더 둘은 Tab 으로
포커스를 받아도 **4386px 중 0px** 이 바뀐다 — 네 테마 전부. 원인은
`.dual-slider-track input[type=range] { outline: none }` 이 전역
`*:focus-visible { outline: 2px solid var(--accent) }` 를 특이도로 이기고 **대체가 없는 것**.
WCAG 2.4.7 Focus Visible(Level AA).

색 쪽은 pastel 이 미달이었다 — `--accent`(#8c82d2)를 링으로 쓰는데 페이지 바탕에서
실측 2.77~2.88(기준 3.0). 링 역할을 `--focus-ring` 으로 떼어 낸다.
"""
import re

import pytest

from ._contrast import (
    ROOT, THEMES, decl, over, parse_color, ratio, read, resolve,
    strip_css_comments, theme_block,
)

NON_TEXT = 3.0


def _body_background_stops(base_html: str, theme: str) -> list[tuple]:
    """`body[data-theme="X"]` 이 `background` 로 덮는 색들 — 없으면 빈 목록."""
    m = re.search(rf'body\[data-theme="{theme}"\]\s*\{{([^}}]*)\}}', base_html)
    if not m:
        return []
    decl_m = re.search(r"background\s*:\s*([^;]+);", m.group(1))
    if not decl_m:
        return []
    return [parse_color(c) for c in
            re.findall(r"#[0-9a-fA-F]{3,6}|rgba?\([^)]*\)", decl_m.group(1))]


def test_focus_ring_token_meets_non_text_contrast_in_every_theme():
    """🔴 포커스 링은 그것이 얹히는 두 바탕(페이지·카드) 위에서 3:1 이상이어야 한다.

    실측(픽셀·5화면): pastel 의 링이 페이지 바탕에서 2.77 이었다. 카드 위만 재면
    통과하므로 **두 바탕을 다 본다** — 실제로 미달한 9건은 전부 페이지 바탕 위였다.
    """
    src = read("src/static/css/tokens.css")
    base_html = strip_css_comments(read("src/templates/base.html"))
    bad = []
    for theme in THEMES:
        block = theme_block(src, theme)
        ring = parse_color(resolve(block, decl(block, "--focus-ring")))
        grounds = {name: parse_color(resolve(block, decl(block, name)))
                   for name in ("--bg-base", "--bg-card")}
        # 🔴 토큰이 곧 «칠해지는» 바탕은 아니다. pastel 은 `body[data-theme="pastel"]` 이
        #    `--bg-base`(따뜻한 크림)를 라벤더 그라디언트로 «덮는다» — 그 위에 링이 앉는다.
        #    토큰만 보면 실제로 링이 놓이는 색을 재지 못한다.
        for i, stop in enumerate(_body_background_stops(base_html, theme)):
            grounds[f"body[data-theme={theme}] stop{i}"] = stop
        for name, ground in grounds.items():
            r = ratio(over(ring, ground), ground)
            if r < NON_TEXT:
                bad.append(f"{theme}: --focus-ring on {name} = {r:.2f} (< {NON_TEXT})")
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
# 🔴 손으로 적던 목록을 **없앤다.** 종전 판은 파일 3개를 열거하고 바로 위 주석이
#    「새 자리가 생기면 red 가 된다」고 적었는데 그것은 **거짓**이었다 — 목록 밖 파일은
#    읽지도 않으므로 새 자리는 영원히 안 보인다. 실측으로 그 시점에 이미 두 자리가
#    목록 밖이었다(`src/static/css/components.css` 의 `.input:focus`,
#    `src/templates/add_repo.html` 의 `.form-select:focus`). 둘 다 대체 표시가 있어서
#    결함은 아니었지만, 대체가 지워져도 아무 시험도 울리지 않는 상태였다.
#
# 🔴 「`:focus` 규칙 안의 `outline:none` 만 본다」로 좁히면 안 된다 — 원래 이 가드를 만든
#    결함(`repo_detail.html` 의 슬라이더)은 **비-focus 규칙**에 있었다. 그래서 규칙 종류를
#    가리지 않고 `outline: none|0` 을 «전부» 걷는다.
#
# The old hand list's own comment lied: files outside it were never read. Derive instead,
# and do not narrow to focus rules — the original defect lived in a non-focus rule.
_FOCUS_KILLER_ROOTS = ("src/templates", "src/static/css")
_OUTLINE_KILLED = re.compile(r"outline\s*:\s*(none|0)\b")


def _focus_killer_files() -> list[str]:
    """`outline: none|0` 을 선언하는 파일 전부 — 열거가 아니라 파생이다."""
    out = []
    for rel_root in _FOCUS_KILLER_ROOTS:
        for path in sorted((ROOT / rel_root).rglob("*")):
            if path.suffix not in (".html", ".css") or "dist" in path.parts:
                continue
            if _OUTLINE_KILLED.search(strip_css_comments(path.read_text(encoding="utf-8"))):
                out.append(path.relative_to(ROOT).as_posix())
    return out


def _rules(src: str):
    """(선택자, 본문) 쌍 — 주석을 지운 뒤."""
    clean = strip_css_comments(src)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", clean)


# 🔴 «대체가 아예 없는가» 와 «대체가 충분한가» 는 다른 질문이다.
#    실측: settings 의 임계값 슬라이더는 대체가 «있었다» — 일반 규칙
#    `input:focus, select:focus, textarea:focus` 가 15% accent 글로를 준다
#    (실측 `color(srgb 0.486 0.478 1 / 0.15) 0 0 0 3px`). 그건 2.4.7 이 아니라 1.4.11
#    문제다. 반면 `#scoreMin`·`.danger-summary` 는 정말 아무것도 없었다(실측: 픽셀 0개).
#    그래서 이 시험은 「없는가」만 보고, 「충분한가」는 아래 손잡이 링 시험이 맡는다.
_GENERIC_INPUT_FOCUS = re.compile(r"\b(input|select|textarea)\s*:focus\b")


def test_outline_none_is_always_paired_with_a_replacement_indicator():
    """🔴 `outline: none` 을 쓰는 규칙마다 «대체 표시» 가 같은 파일에 있어야 한다.

    실측: `#scoreMin`·`#scoreMax`·`.danger-summary` 는 대체가 없어 포커스 시
    `outline` 이 `none 0px` 이고 픽셀이 0개 바뀐다. 대체로 인정하는 것은 같은 요소를
    겨냥한 `:focus`/`:focus-visible` 규칙이 `outline`(none 아님) · `box-shadow` ·
    `border-color` 중 하나를 선언하는 것 — 요소 이름을 겨냥한 «일반» 규칙도 포함한다.

    이 시험은 «있는가» 만 본다. 그 대체가 3:1 을 넘는지는
    `test_range_slider_has_a_thumb_focus_ring` + `--focus-ring` 토큰 시험이 맡는다.
    """
    offenders = []
    checked = 0
    files = _focus_killer_files()
    assert files, "`outline: none` 을 쓰는 파일을 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    for rel in files:
        src = read(rel)
        rules = _rules(src)
        killers = [(s.strip(), b) for s, b in rules
                   if re.search(r"outline\s*:\s*(none|0)\b", b)]
        for sel, _body in killers:
            checked += 1
            key = sel.split(":")[0].split("::")[0].strip().rstrip(",").strip()
            if not key:
                continue
            tag = re.search(r"\b(input|select|textarea)\b", key)
            repl = [
                (s, b) for s, b in rules
                if (key in s or (tag and _GENERIC_INPUT_FOCUS.search(s)
                                 and tag.group(1) in s))
                and re.search(r":focus(-visible)?", s)
                # 🔴 `(?!none|0\b)` 만으로는 `outline: none` 이 **자기 자신의 대체**로
                #    인정된다 — `\s*` 가 0글자로 물러나면 lookahead 가 공백 위에서
                #    성립한다(실측: `outline: none;` → True, `outline: 0;` → True).
                #    뒤에 «공백 아닌 글자» 를 요구해 그 되돌림을 막는다.
                and (re.search(r"outline\s*:\s*(?!none\b|0\b)\S", b)
                     or "box-shadow" in b or "border-color" in b
                     or re.search(r"\bborder\s*:", b))
            ]
            if not repl:
                offenders.append(f"{rel}: `{sel[:70]}` 이 outline 을 지우고 대체가 없다")
    assert checked >= 3, (
        f"`outline:none` 규칙을 {checked}건만 봤다 — 못 재면 초록이 아니라 red 다")
    assert not offenders, (
        "포커스 표시가 사라지는 자리가 있다 (WCAG 2.4.7 Level AA):\n  "
        + "\n  ".join(offenders))


# range 슬라이더가 있는 모든 화면 — 새 화면이 생기면 여기에 더한다
_RANGE_SLIDER_TEMPLATES = (
    "src/templates/repo_detail.html",   # 점수 범위(#scoreMin/#scoreMax)
    "src/templates/settings.html",      # 승인·거부 임계값
)


@pytest.mark.parametrize("rel", _RANGE_SLIDER_TEMPLATES)
def test_range_slider_has_a_thumb_focus_ring(rel):
    """range 슬라이더는 «손잡이» 에 `--focus-ring` 링을 준다.

    트랙 전체를 두르면 두 손잡이가 같은 트랙을 공유해 «어느 쪽이 포커스인지» 를 못 알린다.
    webkit·moz 두 의사요소를 다 적는다 — 한쪽만 적으면 다른 엔진에서 그대로 사라진다.

    🔴 이것이 range 의 «대비» 축을 맡는 유일한 가드다. e2e 대비 가드는 range 를 건너뛴다 —
    링이 UA 섀도 의사요소에 있어 `getComputedStyle` 이 돌려주지 않기 때문이다.
    settings 슬라이더는 일반 `input:focus` 규칙에서 15% accent 글로를 «이미» 받고 있었다
    (실측 알파 0.15) — 있지만 3:1 에 한참 못 미친다. 그 자리를 이 링이 대신한다.
    """
    src = strip_css_comments(read(rel))
    for pseudo in ("::-webkit-slider-thumb", "::-moz-range-thumb"):
        m = re.search(
            r"input\[type=range\]:focus-visible" + re.escape(pseudo) + r"\s*\{([^}]*)\}", src)
        assert m, f"{rel}: 슬라이더 손잡이 포커스 링 부재 — {pseudo}"
        assert "var(--focus-ring)" in m.group(1), (
            f"{rel}: {pseudo} 링이 `--focus-ring` 을 쓰지 않는다 "
            f"— {m.group(1).strip()[:60]!r}")


def _contexts(src: str):
    """(문맥이름, 본문) — 최상위 하나 + `@media` 블록 각각. 중괄호 균형으로 뜬다.

    문맥을 나누는 이유: `@media` 안의 규칙은 밖의 규칙과 «다른 조건» 에서만 산다.
    문맥을 섞어 세면 「밖에 moz 가 있으니 됐다」로 통과해 버린다 — 그것이 이 결함이
    살아남은 방식이다(기본 규칙은 두 벌, 모바일 확대만 한 벌이었다).
    """
    out, cut = [], []
    for m in re.finditer(r"@media([^{]*)\{", src):
        i = m.end() - 1
        depth, j = 0, i
        while j < len(src):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((f"@media{m.group(1).strip()}", src[i + 1:j]))
        cut.append((m.start(), j + 1))
    top = src
    for a, b in reversed(cut):
        top = top[:a] + top[b:]
    return [("(최상위)", top)] + out


_THUMB_SIZE = re.compile(r"(width|height)\s*:\s*([0-9.]+px)", re.I)


def _thumb_sizes(body: str, pseudo: str) -> dict[str, dict[str, str]]:
    """{선택자(의사요소 제외): {width/height: 값}} — 크기를 «정하는» 규칙만."""
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"([^{}]*" + re.escape(pseudo) + r"[^{}]*)\{([^{}]*)\}", body):
        sel, decls = m.group(1).strip(), m.group(2)
        if ":focus" in sel:            # 링 규칙은 크기 축이 아니다 — 위 시험이 맡는다
            continue
        sizes = {k.lower(): v for k, v in _THUMB_SIZE.findall(decls)}
        if sizes:
            out[sel.replace(pseudo, "").strip()] = sizes
    return out


@pytest.mark.parametrize("rel", _RANGE_SLIDER_TEMPLATES)
def test_thumb_size_is_declared_for_both_engines_in_every_context(rel):
    """🔴 손잡이 «크기» 도 두 엔진에 다 적는다 — 링만이 아니다.

    Gecko 는 `::-webkit-slider-thumb` 를 통째로 무시한다. 기본 규칙은 두 벌로 적혀
    있었는데 **모바일 확대만 webkit 한 벌**이었다:

        repo_detail @768   webkit 16 -> 24 · moz 는 16 그대로
        settings    @480   webkit 18 -> 24 · moz 는 18 그대로

    즉 Firefox 모바일에서만 손잡이가 작았다. 데스크톱(1440px)에서도, Chromium 에서도
    보이지 않는다 — 두 조건이 겹쳐야 드러나는 자리라 여태 아무도 재지 않았다.

    🔴 문맥별로 판정하는 이유를 «실측대로» 적는다 — 처음 쓴 사유는 틀렸다.
    위 두 사례는 문맥을 합쳐 세도 잡힌다(선택자가 같아 mobile 값이 base 를 덮고, moz 와
    값이 어긋나 red 가 된다 — 심어서 확인). 문맥 분리가 실제로 필요한 것은 **모바일 값이
    base 의 moz 값과 겹치는** 경우다: base 를 24/24 로 두고 모바일 moz 만 없애면
    분리판은 red, 합침판은 **green** 이었다. 그 자리가 이 가드의 존재 이유다.

    🔴 한 선택자 목록에 두 의사요소를 합쳐 적으면 «두 엔진 다» 규칙을 버린다 — 그래서
    합침을 처방으로 제안하지 않는다.

    Size parity, per media context: Gecko ignores the webkit pseudo entirely.
    """
    src = strip_css_comments(read(rel))
    checked, offenders = 0, []
    for name, body in _contexts(src):
        webkit = _thumb_sizes(body, "::-webkit-slider-thumb")
        moz = _thumb_sizes(body, "::-moz-range-thumb")
        for sel, sizes in webkit.items():
            checked += 1
            if sel not in moz:
                offenders.append(f"{rel} {name}: `{sel}` 이 webkit 만 크기를 정한다 "
                                 f"({sizes}) — Gecko 에는 안 닿는다")
            elif moz[sel] != sizes:
                offenders.append(f"{rel} {name}: `{sel}` 크기가 엔진마다 다르다 "
                                 f"webkit={sizes} moz={moz[sel]}")
    assert checked, f"{rel}: 크기를 정하는 webkit 손잡이 규칙을 0개 찾았다 — 판정이 공허하다"
    assert not offenders, "손잡이 크기가 한 엔진에만 적용된다:\n  " + "\n  ".join(offenders)


def test_focus_ring_token_is_defined_in_every_theme():
    """네 테마 전부에 정의돼야 한다 — 한 테마만 빠지면 그 테마에서 링이 사라진다."""
    src = read("src/static/css/tokens.css")
    for theme in THEMES:
        decl(theme_block(src, theme), "--focus-ring")
    assert (ROOT / "src/static/css/tokens.css").exists()
