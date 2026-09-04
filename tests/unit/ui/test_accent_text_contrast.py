"""UI 감사 후속 — accent 색을 «글자» 로 쓰는 곳, 그리고 accent 면 «위» 의 글자.

#1609 는 `.btn-primary` 하나에 대해 「면이 아니라 글자를 바꾼다」를 세웠다. 같은 부류가
다섯 군데 더 남아 있었고, 그 «역방향» — accent 를 글자색으로 쓰는 경우 — 은 토큰이 아예
없었다. `--accent-text-on`(accent 면 위의 글자)의 짝으로 `--accent-text`(바탕 위의 accent
글자)를 둔다.

실측(수정 전, 실제 브라우저): accent 를 글자로 쓰는 29건이 light·pastel 에서 2.07~3.94.
accent 면 위 흰 글자는 catppuccin 1.79 까지 내려갔다.

행동 판정은 e2e 가 «칠해진 색» 으로 한다. 여기 있는 것은 그 수정이 되돌려졌는지를 단위
수준에서 잡는 가드다.
"""
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[3]

_AA = 4.5
_THEMES = ("dark", "light", "pastel", "catppuccin")

# accent 글자가 앉는 바탕. 페이지 바탕 + 이 부류가 실제로 얹히는 옅은 칩 면들.
_ACCENT_TEXT_GROUNDS = ("--bg-base", "--bg-canvas", "--bg-card", "--bg-elevated")


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _strip_css_comments(src: str) -> str:
    """판정 전에 주석을 지운다 — 주석이 규칙을 인용하면 가드가 산문을 통과시킨다."""
    return re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)


def _rule_blocks(src: str, selector: str) -> list[str]:
    """`<selector> {` 의 선언부 **전부**. 주석은 미리 지운다.

    🔴 두 가지를 지킨다.
    1. 선택자 앞 경계를 요구한다 — `find("a {")` 는 `.grade--a {` 안에서도 맞아
       엉뚱한 규칙을 돌려준다(실측: 본문 링크 대신 등급 뱃지 규칙이 잡혔다).
    2. **첫 규칙만 보지 않는다** — 같은 선택자가 미디어 쿼리에도 있고, 거기서는
       `display: none` 만 쓴다(실측: `.nav-badge`). 첫 규칙만 보면 색을 정하는 규칙을
       영영 못 본다.
    """
    clean = _strip_css_comments(src)
    out = []
    for m in re.finditer(rf"(?:^|[}}\n;>,])\s*{re.escape(selector)}\s*\{{", clean, re.MULTILINE):
        j = clean.find("}", m.end())
        assert j > m.end(), f"`{selector}` 블록이 닫히지 않는다"
        out.append(clean[m.end():j])
    assert out, f"`{selector}` 규칙 부재 — 테스트가 늙었다"
    return out


def _declaring_block(src: str, selector: str, prop: str) -> str:
    """그 선택자의 규칙 중 `prop` 을 «정하는» 것. 없으면 red."""
    blocks = [b for b in _rule_blocks(src, selector) if f"{prop}:" in b]
    assert blocks, (
        f"`{selector}` 규칙 {len(_rule_blocks(src, selector))}건 중 `{prop}` 을 정하는 것이 "
        "하나도 없다 — 재지 못한 것이지 통과한 것이 아니다"
    )
    assert len(blocks) == 1, (
        f"`{selector}` 에 `{prop}` 을 정하는 규칙이 {len(blocks)}건이다 — "
        "어느 것이 이기는지 이 테스트는 판정하지 못한다"
    )
    return blocks[0]


def _theme_block(src: str, theme: str) -> str:
    """그 테마의 «모든» `[data-theme]` 블록을 이어 붙인다.

    🔴 이 파일은 테마당 블록이 둘이다 — 팔레트(원색)와 의미 토큰(`--hook-btn-tx` 등).
    첫 블록만 보면 의미 토큰을 「미정의」로 읽는다(실측: `--hook-btn-tx`).
    Each theme has two blocks here: raw palette, then semantic tokens.
    """
    src = _strip_css_comments(src)
    blocks, start = [], 0
    anchor = f'[data-theme="{theme}"] {{'
    while (i := src.find(anchor, start)) >= 0:
        j = src.find("\n}", i)
        assert j > i, f"{theme} 블록이 닫히지 않는다"
        blocks.append(src[i:j])
        start = j
    assert blocks, f"{theme} 블록 부재 — 테스트가 늙었다"
    return "\n".join(blocks)


def _decl(block: str, name: str) -> str:
    """마지막 정의를 돌려준다 — CSS 는 뒤에 오는 선언이 이긴다."""
    ms = re.findall(rf"{re.escape(name)}\s*:\s*([^;]+);", block)
    assert ms, f"{name} 미정의 — 못 재면 초록이 아니라 red 다"
    return ms[-1].strip()


def _resolve(block: str, value: str, depth: int = 0) -> str:
    """`var(--x)` 를 같은 테마 블록 안에서 한 단계씩 푼다."""
    assert depth < 8, f"토큰 참조가 순환한다: {value}"
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*\)", value.strip())
    if m:
        return _resolve(block, _decl(block, m.group(1)), depth + 1)
    return value.strip()


def _parse_color(value: str) -> tuple[float, float, float, float]:
    value = value.split("/*")[0].strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(([^)]+)\)", value)
    if m:
        nums = [float(p.strip().rstrip("%"))
                for p in m.group(1).replace("/", ",").split(",") if p.strip()]
        return (nums[0], nums[1], nums[2], nums[3] if len(nums) > 3 else 1.0)
    raise AssertionError(f"이 계기가 읽지 못하는 색 형식이다: {value!r} — 초록으로 넘기지 않는다")


def _over(fg: tuple, bg: tuple) -> tuple:
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def _luminance(c: tuple) -> float:
    def lin(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def _ratio(a: tuple, b: tuple) -> float:
    la, lb = _luminance(a), _luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _grounds(block: str) -> dict[str, tuple]:
    base = _parse_color(_resolve(block, _decl(block, "--bg-base")))
    canvas = _parse_color(_resolve(block, _decl(block, "--bg-canvas")))
    out: dict[str, tuple] = {}
    for name in _ACCENT_TEXT_GROUNDS:
        c = _parse_color(_resolve(block, _decl(block, name)))
        out[name] = c if c[3] >= 1.0 else _over(c, canvas if "card" in name else base)
    return out


def test_accent_text_token_is_defined_in_every_theme():
    """🔴 `--accent-text` 는 네 테마 «전부» 에 있어야 한다.

    한 테마라도 빠지면 `var(--accent-text)` 가 invalid 로 떨어져 그 테마에서 링크·뱃지 색이
    상속색으로 무너진다 — cleanup PR #169 이 catppuccin 에서 실제로 겪은 사고다.
    """
    src = _read("src/static/css/tokens.css")
    for theme in _THEMES:
        block = _theme_block(src, theme)
        assert _decl(block, "--accent-text"), f"[{theme}] --accent-text 미정의"


def test_accent_used_as_text_meets_aa_on_every_ground():
    """🔴 `--accent-text` 는 글자가 앉는 바탕에서 AA 를 넘어야 한다.

    실측(수정 전, `--accent` 를 그대로 글자로 쓸 때): light 3.86 · pastel 2.43 이 최악이었다.
    dark·catppuccin 은 accent 가 어두운 바탕 위라 이미 통과한다(5.29 · 6.19).
    🔴 accent «면» 색(`--accent-1`)은 건드리지 않는다 — 글자 전용 색을 따로 둔다.
    """
    src = _read("src/static/css/tokens.css")
    failures = []
    for theme in _THEMES:
        block = _theme_block(src, theme)
        fg = _parse_color(_resolve(block, _decl(block, "--accent-text")))
        for name, bg in _grounds(block).items():
            r = _ratio(_over(fg, bg), bg)
            if r < _AA:
                failures.append(f"[{theme}] --accent-text on {name}: {r:.2f} < {_AA}")
    assert not failures, "accent 글자색이 AA 미달인 조합:\n  " + "\n  ".join(failures)


def test_brand_accent_surface_is_unchanged():
    """🔴 이 PR 은 accent «면» 색을 바꾸지 않는다 — 글자만 바꾼다(#1609 가 세운 선례).

    `--accent-text` 를 도입하면서 브랜드 색을 슬쩍 옮기는 것을 막는다. 값이 바뀌어야 할
    이유가 생기면 이 테스트를 «의도적으로» 고쳐야 한다.
    """
    expected = {"dark": "#7c7aff", "light": "#5b5ef0",
                "pastel": "#8c82d2", "catppuccin": "#cba6f7"}
    src = _read("src/static/css/tokens.css")
    for theme, want in expected.items():
        got = _decl(_theme_block(src, theme), "--accent-1").split()[0].lower()
        assert got == want, (
            f"[{theme}] --accent-1 이 {want} 에서 {got} 로 바뀌었다 — "
            "브랜드 면색 변경은 이 PR 의 범위가 아니다"
        )


def test_text_on_flat_accent_surface_uses_the_on_accent_token():
    """🔴 채워진 accent 면 위의 글자는 하드코딩이 아니라 `--accent-text-on` 을 쓴다.

    실측(흰 글자 기준): `.mode-toggle-btn.active` dark 3.45 · pastel 3.37 ·
    catppuccin 2.03. 토큰으로 바꾸면 5.61 · 5.59 · 8.07 (light 는 4.88 로 원래 통과).
    #1609 가 `.btn-primary` 에 적용한 것과 «같은» 처방이다.
    """
    src = _read("src/templates/settings.html")
    block = _declaring_block(src, ".mode-toggle-btn.active", "color")
    assert "var(--accent-text-on" in block, (
        "`.mode-toggle-btn.active` 라벨 색이 토큰이 아니다 — accent 면 위 대비가 무력화된다"
    )
    for literal in ("color: white", "color:#fff", "color: #fff"):
        assert literal not in block, (
            f"`.mode-toggle-btn.active` 에 {literal!r} 이 하드코딩됐다"
        )


def test_no_hardcoded_white_on_accent_surfaces():
    """🔴 accent 면(단색·그라디언트)을 칠하는 규칙에 흰 글자를 하드코딩하지 않는다.

    실측: `.nav-avatar`·`.step-card__num` 은 accent 그라디언트 위 흰 글자로
    catppuccin 1.79 · pastel 2.32 · dark 2.65 였다.

    🔴 light 는 이 수정으로도 4.23 에 머문다 — 그 테마의 `--accent-text-on` 이 흰색이고,
    `--accent-2`(#8b5cf6) 위에서는 «어떤 글자색도» AA 에 도달하지 못한다(흰색 4.23 이 상한,
    더 어둡게 하면 가까운 stop 에서 무너진다). 면을 옮겨야 풀리므로 이 PR 범위 밖이다.
    """
    targets = [
        ("src/templates/base.html", ".nav-avatar"),
        ("src/templates/add_repo.html", ".step-card__num"),
    ]
    for rel, selector in targets:
        block = _declaring_block(_read(rel), selector, "color")
        surface = " ".join(_rule_blocks(_read(rel), selector))
        assert "var(--accent" in surface, f"[{rel}] `{selector}` 가 accent 면이 아니다 — 테스트 stale"
        for literal in ("#fff", "#ffffff", "color: white"):
            assert literal not in block, (
                f"[{rel}] `{selector}` 에 {literal!r} 이 하드코딩됐다 — "
                "테마별 on-accent 글자색이 무력화된다"
            )
        assert "var(--accent-text-on" in block, (
            f"[{rel}] `{selector}` 의 글자색이 `--accent-text-on` 이 아니다"
        )


def test_accent_as_text_consumers_route_through_the_token():
    """🔴 accent 를 글자색으로 쓰던 자리는 `--accent-text` 를 지난다.

    바꾸지 않으면 토큰만 생기고 화면은 그대로다 — 「쓰기만 넓히고 읽는 쪽은 그대로」.
    """
    checks = [
        ("src/templates/base.html", "a", "본문 링크"),
        ("src/templates/base.html", ".nav-badge", "nav 뱃지"),
        ("src/templates/base.html", "code", "인라인 코드"),
        ("src/static/css/repo_insights.css", ".ri-day-btn.active", "기간 선택 활성"),
    ]
    for rel, selector, label in checks:
        block = _declaring_block(_read(rel), selector, "color")
        assert "var(--accent-text)" in block, (
            f"[{rel}] {label}(`{selector}`)이 `--accent-text` 를 쓰지 않는다 — "
            "토큰만 만들고 배선하지 않으면 화면은 그대로다"
        )

    # `.hook-btn` 은 자기 토큰을 지난다. 🔴 밝은 두 테마만 옮긴다 — dark·catppuccin 에서
    # `--accent-2` 는 어두운 바탕 위라 원래 통과하고, 거기까지 바꾸면 «고칠 것이 없는
    # 테마의 색상만» 달라진다(dark #b289ff → #7c7aff · catppuccin lavender → mauve).
    src = _read("src/static/css/tokens.css")
    expected = {"light": "var(--accent-text)", "pastel": "var(--accent-text)",
                "dark": "var(--accent-2)", "catppuccin": "var(--accent-2)"}
    for theme, want in expected.items():
        got = _decl(_theme_block(src, theme), "--hook-btn-tx")
        assert got == want, (
            f"[{theme}] --hook-btn-tx 가 {want} 가 아니라 {got} 다 — "
            "밝은 테마만 글자 전용 색으로 옮긴다(실측 pastel 2.07 · light 3.84)"
        )
