"""E2E 성능 측정 테스트 — @pytest.mark.perf 마커로 선택 실행.
E2E performance tests — selectively run via @pytest.mark.perf.
"""
import pytest

from e2e._perf_helpers import LCP_INIT_JS as _LCP_INIT_JS
from e2e._perf_helpers import measure_one as _measure_one
from e2e._perf_helpers import measure_page as _measure_page

THRESHOLDS = {
    "ttfb": 500,   # ms — 로컬 SQLite 기준 완화값 / relaxed for local SQLite
    "fcp":  1500,
    "lcp":  2500,
    "dcl":  1500,
    "load": 3000,
    "health_ttfb": 300,   # /health endpoint — tighter TTFB budget / tighter for health check
}


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
    assert stats["fcp"]["avg"] is not None, "FCP was not captured by PerformanceObserver"
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
def test_health_ttfb(base_url):
    """/health API 응답 시간 < 300ms — requests Session으로 직접 측정.
    /health TTFB measured with requests.Session — Playwright overhead unnecessary.
    """
    # Session 재사용으로 TCP 연결 유지 — Windows localhost DNS fallback 오버헤드 제거
    # Session reuse keeps TCP alive — eliminates Windows localhost IPv6→IPv4 DNS fallback latency.
    times = []
    with requests.Session() as session:
        # 워밍업 요청 — 첫 연결 오버헤드 제외
        # Warmup request to establish connection and eliminate cold-start latency.
        session.get(f"{base_url}/health", timeout=5)
        for _ in range(3):
            start = time.perf_counter()
            resp = session.get(f"{base_url}/health", timeout=5)
            elapsed_ms = round((time.perf_counter() - start) * 1000)
            assert resp.status_code == 200
            times.append(elapsed_ms)
    avg_ms = round(sum(times) / len(times))
    assert avg_ms < THRESHOLDS["health_ttfb"], (
        f"/health avg {avg_ms}ms >= {THRESHOLDS['health_ttfb']}ms"
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
    assert stats["lcp"]["avg"] is not None, "LCP was not captured by PerformanceObserver"
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
