"""도넛 차트는 색만으로 뜻을 나른다 — 범례가 어디에도 없었다.

실측(캔버스 픽셀·4테마): 조각 4개, `borderWidth: 0`, 인접 조각 대비

    dark 1.66 / 2.07 / 1.46 / 1.17 · light 1.29 / 1.03 / 1.44 / 1.09
    pastel 1.52 / 1.16 / 2.61 / 2.00 · catppuccin 1.82 / 1.60 / 1.15 / 1.31

Chart.js 범례는 `display: false` 고 HTML 범례도 없다. 조각 이름은 **툴팁에만** 있어
키보드·터치로는 도달할 수 없다 — WCAG 1.4.1(Level A).

처방은 색을 바꾸는 게 아니라 «이름과 수를 주는 것» 이다. 이름만으로는 1.4.1 만 풀린다 —
1.4.11 은 「조각을 봐야 비율을 읽는가」를 묻고(Understanding Figure 44), 값이 함께 있어야
조각이 «이해에 필요» 하지 않게 된다(Figure 45).

🔴 이 파일은 템플릿 «소스» 가 아니라 **렌더된 DOM** 을 본다. 처음엔 소스를 정규식으로
읽었는데, 범례를 `<!--` 로 감싸는 뮤테이션이 그대로 초록으로 통과했다 — 문자열은 여전히
파일에 있기 때문이다. 파서는 주석을 본문과 구분한다.
"""
from __future__ import annotations

import pathlib
from html.parser import HTMLParser

import jinja2
import pytest

_TEMPLATE_DIR = pathlib.Path(__file__).parents[3] / "src" / "templates"

# 도넛이 그려지는 최소 컨텍스트 — `breakdown.total > 0` 이어야 캔버스와 범례가 나온다
_CONTEXT = {
    "repo": {"full_name": "owner/test-repo", "id": 1},
    "repo_name": "owner/test-repo",
    "locale": "ko",
    "current_user": None,
    "days": 30,
    "kpi": {
        "analysis_count": 8, "avg_score": 74.0, "grade": "B", "score_delta": 2.5,
        "high_security_count": 3, "top_recurring_count": 4,
        "top_recurring_issue": "unused import",
    },
    "top_suggestions": [],
    "narrative": None,
    "recurring_issues": [],
    "problem_files": [],
    "score_trend": [],
    "breakdown": {
        "security_error": 3,
        "security_warning": 5,
        "code_quality_error": 4,
        "code_quality_warning": 7,
        "total": 19,
    },
}

# 조각 이름 — ko 번역의 실제 문자열로 대조한다(키 문자열이 아니라)
_SEGMENT_KEYS = (
    "repo_insights.chart_sec_err",
    "repo_insights.chart_sec_warn",
    "repo_insights.chart_qual_err",
    "repo_insights.chart_qual_warn",
)


class _Legend(HTMLParser):
    """`.ri-legend` 안의 «본문 글자» 만 모은다 — 주석은 `handle_comment` 로 갈린다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.labels: list[str] = []
        self.counts: list[str] = []
        self.swatches: list[dict] = []
        self.list_attrs: dict | None = None
        self._cur: str | None = None
        self.comments: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if "ri-legend" in cls:
            self.depth = 1
            self.list_attrs = a
            return
        if not self.depth:
            return
        self.depth += 1
        if "ri-legend-dot" in cls:
            self.swatches.append(a)
        elif "ri-legend-label" in cls:
            self._cur = "label"
        elif "ri-legend-count" in cls:
            self._cur = "count"

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1
        self._cur = None

    def handle_data(self, data):
        if not self.depth or not self._cur:
            return
        text = data.strip()
        if not text:
            return
        (self.labels if self._cur == "label" else self.counts).append(text)

    def handle_comment(self, data):
        self.comments.append(data)


@pytest.fixture(scope="module")
def legend() -> _Legend:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=jinja2.select_autoescape(["html"]),
        # 🔴 `ChainableUndefined` — 이 시험의 관심은 «범례» 하나뿐이라 나머지 컨텍스트를
        #    다 채우지 않는다. 대신 아래 단언들이 범례가 «실제 값으로» 렌더됐는지 확인하므로
        #    컨텍스트가 비어 조용히 통과하는 일은 없다.
        undefined=jinja2.ChainableUndefined,
    )
    from src.i18n.filters import register_i18n_filters  # noqa: PLC0415
    register_i18n_filters(env)
    html = env.get_template("repo_insights.html").render(**_CONTEXT)
    parser = _Legend()
    parser.feed(html)
    return parser


@pytest.fixture(scope="module")
def expected_labels() -> list[str]:
    """ko 번역의 실제 문자열 — 템플릿과 «따로» 가져온다.

    템플릿에서 키를 긁어 오면 키가 사라져도 초록이다. 번역 원본에서 뽑아 대조한다.
    """
    from src.i18n.filters import register_i18n_filters  # noqa: PLC0415
    env = jinja2.Environment(autoescape=False)
    register_i18n_filters(env)
    out = []
    for key in _SEGMENT_KEYS:
        text = env.from_string("{{ k | i18n_args('ko') }}").render(k=key)
        assert text and text != key, f"{key} 번역 부재 — 대조군이 없다"
        out.append(text)
    return out


def test_donut_segments_are_named_in_the_rendered_html(legend, expected_labels):
    """🔴 네 조각의 이름이 «렌더된 글자» 로 캔버스 곁에 있어야 한다.

    `data-i18n-chart-*` «속성» 은 JS 가 툴팁에 쓰려고 읽는 값이라 화면 글자가 아니다.
    """
    assert legend.list_attrs is not None, "`.ri-legend` 가 렌더되지 않았다"
    missing = [t for t in expected_labels if t not in legend.labels]
    assert not missing, (
        "도넛 조각 이름이 화면 글자로 없다 — 색만으로 구분해야 한다 (WCAG 1.4.1):\n  "
        + "\n  ".join(missing)
        + f"\n  (렌더된 라벨: {legend.labels})"
    )


def test_donut_legend_shows_the_count_of_each_segment(legend):
    """범례는 이름뿐 아니라 그 조각의 «수» 도 보여야 한다.

    수가 없으면 1.4.11 이 그대로 남는다 — 조각을 봐야 비율을 읽게 되기 때문이다
    (Understanding 1.4.11 Figure 44 vs 45).
    """
    want = sorted(str(_CONTEXT["breakdown"][k]) for k in
                  ("security_error", "security_warning",
                   "code_quality_error", "code_quality_warning"))
    assert sorted(legend.counts) == want, (
        f"범례 건수가 breakdown 과 다르다 — 렌더 {sorted(legend.counts)} ≠ 기대 {want}"
    )


def test_donut_legend_is_not_hidden(legend):
    """🔴 범례가 렌더되기만 하고 «숨어» 있으면 안 된다.

    첫 판의 가드는 소스를 정규식으로 읽어서, `hidden` 을 붙이거나 `<!--` 로 감싸는
    뮤테이션을 둘 다 통과시켰다.
    """
    attrs = legend.list_attrs or {}
    assert "hidden" not in attrs, "범례에 `hidden` 이 붙어 있다"
    style = (attrs.get("style") or "").replace(" ", "")
    assert "display:none" not in style and "visibility:hidden" not in style, (
        f"범례가 style 로 숨겨져 있다 — {attrs.get('style')!r}")


def test_donut_legend_swatch_is_marked_decorative(legend):
    """색 견본은 보조 표시다 — 글자가 뜻을 나르므로 보조기술이 읽을 것이 아니다."""
    assert len(legend.swatches) == 4, (
        f"범례 색 견본이 4개가 아니다 — {len(legend.swatches)}개")
    bad = [s for s in legend.swatches if s.get("aria-hidden") != "true"]
    assert not bad, f"색 견본에 aria-hidden 이 없다: {bad[:2]}"
