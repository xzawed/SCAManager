"""E2E 성능 측정 테스트 — @pytest.mark.perf 마커로 선택 실행.
E2E performance tests — selectively run via @pytest.mark.perf.
"""
import pytest

THRESHOLDS = {
    "ttfb": 500,   # ms — 로컬 SQLite 기준 완화값 / relaxed for local SQLite
    "fcp":  1500,
    "lcp":  2500,
    "dcl":  1500,
    "load": 3000,
}

_LCP_INIT_JS = """
    window._perf_lcp = null;
    try {
        new PerformanceObserver((list) => {
            const entries = list.getEntries();
            if (entries.length > 0) {
                window._perf_lcp = entries[entries.length - 1].startTime;
            }
        }).observe({ type: 'largest-contentful-paint', buffered: true });
    } catch(e) {}
"""


def _measure_one(pg, url: str) -> dict:
    """단일 측정 — TTFB/FCP/LCP/DCL/Load(ms) + 느린 요청 목록 반환.
    Single measurement — TTFB/FCP/LCP/DCL/Load(ms) + slow request list.
    """
    slow: list[dict] = []

    def _on_finished(req):
        t = req.timing()
        dur = t.get("responseEnd", 0) - t.get("requestStart", 0)
        if dur > 500:
            slow.append({"url": req.url, "ms": round(dur)})

    pg.on("requestfinished", _on_finished)
    try:
        pg.goto(url, wait_until="networkidle", timeout=30_000)
        metrics = pg.evaluate("""() => {
            const nav = performance.getEntriesByType('navigation')[0] || {};
            const fcp = performance.getEntriesByType('paint')
                .find(e => e.name === 'first-contentful-paint');
            return {
                ttfb: Math.round((nav.responseStart || 0) - (nav.requestStart || 0)),
                dcl:  Math.round((nav.domContentLoadedEventEnd || 0) - (nav.startTime || 0)),
                load: Math.round((nav.loadEventEnd || 0) - (nav.startTime || 0)),
                fcp:  fcp ? Math.round(fcp.startTime) : null,
                lcp:  (typeof window._perf_lcp === 'number')
                          ? Math.round(window._perf_lcp) : null,
            };
        }""")
        metrics["slow_requests"] = slow[:]
        return metrics
    finally:
        pg.remove_listener("requestfinished", _on_finished)


def _measure_page(pg, url: str, runs: int = 3) -> dict:
    """N회 측정 후 avg/min/max 통계 반환.
    Returns avg/min/max stats over N runs.
    """
    results = [_measure_one(pg, url) for _ in range(runs)]
    stats: dict = {}
    for key in ("ttfb", "fcp", "lcp", "dcl", "load"):
        vals = [r[key] for r in results if r.get(key) is not None]
        stats[key] = {
            "avg": round(sum(vals) / len(vals)) if vals else None,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
        }
    stats["slow_requests"] = [req for r in results for req in r.get("slow_requests", [])]
    return stats


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def perf_page(page):
    """LCP observer가 주입된 일반 page fixture.
    Standard page fixture with LCP PerformanceObserver injected.
    """
    page.add_init_script(_LCP_INIT_JS)
    return page


@pytest.fixture
def perf_seeded_page(seeded_page):
    """LCP observer가 주입된 seeded page fixture.
    Seeded page fixture with LCP PerformanceObserver injected.
    """
    seeded_page.add_init_script(_LCP_INIT_JS)
    return seeded_page


@pytest.fixture
def analysis_page(browser_instance, live_server, seeded_analysis):
    """분석 상세 페이지용 page fixture — (page, analysis_id) 반환.
    Page fixture for analysis detail — yields (page, analysis_id).
    """
    context = browser_instance.new_context(base_url=live_server)
    pg = context.new_page()
    pg.add_init_script(_LCP_INIT_JS)
    yield pg, seeded_analysis
    context.close()


# ── Public pages ──────────────────────────────────────────────────────────

@pytest.mark.perf
def test_login_ttfb(perf_page, base_url):
    """/login 초기 서버 응답 시간 < 500ms."""
    stats = _measure_page(perf_page, f"{base_url}/login")
    assert stats["ttfb"]["avg"] is not None
    assert stats["ttfb"]["avg"] < THRESHOLDS["ttfb"], (
        f"TTFB {stats['ttfb']['avg']}ms >= {THRESHOLDS['ttfb']}ms"
    )


@pytest.mark.perf
def test_login_load(perf_page, base_url):
    """/login 전체 로드 시간 < 3000ms."""
    stats = _measure_page(perf_page, f"{base_url}/login")
    assert stats["load"]["avg"] is not None
    assert stats["load"]["avg"] < THRESHOLDS["load"], (
        f"Load {stats['load']['avg']}ms >= {THRESHOLDS['load']}ms"
    )


@pytest.mark.perf
def test_root_fcp(perf_page, base_url):
    """/ (landing) FCP < 1500ms."""
    stats = _measure_page(perf_page, f"{base_url}/")
    if stats["fcp"]["avg"] is not None:
        assert stats["fcp"]["avg"] < THRESHOLDS["fcp"], (
            f"FCP {stats['fcp']['avg']}ms >= {THRESHOLDS['fcp']}ms"
        )


@pytest.mark.perf
def test_root_load(perf_page, base_url):
    """/ (landing) Load < 3000ms."""
    stats = _measure_page(perf_page, f"{base_url}/")
    assert stats["load"]["avg"] is not None
    assert stats["load"]["avg"] < THRESHOLDS["load"], (
        f"Load {stats['load']['avg']}ms >= {THRESHOLDS['load']}ms"
    )


@pytest.mark.perf
def test_health_ttfb(perf_page, base_url):
    """/health API 응답 시간 < 300ms."""
    stats = _measure_page(perf_page, f"{base_url}/health")
    assert stats["ttfb"]["avg"] is not None
    assert stats["ttfb"]["avg"] < 300, (
        f"/health TTFB {stats['ttfb']['avg']}ms >= 300ms"
    )


# ── Auth-bypass pages ─────────────────────────────────────────────────────

@pytest.mark.perf
def test_dashboard_ttfb(perf_page, base_url):
    """/dashboard TTFB < 500ms."""
    stats = _measure_page(perf_page, f"{base_url}/dashboard")
    assert stats["ttfb"]["avg"] is not None
    assert stats["ttfb"]["avg"] < THRESHOLDS["ttfb"], (
        f"TTFB {stats['ttfb']['avg']}ms >= {THRESHOLDS['ttfb']}ms"
    )


@pytest.mark.perf
def test_dashboard_lcp(perf_page, base_url):
    """/dashboard LCP < 2500ms."""
    stats = _measure_page(perf_page, f"{base_url}/dashboard")
    if stats["lcp"]["avg"] is not None:
        assert stats["lcp"]["avg"] < THRESHOLDS["lcp"], (
            f"LCP {stats['lcp']['avg']}ms >= {THRESHOLDS['lcp']}ms"
        )


@pytest.mark.perf
def test_add_repo_ttfb(perf_page, base_url):
    """/repos/add TTFB < 500ms."""
    stats = _measure_page(perf_page, f"{base_url}/repos/add")
    assert stats["ttfb"]["avg"] is not None
    assert stats["ttfb"]["avg"] < THRESHOLDS["ttfb"], (
        f"TTFB {stats['ttfb']['avg']}ms >= {THRESHOLDS['ttfb']}ms"
    )


# ── Seeded repo pages ─────────────────────────────────────────────────────

@pytest.mark.perf
def test_repo_detail_ttfb(perf_seeded_page, base_url):
    """/repos/owner%2Ftestrepo TTFB < 500ms."""
    stats = _measure_page(perf_seeded_page, f"{base_url}/repos/owner%2Ftestrepo")
    assert stats["ttfb"]["avg"] is not None
    assert stats["ttfb"]["avg"] < THRESHOLDS["ttfb"], (
        f"TTFB {stats['ttfb']['avg']}ms >= {THRESHOLDS['ttfb']}ms"
    )


@pytest.mark.perf
def test_repo_detail_load(perf_seeded_page, base_url):
    """/repos/owner%2Ftestrepo Load < 3000ms."""
    stats = _measure_page(perf_seeded_page, f"{base_url}/repos/owner%2Ftestrepo")
    assert stats["load"]["avg"] is not None
    assert stats["load"]["avg"] < THRESHOLDS["load"], (
        f"Load {stats['load']['avg']}ms >= {THRESHOLDS['load']}ms"
    )


@pytest.mark.perf
def test_repo_insights_load(perf_seeded_page, base_url):
    """/repos/owner%2Ftestrepo/insights Load < 3000ms."""
    stats = _measure_page(
        perf_seeded_page,
        f"{base_url}/repos/owner%2Ftestrepo/insights",
    )
    assert stats["load"]["avg"] is not None
    assert stats["load"]["avg"] < THRESHOLDS["load"], (
        f"Load {stats['load']['avg']}ms >= {THRESHOLDS['load']}ms"
    )


# ── Seeded analysis pages ─────────────────────────────────────────────────

@pytest.mark.perf
def test_analysis_detail_load(analysis_page, base_url):
    """/repos/owner%2Ftestrepo/analyses/{id} Load < 3000ms."""
    pg, analysis_id = analysis_page
    url = f"{base_url}/repos/owner%2Ftestrepo/analyses/{analysis_id}"
    stats = _measure_page(pg, url)
    assert stats["load"]["avg"] is not None
    assert stats["load"]["avg"] < THRESHOLDS["load"], (
        f"Load {stats['load']['avg']}ms >= {THRESHOLDS['load']}ms"
    )
