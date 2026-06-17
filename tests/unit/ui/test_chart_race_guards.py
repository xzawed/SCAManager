"""Chart.js 비동기 로드 race 가드 정적 회귀 테스트.

hx-boost body swap 시 vendored `chart.umd.min.js` 가 비동기로 재삽입/실행되는 동안
인라인 `buildXChart()` 가 동기 즉시 실행돼 `new Chart` 가 `Chart is not defined` 로
throw → 차트 미표시 + (호출이 재트리거 핸들러 등록보다 앞이면) 핸들러 등록까지
중단되어 영구 공백/지연되던 사고를 봉인한다. 모든 차트 템플릿이
(1) `new Chart` 앞 `typeof Chart === 'undefined'` early-return 가드(throw→graceful)
+ (2) vendor `<script>` 의 onload 즉시 재빌드 + `fetchpriority` 다운로드 우선
패턴을 유지하는지 소스 정적 스캔으로 회귀 차단한다.

Static source-scan guard for the Chart.js async-load race on hx-boost swaps:
every chart template must keep a `typeof Chart === 'undefined'` early-return guard
before `new Chart` (graceful return, not throw) and an onload-driven repaint plus a
`fetchpriority` download hint on the vendored Chart.js script.

참고: `src/templates/*.html` 인라인 JS 는 `--cov=src`(Python) 미측정이므로 본 정적
스캔이 1차 회귀 가드다. 런타임(hx-boost 재방문) 검증은 E2E + pageerror trap (testing.md).
"""
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[3]

# 템플릿 → vendor <script onload> 가 호출하는 ready 핸들러명 (document.<name>)
# template → ready handler (document.<name>) invoked by the vendor <script onload>
_CHART_TEMPLATES = {
    "src/templates/dashboard.html": "_dashChartReady",
    "src/templates/analysis_detail.html": "_adChartReady",
    "src/templates/repo_insights.html": "_riChartReady",
    "src/templates/repo_detail.html": "_repoChartReady",
}


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("tpl", sorted(_CHART_TEMPLATES))
def test_chart_template_has_async_load_race_guard(tpl):
    """모든 차트 템플릿은 `new Chart` 앞에 typeof Chart undefined early-return 가드 유지.

    Every chart template keeps a typeof-Chart early-return guard before `new Chart`.
    """
    src = _read(tpl)
    assert "new Chart(" in src, f"{tpl}: 차트 생성 코드 부재 — 테스트가 stale 함"
    assert "if (typeof Chart === 'undefined') return;" in src, (
        f"{tpl}: Chart.js async 로드 race 가드 누락 → hx-boost swap 시 "
        "'Chart is not defined' throw 로 차트 미표시 회귀"
    )


@pytest.mark.parametrize("tpl,ready", sorted(_CHART_TEMPLATES.items()))
def test_chart_vendor_script_has_onload_repaint(tpl, ready):
    """vendor `chart.umd.min.js` <script> 는 onload 즉시 재빌드 + fetchpriority 유지 (노출 속도).

    The vendored Chart.js <script> keeps an onload repaint hook and a fetchpriority hint.
    """
    src = _read(tpl)
    # bare(무-onload) vendor script 회귀 차단 — async 로드 후 자동 페인트 불가해짐
    # Block regression to a bare vendor <script> (no onload → no auto-repaint after async load)
    assert '<script src="/static/vendor/chart.umd.min.js"></script>' not in src, (
        f"{tpl}: bare chart vendor script 회귀 (onload 미부착)"
    )
    # onload 가 ready 핸들러를 호출 (존재 가드 동반 — onload 가 정의 전 발화해도 안전)
    # onload invokes the ready handler (existence-guarded — safe even if it fires early)
    assert f'onload="if(document.{ready})document.{ready}()"' in src, (
        f"{tpl}: vendor script onload 재빌드({ready}) 누락"
    )
    assert 'fetchpriority="high"' in src, f"{tpl}: chart vendor fetchpriority 다운로드 우선 hint 누락"
    # ready 핸들러는 no-anim 재빌드로 노출 (full-load 이중 호출 시 애니메이션 flash 방지)
    # ready handler exposed as a no-animation rebuild (avoids double-animation on full load)
    assert f"document.{ready} = function()" in src, (
        f"{tpl}: document.{ready} ready 핸들러 노출 누락"
    )
