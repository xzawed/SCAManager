#!/usr/bin/env python3
"""SCAManager 페이지 성능 측정 스크립트 — 로컬 + 운영 양쪽 측정.
SCAManager page performance measurement script — measures both local and production.

Usage:
    python scripts/perf_measure.py               # 로컬 + 운영 / local + production
    python scripts/perf_measure.py --local-only  # 로컬만 / local only
    python scripts/perf_measure.py --prod-only   # 운영만 / production only
"""
import argparse
import asyncio
import importlib
import json
import os
import pkgutil
import signal
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed.")
    print("Run: pip install playwright && playwright install chromium")
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────

# E2E 포트(8001)와 구분 — 동시 실행 시 충돌 방지
# Different from E2E port 8001 — prevents conflict during concurrent runs.
LOCAL_PORT = 8002
LOCAL_URL = f"http://127.0.0.1:{LOCAL_PORT}"
PROD_URL = os.environ.get("PERF_PROD_URL", "https://scamanager-production.up.railway.app")
# 운영 API 키 — X-Api-Key 헤더로 전달 (없으면 401 예상)
# Production API key — passed as X-Api-Key header (401 expected if absent).
PERF_API_KEY = os.environ.get("PERF_API_KEY", "")

THRESHOLDS_LOCAL = {
    "ttfb": 500,
    "health_ttfb": 300,   # /health 전용 — e2e/test_performance.py THRESHOLDS["health_ttfb"]과 동기
    # /health-specific — kept in sync with e2e/test_performance.py THRESHOLDS["health_ttfb"]
    "fcp": 1500, "lcp": 2500, "dcl": 1500, "load": 3000,
}
THRESHOLDS_PROD = {"ttfb": 300, "fcp": 1500, "lcp": 2500, "dcl": 1500, "load": 3000}

# 로컬 테스트용 더미 API 키 / Dummy API key for local test server
_LOCAL_API_KEY = "perf-api-key"

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

# ── DB / Server setup ──────────────────────────────────────────────────────


def _setup_db(db_path: str) -> None:
    """SQLite DB 생성 — ORM 스키마 직접 적용.
    Create SQLite DB with ORM schema applied directly (bypasses Alembic SQLite issues).
    """
    from sqlalchemy import create_engine  # noqa: PLC0415
    from src.database import Base  # noqa: PLC0415
    import src.models as _models_pkg  # noqa: PLC0415

    for _, name, _ in pkgutil.iter_modules(_models_pkg.__path__):
        importlib.import_module(f"src.models.{name}")

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()


def _seed_data(db_path: str) -> int:
    """User + Repo + Analysis 시딩 — analysis_id 반환.
    Seed User + Repo + Analysis records — returns analysis_id.
    """
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT OR IGNORE INTO users
                (id, github_id, github_login, github_access_token, email, display_name, created_at)
            VALUES
                (1, 'perf-uid', 'perf-tester', 'gho_perf',
                 'perf@test.com', 'Perf Test User', datetime('now'))
        """))
        conn.execute(text("""
            INSERT OR IGNORE INTO repositories
                (full_name, user_id, webhook_secret, created_at)
            VALUES ('owner/testrepo', 1, 'perf-secret', datetime('now'))
        """))
        conn.commit()
        repo_id = conn.execute(text(
            "SELECT id FROM repositories WHERE full_name='owner/testrepo'"
        )).fetchone()[0]
        conn.execute(text("""
            INSERT OR IGNORE INTO analyses
                (repo_id, commit_sha, commit_message, score, grade, result, author_login, created_at)
            VALUES
                (:rid, 'perf-sha-001', 'perf: standalone script seed',
                 85, 'B', :res, 'perf-tester', datetime('now'))
        """), {"rid": repo_id, "res": json.dumps({"summary": "perf test"})})
        conn.commit()
        analysis_row = conn.execute(text(
            "SELECT id FROM analyses WHERE repo_id=:rid AND commit_sha='perf-sha-001'"
        ), {"rid": repo_id}).fetchone()
        if analysis_row is None:
            raise RuntimeError("_seed_data: analysis row not found after INSERT")
    engine.dispose()
    return analysis_row[0]


def _start_local_server(db_path: str):
    """uvicorn 서버를 별도 스레드에서 시작하고 server 객체를 반환한다.
    Start uvicorn server in a background thread and return the server object.
    """
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "GITHUB_WEBHOOK_SECRET": "perf-test-secret",
        "GITHUB_TOKEN": "perf-test-token",
        "TELEGRAM_BOT_TOKEN": "1234567890:AAperftest",
        "TELEGRAM_CHAT_ID": "-100000000",
        "API_KEY": _LOCAL_API_KEY,
        "GITHUB_CLIENT_ID": "perf-github-client-id",
        "GITHUB_CLIENT_SECRET": "perf-github-client-secret",
        "SESSION_SECRET": "perf-session-secret-32chars-long!!",
    })

    # pydantic-settings 캐시 무효화 / Invalidate pydantic-settings cache.
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("src."):
            del sys.modules[mod_name]

    import uvicorn  # noqa: PLC0415
    from src.main import app  # noqa: PLC0415
    from src.auth.session import require_login, CurrentUser  # noqa: PLC0415

    _user = CurrentUser(
        id=1,
        github_login="perf-tester",
        email="perf@test.com",
        display_name="Perf Test User",
        plaintext_token="gho_perf_test_token",
    )
    app.dependency_overrides[require_login] = lambda: _user

    config = uvicorn.Config(app, host="127.0.0.1", port=LOCAL_PORT, log_level="error")
    server = uvicorn.Server(config)

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()

    threading.Thread(target=_run, daemon=True).start()

    # 서버 준비 대기 (최대 30초) / Wait for server readiness (up to 30s).
    for _ in range(60):
        try:
            r = requests.get(f"{LOCAL_URL}/health", timeout=1)
            if r.status_code == 200:
                return server
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)

    server.should_exit = True
    raise RuntimeError(f"Local server failed to start on port {LOCAL_PORT} within 30s")


# ── Measurement helpers ────────────────────────────────────────────────────

def _measure_one(pg, url: str) -> dict:
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


def _http_ttfb(url: str, *, headers: dict | None = None, allow_redirects: bool = True) -> dict:
    """HTTP TTFB 전용 측정 — requests 라이브러리, 3회 평균.
    TTFB-only measurement via requests library, 3-run average.

    stream=True + response.elapsed 로 첫 응답 헤더 수신 시점만 측정 (strict TTFB).
    Uses stream=True + response.elapsed to measure only the first response header receipt (strict TTFB).
    """
    times: list[float] = []
    status = None
    with requests.Session() as session:
        # 워밍업 — TCP 연결 수립, Windows IPv6→IPv4 DNS fallback 지연 제거, 측정값 제외
        # Warmup — establish TCP connection, eliminates Windows IPv6→IPv4 DNS fallback latency, excluded from measurements
        try:
            session.get(url, headers=headers or {}, allow_redirects=allow_redirects, timeout=10)
        except Exception:  # noqa: BLE001
            pass
        for _ in range(3):
            try:
                # stream=True: 응답 헤더만 수신 후 반환 — body 다운로드 제외 (strict TTFB)
                # stream=True: returns after receiving headers only — excludes body download (strict TTFB)
                with session.get(
                    url, headers=headers or {}, allow_redirects=allow_redirects,
                    timeout=10, stream=True,
                ) as r:
                    times.append(r.elapsed.total_seconds() * 1000)
                    status = r.status_code
            except Exception:  # noqa: BLE001
                pass
    avg = round(sum(times) / len(times)) if times else None
    return {
        "ttfb": {
            "avg": avg,
            "min": round(min(times)) if times else None,
            "max": round(max(times)) if times else None,
        },
        "fcp": {}, "lcp": {}, "dcl": {}, "load": {},
        "slow_requests": [],
        "status": status,
    }


# ── Report generation ──────────────────────────────────────────────────────

def _is_health_page(page: str) -> bool:
    """/health 페이지 여부 정규화 판별 (쿼리 파라미터·trailing slash 무시).
    Check if page is /health — normalises path (ignores query params and trailing slash).
    """
    return urlsplit(str(page)).path.rstrip("/") == "/health"


def _fmt(v: int | None) -> str:
    """ms 값을 사람이 읽기 좋은 문자열로 변환 / Format ms value for humans."""
    if v is None:
        return "—"
    return f"{v}ms" if v < 1000 else f"{v / 1000:.1f}s"


def _verdict(metrics: dict, thresholds: dict, page: str = "") -> str:
    """임계값 초과 시 🔴, 이내 시 ✅ 반환 — /health 는 health_ttfb 임계값 적용.
    Return 🔴 if any threshold exceeded, else ✅ — /health uses health_ttfb threshold.
    """
    for key in ("ttfb", "fcp", "lcp", "dcl", "load"):
        avg = (metrics.get(key) or {}).get("avg")
        if avg is None:
            continue
        # /health 페이지 TTFB 는 health_ttfb 전용 임계값 적용 (더 엄격한 300ms)
        # For /health page TTFB use health_ttfb threshold (stricter 300ms)
        if key == "ttfb" and _is_health_page(page) and "health_ttfb" in thresholds:
            thr = thresholds["health_ttfb"]
        else:
            thr = thresholds.get(key, 9_999)
        if avg > thr:
            return "🔴"
    return "✅"


def _render_table(results: list[dict], thresholds: dict) -> str:
    """결과 목록을 Markdown 표로 변환 / Convert result list to a Markdown table."""
    rows = [
        "| 페이지 | TTFB avg | FCP avg | LCP avg | DCL avg | Load avg | 판정 |",
        "|--------|----------|---------|---------|---------|----------|------|",
    ]
    for r in results:
        m = r["metrics"]
        if r.get("auth_only"):
            rows.append(
                f"| {r['page']} | {_fmt((m.get('ttfb') or {}).get('avg'))} "
                f"| — | — | — | — | *(auth-only)* |"
            )
        else:
            rows.append(
                f"| {r['page']} "
                f"| {_fmt((m.get('ttfb') or {}).get('avg'))} "
                f"| {_fmt((m.get('fcp') or {}).get('avg'))} "
                f"| {_fmt((m.get('lcp') or {}).get('avg'))} "
                f"| {_fmt((m.get('dcl') or {}).get('avg'))} "
                f"| {_fmt((m.get('load') or {}).get('avg'))} "
                f"| {_verdict(m, thresholds, page=r['page'])} |"
            )
    return "\n".join(rows)


def _render_markdown(
    local_results: list[dict] | None,
    prod_results: list[dict] | None,
) -> str:
    """전체 Markdown 리포트 생성.
    Generate full Markdown performance report.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# SCAManager 페이지 성능 리포트",
        f"측정일시: {ts} | 반복: 3회 | 브라우저: Chromium headless",
        "",
    ]

    if local_results:
        lines += [
            "## 🏠 로컬 E2E 서버 (SQLite)",
            "",
            _render_table(local_results, THRESHOLDS_LOCAL),
            "",
        ]

    if prod_results:
        lines += [
            "## 🌐 운영 서버 (Railway)",
            "",
            _render_table(prod_results, THRESHOLDS_PROD),
            "",
        ]

    # 로컬 vs 운영 비교 표 (양쪽 결과 모두 있을 때만) / Local vs prod comparison table (only when both present)
    if local_results and prod_results:
        local_map = {r["page"]: r for r in local_results}
        prod_map = {r["page"]: r for r in prod_results}
        common_pages = [p for p in local_map if p in prod_map]
        if common_pages:
            cmp_rows = [
                "| 페이지 | 로컬 Load | 운영 Load | 배율 |",
                "|--------|----------|----------|------|",
            ]
            for page in common_pages:
                local_load = (local_map[page]["metrics"].get("load") or {}).get("avg")
                prod_load = (prod_map[page]["metrics"].get("load") or {}).get("avg")
                if local_load is not None and prod_load is not None and local_load > 0:
                    ratio = f"{prod_load / local_load:.1f}x"
                else:
                    ratio = "—"
                cmp_rows.append(
                    f"| {page} | {_fmt(local_load)} | {_fmt(prod_load)} | {ratio} |"
                )
            lines += [
                "## 📊 로컬 vs 운영 비교",
                "",
            ] + cmp_rows + [""]

    # 임계값 초과 항목 / Threshold violations
    violations = []
    for r in (local_results or []):
        if r.get("auth_only"):
            continue
        m = r["metrics"]
        for key, thr in THRESHOLDS_LOCAL.items():
            # health_ttfb 는 TTFB 키에 /health 페이지 한정 적용 — 중복 위반 방지
            # health_ttfb applies only to /health TTFB — skip double-counting
            if key == "health_ttfb":
                if not _is_health_page(r["page"]):
                    continue
                avg = (m.get("ttfb") or {}).get("avg")
                report_key = "health_ttfb"
            else:
                if key == "ttfb" and _is_health_page(r["page"]):
                    continue  # /health TTFB handled by health_ttfb entry above
                avg = (m.get(key) or {}).get("avg")
                report_key = key
            if avg is not None and avg > thr:
                violations.append(
                    f"- 🏠 {r['page']} **{report_key.upper()}**: {_fmt(avg)} (>{_fmt(thr)})"
                )
    for r in (prod_results or []):
        if r.get("auth_only"):
            continue
        m = r["metrics"]
        for key, thr in THRESHOLDS_PROD.items():
            avg = (m.get(key) or {}).get("avg")
            if avg is not None and avg > thr:
                violations.append(
                    f"- 🌐 {r['page']} **{key.upper()}**: {_fmt(avg)} (>{_fmt(thr)})"
                )

    if violations:
        lines += ["## 🔴 임계값 초과 항목", ""] + violations + [""]
    else:
        lines += ["## ✅ 모든 페이지 임계값 이내", ""]

    # 느린 API 엔드포인트 / Slow API endpoints
    slow_all = []
    for r in (local_results or []) + (prod_results or []):
        for req in r.get("metrics", {}).get("slow_requests", []):
            slow_all.append(f"| {req['url']} | {req['ms']}ms |")

    if slow_all:
        lines += [
            "## 🔍 느린 API 엔드포인트 (> 500ms)",
            "",
            "| 엔드포인트 | 평균 응답 |",
            "|-----------|---------|",
        ] + slow_all + [""]

    return "\n".join(lines)


# ── Page definitions ───────────────────────────────────────────────────────

def _local_pages(analysis_id: int) -> list[dict]:
    """로컬 측정 대상 페이지 목록 / List of pages to measure locally."""
    return [
        {"page": "/login", "url": f"{LOCAL_URL}/login"},
        {"page": "/", "url": f"{LOCAL_URL}/"},
        {"page": "/health", "url": f"{LOCAL_URL}/health"},
        {"page": "/dashboard", "url": f"{LOCAL_URL}/dashboard"},
        {"page": "/repos/add", "url": f"{LOCAL_URL}/repos/add"},
        {"page": "/repos/owner%2Ftestrepo", "url": f"{LOCAL_URL}/repos/owner%2Ftestrepo"},
        {"page": "/repos/owner%2Ftestrepo/insights", "url": f"{LOCAL_URL}/repos/owner%2Ftestrepo/insights"},
        {
            "page": f"/repos/.../analyses/{analysis_id}",
            "url": f"{LOCAL_URL}/repos/owner%2Ftestrepo/analyses/{analysis_id}",
        },
        {"page": "/repos/owner%2Ftestrepo/settings", "url": f"{LOCAL_URL}/repos/owner%2Ftestrepo/settings"},
        {"page": "/api/repos", "url": f"{LOCAL_URL}/api/repos", "api_only": True},
        {
            "page": "/api/repos/owner%2Ftestrepo/report",
            "url": f"{LOCAL_URL}/api/repos/owner%2Ftestrepo/report",
            "api_only": True,
        },
    ]


def _prod_pages() -> list[dict]:
    """운영 측정 대상 페이지 목록 / List of production pages to measure."""
    return [
        # 공개 페이지 — 전체 측정 / Public pages — full measurement
        {"page": "/login", "url": f"{PROD_URL}/login", "auth_only": False},
        {"page": "/", "url": f"{PROD_URL}/", "auth_only": False},
        {"page": "/health", "url": f"{PROD_URL}/health", "auth_only": False},
        # 인증 필요 — TTFB only / Auth-required — TTFB only
        {"page": "/dashboard", "url": f"{PROD_URL}/dashboard", "auth_only": True},
        {"page": "/repos/add", "url": f"{PROD_URL}/repos/add", "auth_only": True},
        # API 엔드포인트 — X-Api-Key 헤더, TTFB only / API endpoints — X-Api-Key header, TTFB only
        {"page": "/api/repos", "url": f"{PROD_URL}/api/repos", "api_only": True},
        {
            "page": "/api/repos/owner%2Ftestrepo/report",
            "url": f"{PROD_URL}/api/repos/owner%2Ftestrepo/report",
            "api_only": True,
        },
    ]


# ── Main ───────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    """CLI 인수 파싱 / Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="SCAManager 페이지 성능 측정")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--local-only", action="store_true", help="로컬 측정만")
    group.add_argument("--prod-only", action="store_true", help="운영 측정만")
    return parser.parse_args()


def main() -> None:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """성능 측정 메인 진입점 / Main entry point for performance measurement."""
    args = _parse_args()
    run_local = not args.prod_only
    run_prod = not args.local_only

    server = None
    db_file = None
    local_results: list[dict] = []
    prod_results: list[dict] = []

    def _cleanup(signum=None, frame=None):  # noqa: ARG001
        if server:
            server.should_exit = True
        if db_file and os.path.exists(db_file):
            try:
                os.unlink(db_file)
            except OSError as exc:
                print(f"[WARN] Failed to remove temporary DB file '{db_file}': {exc}", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    try:
        if run_local:
            print("▶ 로컬 서버 시작 중... / Starting local server...")
            # fd를 즉시 닫아 Windows SQLite 잠금 방지 / Close fd immediately to avoid SQLite file lock on Windows
            fd, db_path = tempfile.mkstemp(suffix=".db", prefix="perf_")
            os.close(fd)
            db_file = db_path
            _setup_db(db_path)
            analysis_id = _seed_data(db_path)
            server = _start_local_server(db_path)
            print(f"  ✓ 로컬 서버 준비 (port {LOCAL_PORT})")

            pages_to_measure = _local_pages(analysis_id)
            browser_pages = [p for p in pages_to_measure if not p.get("api_only")]
            api_pages_local = [p for p in pages_to_measure if p.get("api_only")]

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()
                pg = ctx.new_page()
                pg.add_init_script(_LCP_INIT_JS)

                for page_def in browser_pages:
                    page_label = str(page_def.get("page", "")).replace("\n", "").replace("\r", "")
                    print(f"  측정 중: {page_label}")
                    metrics = _measure_page(pg, page_def["url"])
                    local_results.append({"page": page_def["page"], "metrics": metrics})

                ctx.close()
                browser.close()
            for idx, page_def in enumerate(api_pages_local, start=1):
                print(f"  측정 중 (API TTFB) [{idx}/{len(api_pages_local)}]")
                print(f"  측정 중 (API TTFB): {page_def['page']}")
                metrics = _http_ttfb(page_def["url"], headers={"X-Api-Key": page_def.get("api_key", _LOCAL_API_KEY)})
                local_results.append({"page": page_def["page"], "metrics": metrics, "auth_only": True})

            server.should_exit = True
            print("  ✓ 로컬 서버 종료")

        if run_prod:
            print(f"\n▶ 운영 서버 측정 중... / Measuring production: {PROD_URL}")
            prod_pages_all = _prod_pages()
            public_pages = [p for p in prod_pages_all if not p.get("auth_only") and not p.get("api_only")]
            auth_pages = [p for p in prod_pages_all if p.get("auth_only")]
            api_pages_prod = [p for p in prod_pages_all if p.get("api_only")]

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()
                pg = ctx.new_page()
                pg.add_init_script(_LCP_INIT_JS)

                for page_def in public_pages:
                    print(f"  측정 중: {page_def['page']}")
                    metrics = _measure_page(pg, page_def["url"])
                    prod_results.append({"page": page_def["page"], "metrics": metrics})

                ctx.close()
                browser.close()

            for page_def in auth_pages:
                print(f"  측정 중 (TTFB only): {page_def['page']}")
                metrics = _http_ttfb(page_def["url"], allow_redirects=False)
                prod_results.append({
                    "page": page_def["page"],
                    "metrics": metrics,
                    "auth_only": True,
                })

            for page_def in api_pages_prod:
                print(f"  측정 중 (API TTFB): {page_def['page']}")
                metrics = _http_ttfb(page_def["url"], headers={"X-Api-Key": PERF_API_KEY})
                prod_results.append({"page": page_def["page"], "metrics": metrics, "auth_only": True})

        report = _render_markdown(
            local_results if run_local else None,
            prod_results if run_prod else None,
        )

        ts = datetime.now().strftime("%Y-%m-%d-%H%M")
        # 스크립트 위치 기준으로 프로젝트 루트 결정 / Resolve project root from script location
        report_path = Path(__file__).parent.parent / "docs" / "reports" / f"perf-{ts}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"\n✅ 리포트 저장: {report_path}")
        print("\n" + report)

    finally:
        if server:
            server.should_exit = True
        if db_file and os.path.exists(db_file):
            try:
                os.unlink(db_file)
            except OSError as exc:
                print(f"[WARN] Failed to remove temporary DB file '{db_file}': {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
