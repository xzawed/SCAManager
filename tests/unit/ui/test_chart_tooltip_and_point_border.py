"""차트 툴팁의 «경계» 와 포인트 테두리 — canvas 위의 색은 CSS 가 아니라 JS 가 고른다.

실측(#1639 W17): 툴팁 면이 카드와 **같은 토큰**(`--bg-card`)이라 `vsCard = 1.00` 이고,
테두리(`--border-subtle`)는 알파 합성 후 **1.13~1.28** 이다. 즉 툴팁의 네 변 어디에도
3:1 경계가 없다 — 카드 위에 떠 있는 상자가 카드와 구분되지 않는다.

실측(#1639 W18): `pointHoverBorderColor: '#fff'` 가 세 곳에 하드코딩돼 있다. 바로 위
40줄에 「CSS 변수로만 색상 결정 — hex 직접 사용 금지」라고 적혀 있었는데, 그 규칙을
집행하는 것이 없어서 규칙과 코드가 반대였다.

🔴 canvas 는 CSS 선택자가 닿지 않는다. e2e 대비 스윕은 DOM 요소를 훑으므로 차트 내부
   색을 **원리적으로 관측하지 못한다**. 이 축은 정적 가드가 유일한 관측자다.

🔴 열거하지 않는다 — 차트 템플릿은 `new Chart(` 에서 파생한다. 손으로 적으면 여섯 번째
   차트가 조용히 빠진다.
"""
import re

from ._contrast import (
    THEMES, card_surface, decl, over, parse_color, ratio, read, resolve, strip_css_comments,
    theme_block,
)

TOKENS = "src/static/css/tokens.css"
TEMPLATE_DIR = "src/templates"

# 비-글자 대비(WCAG 1.4.11) — UI 컴포넌트의 «경계» 는 인접색 대비 3:1
NON_TEXT_AA = 3.0
# 툴팁 «글자» 는 본문과 같은 규범을 따른다
TEXT_AA = 4.5

# 툴팁의 «잠긴 3종 세트» — 면·테두리·글자. 하나만 바꾸면 다른 축이 깨진다.
TOOLTIP_SURFACE = "--tooltip-bg"
TOOLTIP_BORDER = "--tooltip-border"
TOOLTIP_TEXT = "--tooltip-text"


def _chart_templates() -> dict[str, str]:
    """`new Chart(` 를 부르는 템플릿 — 파생이지 손 목록이 아니다."""
    import pathlib

    from ._contrast import ROOT

    found = {}
    for path in sorted((ROOT / TEMPLATE_DIR).glob("*.html")):
        src = path.read_text(encoding="utf-8")
        if "new Chart(" in src:
            found[path.name] = src
    assert len(found) >= 4, (
        f"차트 템플릿이 {len(found)}개뿐 — 파생이 늙었거나 `new Chart(` 관용구가 바뀌었다. "
        "0에 가까우면 이 파일 전체가 공허한 초록이 된다."
    )
    assert isinstance(pathlib.Path(TEMPLATE_DIR), pathlib.Path)
    return found


def test_tooltip_has_a_boundary_against_the_card_in_every_theme():
    """🔴 툴팁 테두리가 카드 면 대비 3:1 이상 — 네 테마 전부.

    red 로 만드는 뮤테이션: `--tooltip-border` 를 `var(--border-subtle)` 로 되돌리면
    1.13~1.28 이 되어 전 테마 red.
    """
    src = read(TOKENS)
    failures = []
    for theme in THEMES:
        block = theme_block(src, theme)
        card = card_surface(block)
        surface = parse_color(resolve(block, decl(block, TOOLTIP_SURFACE)))
        surface = over(surface, card) if surface[3] < 1 else surface
        border = parse_color(resolve(block, decl(block, TOOLTIP_BORDER)))
        # 테두리는 툴팁 면 «위» 가 아니라 면과 카드 «사이» 에 그려진다 —
        # 알파가 있으면 어느 쪽에 얹히든 대비가 깎이므로 나쁜 쪽(카드)으로 합성한다.
        drawn = over(border, card) if border[3] < 1 else border
        against_card = ratio(drawn, card)
        against_surface = ratio(drawn, surface)
        if min(against_card, against_surface) < NON_TEXT_AA:
            failures.append(
                f"{theme}: 테두리 vs 카드 {against_card:.2f} · vs 툴팁면 "
                f"{against_surface:.2f} (3.0 미만)"
            )
    assert not failures, "툴팁에 경계가 없다 — " + " / ".join(failures)


def test_tooltip_text_meets_aa_on_the_tooltip_surface():
    """툴팁 글자가 그 면 위에서 AA — 경계를 만들다 글자를 깨뜨리지 않았는지."""
    src = read(TOKENS)
    failures = []
    for theme in THEMES:
        block = theme_block(src, theme)
        card = card_surface(block)
        surface = parse_color(resolve(block, decl(block, TOOLTIP_SURFACE)))
        surface = over(surface, card) if surface[3] < 1 else surface
        text = parse_color(resolve(block, decl(block, TOOLTIP_TEXT)))
        text = over(text, surface) if text[3] < 1 else text
        got = ratio(text, surface)
        if got < TEXT_AA:
            failures.append(f"{theme}: {got:.2f}")
    assert not failures, "툴팁 글자가 AA 미달 — " + " / ".join(failures)


def test_every_chart_reads_the_tooltip_boundary_token():
    """🔴 토큰이 있어도 «읽지 않으면» 화면은 그대로다 — 배선을 따로 잰다.

    실측: 다섯 차트 중 둘은 툴팁 설정이 아예 없어 Chart.js 기본값(불투명에 가까운 검정)을
    쓴다. 그 기본값은 밝은 테마에서는 잘 보이지만 dark 카드(`#0c0c14`) 위에서는 1.15 다 —
    「기본값이라 괜찮다」가 성립하지 않는다.
    """
    missing = [
        name for name, src in _chart_templates().items()
        if f"'{TOOLTIP_BORDER}'" not in src and f'"{TOOLTIP_BORDER}"' not in src
    ]
    assert not missing, (
        f"{TOOLTIP_BORDER} 를 읽지 않는 차트 템플릿: {missing} — "
        "토큰만 늘리고 배선하지 않으면 화면은 그대로다"
    )


def test_every_chart_actually_sets_a_tooltip_border():
    """읽기만 하고 Chart.js 에 넘기지 않는 경우를 막는다 — «읽음 ≠ 배선»."""
    missing = [
        name for name, src in _chart_templates().items()
        if not re.search(r"tooltip\s*:\s*\{[^}]*borderColor", src, re.DOTALL)
    ]
    assert not missing, f"tooltip.borderColor 를 넘기지 않는 템플릿: {missing}"


_POINT_COLOR_RE = re.compile(r"(point\w*Color)\s*:\s*(.+?)[,\n]")


def test_no_chart_point_color_is_a_hardcoded_literal():
    """🔴 `pointHoverBorderColor: '#fff'` 처럼 리터럴 색을 박지 않는다.

    dark 에서만 «흰 고리» 가 의도대로 보이고, light/pastel 카드(`#ffffff`/`#fffaf2`)
    위에서는 고리가 사라진다. 값은 테마 토큰을 읽은 «식별자» 여야 한다.

    red 로 만드는 뮤테이션: 한 곳을 `'#fff'` 로 되돌리면 red.
    """
    offenders = []
    for name, src in _chart_templates().items():
        for m in _POINT_COLOR_RE.finditer(src):
            value = m.group(2).strip().rstrip(",")
            if re.match(r"""^['"]""", value) or value.startswith("#"):
                offenders.append(f"{name}: {m.group(1)} = {value}")
    assert not offenders, (
        "차트 포인트 색이 하드코딩됐다 — 테마 토큰에서 읽을 것: " + " / ".join(offenders)
    )


def test_the_literal_probe_can_actually_see_a_hardcoded_color():
    """탐지기가 «잴 수 있는지» 를 잰다 — 리터럴을 심으면 잡히는가."""
    planted = "          pointHoverBorderColor: '#fff',\n"
    hits = [
        m.group(2).strip().rstrip(",")
        for m in _POINT_COLOR_RE.finditer(planted)
    ]
    assert hits == ["'#fff'"], f"탐지기가 리터럴을 못 본다: {hits}"
    ok = "          pointHoverBorderColor: bgBase,\n"
    values = [m.group(2).strip().rstrip(",") for m in _POINT_COLOR_RE.finditer(ok)]
    assert values == ["bgBase"], f"식별자를 못 읽는다: {values}"
    assert not re.match(r"""^['"]""", values[0]), "식별자를 리터럴로 오판한다"


def test_tooltip_tokens_are_declared_in_every_theme():
    """세 토큰이 네 테마 전부에 있어야 — 한 테마만 빠지면 그 테마에서 무효 색이 된다."""
    src = strip_css_comments(read(TOKENS))
    for token in (TOOLTIP_SURFACE, TOOLTIP_BORDER, TOOLTIP_TEXT):
        count = len(re.findall(rf"(?:^|[{{;])\s*{re.escape(token)}(?![\w-])\s*:", src, re.M))
        assert count >= len(THEMES), (
            f"{token} 선언 {count}회 — {len(THEMES)} 테마 전부에 있어야 한다"
        )
