"""도넛 차트는 색만으로 뜻을 나른다 — 범례가 어디에도 없었다.

실측(캔버스 픽셀·4테마): 조각 4개, `borderWidth: 0`, 인접 조각 대비

    dark 1.66 / 2.07 / 1.46 / 1.17 · light 1.29 / 1.03 / 1.44 / 1.09
    pastel 1.52 / 1.16 / 2.61 / 2.00 · catppuccin 1.82 / 1.60 / 1.15 / 1.31

Chart.js 범례는 `display: false` 고 HTML 범례도 없다. 조각 이름은 **툴팁에만** 있어
키보드·터치로는 도달할 수 없다 — WCAG 1.4.1(Level A).

처방은 색을 바꾸는 게 아니라 «글자를 주는 것» 이다. 글자가 있으면 색은 더 이상
정보를 혼자 나르지 않는다.
"""
import re

from ._contrast import read, strip_css_comments

_TEMPLATE = "src/templates/repo_insights.html"

# 도넛의 네 조각 — canvas 의 data-i18n-chart-* 가 쓰는 것과 같은 키
_SEGMENT_KEYS = (
    "repo_insights.chart_sec_err",
    "repo_insights.chart_sec_warn",
    "repo_insights.chart_qual_err",
    "repo_insights.chart_qual_warn",
)


def _donut_wrap(src: str) -> str:
    """`.ri-donut-wrap` 의 내용 — 범례는 캔버스 곁에 있어야 뜻이 붙는다."""
    i = src.find('class="ri-donut-wrap"')
    assert i > 0, "`.ri-donut-wrap` 부재 — 테스트가 늙었다"
    depth, j, start = 0, src.find(">", i) + 1, None
    start = j
    for m in re.finditer(r"<(/?)div\b", src[j:]):
        depth += -1 if m.group(1) else 1
        if depth < 0:
            return src[start:j + m.start()]
    raise AssertionError("`.ri-donut-wrap` 이 닫히지 않는다")


def test_donut_segments_are_named_in_html_not_only_in_the_tooltip():
    """🔴 네 조각의 이름이 «HTML 글자» 로 캔버스 곁에 있어야 한다.

    `data-i18n-chart-*` «속성» 은 JS 가 툴팁에 쓰려고 읽는 값이라 화면 글자가 아니다.
    속성 자리는 세지 않고, 요소 내용으로 렌더되는 자리만 센다.
    """
    src = read(_TEMPLATE)
    wrap = _donut_wrap(src)
    missing = []
    for key in _SEGMENT_KEYS:
        # 속성 안(`data-...="{{ ... }}"`)이 아닌 자리에 있는가
        rendered = [
            m for m in re.finditer(re.escape(key), wrap)
            if not re.search(r'data-i18n-chart-[\w-]+="[^"]*$', wrap[:m.start()])
        ]
        if not rendered:
            missing.append(key)
    assert not missing, (
        "도넛 조각 이름이 화면 글자로 없다 — 색만으로 구분해야 한다 (WCAG 1.4.1):\n  "
        + "\n  ".join(missing))


def test_donut_legend_shows_the_count_of_each_segment():
    """범례는 «이름» 뿐 아니라 그 조각의 «수» 도 보여야 한다.

    수가 없으면 어느 조각이 큰지를 여전히 넓이·색으로만 읽어야 한다.
    """
    wrap = strip_css_comments(_donut_wrap(read(_TEMPLATE)))
    fields = ("security_error", "security_warning",
              "code_quality_error", "code_quality_warning")
    missing = [f for f in fields if f"breakdown.{f}" not in wrap]
    assert not missing, f"범례에 조각별 건수가 없다: {missing}"


def test_donut_legend_swatch_is_marked_decorative():
    """색 견본은 보조 표시다 — 보조기술이 읽을 것이 아니다.

    글자가 뜻을 나르므로 견본은 `aria-hidden` 이어야 중복 낭독이 없다.
    """
    wrap = _donut_wrap(read(_TEMPLATE))
    swatches = re.findall(r'<span[^>]*class="[^"]*ri-legend-dot[^"]*"[^>]*>', wrap)
    assert swatches, "범례 색 견본(`.ri-legend-dot`)이 없다"
    bad = [s for s in swatches if "aria-hidden" not in s]
    assert not bad, f"색 견본에 aria-hidden 이 없다: {bad[:2]}"
