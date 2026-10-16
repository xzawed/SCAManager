"""테스트용 대비 계산 — `tokens.css` 를 읽어 WCAG 명암비를 «계산» 하는 공용 도구.

행동 판정은 e2e 가 실제로 칠해진 색으로 한다. 여기 있는 것은 그 수정이 되돌려졌는지를
단위 수준에서 빠르게 잡기 위한 계산이다.

🔴 이 계산은 «조상 사슬» 만 본다 — 형제가 칠하는 층(`.atmosphere__orb`)은 못 본다.
그래서 카드 표면이 반드시 불투명이어야 하고(`test_card_surfaces_are_opaque…`), 그 불변식이
성립할 때만 이 계산이 화면과 일치한다.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]

AA = 4.5
THEMES = ("dark", "light", "pastel", "catppuccin")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# 주석 · 문자열 · 따옴표 없는 `url(...)` — 왼쪽부터 «먼저 시작하는 것» 이 이긴다.
# 문자열·url 안의 `/*` 는 주석이 아니고, 주석 안의 따옴표는 문자열이 아니다.
# 문자열은 줄바꿈에서 끝난다(CSS 의 bad-string). 닫히지 않은 주석은 끝까지 간다.
# Comment, string or unquoted url token — whichever starts first wins.
_CSS_OPAQUE = re.compile(
    r"/\*.*?(?:\*/|\Z)"
    r'|"(?:\\.|[^"\\\n])*"?'
    r"|'(?:\\.|[^'\\\n])*'?"
    r"|(?<![\w-])url\(\s*(?=[^\"'\s)])[^)]*\)",
    re.S | re.I)


def strip_css_comments(src: str) -> str:
    r"""판정 전에 주석을 지운다 — 주석이 규칙을 인용하면 가드가 산문을 통과시킨다.

    🔴 `re.sub(r"/\*.*?\*/", "", src)` 를 쓰지 않는다 — 문자열·`url(...)` 안의 `/*` 부터
       다음 `*/` 까지, 그 사이의 규칙까지 지운다(`test_css_comment_strip.py`).
    지운 자리엔 그 주석이 품었던 줄바꿈만 남긴다 — 보고하는 줄이 파일의 줄과 맞도록.
    Strings and url tokens are copied through; comments keep only their newlines.
    """
    return _CSS_OPAQUE.sub(
        lambda m: "\n" * m.group(0).count("\n") if m.group(0).startswith("/*") else m.group(0),
        src)


def theme_block(src: str, theme: str) -> str:
    """그 테마의 «모든» `[data-theme]` 블록(팔레트 + 의미 토큰)을 이어 붙인다."""
    src = strip_css_comments(src)
    blocks, start = [], 0
    anchor = f'[data-theme="{theme}"] {{'
    while (i := src.find(anchor, start)) >= 0:
        j = src.find("\n}", i)
        assert j > i, f"{theme} 블록이 닫히지 않는다"
        blocks.append(src[i:j])
        start = j
    assert blocks, f"{theme} 블록 부재 — 테스트가 늙었다"
    return "\n".join(blocks)


def decl(block: str, name: str) -> str:
    """마지막 정의를 돌려준다 — CSS 는 뒤에 오는 선언이 이긴다."""
    ms = re.findall(rf"{re.escape(name)}\s*:\s*([^;]+);", block)
    assert ms, f"{name} 미정의 — 못 재면 초록이 아니라 red 다"
    return ms[-1].strip()


def resolve(block: str, value: str, depth: int = 0) -> str:
    """`var(--x)` 를 같은 테마 블록 안에서 한 단계씩 푼다."""
    assert depth < 8, f"토큰 참조가 순환한다: {value}"
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*\)", value.strip())
    if m:
        return resolve(block, decl(block, m.group(1)), depth + 1)
    return value.strip()


def parse_color(value: str) -> tuple[float, float, float, float]:
    """#rgb / #rrggbb / rgb(a)() → (r, g, b, alpha). 그 외 형식은 «못 잰다» 고 실패한다."""
    value = value.split("/*")[0].strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(([^)]+)\)", value)
    if m:
        try:
            nums = [float(p.strip().rstrip("%"))
                    for p in m.group(1).replace("/", ",").split(",") if p.strip()]
        except ValueError as exc:
            # `rgba(var(--x-rgb), .12)` — 채널이 토큰이면 이 계기는 못 푼다. 터지지 말고 «못 잰다».
            # Channels given by a token cannot be resolved here: unmeasurable, not a crash.
            raise AssertionError(
                f"이 계기가 읽지 못하는 색 형식이다: {value!r} — 초록으로 넘기지 않는다") from exc
        return (nums[0], nums[1], nums[2], nums[3] if len(nums) > 3 else 1.0)
    raise AssertionError(f"이 계기가 읽지 못하는 색 형식이다: {value!r} — 초록으로 넘기지 않는다")


def over(fg: tuple, bg: tuple) -> tuple:
    """알파 합성 — fg 를 불투명 bg 위에 얹은 «칠해지는» 색."""
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def luminance(c: tuple) -> float:
    def lin(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def ratio(a: tuple, b: tuple) -> float:
    la, lb = luminance(a), luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def card_surface(block: str) -> tuple:
    """그 테마의 카드 면 — 칩이 얹히는 바탕."""
    return parse_color(resolve(block, decl(block, "--bg-card")))


def body_gradient_stops(theme: str) -> dict[str, tuple]:
    """토큰 밖의 바탕 — pastel 은 `body` 가 그라디언트라 stop 전부가 «페이지» 글자의 바탕이다.

    면이 없는 머리 영역(`.ri-header` 등)의 글자는 카드가 아니라 이 위에 앉는다. 다른 테마는 빈 dict.
    The pastel body is a gradient: every stop is a ground for text placed directly on the page.
    """
    if theme != "pastel":
        return {}
    src = strip_css_comments(read("src/templates/base.html"))
    i = src.find('body[data-theme="pastel"]')
    assert i >= 0, "pastel body 규칙 부재 — 테스트가 늙었다"
    stops = re.findall(r"#[0-9a-fA-F]{6}", src[i:src.find("}", i)])
    assert stops, "pastel body 그라디언트 stop 을 못 읽었다 — 못 재면 red"
    return {f"body-gradient-stop-{n}": parse_color(s) for n, s in enumerate(stops)}


# 글자가 앉는 «면» 토큰 — 페이지 바탕 둘 · 카드 · 떠 있는 면 · 칩 면(탭 띠).
PAGE_TEXT_GROUNDS = ("--bg-base", "--bg-canvas", "--bg-card", "--bg-elevated", "--bg-mute")
# 마우스를 올리면 행·카드가 바꿔 칠하는 면. 그 안의 글자는 전부 이 위에 앉는다(회고 P1-28).
# Surfaces a row or card repaints on hover; every glyph inside sits on them.
HOVER_GROUNDS = ("--table-row-hover", "--bg-card-hover")


def _opaque_grounds(theme: str, names: tuple[str, ...]) -> dict[str, tuple]:
    scope = token_scope(read("src/static/css/tokens.css"), theme)
    card = paint_colours(scope, "var(--bg-card)")[0]
    out = {}
    for name in names:
        c = paint_colours(scope, f"var({name})")[0]
        out[name] = c if c[3] >= 1 else over(c, card)
    return out


def hover_grounds(theme: str) -> dict[str, tuple]:
    """hover 면 — 반투명이면 카드 위에 합성한다(행·카드는 카드 안에 있다)."""
    return _opaque_grounds(theme, HOVER_GROUNDS)


def text_grounds(theme: str) -> dict[str, tuple]:
    """그 테마에서 글자가 앉을 수 있는 바탕 전부 — 불투명색으로(반투명 면은 카드 위에 합성)."""
    return {**_opaque_grounds(theme, PAGE_TEXT_GROUNDS + HOVER_GROUNDS),
            **body_gradient_stops(theme)}


class Unmeasurable(AssertionError):
    """이 계기가 색으로 풀지 못하는 값 — `color-mix()`·`url()`·`currentColor` 등."""


def token_scope(src: str, theme: str) -> str:
    """그 테마의 html 에 «실제로 적용되는» 토큰 블록 전부 — 소스 순서 그대로 이어 붙인다.

    `:root` · `[data-theme]` · `[data-theme="<theme>"]` 만 모은다. 명시도가 같아 «뒤에 오는
    선언이 이긴다» — `decl` 이 마지막 정의를 돌려주는 것과 맞물린다. `[data-variant]` 블록은
    `base.html` 이 `data-variant="refined"` 로 고정해 적용되지 않는다.
    `theme_block` 과 달리 `:root` 의 공용 별칭(`--bg-hover` 등)까지 풀린다.
    """
    want = {":root", "[data-theme]", f'[data-theme="{theme}"]'}
    blocks = [(" ".join(m.group(1).split()), m.group(2))
              for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", strip_css_comments(src))]
    assert any(sel == f'[data-theme="{theme}"]' for sel, _ in blocks), (
        f"{theme} 블록 부재 — 테스트가 늙었다")
    return "\n".join(body for sel, body in blocks if sel in want)


def resolve_value(scope: str, value: str, depth: int = 0) -> str:
    """`var(--x)`·`var(--x, 대체값)` 을 끝까지 푼다 — 대체값은 그 이름이 «없을 때만» 쓴다."""
    assert depth < 12, f"토큰 참조가 순환한다: {value}"
    v = value.replace("!important", "").strip()
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.*))?\)", v, re.S)
    if not m:
        return v
    ms = re.findall(rf"(?<![\w-]){re.escape(m.group(1))}\s*:\s*([^;]+);", scope)
    if ms:
        return resolve_value(scope, ms[-1], depth + 1)
    if m.group(2) is not None:
        return resolve_value(scope, m.group(2), depth + 1)
    raise Unmeasurable(f"{m.group(1)} 미정의 · 대체값 없음")


_NAMED = {"white": "#ffffff", "black": "#000000", "transparent": "rgba(0,0,0,0)",
          "none": "rgba(0,0,0,0)"}
_COLOUR_TOKEN = re.compile(r"var\((?:[^()]|\([^()]*\))*\)|#[0-9a-fA-F]{3,6}\b|rgba?\([^)]*\)"
                           r"|\b(?:white|black|transparent)\b")


def _split_top(args: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in args:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return parts + [cur]


def paint_colours(scope: str, value: str) -> list[tuple]:
    """칠하는 값 → 색 목록. 단색이면 하나, 그라디언트면 stop 전부. 못 풀면 `Unmeasurable`."""
    v = resolve_value(scope, value)
    v = _NAMED.get(v.lower(), v)
    g = re.fullmatch(r"(?:repeating-)?(?:linear|radial|conic)-gradient\((.*)\)", v, re.S)
    if g:
        out = []
        for arg in _split_top(g.group(1)):
            hit = _COLOUR_TOKEN.search(arg)
            if not hit:
                continue                                  # 방향·위치·색 힌트
            if "color-mix" in arg:
                raise Unmeasurable(f"그라디언트 stop 이 color-mix 다: {arg.strip()}")
            out += paint_colours(scope, hit.group(0))
        if not out:
            raise Unmeasurable(f"그라디언트에서 stop 을 하나도 못 읽었다: {v[:60]}")
        return out
    try:
        return [parse_color(v)]
    except AssertionError as e:
        raise Unmeasurable(str(e)) from e
