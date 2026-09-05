"""UI 감사 후속 — 보조·3차 글자색이 «칠해지는 바탕» 에서 AA 를 넘는지 정적으로 잰다.

#1609 가 미룬 일이다: `.kpi__delta--flat` 하나를 고치려면 `--text-3` 토큰을 올려야 하고,
그러면 모든 화면의 보조 문구가 함께 바뀐다. 그 토큰 작업이 여기 있다.

실측(수정 전, 실제 브라우저 10화면 x 4테마): `--text-3` 을 쓰는 글자 59건 중
dark·light·pastel 은 **59건 전부**, catppuccin 은 48건이 4.5:1 미달이었다(최저 2.40).

행동 판정은 e2e(`e2e/test_theme_mobile_guards.py`)가 실제로 칠해진 색으로 한다.
여기 있는 것은 그 수정이 되돌려졌는지를 단위 수준에서 잡는 가드다 — e2e 를 돌리지 않는
경로(역-뮤테이션 게이트 포함)에서도 회귀가 red 가 된다.

Behavioral judgment lives in e2e (real browser, painted color). These are the fast static
guards that catch a revert where e2e is not run.
"""
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[3]

# WCAG 2.1 SC 1.4.3 — 본문 크기 글자. `--text-2`·`--text-3` 은 10~13px 에만 쓰인다.
_AA = 4.5

# 「글자가 실제로 앉는 바탕」. 칩·인셋 표면(`--bg-mute`·`--bg-input`·`--bg-card-hi`)은
# 제외한다 — 그 위에 3차 글자를 얹지 않는 것이 이 PR 이 세운 규칙이고,
# `test_faint_text_is_not_painted_on_chip_surfaces` 가 그것을 따로 지킨다.
_GROUNDS = ("--bg-base", "--bg-canvas", "--bg-card", "--bg-nav", "--bg-elevated")

_THEMES = ("dark", "light", "pastel", "catppuccin")


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _strip_css_comments(src: str) -> str:
    """🔴 판정 전에 주석을 지운다 — 주석이 규칙을 흉내 내면 가드가 산문을 통과시킨다.

    실측: 이 PR 이 `.tbl th` 에 붙인 설명 주석이 «`table thead tr th { color: var(--text-2) }`»
    를 인용하고 있어, 규칙 블록을 `}` 로 자르던 첫 판이 **주석 안에서 잘렸고**
    선언을 3차 색으로 되돌리는 뮤테이션이 초록으로 통과했다.
    A comment quoting a CSS rule made the block scan terminate inside the comment, so the
    guard matched the prose instead of the declaration.
    """
    return re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)


def _rule_block(src: str, selector: str) -> str:
    """`<selector> {` 의 선언부. 주석은 미리 지운 뒤 찾는다."""
    clean = _strip_css_comments(src)
    i = clean.find(selector + " {")
    assert i >= 0, f"`{selector}` 규칙 부재 — 테스트가 늙었다"
    j = clean.find("}", i)
    assert j > i, f"`{selector}` 블록이 닫히지 않는다"
    return clean[i:j]


def _theme_block(src: str, theme: str) -> str:
    """`[data-theme="<theme>"] {` 팔레트 블록 본문. 여러 개면 첫 블록(팔레트).

    주석은 먼저 지운다 — 이 파일의 설명 주석이 토큰 이름을 인용한다.
    """
    src = _strip_css_comments(src)
    i = src.find(f'[data-theme="{theme}"] {{')
    assert i >= 0, f"{theme} 팔레트 블록 부재 — 테스트가 늙었다"
    j = src.find("\n}", i)
    assert j > i, f"{theme} 블록이 닫히지 않는다"
    return src[i:j]


def _decl(block: str, name: str) -> str:
    m = re.search(rf"{re.escape(name)}\s*:\s*([^;]+);", block)
    assert m, f"{name} 미정의 — 못 재면 초록이 아니라 red 다"
    return m.group(1).strip()


def _parse_color(value: str) -> tuple[float, float, float, float]:
    """#rgb / #rrggbb / rgba(r,g,b,a) → (r, g, b, alpha). 그 외는 못 잰다고 실패."""
    value = value.split("/*")[0].strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(([^)]+)\)", value)
    if m:
        parts = [p.strip() for p in m.group(1).replace("/", ",").split(",") if p.strip()]
        nums = [float(p.rstrip("%")) for p in parts]
        alpha = nums[3] if len(nums) > 3 else 1.0
        return (nums[0], nums[1], nums[2], alpha)
    raise AssertionError(f"이 계기가 읽지 못하는 색 형식이다: {value!r} — 초록으로 넘기지 않는다")


def _over(fg: tuple, bg: tuple) -> tuple:
    """알파 합성 — fg 를 불투명 bg 위에 얹은 «칠해지는» 색."""
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
    """테마의 글자 바탕들을 «칠해지는» 불투명색으로. 알파 표면은 그 테마 위에 합성한다."""
    base = _parse_color(_decl(block, "--bg-base"))
    canvas = _parse_color(_decl(block, "--bg-canvas"))
    out: dict[str, tuple] = {}
    for name in _GROUNDS:
        c = _parse_color(_decl(block, name))
        if c[3] >= 1.0:
            out[name] = c
        else:
            # 카드는 캔버스 위에, nav 는 페이지 바탕 위에 얹힌다.
            out[name] = _over(c, canvas if name == "--bg-card" else base)
    return out


def _extra_grounds(theme: str) -> dict[str, tuple]:
    """토큰 밖의 바탕 — pastel 은 body 가 그라디언트라 stop 전부가 글자 바탕이다.

    실측에서 이 테마의 최악 표면(2.40)이 바로 이 그라디언트의 어두운 stop 이었다.
    """
    if theme != "pastel":
        return {}
    src = _strip_css_comments(_read("src/templates/base.html"))
    i = src.find('body[data-theme="pastel"]')
    assert i >= 0, "pastel body 규칙 부재 — 테스트가 늙었다"
    block = src[i:src.find("}", i)]
    stops = re.findall(r"#[0-9a-fA-F]{6}", block)
    assert stops, "pastel body 그라디언트 stop 을 못 읽었다 — 못 재면 red"
    return {f"body-gradient-stop-{n}": _parse_color(s) for n, s in enumerate(stops)}


def test_faint_text_token_meets_aa_on_every_ground():
    """🔴 `--text-3` 은 글자가 앉는 모든 바탕에서 AA(4.5:1)를 넘어야 한다.

    실측(수정 전): dark 3.56~3.92 · light 3.11~3.38 · pastel 2.40~2.88 ·
    catppuccin 3.40~4.75 — 네 테마 전부 미달이었다. 이것이 #1609 가 미룬 결함이다.
    """
    src = _read("src/static/css/tokens.css")
    failures = []
    for theme in _THEMES:
        block = _theme_block(src, theme)
        fg = _parse_color(_decl(block, "--text-3"))
        grounds = {**_grounds(block), **_extra_grounds(theme)}
        assert grounds, f"{theme} 바탕을 하나도 못 읽었다"
        for name, bg in grounds.items():
            r = _ratio(_over(fg, bg), bg)
            if r < _AA:
                failures.append(f"[{theme}] --text-3 on {name}: {r:.2f} < {_AA}")
    assert not failures, "3차 글자색이 AA 미달인 조합:\n  " + "\n  ".join(failures)


def test_secondary_text_token_meets_aa_on_every_ground():
    """`--text-2` 도 같은 바탕들에서 AA 를 넘어야 한다.

    수정 전에도 대체로 통과했으나, `--text-3` 을 올리면서 pastel 의 `--text-2` 를
    함께 옮겼다(아래 계단 테스트가 이유다). 그 이동이 AA 를 깨지 않았는지 잰다.
    """
    src = _read("src/static/css/tokens.css")
    failures = []
    for theme in _THEMES:
        block = _theme_block(src, theme)
        fg = _parse_color(_decl(block, "--text-2"))
        for name, bg in {**_grounds(block), **_extra_grounds(theme)}.items():
            r = _ratio(_over(fg, bg), bg)
            if r < _AA:
                failures.append(f"[{theme}] --text-2 on {name}: {r:.2f} < {_AA}")
    assert not failures, "보조 글자색이 AA 미달인 조합:\n  " + "\n  ".join(failures)


def test_text_hierarchy_stays_visibly_separated():
    """🔴 `--text-3` 을 올리면 `--text-2` 와 붙는다 — 계단이 남아 있는지 잰다.

    이 테스트가 있어서 pastel 의 `--text-2` 도 같이 옮겼다: `--text-3` 만 올리면
    카드 위 대비가 5.58 대 5.40(x1.03)이 되어 두 층이 사실상 한 색이 된다.
    """
    src = _read("src/static/css/tokens.css")
    for theme in _THEMES:
        block = _theme_block(src, theme)
        card = _grounds(block)["--bg-card"]
        r1, r2, r3 = (
            _ratio(_over(_parse_color(_decl(block, f"--text-{n}")), card), card)
            for n in (1, 2, 3)
        )
        assert r1 > r2 > r3, (
            f"[{theme}] 글자 계단이 순서를 잃었다 — "
            f"text-1 {r1:.2f} / text-2 {r2:.2f} / text-3 {r3:.2f}"
        )
        # 두 층의 대비비가 1.15배 미만이면 눈으로 구별되지 않는다.
        assert r2 / r3 >= 1.15, (
            f"[{theme}] --text-2({r2:.2f})와 --text-3({r3:.2f})가 붙었다 (x{r2 / r3:.2f}) — "
            "3차 글자를 올렸으면 보조 글자도 같이 올려야 계단이 남는다"
        )
        assert r1 / r2 >= 1.15, (
            f"[{theme}] --text-1({r1:.2f})와 --text-2({r2:.2f})가 붙었다 (x{r1 / r2:.2f})"
        )


def test_faint_text_is_not_painted_on_chip_surfaces():
    """🔴 3차 글자를 칩 표면(`--bg-mute`)에 얹지 않는다 — 그 조합은 어느 테마도 AA 를 못 넘는다.

    실측: `--bg-mute` 위에서 `--text-3` 은 dark 3.14 · light 2.93 · pastel 2.41 ·
    catppuccin 2.47. 여기를 통과시키려면 `--text-3` 이 `--text-2` 를 지나쳐야 한다
    (catppuccin 은 팔레트에 그런 색이 없다). 그래서 색이 아니라 «조합» 을 막는다.

    대상: `.kpi__delta--flat` — 회색 워시를 깔고 그 위에 3차 글자를 얹어
    네 테마 전부에서 최악 표면(2.63~3.20)을 만들고 있었다.
    """
    # 🔴 «모든» 선언을 본다. 지금 칠해지는 한 곳만 보면, 그 규칙이 사라졌을 때
    #    뒤에 숨어 있던 다른 선언이 조용히 칠해진다 — 실제로 `components.css` 에
    #    같은 이름의 규칙이 `--text-3` 을 `--bg-mute` 위에 얹은 채 남아 있었다.
    #    Check every declaration: the losing one paints as soon as the winner is removed.
    sources = ("src/templates/dashboard.html", "src/static/css/components.css")
    found = 0
    for rel in sources:
        src = _strip_css_comments(_read(rel))
        for m in re.finditer(r"\.kpi__delta--flat\s*\{([^}]*)\}", src):
            found += 1
            assert "var(--text-3" not in m.group(1), (
                f"[{rel}] `.kpi__delta--flat` 이 워시 배경 위에 3차 글자를 얹는다 — "
                "이 조합은 네 테마 전부 AA 미달이다(2.41~3.20). 형제인 --up/--down 처럼 "
                "강조 층(--text-2)을 쓴다"
            )
    assert found >= 2, (
        f"`.kpi__delta--flat` 선언을 {found}건만 찾았다 — 둘(페이지·컴포넌트)을 다 보지 못하면 "
        "재지 못한 것이지 통과한 것이 아니다"
    )


def test_no_rule_pairs_the_faintest_tier_with_a_chip_surface():
    """🔴 어떤 규칙도 «칩 표면 위에 3차 글자» 를 만들지 않는다 — 전역 불변식.

    위 `test_faint_text_token_meets_aa_on_every_ground` 는 바탕 5종만 본다.
    그 «제외» 가 정당한 근거가 바로 이 테스트다 — 제외한 표면 위에 3차 글자를 얹는 규칙이
    하나도 없어야 그 검사가 거짓 집행자가 아니게 된다. 개별 사례를 하나씩 막는 대신
    부류를 막는다.

    실측: `--bg-mute` 위에서 `--text-3` 은 dark 3.14 · light 2.93 · pastel 2.41 ·
    catppuccin 2.47. 통과시키려면 `--text-3` 이 `--text-2` 를 지나쳐야 한다.

    This is what makes the 5-ground check above honest: the excluded surfaces are excluded
    only because no rule may pair them with the faintest tier.
    """
    chip = ("--bg-mute", "--bg-input", "--bg-card-hi")
    offenders = []
    for path in sorted((_ROOT / "src").rglob("*.css")) + sorted(
        (_ROOT / "src" / "templates").glob("*.html")
    ):
        text = _strip_css_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"\{([^{}]*)\}", text):
            body = m.group(1)
            if "var(--text-3" not in body:
                continue
            hit = next((c for c in chip if f"var({c}" in body), None)
            if hit:
                sel = text[max(0, m.start() - 90):m.start()].strip().splitlines()
                offenders.append(
                    f"{path.relative_to(_ROOT).as_posix()}: "
                    f"{(sel[-1] if sel else '?')[:60]} — --text-3 on {hit}"
                )
    assert not offenders, (
        "칩 표면 위에 3차 글자를 얹는 규칙이 있다 — 이 조합은 네 테마 전부 AA 미달이고,\n"
        "위 바탕 5종 검사는 이 표면을 «보지 않으므로» 초록으로 통과한다:\n  "
        + "\n  ".join(offenders)
    )


def test_shared_table_header_uses_secondary_not_faint():
    """🔴 `.tbl th` 는 보조 글자색을 쓴다 — 저자 의도가 그것이었다는 증거가 있다.

    `repo_detail.html` 은 `table thead tr th { color: var(--text-2) }` 를 썼지만
    명시도(0,0,4)가 `.tbl th`(0,1,1)에 져서 **한 번도 적용된 적이 없었다**.
    `admin.css` 의 `.admin-table th` 도 `--text-2` 다. 표 머리글에 3차 색을 쓰는 곳은
    `components.css` 한 군데뿐이었다.
    """
    block = _rule_block(_read("src/static/css/components.css"), ".tbl th")
    assert "color: var(--text-2)" in block, (
        "`.tbl th` 가 보조 글자색을 쓰지 않는다 — 표 머리글이 3차 색으로 돌아가면 "
        "네 테마 전부 AA 미달(2.88~3.56)"
    )


def test_nav_control_labels_do_not_use_the_faintest_tier():
    """🔴 자기 워시를 깔고 그 위에 라벨을 얹는 nav 컨트롤은 3차 색을 쓰지 않는다.

    `.nav-logout-btn` · `.theme-btn` 은 `rgba(255,255,255,.06)` 을 자기 배경으로 깔고
    그 위에 `--text-3` 을 얹고 있었다. 토큰을 AA 까지 올린 «뒤에도» dark 에서 4.44 로
    남았다 — 이 표면은 `tokens.css` 에 없어서 토큰만 보는 검사로는 보이지 않는다.
    These two paint their own wash, a surface tokens.css cannot see; the token fix alone
    left dark at 4.44.
    """
    src = _read("src/templates/base.html")
    for selector in (".nav-logout-btn", ".theme-btn"):
        block = _rule_block(src, selector)
        assert "var(--text-3" not in block, (
            f"`{selector}` 이 자기 워시 위에 3차 글자를 얹는다 — "
            "누르는 컨트롤의 라벨이고, dark 에서 4.44 로 AA 미달이 된다"
        )
        assert "color: var(--text-2)" in block, (
            f"`{selector}` 의 라벨 색이 보조 토큰이 아니다"
        )


def test_no_dead_color_declaration_shadowed_by_a_later_equal_rule():
    """🔴 `.ri-kpi-sub` 의 색 선언은 죽어 있었다 — 되살아나지 않게 지운 것을 지킨다.

    `repo_insights.css` 의 `.ri-kpi-sub { color: var(--text-2) }` 는 명시도가 같은
    `repo_insights.html` 의 `.kpi__foot` 이 «나중에» 로드돼 한 번도 이긴 적이 없다.
    죽은 선언은 「이 값이 쓰인다」고 거짓말한다.
    """
    block = _rule_block(_read("src/static/css/repo_insights.css"), ".ri-kpi-sub")
    assert "color:" not in block, (
        "`.ri-kpi-sub` 에 색 선언이 되살아났다 — 같은 요소의 `.kpi__foot` 이 "
        "`repo_insights.html` 에서 더 나중에 로드돼 항상 이긴다(죽은 선언)"
    )


# 카드 표면은 «고정» 이어야 한다 — 그 위 글자의 배경이 정해지지 않으면 대비를 약속할 수 없다.
# Card surfaces must be opaque: text on a see-through card has no fixed background to measure.
_CARD_SURFACES = ("--bg-card", "--bg-card-hi", "--bg-input", "--bg-elevated")


def test_card_surfaces_are_opaque_so_text_has_a_fixed_background():
    """🔴 글자를 얹는 카드 표면 토큰은 «불투명» 이어야 한다.

    dark 의 `--bg-card` 는 `rgba(255,255,255,0.024)` — 사실상 투명이었다. 그 뒤에서
    `.atmosphere__orb` 셋이 `mix-blend-mode: screen` 으로 38·48·56초 주기로 움직인다.
    그래서 «같은 토큰 위의 같은 글자» 인데 실제로 칠해진 배경이
    `rgb(8,8,19)` ~ `rgb(48,37,80)` 사이를 오갔다(픽셀 실측).

    이것이 #1611 에서 `--text-3` 을 올리고도 dark 에서 다시 미달이 난 이유다 —
    토큰 대 토큰으로 계산하면 통과하지만 화면에서는 통과하지 않는다.
    페이지 배경의 orb 분위기는 그대로 두고, 카드 «안» 만 고정한다.

    A translucent card over the animated atmosphere has no fixed background, so no contrast
    guarantee is possible for text on it.
    """
    src = _read("src/static/css/tokens.css")
    offenders = []
    for theme in _THEMES:
        block = _theme_block(src, theme)
        for name in _CARD_SURFACES:
            value = _decl(block, name)
            alpha = _parse_color(value)[3]
            if alpha < 1.0:
                offenders.append(f"[{theme}] {name} = {value} (alpha {alpha})")
    assert not offenders, (
        "카드 표면이 반투명이다 — 그 위 글자의 배경이 orb 애니메이션에 따라 움직여\n"
        "어떤 글자색으로도 대비를 보장할 수 없다:\n  " + "\n  ".join(offenders)
    )
