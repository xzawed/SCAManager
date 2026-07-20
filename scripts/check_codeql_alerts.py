#!/usr/bin/env python3
"""PR 신규 CodeQL alert 게이트 — note 심각도 포함 전건 차단 (회고 2026-07-19 P1).

🔴 실측 반증: 자초 alert #547·#548·#549 는 **PR 시점에 이미 탐지돼 있었다** — instances API 로
각각 `refs/pull/1081/merge`·`1082`·`1083` 인스턴스 확인. 심각도가 `note` 라 Code scanning 체크가
SUCCESS 였을 뿐이다. 즉 근본 원인은 '클래스 게이트 부재'가 아니라 **'임계값 미설정'** 이고,
룰별 stdlib 가드 증축(py/unused-import·py/import-and-import-from·py/empty-except)은
**이미 잡힌 것을 다시 잡는** 대응이었다(3회 반복).
Measured: each self-inflicted alert had a `refs/pull/<n>/merge` instance — PR-time CodeQL detected
them; the check passed only because `note` is below the check-failure threshold.

이 게이트는 PR ref 에서 **열려 있고 base(main)에는 없는** alert 를 신규로 보고 차단한다.
룰별 가드를 대체하지 않는다 — 그쪽은 CodeQL 실행 전 turn-0 로컬 피드백(빠른 실패 메시지),
이쪽은 **가드를 아직 안 만든 룰까지 잡는 백스톱**이다.
This gates alerts open on the PR ref but not on base; it complements (not replaces) the per-rule
guards, which give faster turn-0 feedback for the rules they cover.

🔴 타임아웃을 통과로 처리하지 않는다 (fail-OPEN 재발 차단): 분석 인덱싱 전에는 alert 조회가
0건을 반환한다. head SHA 의 분석 존재를 먼저 확인하고, 확인 못 하면 exit 2(판정 불가).
Never treat "not indexed yet" as clean — verify the analysis for the head SHA exists first.

사용법 / Usage:
  python scripts/check_codeql_alerts.py <repo> <pr_number> <head_sha> [base_ref]
"""
import json
import os
import subprocess
import sys
import time

# 분석 인덱싱 대기 — 총 대기 상한(초)과 폴링 간격.
# Analysis-indexing wait — total budget (seconds) and poll interval.
_WAIT_SECONDS = 180
_POLL_INTERVAL = 10


def select_new_alerts(pr_alerts, base_numbers):
    """PR ref 에서 열려 있고 base 에는 없는 alert 목록 — 심각도 무관(note 포함).
    Alerts open on the PR ref and absent from base; severity-agnostic (includes `note`)."""
    return [
        a for a in pr_alerts
        if a.get("state") == "open" and a.get("number") not in base_numbers
    ]


def analysis_ready(analyses, head_sha):
    """head SHA 에 대한 CodeQL 분석이 업로드됐으면 True.
    True when a CodeQL analysis for the head SHA has been uploaded."""
    return any(a.get("commit_sha") == head_sha for a in analyses)


def format_violations(alerts):
    """차단 보고 문자열 — 룰 ID·경로:라인·alert 번호 노출(조치 가능성).
    Violation report exposing rule id, path:line and alert number."""
    lines = []
    for a in alerts:
        inst = a.get("most_recent_instance") or {}
        loc = inst.get("location") or {}
        rule = (a.get("rule") or {}).get("id", "?")
        sev = (a.get("rule") or {}).get("severity", "?")
        lines.append(
            f"   - [{sev}] {rule} — {loc.get('path','?')}:{loc.get('start_line','?')}"
            f" (alert #{a.get('number')})"
        )
    return "\n".join(lines)


class Undecidable(Exception):
    """게이트가 **판정할 수 없는** 상태 — 위반(exit 1)과 구별되는 별개 사건.

    🔴 이 둘을 같은 exit 로 뭉개면 "판정 불가" 를 "위반" 으로 보고하게 되고,
    Dependabot 처럼 구조적으로 판정할 수 없는 PR 이 영구 차단된다(2026-07-20 실측).
    Distinct from a violation: conflating them permanently blocks unjudgeable PRs.
    """


# 🔴 exit 2(판정 불가) 완화를 허용하는 actor — **정확 일치만**.
#   prefix/포함 매칭 금지: `dependabot`, `my-dependabot[bot]` 등이 통과하면 안 된다.
_SOFT_EXIT2_ACTOR = "dependabot[bot]"

# 🔴 이 경로가 하나라도 바뀌면 완화하지 않는다 — `.github/workflows/**` 포함 의무.
#   Dependabot 은 action 버전도 올리는데(#1018), 그건 **control-plane** 변경이라
#   "의존성이니 안전" 논리가 성립하지 않는다. 게이트 자신을 약화시킬 수 있는 면이다.
#   Workflow diffs are control-plane, not "just deps" — never soften for them.
_CODE_PREFIXES = ("src/", "scripts/", "tests/", "e2e/", "alembic/", ".github/")

# 🔴 변경 경로를 못 구했을 때의 센티넬 — **완화 거부** 사유다.
#   빈 목록/미상은 "코드 변경 없음" 과 구별되지 않으므로 통과시키면 완화가 무조건 통과가 된다.
UNKNOWN_PATH = "<unknown>"


def soft_exit2_allowed(actor, changed_paths):
    """판정 불가(exit 2)를 **비차단**으로 완화해도 되는가 — 순수 함수.

    Whether an undecidable verdict may be downgraded to non-blocking.

    🔴 완화 대상은 **판정 불가뿐**이다. 신규 alert 발견(exit 1)은 누구에게도 완화되지 않는다.
    Only the undecidable case is softened; a real violation stays hard for every actor.
    """
    if actor != _SOFT_EXIT2_ACTOR:
        return False
    paths = list(changed_paths)
    if not paths or UNKNOWN_PATH in paths:
        # 경로 미상 = 판단 근거 부재 → 완화하지 않는다(판단 못 하면 막는다).
        return False
    return not any(str(p).startswith(_CODE_PREFIXES) for p in paths)


def _changed_paths(base_ref):
    """PR 이 바꾼 파일 목록 — **git 으로** 구한다(API 아님).

    🔴 API 로 구하면 판정 불가 상황(=API 가 죽은 상황)에서 같이 죽는다. 완화 여부를
    판단하는 입력이 완화가 필요한 원인과 같은 실패면 판단 자체가 불가능해진다.
    Uses git, not the API: the API is exactly what failed when we need this.
    """
    base = base_ref.rsplit("/", 1)[-1] if base_ref else "main"
    for spec in (f"origin/{base}...HEAD", f"{base}...HEAD", "HEAD~1..HEAD"):
        out = subprocess.run(
            ["git", "diff", "--name-only", spec],
            capture_output=True, text=True, check=False, encoding="utf-8", errors="replace",
        )
        if out.returncode == 0 and out.stdout.strip():
            return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    # 🔴 경로를 못 구하면 **완화하지 않는다** — 빈 목록은 "코드 변경 없음" 과 구별 불가.
    # Unknown paths must NOT be treated as "no code changed".
    return [UNKNOWN_PATH]


def _gh_api(path):
    """gh api 호출 → 파싱된 JSON. 실패 시 loud 종료(fail-CLOSED).
    gh api call returning parsed JSON; loud exit on failure (fail-closed)."""
    out = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, check=False, encoding="utf-8"
    )
    if out.returncode != 0:
        print(f"🔴 GitHub API 실패 — 게이트 판정 불가: {path}")
        print(f"   {(out.stderr or '').strip()[:300]}")
        raise Undecidable(f"API 실패: {path}")
    try:
        return json.loads(out.stdout or "[]")
    except json.JSONDecodeError as exc:
        print(f"🔴 API 응답 파싱 실패 — 게이트 판정 불가: {path}")
        raise Undecidable(f"응답 파싱 실패: {path}") from exc


def _wait_for_analysis(repo, pr_ref, head_sha):
    """head SHA 분석이 인덱싱될 때까지 폴링 — 미확인 시 exit 2.
    Poll until the analysis for head_sha is indexed; exit 2 if never confirmed."""
    deadline = time.monotonic() + _WAIT_SECONDS
    while True:
        analyses = _gh_api(f"repos/{repo}/code-scanning/analyses?ref={pr_ref}&per_page=20")
        if analysis_ready(analyses, head_sha):
            return
        if time.monotonic() >= deadline:
            print(f"🔴 CodeQL 분석 미인덱싱 ({_WAIT_SECONDS}s 초과) — 게이트 판정 불가 (fail-closed).")
            print(f"   ref={pr_ref} head={head_sha[:8]}")
            print("   🔴 '분석 없음'을 '위반 없음'으로 처리하지 않는다 (fail-OPEN 재발 차단).")
            raise Undecidable("분석 미인덱싱")
        time.sleep(_POLL_INTERVAL)


def main(argv):
    """게이트 진입점 — 0 정상 · 1 신규 alert · 2 판정 불가(완화 불가 시)."""
    if len(argv) < 4:
        print("사용법 / Usage: check_codeql_alerts.py <repo> <pr_number> <head_sha> [base_ref]")
        return 2
    repo, pr_number, head_sha = argv[1], argv[2], argv[3]
    base_ref = argv[4] if len(argv) > 4 else "refs/heads/main"
    pr_ref = f"refs/pull/{pr_number}/merge"

    try:
        _wait_for_analysis(repo, pr_ref, head_sha)
        pr_alerts = _gh_api(
            f"repos/{repo}/code-scanning/alerts?ref={pr_ref}&state=open&per_page=100"
        )
        base_alerts = _gh_api(
            f"repos/{repo}/code-scanning/alerts?ref={base_ref}&state=open&per_page=100"
        )
    except Undecidable as exc:
        # 🔴 판정 불가 — 위반(exit 1)이 **아니다**. 기본은 여전히 차단(fail-closed).
        actor = os.environ.get("GITHUB_ACTOR", "")
        changed = _changed_paths(base_ref)
        if soft_exit2_allowed(actor, changed):
            print(f"::warning::CodeQL 게이트 판정 불가 — {exc}")
            print("⚠️  UNVERIFIED: 게이트가 판정하지 못했으나 **비차단**으로 통과시킨다.")
            print(f"   actor={actor} · 변경 경로가 코드 면을 건드리지 않음({len(changed)}개)")
            print("   🔴 이것은 '위반 없음' 이 아니라 '**확인하지 못함**' 이다.")
            print("   근거: Dependabot 은 read-only 토큰이라 code-scanning API 를 못 읽는다(구조적).")
            return 0
        print("🔴 게이트 판정 불가 — 차단한다 (fail-closed).")
        print(f"   actor={actor!r} · 완화 대상 아님. '분석 없음'을 '위반 없음'으로 처리하지 않는다.")
        return 2

    base_numbers = {a.get("number") for a in base_alerts}

    new = select_new_alerts(pr_alerts, base_numbers)
    if not new:
        print(f"✅ 신규 CodeQL alert 없음 (base 대비) / no new CodeQL alerts vs {base_ref}")
        return 0

    print("🔴 이 PR 이 신규 CodeQL alert 를 도입했습니다 (note 심각도 포함):")
    print("   This PR introduces new CodeQL alert(s), including `note` severity:")
    print(format_violations(new))
    print()
    print("해결 / Fix: 코드를 수정하거나, 의도된 패턴이면 Security 탭에서 사유와 함께 dismiss 하세요.")
    print("   자초 CodeQL 3회 재발(#517·#540~545·#547~549)의 근본은 note 가 체크를 통과한 것입니다.")
    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure
    sys.exit(main(sys.argv))
