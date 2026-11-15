"""E2E 시간 예산 — 스위트가 그 스텝 벽(ci.yml)의 85% 를 넘으면 red, 75% 부터 경고(회고 원장 L08).
E2E time budget: red above 85% of the suite step's wall in ci.yml, a warning from 75%.

    python scripts/e2e_budget.py --started-at 1763190000   # CI E2E 잡 — 스위트 바로 앞 스텝이 적은 시작 시각(epoch 초)

스위트 시간 = 지금 − 시작 시각(스위트 스텝은 한 줄 그대로 둔다). 벽은 ci.yml 의 E2E 잡 «Run E2E suite» 스텝
`timeout-minutes` 한 곳에서 읽는다(숫자를 복사하지 않는다). 스위트가 그 벽에 닿으면 스텝이 시간 초과로 끝나 시험 결과가
남지 않으므로, 그 전에 이 검사가 red 를 내 «스위트를 나누거나 벽을 다시 잰다» 를 먼저 하게 한다. 시작 시각을 못 읽거나
(빈 값 · 숫자 아님 · 미래) 벽을 못 찾으면 red 다(못 재면 red).
"""
import argparse
import math
import os
import sys
import time
from pathlib import Path

import yaml

_CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
_JOB = "e2e"
_STEP = "Run E2E suite"
WARN = 0.75
FAIL = 0.85


def suite_wall_minutes(ci_path: Path = _CI) -> int | None:
    """E2E 스위트 스텝의 벽(분) — 못 찾거나 꼴이 다르면 None / the suite step's wall, or None."""
    try:
        steps = yaml.safe_load(ci_path.read_text(encoding="utf-8"))["jobs"][_JOB]["steps"]
        matches = [s for s in steps if isinstance(s, dict) and s.get("name") == _STEP]
    except (OSError, ValueError, yaml.YAMLError, KeyError, TypeError):  # ValueError ⊃ UnicodeDecodeError
        return None
    if len(matches) != 1:
        return None
    wall = matches[0].get("timeout-minutes")
    return wall if type(wall) is int and wall > 0 else None


def parse_seconds(raw: str | None) -> float | None:
    """스텝이 넘긴 초(epoch 포함) — 유한한 양수만 / finite positive seconds only."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def elapsed_seconds(started_at: str | None, now: float) -> float | None:
    """지금 − 시작 시각 — 시작 시각을 못 읽거나 미래면 None / now minus the start, or None."""
    start = parse_seconds(started_at)
    if start is None:
        return None
    elapsed = now - start
    return elapsed if elapsed > 0 else None


def judge(seconds: float | None, wall_minutes: int | None) -> tuple[int, str]:
    """(종료 코드, 한 줄) — 0 = 예산 안(경고 포함) · 1 = 예산 초과 또는 못 잼."""
    if wall_minutes is None:
        return 1, f"🔴 ci.yml 의 «{_STEP}» 스텝 벽(timeout-minutes)을 못 읽었다 — 예산을 못 잰다"
    if seconds is None:
        return 1, "🔴 스위트 시간을 못 읽었다 — 예산을 못 잰다"
    ratio = seconds / (wall_minutes * 60)
    line = f"E2E 스위트 {seconds / 60:.1f}분 = 스텝 벽 {wall_minutes}분의 {ratio:.0%}"
    if ratio > FAIL:
        return 1, f"🔴 {line} — {FAIL:.0%} 초과. 벽에 닿기 전에 스위트를 나누거나 벽을 다시 재는 PR 이 먼저다"
    if ratio >= WARN:
        return 0, f"⚠️ {line} — {WARN:.0%} 이상"
    return 0, f"✅ {line}"


def main(argv=None, *, ci_path: Path = _CI, out=print, now=time.time) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--started-at", required=True, help="스위트 바로 앞 스텝이 적은 시작 시각(epoch 초)")
    args = parser.parse_args(argv)
    code, line = judge(elapsed_seconds(args.started_at, now()), suite_wall_minutes(ci_path))
    out(line)
    if code:
        out(f"::error title=E2E 시간 예산::{line}")
    elif line.startswith("⚠️"):
        out(f"::warning title=E2E 시간 예산::{line}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return code


def _make_stdout_safe() -> None:
    """한글 · 기호를 찍으므로 두 출력을 UTF-8 로 — Windows(cp949) 콘솔에서 찍는 순간 죽지 않게.

    Print streams as UTF-8 so Korean text and symbols never crash a cp949 console.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            # 캡처 · 대체된 스트림에는 reconfigure 가 없다 — 그 스트림은 이미 호출자가 인코딩을 정했다.
            # Captured or replaced streams lack reconfigure; their owner already chose the encoding.
            continue


if __name__ == "__main__":
    _make_stdout_safe()
    sys.exit(main())
