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
    # 🔴 모든 `new Chart(` 호출이 각각 가드돼야 한다 — 단순 substring 존재 검사는 한 템플릿에
    # 차트가 2개 이상일 때 그중 하나만 가드해도 통과한다. dashboard.html 의 buildRepoTrendChart
    # (repos 모드 점수추이 차트)가 미가드로 이 갭을 통해 #921 회귀 가드를 통과 → 영구 공백 사고.
    # Every `new Chart(` must be guarded: substring presence passes even when only one of multiple
    # charts is guarded. dashboard.html's buildRepoTrendChart slipped through this gap (blank chart).
    n_charts = src.count("new Chart(")
    n_guards = src.count("if (typeof Chart === 'undefined') return;")
    assert n_guards >= n_charts, (
        f"{tpl}: `new Chart(` {n_charts}개 중 가드 {n_guards}개만 — 미가드 차트가 async/hx-boost "
        "로드 race 시 'Chart is not defined' throw 로 영구 공백"
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
    # onload 가 ready 핸들러를 호출 (존재 가드 동반 — onload 가 정의 전 발화해도 안전).
    # 한 onload 가 여러 ready 핸들러를 호출할 수 있으므로(예: dashboard 는 _dash + _repos 둘 다)
    # 끝의 닫는 따옴표를 요구하지 않고 '존재 가드 + 호출' 패턴만 검사한다.
    # onload invokes the ready handler (existence-guarded). A single onload may call multiple
    # ready handlers (dashboard calls both _dash and _repos), so we don't require a trailing quote.
    assert 'onload="' in src, f"{tpl}: vendor script onload 속성 누락 (async 로드 후 자동 페인트 불가)"
    assert f'if(document.{ready})document.{ready}()' in src, (
        f"{tpl}: vendor script onload 재빌드({ready}) 누락"
    )
    assert 'fetchpriority="high"' in src, f"{tpl}: chart vendor fetchpriority 다운로드 우선 hint 누락"
    # ready 핸들러는 no-anim 재빌드로 노출 (full-load 이중 호출 시 애니메이션 flash 방지)
    # ready handler exposed as a no-animation rebuild (avoids double-animation on full load)
    assert f"document.{ready} = function()" in src, (
        f"{tpl}: document.{ready} ready 핸들러 노출 누락"
    )


def test_dashboard_loads_chartjs_in_repos_mode():
    """dashboard.html 의 Chart.js vendor <script> 로드 조건이 repos 모드 점수추이 차트를 포함해야 한다.

    🔴 회귀(#921 후속): vendor <script> 가 overview `trend` 만 검사하면 repos 모드에서는 trend 가
    비어 Chart.js 가 로드조차 안 돼 repoTrendChart 가 영구 공백(`Chart is not defined`). repos 차트
    렌더 조건(_show_repos_trend)이 로드 조건에 OR 로 포함되고, onload 가 _reposChartReady 를 호출하며,
    repos 차트가 _reposChartReady 핸들러를 노출하는지 정적으로 봉인한다.
    dashboard.html must load Chart.js in repos mode too (vendor <script> condition includes the
    repos-mode chart), invoke _reposChartReady on onload, and expose that ready handler.
    """
    src = _read("src/templates/dashboard.html")
    assert "_show_repos_trend" in src, (
        "dashboard.html: Chart.js vendor 로드 조건에 repos 모드 차트 조건(_show_repos_trend) 누락 "
        "→ repos 모드 Chart.js 미로드 → repoTrendChart 영구 공백"
    )
    assert "document._reposChartReady = function()" in src, (
        "dashboard.html: _reposChartReady ready 핸들러 노출 누락 (repos 차트 async 로드 복구 불가)"
    )
    assert "if(document._reposChartReady)document._reposChartReady()" in src, (
        "dashboard.html: vendor onload 가 _reposChartReady 미호출 → repos 모드 async 로드 후 차트 미재빌드"
    )


def test_repo_detail_i18n_accessible_to_buildchart():
    """🔴 repo_detail.html: I18N 이 buildChart 에서 접근 가능(전역)해야 + onload race graceful 가드.

    운영 사고(2026-06-18, F12 `Uncaught ReferenceError: I18N is not defined at buildChart`):
    `I18N` 이 block2 IIFE 내 `const` 로 격리(repo_detail.html:860)돼 있어, block1 의 `buildChart`
    (:722)가 stats 배지에서 `I18N.chartAvg`(:751)를 참조하면 전역 스코프만 탐색 → IIFE const 가
    안 보여 ReferenceError → buildChart throw → `new Chart` 미도달 → scoreChart 영구 미표시.
    호출 경로: vendor chart.umd.min.js onload(:686) → _repoChartReady(:848) → buildChart.
    캐시 즉시 로드(라이브 immutable)가 onload 를 I18N 정의보다 앞당겨 트리거.

    수정 봉인: (1) I18N 을 window 전역으로 노출(IIFE const 격리 회귀 차단 — buildChart 가 전역
    탐색으로 접근) + (2) buildChart 가 I18N 미정의 시 graceful return(onload race: I18N 정의 전
    호출 시 throw 대신 skip, 이후 applyFilters→buildChart 가 정상 렌더).
    """
    src = _read("src/templates/repo_detail.html")
    # (1) repo 고유 전역 노출 — buildChart(별도 block)가 접근. IIFE-격리 const 단독이면 ReferenceError.
    assert "window._repoChartI18N" in src, (
        "repo_detail.html: I18N 을 repo 고유 전역(window._repoChartI18N)으로 미노출 → IIFE const "
        "격리 시 buildChart 의 I18N 참조가 ReferenceError (운영 scoreChart 미표시 사고)"
    )
    # 🔴 범용 window.I18N 전역 회귀 차단 — 다른 페이지(add_repo 의 var I18N 등)와 충돌해 hx-boost
    # 왕복 시 덮어써져 차트 재빌드가 깨진다(Codex P2). repo 고유 네임스페이스만 허용.
    # `window.I18N = {` 할당 패턴만 검사(주석의 'window.I18N' 언급은 허용)
    assert "window.I18N = {" not in src, (
        "repo_detail.html: 범용 window.I18N 전역 할당 회귀 → 다른 페이지 var I18N(add_repo.html:201)과 "
        "충돌(hx-boost 왕복 시 덮어쓰기, Codex P2). window._repoChartI18N 고유 네임스페이스 사용"
    )
    # (2) buildChart 가 고유 전역을 지역 참조 + onload race graceful (미정의 시 return)
    assert "var I18N = window._repoChartI18N" in src, (
        "repo_detail.html: buildChart 가 고유 전역(window._repoChartI18N) 지역 참조 누락 → 스코프/충돌 "
        "회귀. onload race(I18N block 정의 전 호출) 시 graceful return 동반 필요"
    )
