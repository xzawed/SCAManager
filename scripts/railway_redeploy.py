"""실패한 Railway 배포를 조건을 확인한 뒤 다시 건다 — 에이전트가 혼자 쓰는 유일한 배포 경로(회고 원장 L02, A안).
Retry a failed Railway deployment after mechanical checks — the only deploy path the agent may run alone.

    py -3 scripts/railway_redeploy.py            # 실패 · 건너뛴 배포를 main 최신 커밋으로 다시 빌드
    py -3 scripts/railway_redeploy.py --restart  # 크래시한 배포를 빌드 없이 재시작
    py -3 scripts/railway_redeploy.py --check    # 조건만 본다(명령을 내지 않는다)

🔴 왜 스크립트인가: 날 `railway redeploy` 는 CI 가 빨간 main 도 배포하고, 비밀번호 교체 중(새 변수가 이미 반영된
실패 배포)에 재시도가 성공하면 사용자가 곧바로 SQL 을 실행해야 한다. 그래서 훅은 날 railway 변경 명령을 막고,
이 스크립트만 아래를 기계로 확인한 뒤 건다. 하나라도 못 재면 막는다(fail-closed).
  1. «교체 진행 중» 표지(~/.scamanager/rotation-in-progress, 48시간 안)가 없다. 교체 순서의 값 생성기가 만든다 —
     Railway CLI 로는 «변수를 바꿔 배포했다» 를 GitHub 푸시 배포와 구별할 수 없어서다(배포 사유가 모두 `deploy`).
  2. 가장 새 배포가 main 최신 커밋의 것이고 끝난 상태다 — 재배포는 FAILED · SKIPPED, 재시작은 CRASHED.
  3. 그 커밋의 CI 검사(check-run)가 모두 끝났고 실패가 없다 · Railway 가 아닌 커밋 상태도 성공이다. Railway 가 남기는
     배포 상태(`railway-app[bot]`)는 이 배포 자체의 결과라 뺀다.
건 뒤에는 배포가 끝날 때까지 상태만 찍고(값 없음), 성공하면 배포 로그의 오류 부류를 개수만 센다.
`railway up`(이 PC 의 코드) · `down` · 옛 배포 되돌리기 · 변수 변경은 이 스크립트가 하지 않는다 — 사용자가 `!` 로.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

_REPO = "xzawed/SCAManager"
MARKER = Path.home() / ".scamanager" / "rotation-in-progress"
MARKER_HOURS = 48
# 다시 걸 수 있는 가장 새 배포 상태 / statuses of the newest deployment each action may act on
RETRYABLE = {"redeploy": frozenset({"FAILED", "SKIPPED"}), "restart": frozenset({"CRASHED"})}
_GREEN = frozenset({"success", "skipped", "neutral"})
_RAILWAY_BOT = "railway-app[bot]"
_TERMINAL = frozenset({"SUCCESS", "FAILED", "CRASHED", "REMOVED", "SKIPPED"})
_WATCH_SECONDS = {"redeploy": 1800, "restart": 300}
_POLL_SECONDS = 30
# 로그 오류 부류 — 줄 내용은 찍지 않고 개수만 / log error classes, counted only
_LOG_CLASSES = {
    "ERROR": re.compile(r"\bERROR\b"),
    "Traceback": re.compile(r"Traceback \(most recent call last\)"),
    "read-only 트랜잭션": re.compile(r"read-only transaction"),
    "DB 인증 실패": re.compile(r"password authentication failed"),
}


class CommandFailed(RuntimeError):
    """외부 명령 실패 — 막는 쪽으로 간다 / an external command failed; callers fail closed."""

    def __init__(self, args, returncode):
        super().__init__(f"exit {returncode}: {' '.join(args[:3])} …")
        self.args_list, self.returncode = list(args), returncode


def _run(args):
    """셸 없이 실행해 stdout 을 돌려준다 · 실패면 CommandFailed / run without a shell; raise on failure."""
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=120, check=False)
    if proc.returncode != 0:
        raise CommandFailed(args, proc.returncode)
    return proc.stdout


def _railway_exe():
    """railway 실행 파일 — npm 래퍼(.cmd)면 옆의 실제 바이너리를 쓴다(셸 없이 부르려고).
    The railway binary; an npm .cmd shim is swapped for the native binary next to it."""
    found = shutil.which("railway")
    if not found:
        raise CommandFailed(["railway"], 127)
    if found.lower().endswith((".cmd", ".bat")):
        native = Path(found).parent / "node_modules" / "@railway" / "cli" / "bin" / "railway.exe"
        if native.exists():
            return str(native)
    return found


def _newest(run, railway):
    """가장 새 배포(값 없는 필드만) / the newest deployment, value-less fields only."""
    items = json.loads(run([railway, "deployment", "list", "--json"]))
    items = items if isinstance(items, list) else items.get("deployments", [])
    if not items:
        return None
    meta = items[0].get("meta") or {}
    return {"id": items[0].get("id"), "status": items[0].get("status"),
            "commit": meta.get("commitHash"), "branch": meta.get("branch")}


def gather_state(run, railway, now, marker):
    """판정에 쓸 사실을 모은다 / collect the facts the decision needs."""
    main_sha = run(["git", "ls-remote", "origin", "refs/heads/main"]).split("\t", 1)[0].strip() or None
    runs = json.loads(run(["gh", "api", f"repos/{_REPO}/commits/{main_sha}/check-runs?per_page=100"])) \
        if main_sha else {}
    raw_statuses = json.loads(run(["gh", "api", f"repos/{_REPO}/commits/{main_sha}/statuses?per_page=100"])) \
        if main_sha else []
    latest = {}
    for status in raw_statuses:  # 최신이 먼저 온다 — 맥락마다 첫 것만 / newest first: keep one per context
        latest.setdefault(status.get("context"), {
            "context": status.get("context"), "state": status.get("state"),
            "creator": (status.get("creator") or {}).get("login")})
    age = (now() - marker.stat().st_mtime) / 3600 if marker.exists() else None
    return {
        "main_sha": main_sha,
        "newest": _newest(run, railway),
        "check_runs": [{"name": c.get("name"), "status": c.get("status"), "conclusion": c.get("conclusion")}
                       for c in runs.get("check_runs", [])],
        "check_runs_total": runs.get("total_count"),
        "statuses": list(latest.values()),
        "marker_age_hours": age,
    }


def decide(state, action):
    """거부 사유 목록 — 비면 다시 걸어도 된다 / the reasons to refuse; empty means go."""
    reasons = []
    age = state.get("marker_age_hours")
    # «48시간 이상» 일 때만 무효 — 나이를 못 재면(NaN 등) 막는다(Grok 반례 a9bf7844: `nan < 48` 은 거짓)
    # only an age of at least 48 h voids the marker; an unmeasurable age (NaN) blocks
    if age is not None and not age >= MARKER_HOURS:
        reasons.append(f"교체 진행 중 표지가 있다({age:.1f}시간 전) — 비밀번호 교체 중 재배포는 사용자가 `!` 로 한다")
    main_sha, newest = state.get("main_sha"), state.get("newest")
    if not main_sha or not newest:
        reasons.append("main 최신 커밋이나 가장 새 배포를 읽지 못했다(막는 쪽)")
        return reasons
    if newest.get("branch") != "main" or newest.get("commit") != main_sha:
        reasons.append("가장 새 배포가 main 최신 커밋의 것이 아니다 — 새 커밋의 자동 배포를 기다린다")
    allowed = RETRYABLE[action]
    if newest.get("status") not in allowed:
        reasons.append(f"가장 새 배포가 {newest.get('status')} — {action} 은 {'/'.join(sorted(allowed))} 일 때만")
    runs = state.get("check_runs") or []
    # 총수와 받은 목록이 정확히 같아야 «다 읽음» — 어긋나거나 없으면 막는다(Grok 반례 a9bf7844: total 0 · 목록 1)
    # a complete read needs total == len(runs); a mismatch or a missing total fails closed
    if not runs or state.get("check_runs_total") != len(runs):
        reasons.append("CI 검사 목록을 다 읽지 못했다(막는 쪽)")
    not_green = [c["name"] for c in runs if c.get("status") != "completed" or c.get("conclusion") not in _GREEN]
    if not_green:
        reasons.append(f"CI 검사 {len(not_green)}개가 초록이 아니다: {', '.join(sorted(map(str, not_green))[:5])}")
    bad = [s["context"] for s in state.get("statuses") or []
           if s.get("creator") != _RAILWAY_BOT and s.get("state") != "success"]
    if bad:
        reasons.append(f"커밋 상태 {len(bad)}개가 성공이 아니다: {', '.join(sorted(map(str, bad))[:5])}")
    return reasons


def _watch(run, railway, sleep, action, before_id, now):
    """끝날 때까지 상태만 찍는다 → 마지막 상태 / print status changes until done; return the final status."""
    deadline, seen, current = now() + _WATCH_SECONDS[action], None, None
    while now() <= deadline:
        newest = _newest(run, railway)
        target = newest if newest and (action == "restart" or newest.get("id") != before_id) else None
        if target:
            current = target.get("status")
            if current != seen:
                print(f"  배포 {str(target.get('id'))[:8]} → {current}", flush=True)
                seen = current
            if action == "restart" and current == "SUCCESS":
                return current
            if action == "redeploy" and current in _TERMINAL:
                return current
        sleep(_POLL_SECONDS)
    return f"TIMEOUT({current})"


def _count_log_errors(run, railway, dep_id):
    """배포 로그의 오류 부류를 개수만 센다 — 줄 내용은 찍지 않는다 / count error classes, never print lines."""
    text = run([railway, "logs", dep_id, "--deployment", "--lines", "500"])
    return {name: sum(1 for line in text.splitlines() if pattern.search(line))
            for name, pattern in _LOG_CLASSES.items()}


def main(argv=None, *, run=_run, sleep=time.sleep, now=time.time, marker=MARKER, railway_exe=None):
    """0 = 성공(또는 --check 통과) · 1 = 거부 · 2 = 다시 건 배포가 성공하지 못함 · 3 = 도구 실패(막는 쪽).
    0 success (or --check passed) · 1 refused · 2 the retried deployment did not succeed · 3 tool failure."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--restart", action="store_true", help="크래시한 배포를 빌드 없이 재시작")
    parser.add_argument("--check", action="store_true", help="조건만 본다")
    args = parser.parse_args(argv)
    action = "restart" if args.restart else "redeploy"
    try:
        railway = railway_exe or _railway_exe()
        state = gather_state(run, railway, now, marker)
    except (CommandFailed, subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        print(f"🔴 조건을 재지 못했다 — 막는다(fail-closed): {exc}")
        return 3
    newest = state["newest"] or {}
    print(f"main {str(state['main_sha'])[:8]} · 가장 새 배포 {str(newest.get('id'))[:8]} {newest.get('status')} · "
          f"CI 검사 {len(state['check_runs'])}개 · 동작 {action}")
    reasons = decide(state, action)
    if reasons:
        print("🔴 거부 — 사용자가 `!` 로 직접 실행하거나 조건이 맞을 때 다시:")
        for reason in reasons:
            print(f"  - {reason}")
        return 1
    if args.check:
        print("✅ 조건 충족 — `--check` 라 명령은 내지 않았다")
        return 0
    try:
        run([railway, "redeploy", "--from-source", "-y"] if action == "redeploy" else [railway, "restart", "-y"])
        final = _watch(run, railway, sleep, action, newest.get("id"), now)
        if final != "SUCCESS":
            print(f"🔴 {action} 뒤 배포가 {final} — 빌드 로그: railway logs <id> --build --lines 3000")
            return 2
        dep = _newest(run, railway) or {}
        counts = _count_log_errors(run, railway, dep.get("id"))
        print("✅ SUCCESS · 배포 로그 오류 부류(개수만): " + " · ".join(f"{k} {v}" for k, v in counts.items()))
        return 0
    except (CommandFailed, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"🔴 명령 실패: {exc}")
        return 3


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 은 reconfigure 를 못 한다 — 무시 / captured streams cannot be reconfigured
    sys.exit(main())
