"""점수 바의 면(트랙·채움)은 `components.css` 한 곳에서 정한다 (2026-09-16 회고 P1-10).

#1651 이 `analysis_detail.html` 의 `.score-bar--a~f::after { background: … }` 5줄을 걷었다 —
그 리터럴(`--b` #60a5fa · `--d` #fb923c)이 등급 토큰을 덮고 있었다. 같은 5줄이 트랙·채움의
기본 규칙과 함께 `overview.html`·`repo_detail.html` 에는 그대로 남아, 같은 등급이 화면마다
다른 색이었다. 페이지 `<style>` 은 `components.css` 보다 나중에 와 같은 명시도에서 이긴다.

🔴 템플릿은 점수 바의 «크기»(높이·폭·배치)만 정한다 — 면을 정하는 순간 화면마다 갈라진다.
행동 판정(실제로 칠해진 색이 화면 간 같은가)은
`e2e/test_state_indication.py::test_a_grade_paints_the_same_score_bar_on_every_screen`.

Templates may size the score bar; only `components.css` may paint it.
"""
from __future__ import annotations

import re

from ._contrast import ROOT, strip_css_comments

# `.score-bar` · `.score-bar--b` · `.score-bar::after` — `.score-bar-wrap` 같은 다른 이름은 아니다.
_SCORE_BAR = re.compile(r"\.score-bar(?:--[\w-]+)?(?![\w-])")
_PAINT = re.compile(r"(?<![\w-])background(?:-color|-image)?\s*:")


def painted_score_bar_rules(src: str) -> list[str]:
    """CSS 원문에서 점수 바의 면을 칠하는 규칙의 셀렉터."""
    return [" ".join(m.group(1).split())
            for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", strip_css_comments(src))
            if _SCORE_BAR.search(m.group(1)) and _PAINT.search(m.group(2))]


def _template_styles() -> list[tuple[str, str]]:
    out = []
    for f in sorted((ROOT / "src" / "templates").rglob("*.html")):
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", f.read_text(encoding="utf-8"),
                             re.S | re.I):
            out.append((f.relative_to(ROOT).as_posix(), m.group(1)))
    return out


def test_no_template_paints_the_score_bar():
    offenders = [f"{where}: {sel}" for where, css in _template_styles()
                 for sel in painted_score_bar_rules(css)]
    assert not offenders, (
        "템플릿이 점수 바의 면을 다시 칠한다 — 같은 등급이 화면마다 다른 색이 된다"
        "(`components.css` 의 `.score-bar--*` 가 정본):\n  " + "\n  ".join(offenders))


def test_the_component_still_paints_every_grade():
    """🔴 대조군 — 정본이 사라지면 위 시험은 「위반 0」으로 조용히 초록이다."""
    css = (ROOT / "src" / "static" / "css" / "components.css").read_text(encoding="utf-8")
    for g in "abcdf":
        assert re.search(rf"\.score-bar--{g}\s*\{{[^}}]*--sb-color\s*:\s*var\(--grade-{g}\)",
                         strip_css_comments(css)), f"`components.css` 에 `.score-bar--{g}` 정본이 없다"


def test_the_scan_catches_the_base_fill_and_ignores_sizes_and_other_names():
    r"""claimed\cheap — 등급 수식자(`--a`~`--f`)만 훑는 과정은 기본 `::after` 의 칠을 놓친다.
    cheap\claimed — 크기만 정하는 규칙 · 이름이 같은 접두사인 다른 컴포넌트는 무시한다."""
    src = (".score-bar::after { content: ''; background: var(--accent-grad); }\n"
           ".score-bar--b::after { background: #60a5fa; }\n"
           ".score-bar { height: 4px; display: inline-block; }\n"
           ".score-bar-wrap { background: var(--bg-card); }")
    assert painted_score_bar_rules(src) == [".score-bar::after", ".score-bar--b::after"]
