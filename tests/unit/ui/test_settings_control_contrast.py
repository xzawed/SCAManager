"""설정 화면 컨트롤 글자의 AA — 토큰 감사가 «보지 못하는» 두 자리.

## 왜 여기 있나

e2e 대비 감사는 «세 토큰(`--text-2`·`--text-3`·`--accent-text`)과 같은 색» 인 글자만
고른다(#1639 S6). 아래 두 자리는 그 셋 중 어디에도 해당하지 않아 **e2e 로는 red 를
만들 수 없다** — 그래서 정적으로 잰다.

## 실측 (2026-09-09, 400조합 픽셀 측정)

| 자리 | 원인 | 현재 | 처방 후 |
|---|---|---|---|
| `.gate-mode-btn.active` | `--btn-gate-active-tx` 가 틴트 면에 비해 옅다 | pastel **2.93** · light 4.28 | pastel 5.48 · light 5.02 |
| `.mode-toggle-hint` | `opacity: 0.85` 가 accent 면 위 흰 글자를 흐린다 | light **4.00** | 4.88 |

🔴 `.mode-toggle-hint` 는 **색이 아니라 투명도** 가 원인이다. 색만 보는 검사로는 안 잡힌다 —
이 리포는 조상 `opacity` 를 무시해 「실제보다 진하게」 재던 전례가 있다.
"""
from __future__ import annotations

import re

from ._contrast import (AA, ROOT, THEMES, decl, over, parse_color, ratio, resolve,
                        strip_css_comments, theme_block)

_TOKENS = (ROOT / "src" / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
_SETTINGS = (ROOT / "src" / "templates" / "settings.html").read_text(encoding="utf-8")

# `.gate-mode-btn.active` 의 면 — `rgba(99,102,241,.15)` 를 `--bg-input` 위에 올린 값.
_GATE_TINT = (99.0, 102.0, 241.0, 0.15)


def _token(theme: str, name: str) -> tuple:
    """테마의 토큰을 해석해 RGBA 로."""
    block = theme_block(_TOKENS, theme)
    value = resolve(block, decl(block, name))
    assert value, f"{theme} 에서 `{name}` 을 해석하지 못했다 — 토큰이 사라졌거나 이름이 바뀌었다"
    return parse_color(value)


def _rule(selector: str) -> str:
    """`settings.html` 에서 그 셀렉터의 선언부 — 없으면 fail-fast(시험이 늙은 것)."""
    src = strip_css_comments(_SETTINGS)
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", src)
    assert m, f"`{selector}` 규칙이 없다 — 시험이 늙었다(셀렉터가 바뀌었나)"
    return m.group(1)


def test_active_gate_mode_button_text_meets_aa_on_its_tint():
    """🔴 활성 게이트 버튼 글자가 자기 틴트 면 위에서 AA 를 넘어야 한다.

    실측(수정 전): pastel **2.93** — 네 테마 중 이 화면 최악이었다.
    e2e 감사는 이 색을 세 토큰 어디로도 분류하지 못해 관측조차 하지 않았다.
    """
    # 🔴 토큰 이름을 박아두지 «않는다». 규칙이 실제로 쓰는 색을 읽어야, 색을 바꾼 수정이
    #    이 시험에 반영된다 — 첫 판은 `--btn-gate-active-tx` 를 직접 읽어서, 규칙을 고쳐도
    #    계속 red 였다(고친 것을 못 보는 시험).
    m = re.search(r"(?<![-\w])color\s*:\s*([^;]+);", _rule(".gate-mode-btn.active"))
    assert m, "`.gate-mode-btn.active` 에 `color` 선언이 없다 — 시험이 늙었다"
    declared = m.group(1).strip()

    bad = []
    for theme in THEMES:
        surface = over(_GATE_TINT, _token(theme, "--bg-input"))
        block = theme_block(_TOKENS, theme)
        fg = parse_color(resolve(block, declared))
        got = ratio(over(fg, surface), surface)
        if got < AA:
            bad.append(f"{theme}: {got:.2f} < {AA} (color: {declared})")
    assert not bad, (
        "활성 게이트 버튼 글자가 틴트 면에서 AA 미달이다 — "
        "`--accent-text` 처럼 «글자용» accent 를 쓴다:\n  " + "\n  ".join(bad))


def test_the_gate_tint_is_still_what_this_test_assumes():
    """🔴 계기 자기검증 — 면이 바뀌면 위 계산은 «다른 화면» 을 재게 된다."""
    block = _rule(".gate-mode-btn.active")
    assert "rgba(99,102,241,.15)" in block.replace(" ", ""), (
        f"`.gate-mode-btn.active` 의 면이 바뀌었다 — 이 시험의 가정({_GATE_TINT})을 갱신하라:\n"
        f"{block.strip()[:160]}")


def test_mode_toggle_hint_is_not_dimmed_by_opacity():
    """🔴 accent 면 위 흰 글자를 `opacity` 로 흐리면 AA 가 깨진다.

    실측: `opacity: 0.85` 로 light **4.00**, 제거하면 4.88. 색은 그대로다 —
    원인이 투명도라 «색만 보는» 검사로는 잡히지 않는다.
    """
    block = _rule(".mode-toggle-hint")
    m = re.search(r"(?<![-\w])opacity\s*:\s*([0-9.]+)", block)
    got = float(m.group(1)) if m else 1.0
    assert got >= 0.995, (
        f"`.mode-toggle-hint` 가 `opacity: {got}` 로 흐려져 있다 — accent 면 위 흰 글자가 "
        f"AA 미달(실측 4.00)이 된다. 흐리려면 색 토큰으로 하고 대비를 함께 재라")


# ── 브랜드 «면» 위의 글자 — 그라디언트 헤더 · danger 채움 ─────────────────────
#
# 🔴 여기는 글자 토큰이 이미 «면 위 전용» 이라 색을 더 바꿀 여지가 없다. 미달이면
#    **면 자체** 를 움직여야 한다. 그래서 이 시험은 면(그라디언트 stop·danger 값)을 잰다.
#    사용자 결정(2026-09-09): 색조·채도는 유지하고 «명도만» 최소 폭으로 조정한다.

def header_surfaces() -> dict[str, str]:
    """{어디: background 선언} — 카드 «헤더» 면을 템플릿에서 파생한다.

    🔴 첫 판은 `--grad-*` 토큰 4개를 손으로 적었다. 그런데 헤더 면은 거기 없는 것이 더
    있었다 — `.hdr-preset` 은 `--accent`/`--accent-2` 를 직접 쓰고, 위험 구역 헤더는
    **인라인 style** 로 danger 그라디언트를 깐다. 둘 다 목록 밖이라 관측되지 않았고,
    실제로 light 4.23 · pastel 3.98 로 미달이었다. 목록이 아니라 «헤더를 찾는다».
    """
    src = strip_css_comments(_SETTINGS)
    out: dict[str, str] = {}
    # (a) 헤더 «컨테이너» 규칙의 background.
    #     🔴 자손 규칙은 헤더 면이 아니다 — `.s-card-hdr .hdr-badge` 는 헤더 «위의 칩» 이라
    #     자기 틴트를 자기 글자색과 견주게 되어 늘 1.00 이 나왔다(거짓 미달).
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", src):
        sel, body = " ".join(m.group(1).split()), m.group(2)
        parts = [t for chunk in sel.split(",") for t in chunk.split()]
        last = parts[-1] if parts else ""
        # 🔴 «자손» 규칙은 헤더 면이 아니다. `.s-card-hdr .hdr-badge` 는 헤더 위의
        #    칩이라 자기 틴트를 자기 글자색과 견주게 되어 늘 1.0x 가 나왔다(거짓 미달).
        if len(parts) > 1 and last != ".s-card-hdr":
            continue
        if not (last == ".s-card-hdr" or last.startswith(".hdr-")):
            continue
        bm = re.search(r"(?<![-\w])background\s*:\s*([^;]+);?", body)
        if bm:
            out[sel] = bm.group(1).strip()
    # (b) 헤더 요소의 «인라인» style
    for m in re.finditer(r"class=\"[^\"]*s-card-hdr[^\"]*\"[^>]*style=\"([^\"]*)\"", src):
        bm = re.search(r"(?<![-\w])background\s*:\s*([^;\"]+)", m.group(1))
        if not bm:
            continue
        decl_text = bm.group(1).strip()
        # 🔴 위험 구역 헤더는 «정적으로 못 모형화» 한다 — 인라인 `color-mix` 로 어둡게 섞은
        #    그라디언트라, 여기서 계산한 값이 픽셀 실측과 어긋났다(정적은 dark/catppuccin
        #    미달이라 했는데 실측 400조합은 pastel 만 잡았다). 틀린 모형으로 red 를 내면
        #    다음 사람이 가드를 끄게 된다. 이 면은 **픽셀 스윕이 맡는다**.
        if "color-mix" in decl_text and "--danger" in decl_text:
            continue
        out[f"inline:{decl_text[:40]}"] = decl_text
    return out


def _stops_of(theme: str, declaration: str) -> list[tuple]:
    """background 선언을 테마에서 해석해 색 stop 전부."""
    block = theme_block(_TOKENS, theme)
    value = declaration
    for _ in range(6):                       # 중첩 var() 를 반복 해석
        nxt = re.sub(r"var\(\s*(--[\w-]+)[^)]*\)",
                     lambda mm: (resolve(block, decl(block, mm.group(1))) or mm.group(0)), value)
        if nxt == value:
            break
        value = nxt
    # 🔴 `color-mix(in srgb, A P%, B)` 를 «먼저» 계산한다. 안 하면 그 인자들이 각각
    #    독립 stop 으로 세어져, 위험 구역 헤더의 `#000`(어둡게 섞는 재료)이 «면» 으로
    #    잡혀 1.09 같은 거짓 미달이 나왔다.
    for _ in range(4):
        mm = re.search(r"color-mix\(\s*in\s+srgb\s*,\s*([^,]+?)\s+([\d.]+)%\s*,\s*([^)]+?)\s*\)", value)
        if not mm:
            break
        a, pct, b = parse_color(mm.group(1)), float(mm.group(2)) / 100.0, mm.group(3).strip()
        bb = (0.0, 0.0, 0.0, 0.0) if b == "transparent" else parse_color(b)
        mixed = tuple(a[i] * pct + bb[i] * (1 - pct) for i in range(4))
        value = value[:mm.start()] + f"rgba({mixed[0]:.1f},{mixed[1]:.1f},{mixed[2]:.1f},{mixed[3]:.3f})" + value[mm.end():]
    stops = re.findall(r"#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)", value)
    return [parse_color(s) for s in stops]


def test_card_header_text_meets_aa_on_every_gradient_stop():
    """🔴 헤더 글자는 그라디언트의 «모든 지점» 에서 AA 를 넘어야 한다.

    한쪽 끝만 재면 반대쪽에서 미달인 채로 통과한다. 실측(수정 전):
    light `--grad-merge`/`--grad-hook`, pastel `--grad-gate`/`--grad-merge` 의
    **두 번째 stop** 이 4.10~4.44 였다 — 첫 stop 만 봤다면 전부 초록이었다.
    """
    surfaces = header_surfaces()
    assert surfaces, "헤더 면을 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    bad = []
    for theme in THEMES:
        for where, decl_text in sorted(surfaces.items()):
            # danger 헤더는 danger 전용 글자 토큰을 쓴다 — 어느 on-토큰인지 선언에서 읽는다.
            on_name = "--danger-text-on" if "--danger" in decl_text else "--btn-on-accent"
            on = _token(theme, on_name)
            stops = _stops_of(theme, decl_text)
            if not stops:
                bad.append(f"{theme} {where}: 색 stop 을 못 읽었다(해석 실패)")
                continue
            for i, stop in enumerate(stops):
                got = ratio(over(on, stop), stop)
                if got < AA:
                    bad.append(f"{theme} {where} stop{i}: {got:.2f} < {AA} ({on_name})")
    assert not bad, (
        "카드 헤더 글자가 그라디언트 위에서 AA 미달이다 — 색조는 두고 «명도» 를 옮긴다:\n  "
        + "\n  ".join(bad))


def test_danger_works_both_as_text_and_as_a_filled_surface():
    """🔴 `--danger` 는 «카드 위 글자» 와 «버튼 면» 양쪽에 쓰인다 — 요구가 반대다.

    글자로 쓰려면 진해야 하고, 어두운 글자를 얹는 면으로 쓰려면 밝아야 한다.
    실측(수정 전, pastel): 글자 4.23 · 면+어두운 글자 4.28 — 양쪽 다 미달이었다.
    그래서 면 위 글자색을 «danger 전용 토큰» 으로 분리하고 danger 값을 한 단계 낮췄다.
    """
    bad = []
    for theme in THEMES:
        block = theme_block(_TOKENS, theme)
        danger = parse_color(resolve(block, decl(block, "--danger")))
        card = parse_color(resolve(block, decl(block, "--bg-card")))
        on_danger = decl(block, "--danger-text-on")
        assert on_danger, (
            f"{theme} 에 `--danger-text-on` 이 없다 — danger 면 위 글자색은 accent 용 "
            "토큰을 빌려 쓰면 안 된다(면이 서로 다른 색이다)")
        on = parse_color(resolve(block, on_danger))
        as_text = ratio(over(danger, card), card)
        on_fill = ratio(over(on, danger), danger)
        if as_text < AA:
            bad.append(f"{theme} danger-as-text: {as_text:.2f} < {AA}")
        if on_fill < AA:
            bad.append(f"{theme} text-on-danger: {on_fill:.2f} < {AA}")
    assert not bad, "danger 계열이 AA 미달이다:\n  " + "\n  ".join(bad)


def test_the_delete_button_uses_the_danger_text_token():
    """🔴 danger 면 위에 «accent» 용 on-토큰을 쓰면 테마마다 우연히 맞거나 틀린다.

    실측: pastel 에서 `--btn-on-accent`(어두움)를 danger 면에 얹어 4.28 이었다.
    """
    # 🔴 `background:var(--danger)` 로만 찾으면 슬라이더 CSS 규칙을 먼저 잡아 오판한다.
    #    그리고 «설정 파일 하나» 만 보면 안 된다 — 같은 형태가 다른 템플릿에도 있었다.
    #    `add_repo.html` 의 토스트가 danger 면에 accent 용 on-토큰을 얹고 있었는데
    #    첫 판은 `settings.html` 만 훑어 그것을 놓쳤다(Grok 반증 `01a0861a`).
    bad = []
    for path in sorted((ROOT / "src" / "templates").rglob("*.html")):
        src = strip_css_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"background:\s*var\(--danger[^;]*;[^}\"]*", src):
            chunk = m.group(0)
            cm = re.search(r"(?<![-\w])color\s*:\s*([^;}\"]+)", chunk)
            if not cm:
                continue          # 면만 칠하고 글자를 얹지 않는 자리(슬라이더 손잡이 등)
            value = cm.group(1).strip()
            if "--danger-text-on" in value or re.fullmatch(r"#fff(fff)?|white", value):
                continue          # 전용 토큰이거나, 네 테마에서 검증된 흰 글자
            bad.append(f"{path.name}: color:{value}")
    assert not bad, (
        "danger 면 위 글자가 danger 전용 토큰을 쓰지 않는다 — accent 용 on-토큰은 "
        "면이 달라 테마마다 우연히 맞거나 틀린다:\n  " + "\n  ".join(bad))
