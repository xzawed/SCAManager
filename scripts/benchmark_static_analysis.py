"""G.6 Go/No-Go 벤치마크 — _run_static_analysis 직렬 기준선 측정.
G.6 Go/No-Go benchmark — serial baseline measurement for _run_static_analysis.

실행 방법:
    python scripts/benchmark_static_analysis.py

출력: 콘솔 요약 + docs/reports/YYYY-MM-DD-static-analysis-baseline.md
Output: console summary + docs/reports/YYYY-MM-DD-static-analysis-baseline.md

Go 조건  : 평균 ≥ 60s → Phase I(G.6 병렬화) 착수
Go condition : mean ≥ 60s → proceed to Phase I (G.6 parallelisation)
No-Go 조건: 평균 < 20s → Phase I 불필요
No-Go condition: mean < 20s → parallelisation unnecessary
중간 (20-60s): ROI 계산 후 재판정
Borderline (20-60s): recalculate ROI before deciding.
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# src 패키지를 찾을 수 있도록 프로젝트 루트를 경로에 추가
# Add the project root to sys.path so the src package can be found.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "bench")
os.environ.setdefault("GITHUB_TOKEN", "ghp_bench")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:BENCH")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100000")

import psutil  # noqa: E402 — 환경변수 주입 이후

from src.github_client.diff import ChangedFile  # noqa: E402
from src.worker.pipeline import _run_static_analysis  # noqa: E402

RUNS = 3  # 페이로드당 반복 횟수 / Repetitions per payload

PYTHON_FILE = """\
import os
import sys

def calculate(a, b):
    password = "secret123"  # S105
    result = a + b
    unused = 42  # F841
    return result

class MyClass:
    def method(self, x):
        if x == True:  # E712
            return x
        return None

def risky():
    import subprocess
    cmd = input("cmd: ")
    subprocess.call(cmd, shell=True)  # B602
"""

JS_FILE = """\
const express = require('express');
const app = express();
var password = 'hardcoded';  // semgrep detects

app.get('/user', function(req, res) {
    var id = req.query.id;
    var sql = "SELECT * FROM users WHERE id = " + id;  // sqli
    res.send(sql);
});

eval(req.body.code);  // dangerous
"""

MIXED_FILE = """\
#!/bin/bash
# shell script
echo "Processing: $1"
eval "$1"  # shellcheck SC2091
rm -rf /tmp/data
"""


def _make_py_files(n: int) -> list[ChangedFile]:
    return [ChangedFile(filename=f"src/module_{i}.py", content=PYTHON_FILE, patch="") for i in range(n)]


def _make_js_files(n: int) -> list[ChangedFile]:
    return [ChangedFile(filename=f"app/service_{i}.js", content=JS_FILE, patch="") for i in range(n)]


def _make_sh_files(n: int) -> list[ChangedFile]:
    return [ChangedFile(filename=f"scripts/run_{i}.sh", content=MIXED_FILE, patch="") for i in range(n)]


PAYLOADS = {
    "Python-heavy (10 .py)": _make_py_files(10),
    "JS+semgrep (5 .js)": _make_js_files(5),
    "Mixed (8 .py + 4 .js + 3 .sh)": _make_py_files(8) + _make_js_files(4) + _make_sh_files(3),
}


def _sample_rss_until(stop_event: threading.Event, samples: list[int]) -> None:
    proc = psutil.Process(os.getpid())
    while not stop_event.is_set():
        try:
            samples.append(proc.memory_info().rss)
        except psutil.NoSuchProcess:
            break
        time.sleep(1)


async def _measure_one(files: list[ChangedFile]) -> tuple[float, int]:
    """단일 실행: (elapsed_seconds, peak_rss_mb).
    Single run: returns (elapsed_seconds, peak_rss_mb).
    """
    stop = threading.Event()
    rss_samples: list[int] = []
    sampler = threading.Thread(target=_sample_rss_until, args=(stop, rss_samples), daemon=True)
    sampler.start()
    t0 = time.perf_counter()
    await _run_static_analysis(files)
    elapsed = time.perf_counter() - t0
    stop.set()
    sampler.join(timeout=3)
    peak_mb = max(rss_samples, default=0) // (1024 * 1024)
    return elapsed, peak_mb


async def run_benchmark() -> dict[str, dict]:
    results: dict[str, dict] = {}
    for label, files in PAYLOADS.items():
        print(f"\n[{label}] ({len(files)} files, {RUNS} runs)...")
        times: list[float] = []
        peaks: list[int] = []
        for i in range(RUNS):
            elapsed, peak = await _measure_one(files)
            times.append(elapsed)
            peaks.append(peak)
            print(f"  run {i+1}: {elapsed:.2f}s  peak RSS {peak} MB")
        avg = sum(times) / len(times)
        results[label] = {
            "files": len(files),
            "runs": times,
            "avg_s": avg,
            "peak_mb": max(peaks),
        }
        print(f"  avg={avg:.2f}s  peak_rss={max(peaks)}MB")
    return results


def _verdict(avg_s: float) -> str:
    if avg_s >= 60:
        return "GO — Phase I(G.6 병렬화) 착수"
    if avg_s < 20:
        return "NO-GO — 병렬화 불필요, 현 속도 충분"
    return "BORDERLINE — ROI 계산 후 재판정 필요"


def _write_report(results: dict[str, dict]) -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = ROOT / "docs" / "reports" / f"{date_str}-static-analysis-baseline.md"

    overall_avg = sum(r["avg_s"] for r in results.values()) / len(results)
    verdict = _verdict(overall_avg)

    lines = [
        f"# 정적분석 직렬 기준선 벤치마크 ({date_str})",
        "",
        "**목적**: G.6 병렬화(Phase I) 착수 여부 판정을 위한 실측 기준선 수집.",
        "",
        "## 측정 환경",
        "",
        f"- **OS**: {sys.platform}",
        f"- **Python**: {sys.version.split()[0]}",
        f"- **반복 횟수**: {RUNS}회 / 페이로드",
        f"- **측정 날짜**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **psutil**: {psutil.__version__}",
        "",
        "## 결과 요약",
        "",
        "| 페이로드 | 파일 수 | 평균 (s) | 최대 RSS (MB) |",
        "|---------|--------|---------|-------------|",
    ]

    for label, r in results.items():
        lines.append(f"| {label} | {r['files']} | {r['avg_s']:.2f} | {r['peak_mb']} |")

    lines += [
        "",
        f"**전체 평균**: {overall_avg:.2f}s",
        "",
        "## 개별 실행 로그",
        "",
    ]

    for label, r in results.items():
        runs_str = " / ".join(f"{t:.2f}s" for t in r["runs"])
        lines.append(f"- **{label}**: {runs_str}")

    lines += [
        "",
        "## Go/No-Go 판정",
        "",
        "| 기준 | 조건 |",
        "|------|------|",
        "| Go | 평균 ≥ 60s — Phase I 착수 |",
        "| No-Go | 평균 < 20s — 병렬화 불필요 |",
        "| Borderline | 20s ≤ 평균 < 60s — ROI 계산 후 재판정 |",
        "",
        f"**판정**: {verdict}",
        "",
        f"> 전체 평균 {overall_avg:.2f}s",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


async def main() -> None:
    print("=" * 60)
    print("SCAManager G.6 Static Analysis Serial Baseline Benchmark")
    print("=" * 60)
    results = await run_benchmark()
    overall_avg = sum(r["avg_s"] for r in results.values()) / len(results)
    verdict = _verdict(overall_avg)
    report_path = _write_report(results)
    print("\n" + "=" * 60)
    print(f"Overall avg: {overall_avg:.2f}s")
    print(f"Verdict: {verdict}")
    print(f"Report: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
