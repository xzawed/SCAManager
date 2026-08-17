#!/usr/bin/env python3
"""push 전에 **CI 가 실제로 강제하는 가드**를 로컬에서 돌린다 — `make` 비의존 진입점.

## 왜 만드나 (2026-08-01 실측)

두 가지가 겹쳐 CI 왕복이 반복됐다.

1. 🔴 **`make` 이 이 머신에 없다**(`make: command not found`). CLAUDE.md 가 처방하는
   `make gate`·`make test`·`make lint` 는 **전부 실행 불가**다. 가드가 틀린 게 아니라
   **호출 명령이 존재하지 않는다**(backlog R29).
2. 🔴 **`make gate` 는 있었어도 부족하다.** 그 타깃은 `pytest` + `pylint` + `bandit` 뿐이라
   CI 의 **repo-integrity 가드와 PR-diff 한정 가드**를 하나도 돌리지 않는다(목록 정본은
   아래 `_INTEGRITY` · `_INTEGRITY_WITH_ARGS` · `_DIFF_SCOPED`). 실제로 이 세션은
   `Block new dual-import` 에 **두 번** 걸렸고, 두 번 다 로컬에서는 초록이었다.
   ⚠️ 2026-08-17 정정 — 이 자리에 «repo-integrity 7종 · PR-diff 한정 4종» 이라 적혀 있었다.
   :24 가 «개수를 여기 적지 않는다» 고 기록한 바로 그 docstring 이 두 문단 위에서 그것을
   어기고 있었고, 그 «7종» 은 실측 13 과 어긋난 채였다.
   The count was written here despite the rule three paragraphs below forbidding it.

즉 "가드가 수행되지 않는" 가장 단순한 형태 — 가드는 옳은데 **로컬에서 부를 방법이 없었다.**

## 이 스크립트가 덮는 것 / 덮지 못하는 것 (정직 기준)

덮는다 — CI 가 강제하고 로컬에서 네트워크 없이 재현 가능한 것:
  · repo-integrity stdlib 가드 (whole-repo 상태) — 목록 정본은 `_INTEGRITY` + `_INTEGRITY_WITH_ARGS`
  · PR-diff 한정 — 목록 정본은 `_DIFF_SCOPED` + flake8 F401/F841
  · `--full` 시 pylint(임계는 README 배지에서 파생) + bandit + `pytest tests/unit`

  개수를 여기 적지 않는다 — 2026-08-16 실측에서 이 docstring 의 «7종» 이 실제 13 과
  어긋나 있었다. 목록이 늘면 손유지 숫자가 조용히 거짓이 된다(N지점 손유지).
  Counts are not duplicated here; the tuples above are the single source.

**덮지 못한다** — 여기서 초록이어도 CI 는 red 일 수 있다:
  · CodeQL · SonarCloud · Codecov(patch coverage) · TruffleHog · pip-audit  (서비스 의존)
  · lint-js (node/eslint 필요) · PG-only job (PostgreSQL 서비스 필요)
  · 통합 테스트(`tests/integration`) — `--full` 도 단위만 돈다(속도)
이 목록을 **출력 끝에 항상 인쇄한다** — "여기 초록 = CI 초록" 으로 읽히면 새 observer-lie 다.

## 사용법 / Usage

    py -3 scripts/pre_push_gate.py              # 빠른 가드만 (수 초)
    py -3 scripts/pre_push_gate.py --full       # + pylint · bandit · pytest tests/unit
    py -3 scripts/pre_push_gate.py --base origin/main

exit 0 = 덮는 범위 전건 통과 / exit 1 = 하나 이상 실패(어느 것인지 인쇄).
"""
import argparse
import re
import subprocess  # nosec B404 — 리포 자신의 가드 스크립트만 실행한다
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# CI 워크플로의 `python-version: "X.Y"` 지점 — 로컬↔CI 인터프리터 이원 관측용 (backlog R30).
# 🔴 기지 한계 (Grok `019fbe61` F2·F3 — 정직 명시): 원시 텍스트 정규식이라 **주석 안의 핀도
#    집합에 들어간다**(현 ci.yml 은 주석 핀 0). ci.yml 외 워크플로(body-edit 등)와 micro
#    버전(3.12.x)은 이 축의 범위 밖이다 — 이 축은 minor 이원(3.14↔3.12)의 관측면일 뿐이다.
# Known limits: a raw-text regex also collects commented pins (none today); other
# workflows and micro versions are out of scope — this axis observes the minor split only.
_CI_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"
_PY_VERSION_RE = re.compile(r"python-version:\s*[\"']?(3\.\d+)")

# whole-repo 상태 가드 — CI `repo-integrity` job 과 같은 목록.
# Whole-repo state guards, mirroring the CI repo-integrity job.
_INTEGRITY = (
    # 커밋된 병합 충돌 마커 (2026-08-12 실사고 — README 2종이 `#1328` 이래 깨진 채 main 에 있었다).
    # 🔴 `check_docs_sync.py` **앞**에 둔다 — 그쪽 `--fix` 가 충돌 블록 안쪽을 고쳐 쓰므로,
    #    마커를 먼저 잡지 않으면 "정합 ✅" 가 깨진 파일 위에서 인쇄된다.
    # Runs first: the badge autofixer can rewrite a line inside a conflict block.
    "check_conflict_markers.py",
    "check_docs_sync.py",
    "check_architecture_tree_sync.py",
    "check_guard_fail_open.py",
    "check_env_vars_sync.py",
    "check_config_5way_sync.py",
    "check_claim_review_trace.py",
    # lint-js job — 가드 자체는 순수 파이썬(eslint 검사 **범위**가 비었는지만 본다).
    # The guard itself is pure Python: it only checks the eslint scope is non-empty.
    "check_lint_js_nonvacuous.py",
    # e2e job — 수집 건수 baseline (backlog R58). 검사 **범위 축소**가 조용히 통과하던 축.
    # E2E scope: a shrinking collection is a failure, not a pass.
    "check_e2e_scope.py",
    # P1 역-뮤테이션 (2026-08-07). 🔴 **로컬에서는 쉰다** — PR env(base/head SHA)가 없으면
    # 즉시 exit 0 이다. 그래야 로컬 push 가 영구 red 가 되지 않는다(정책 17).
    # 등재하는 이유는 `test_pre_push_gate.py` 가 **ci.yml 전체**의 가드 집합과 이 목록의
    # 동기화를 강제하기 때문이다 — 실제 판정은 CI(`test-and-analyze` job) 몫이다.
    # Sleeps locally (no PR env); listed to keep the runner in sync with ci.yml.
    "check_reverse_mutation.py",
    # P4 🔴-예산제 (2026-08-08). 로컬에서는 PR env 가 없어 **현황만 인쇄**하고 쉰다 —
    # 무집행 🔴 이 지금 몇 건인지 매 push 마다 눈에 들어오는 부수 효과가 있다.
    # Prints the current unenforced-🔴 count locally; the delta verdict is CI's job.
)

# 인자가 필요한 whole-repo 가드 — CI 와 같은 형태로 부른다.
# 🔴 `check_test_count_sync` 는 PR 에서 advisory(`--advisory-drift`), main push 에서 enforce 다.
#    로컬은 push 전이므로 PR 모드를 쓴다 — drift 는 경고하되 게이트를 막지 않는다
#    (막으면 trailing sync 전 모든 PR 이 red 가 되어 정책 17 위반).
# Local runs mirror the PR (advisory) mode; enforcing here would red-flag every pre-sync PR.
_INTEGRITY_WITH_ARGS = (
    ("check_test_count_sync.py", ["--advisory-drift"]),
)

# PR-diff 한정 가드 — base sha 를 인자로 받는다.
# Diff-scoped guards; each takes the base sha.
_DIFF_SCOPED = (
    "check_dual_import.py",
    "check_noqa_sideeffect.py",
    "check_dead_code.py",
)

# 여기서 초록이어도 CI 가 red 일 수 있는 축 — 항상 인쇄한다.
# Axes this runner cannot see; printed every run so green here is never read as green in CI.
_NOT_COVERED = (
    "CodeQL · SonarCloud · Codecov(patch coverage) — 서비스 의존",
    "TruffleHog · pip-audit — 서비스/네트워크 의존",
    "lint-js — node + eslint 필요",
    "PG-only job — PostgreSQL 서비스 필요",
    "tests/integration — 이 스크립트는 --full 에서도 단위만 돈다",
)


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    🔴 standalone 실행이라 공유 헬퍼를 import 할 수 없다 — 검증된 관용구를 복제한다
    (정책 16 최소 추상화). 누락 방지 = `tests/unit/scripts/test_stdout_encoding_guard.py`.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 재구성 불가한 스트림(파이프·구버전) — 출력 인코딩은 최선 노력 / best-effort only


def _run(label: str, argv: list[str], show_always: bool = False) -> bool:
    """한 가드를 돌리고 통과 여부를 반환한다.

    🔴 `show_always` — advisory 가드는 **exit 0 이면서 경고를 낸다**. 실패 시에만 출력하면
    그 경고가 삼켜져 "OK" 만 보인다(경고가 존재 이유인데 안 보이는 것 = 이 저장소의
    지배적 결함 재생산). advisory 축은 항상 인쇄한다.
    Advisory guards exit 0 while warning; hiding their output would defeat their purpose.
    """
    proc = subprocess.run(  # nosec B603 — argv 는 이 파일의 상수 + base sha
        argv, cwd=str(_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    ok = proc.returncode == 0
    print(f"  {'OK  ' if ok else 'FAIL'} {label}")
    if not ok or show_always:
        body = (proc.stdout or "") + (proc.stderr or "")
        for line in body.strip().splitlines()[:12]:
            print(f"       {line}")
    return ok


def _base_sha(explicit: str | None) -> str:
    """diff 기준점 — 미지정 시 `origin/main` 과의 merge-base."""
    if explicit:
        return explicit
    proc = subprocess.run(  # nosec B603
        ["git", "merge-base", "origin/main", "HEAD"], cwd=str(_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    return proc.stdout.strip() or "origin/main"


def _changed_test_files(base: str) -> list[str]:
    proc = subprocess.run(  # nosec B603
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base, "HEAD", "--", "tests/"],
        cwd=str(_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return [p for p in proc.stdout.split() if p.endswith(".py")]


def run_integrity(py: str) -> list[str]:
    """whole-repo 상태 가드 — 실패한 것들의 이름. / Names of failed whole-repo guards."""
    print("== repo-integrity (whole-repo 상태) ==")
    failed = [s for s in _INTEGRITY if not _run(s, [py, f"scripts/{s}"])]
    failed += [s for s, extra in _INTEGRITY_WITH_ARGS
               if not _run(f"{s} {' '.join(extra)}", [py, f"scripts/{s}", *extra],
                           show_always=True)]
    return failed


def run_diff_scoped(py: str, base: str) -> list[str]:
    """PR-diff 한정 가드 — CI `lint-changed-tests` job 과 같은 4종.
    Diff-scoped guards mirroring the CI lint-changed-tests job."""
    print(f"\n== PR-diff 한정 (base {base[:12]}) ==")
    failures = []
    changed = _changed_test_files(base)
    if not changed:
        print("  --   flake8 F401/F841 (변경된 test 파일 없음)")
    elif not _run(f"flake8 F401/F841 ({len(changed)} 파일)",
                  [py, "-m", "flake8", "--isolated", "--select=F401,F841", *changed]):
        failures.append("flake8-changed-tests")
    failures += [s for s in _DIFF_SCOPED if not _run(s, [py, f"scripts/{s}", base, "HEAD"])]
    return failures


_PYLINT_BADGE = re.compile(r"badge/pylint-(\d+\.\d+)%2F10")
# 배지는 소수 2자리 반올림 표기 — 실점수가 그만큼 낮을 수 있다(ci.yml 과 동일 폭).
_BADGE_ROUNDING = 0.005


def pylint_floor(root: Path) -> str:
    """README pylint 배지에서 `--fail-under` 를 파생한다 (CI 와 같은 규칙).

    🔴 리터럴 9.90 을 쓰던 시절 이 로컬 게이트는 **CI 와 다른 것을 재고 있었다** — CI 는
    배지에서 파생하는데 여기만 9.90 이면, 배지를 부풀려도 로컬은 초록이다(Grok `019ff301`).
    Keep the local floor derived the same way as CI, or the two gates measure different things.
    """
    m = _PYLINT_BADGE.search((root / "README.md").read_text(encoding="utf-8"))
    if not m:  # fail-closed — 못 읽으면 옛 보수 floor 로 떨어지지 않는다.
        raise SystemExit("❌ README pylint 배지를 읽지 못했다 — 배지 형식 drift 의심")
    return f"{float(m.group(1)) - _BADGE_ROUNDING:.3f}"


def run_slow(py: str) -> list[str]:
    """`--full` 전용 — pylint · bandit · 단위 테스트. / Opt-in slow axes."""
    print("\n== --full (느린 축) ==")
    floor = pylint_floor(Path(__file__).resolve().parents[1])
    checks = (
        (f"pylint --fail-under={floor} src/ (README 배지 파생)",
         [py, "-m", "pylint", f"--fail-under={floor}", "src/"]),
        ("bandit -r src/ -q", [py, "-m", "bandit", "-r", "src/", "-q"]),
        ("pytest tests/unit", [py, "-m", "pytest", "tests/unit", "-q", "--no-header"]),
    )
    return [label for label, argv in checks if not _run(label, argv)]


def _ci_python_versions() -> set[str]:
    """CI 워크플로가 핀한 파이썬 버전 집합 (실측 파싱 — 손유지 상수는 drift 한다).
    The Python versions the CI workflow pins, parsed from the file (constants drift)."""
    try:
        return set(_PY_VERSION_RE.findall(_CI_WORKFLOW.read_text(encoding="utf-8")))
    except OSError:
        return set()


def interpreter_drift_line(local: str, ci: set[str]) -> str:
    """로컬↔CI 인터프리터 이원 한 줄 (backlog R30) — 항상 인쇄될 정보 축.

    🔴 로컬 전건 통과 ≠ CI 통과: 6-step ② 의 "push 전 전체 통과 실측" 이 로컬 3.14 에서의
    통과라면 CI 3.12 의 버전 의존 회귀(문법·표준 라이브러리 deprecation)를 원리적으로 못
    잡는다. 이 이원을 매 실행 인쇄하는 것이 이 축의 전부다 — 파싱 실패도 조용히 생략하지
    않는다(빈 집합 = ⚠️ 로 보고, fail-closed).
    Local green is not CI green when the interpreters differ; parse failure is reported
    loudly instead of silently omitted.
    """
    if not ci:
        return f"⚠️ CI python-version 파싱 실패 ({_CI_WORKFLOW.name}) — 로컬 {local} 과 대조 불가"
    joined = "/".join(sorted(ci))
    if local not in ci:
        return (f"⚠️ 로컬 인터프리터 {local} ↔ CI {joined} — 여기 전건 통과가 "
                "CI 통과를 보장하지 않는다 (backlog R30)")
    return f"· 로컬 인터프리터 {local} = CI {joined} (이원 없음)"


def print_blind_spots(full: bool) -> None:
    """🔴 항상 인쇄 — "여기 초록 = CI 초록" 으로 읽히면 새 observer-lie 다.
    Always printed so a green run is never mistaken for a green CI."""
    print("\n🔴 이 스크립트가 **보지 못하는** 축 (여기 초록 != CI 초록):")
    for item in _NOT_COVERED:
        print(f"  · {item}")
    if not full:
        print("  · pylint · bandit · pytest — `--full` 을 붙여야 실행된다")
    # 🔴 인터프리터 이원은 --full 여부와 무관하게 항상 보인다 (backlog R30).
    # The interpreter drift line is always visible, regardless of --full.
    local = f"{sys.version_info.major}.{sys.version_info.minor}"
    print(f"  {interpreter_drift_line(local, _ci_python_versions())}")


def main() -> int:
    _make_stdout_safe()
    parser = argparse.ArgumentParser(description="CI 가 강제하는 가드를 로컬에서 실행")
    parser.add_argument("--full", action="store_true",
                        help="pylint + bandit + pytest tests/unit 도 실행 (느림)")
    parser.add_argument("--base", default=None, help="diff 기준 sha (기본: origin/main merge-base)")
    args = parser.parse_args()

    py = sys.executable
    base = _base_sha(args.base)

    failures = run_integrity(py) + run_diff_scoped(py, base)
    if args.full:
        failures += run_slow(py)

    print_blind_spots(args.full)
    if failures:
        print(f"\n🔴 실패 {len(failures)}건: {', '.join(failures)}")
        return 1
    print("\n✅ 덮는 범위 전건 통과 (위 미포함 축은 CI 에서 확인)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
