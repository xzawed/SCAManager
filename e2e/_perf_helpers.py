"""E2E + 성능 스크립트 공용 헬퍼 — LCP observer, 단일 측정, 통계 집계.
Shared helpers for E2E and perf scripts — LCP observer, single measurement, stats aggregation.
"""

# LCP PerformanceObserver 주입 스크립트 — page.add_init_script() 에 전달
# LCP PerformanceObserver injection script — pass to page.add_init_script()
LCP_INIT_JS = """
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


def measure_one(pg, url: str) -> dict:
    """단일 측정 — TTFB/FCP/LCP/DCL/Load(ms) + 느린 요청 목록 반환.
    Single measurement — returns TTFB/FCP/LCP/DCL/Load(ms) + slow request list.
    """
    slow: list[dict] = []

    def _on_finished(req):
        t = req.timing
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
                ttfb: Math.round((nav.responseStart || 0) - (nav.fetchStart || 0)),
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


def measure_page(pg, url: str, runs: int = 3) -> dict:
    """N회 측정 후 avg/min/max 통계 반환.
    Returns avg/min/max stats over N runs.
    """
    results = [measure_one(pg, url) for _ in range(runs)]
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
