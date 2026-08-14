#!/usr/bin/env python3
"""main 이 지금 빨간가 — 그리고 **얼마나 오래** 빨갛나 (P3).

## 왜 만드나 (2026-08-08 실측)

`main` 의 CI 실패는 아무도 보지 않는다. 최근 25 run 에서 red 구간이 **4회**였고
지속 시간은 다음과 같다:

| 구간 | 지속 |
|---|---|
| 08-04 17:09 → 17:18 | 9분 |
| 08-04 22:53 → 08-05 19:02 | **20시간 9분** |
| 08-06 14:55 → 15:19 | 24분 |
| 08-07 01:17 → 14:06 | **12시간 49분** |

🔴 **R56 이 이미 증명한 것**: loud 관측자만으로는 아무 일도 일어나지 않는다
(pre-commit 미설치 배너가 19 PR 동안 매 세션 떴지만 조치가 0이었다). 그래서 이 스크립트의
지표는 *"발화했는가"* 가 **아니라** *"몇 시간 만에 고쳤는가"* 다 — 그 값을 매번 인쇄한다.

## 계약

- **advisory (항상 exit 0)** — SessionStart 훅이라 차단하면 세션 자체가 막힌다(정책 17).
- 🔴 **판정 불가를 침묵으로 흘리지 않는다.** `gh` 부재·네트워크 실패·파싱 실패는
  *"판정 불가"* 로 **인쇄**한다. 조용한 0 은 초록과 구별되지 않는다(R0-2 가 고친 클래스).
- 상태는 **어디에도 저장하지 않는다.** red 지속 시간은 `gh run list` 이력에서 그때그때
  유도한다 — 원장 파일을 두면 그 파일이 또 drift 하고, 갱신 의무가 또 사람 기억에 걸린다.

Reports whether main's CI is currently red and, if so, for how long — derived from run history,
never persisted. Advisory only; "cannot judge" is printed, never silent.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_REPO = "xzawed/SCAManager"
_LIMIT = 25

# GitHub run conclusions that mean "main is not green".
# `failure` 만 보면 timed_out·startup_failure 가 "초록" 으로 인쇄된다 (backlog R70).
# Only these are red; cancelled/stale/neutral are not recoveries either, but they
# are not "the build failed" — main() must still refuse to print 초록 for them.
# 워크플로 YAML 파손 = startup_failure, 러너 한도 = timed_out — 둘 다 관측이 가장 필요한 순간.
_RED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})
# 지속시간 역추적에서 구간을 끊지 않는 결론 — cancelled 는 "고쳤다" 가 아니다.
# Do not treat these as the end of a red span; a mid-streak cancel collapsed 60h → 1.0h.
_SPAN_CONTINUE = frozenset({"cancelled"})


def _gh(args: list[str], timeout: int = 60) -> str | None:
    """`gh` 출력 또는 None(판정 불가)."""
    if shutil.which("gh") is None:
        return None
    try:
        proc = subprocess.run(  # nosec B603
            ["gh", *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def fetch_runs() -> list[dict] | None:
    raw = _gh(["run", "list", "--repo", _REPO, "--branch", "main",
               "--workflow=ci.yml", "--limit", str(_LIMIT),
               "--json", "conclusion,status,createdAt,databaseId,url"])
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, list) else None


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def red_span(runs: list[dict], now: datetime | None = None) -> tuple[bool, float, dict | None]:
    """(지금 red 인가, 지속 시간(시간), 최신 실패 run).

    🔴 `gh run list` 는 **최신순**이다. 최신이 실패면 그 앞으로 거슬러 올라가며
    마지막 성공을 찾아 그 사이를 red 구간으로 본다.
    """
    finished = [r for r in runs if r.get("status") == "completed"]
    if not finished:
        return False, 0.0, None
    latest = finished[0]
    # 🔴 최신이 `failure` 가 아니라고 해서 초록이 아니다 — latest 를 돌려줘야
    #    main() 이 실제 결론을 인쇄할 수 있다 (None 이면 무조건 "초록" 이 된다).
    # Returning latest on the non-red path lets main() refuse to print 초록
    # for cancelled/timed_out/startup_failure/action_required/stale/neutral.
    if latest.get("conclusion") not in _RED_CONCLUSIONS:
        return False, 0.0, latest

    started = _parse(latest.get("createdAt", ""))
    for r in finished:
        conc = r.get("conclusion")
        if conc in _RED_CONCLUSIONS:
            started = _parse(r.get("createdAt", "")) or started
        elif conc in _SPAN_CONTINUE:
            # cancelled: 구간을 끊지 않는다. 시작 시각도 당기지 않는다.
            # A cancel is not a recovery and not a new red start.
            continue
        else:
            break
    ref = now or datetime.now(timezone.utc)
    hours = ((ref - started).total_seconds() / 3600) if started else 0.0
    return True, max(hours, 0.0), latest


def failing_jobs(run_id: int) -> list[str]:
    # 🔴 jq 필터를 `_RED_CONCLUSIONS` 에서 **파생**한다 — 손으로 나열하면 두 곳이 갈라지고,
    #    리스트 원소 자리의 인접 문자열은 CodeQL `py/implicit-string-concatenation-in-list` 다.
    # Derive the jq filter from the red set: no duplicated literals, no implicit concatenation.
    _sel = " or ".join(f'.conclusion=="{c}"' for c in sorted(_RED_CONCLUSIONS))
    raw = _gh(["api", f"repos/{_REPO}/actions/runs/{run_id}/jobs",
               "--jq", f"[.jobs[] | select({_sel}) | .name] | .[]"])
    if raw is None:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()][:5]


def _make_stdout_safe() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / unsupported stream


def main() -> int:
    _make_stdout_safe()
    if os.environ.get("SKIP_MAIN_RED_CHECK"):
        # 🔴 무음 skip 은 초록과 구별되지 않는다 (R70). 끈 사실을 인쇄한다.
        # A silent kill-switch is indistinguishable from "main is green".
        print(
            "⚠️ SKIP_MAIN_RED_CHECK 설정 — main red 관측을 **건너뛴다**. "
            + "초록이라는 뜻이 아니다."
        )
        return 0

    runs = fetch_runs()
    if runs is None:
        # 🔴 침묵하지 않는다 — 조용한 0 은 "main 초록" 과 구별되지 않는다(R0-2 클래스).
        print(
            "⚠️ main CI 상태를 **판정하지 못했다**(`gh` 부재·네트워크·파싱 실패). "
            "초록이라는 뜻이 아니다.\n"
            "   확인: gh run list --branch main --workflow=ci.yml --limit 1"
        )
        return 0

    is_red, hours, latest = red_span(runs)
    if not is_red:
        conc = (latest or {}).get("conclusion")
        if conc == "success":
            print("main CI — 최신 run 초록.")
        elif conc:
            # timed_out 등이 여기로 오면 회귀 — _RED_CONCLUSIONS 가 빠져 있다는 뜻.
            # Non-success that is not in _RED still must not print 초록.
            print(
                f"main CI — 최신 run 결론 `{conc}` "
                + "(초록이 아니다 — `failure`/`success` 이외)."
            )
        else:
            print("main CI — 완료된 run 이 없다 (초록이라는 뜻이 아니다).")
        return 0

    jobs = failing_jobs(latest.get("databaseId", 0)) if latest else []
    print(
        f"🔴 **main CI 가 빨갛다 — {hours:.1f}시간째.**\n"
        f"   실패 job: {', '.join(jobs) if jobs else '(조회 실패)'}\n"
        f"   run: {latest.get('url', '?') if latest else '?'}\n"
        "   🔴 이 세션에서 고치거나, 못 고칠 이유를 사용자에게 보고할 것.\n"
        "      실측(2026-08-08): 과거 red 구간이 **20시간·12.8시간**까지 방치됐다 —\n"
        "      배너가 없어서가 아니라 **배너가 조치로 변환되지 않아서**다(R56 과 같은 기전).\n"
        "   ⚠️ 이 검사는 advisory(비차단)다 — 관측면일 뿐 보호가 아니다."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
