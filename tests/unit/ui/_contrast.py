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


def strip_css_comments(src: str) -> str:
    """판정 전에 주석을 지운다 — 주석이 규칙을 인용하면 가드가 산문을 통과시킨다."""
    return re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)


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
        nums = [float(p.strip().rstrip("%"))
                for p in m.group(1).replace("/", ",").split(",") if p.strip()]
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
