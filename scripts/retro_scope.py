#!/usr/bin/env python3
"""회고 범위를 **기계 산출**한다 — 손으로 적지 않는다.

## 왜 필요한가 (2026-07-19 회고 P0)

정책 8 진화 (5)는 회고 범위를 *"직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**"* 로
규정한다(`CLAUDE.md`). 그런데 그 정책을 신설한 세션이 **첫 적용에서 자기 산출물 2건을
누락**했다 — 범위를 손으로 `#1108~#1129` 라 적었고, 회고 착수 직전에 머지된 `#1130`·`#1131`
이 빠졌다. 정책이 명명한 시나리오("가장 검증이 덜 된 코드가 회고를 피해간다")가 정책 신설
당일 그대로 발생했다.

🔴 **손으로 적는 한 항상 '진입 직전 머지분'이 빠진다.** 사람이 범위를 적는 시점과 회고가
시작되는 시점 사이에 머지가 일어나기 때문이고, 이건 주의력으로 못 막는다.

The retro scope must be computed, not typed: whatever is merged between writing the scope and
starting the run is silently excluded — exactly the case the policy exists to prevent.

## 사용법 / Usage

    python scripts/retro_scope.py            # 사람이 읽는 요약
    python scripts/retro_scope.py --json     # 워크플로 args 에 넣을 JSON
    python scripts/retro_scope.py --no-fetch # origin/main 을 받지 않는다 — unmeasured 에 남는다

최신 회고 판정(`newest_retro`)은 이 파일이 단일 출처다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

# 정식 회고 파일명 = YYYY-MM-DD-...retrospective....md
# Formal-retro filename must contain 'retrospective'; audits/reviews/plans are excluded.
_RETRO_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-.*retrospective.*\.md$")


def retro_date(filename: str) -> str | None:
    """정식 회고 파일명에서 날짜(YYYY-MM-DD) 추출 — 회고 아니면 None.
    Extract the date from a formal-retro filename; None if not a retrospective."""
    m = _RETRO_NAME.match(filename)
    return m.group(1) if m else None


def _retro_seq(filename: str) -> int:
    """같은 날 회고의 순번 — `-N.md` 접미사가 있으면 N, 없으면 1.
    Sequence within a same-day set: `-N.md` suffix → N, otherwise 1."""
    m = re.search(r"-(\d+)\.md$", filename)
    return int(m.group(1)) if m else 1


def newest_retro(filenames):
    """정식 회고 파일명 목록에서 가장 최신 반환 — 없으면 None.
    Return the newest formal-retro filename, or None.

    정렬 키 = (날짜, 같은 날 순번). 파일명 문자열은 tie-break 에 쓰지 않는다 —
    사전순은 최신성과 무관하다 (`-`(0x2D) < `.`(0x2E) 이라 1차가 2차를 이긴다).
    Sorted by (date, same-day sequence); the filename string is never a tiebreaker.
    """
    dated = [(d, _retro_seq(f), f) for f in filenames if (d := retro_date(f))]
    return max(dated)[2] if dated else None


_ROOT = Path(__file__).resolve().parents[1]
_REPORTS = _ROOT / "docs" / "reports"

# 범위 상한 — main 의 원격 추적 ref. 리터럴 `HEAD` 를 쓰지 않는다(회고 2026-09-16 P0).
# Upper bound of the range: the remote-tracking main, never the literal HEAD.
_MAIN_REF = "origin/main"


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    🔴 standalone 실행이라 공유 헬퍼를 import 하지 않고 관용구를 복제한다(정책 16 최소 추상화).
    누락 방지는 `tests/unit/scripts/test_stdout_encoding_guard.py` 가 담당.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def _git(args: list[str]) -> str:
    """git 호출 — 실패 시 빈 문자열(호출자가 판단). encoding 명시 의무(cp949 오디코딩 방지)."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )
        return r.stdout if r.returncode == 0 else ""
    except OSError:
        return ""


def boundary_commit(retro_filename: str) -> str | None:
    """회고 리포트가 **추가된** 커밋 = 범위 경계. 없으면 None.
    The commit that ADDED the retro report is the range boundary."""
    path = f"docs/reports/{retro_filename}"
    sha = _git(["log", "--diff-filter=A", "--format=%H", "-1", "--", path]).strip()
    return sha or None


def merged_prs(boundary: str, upper: str = _MAIN_REF) -> list[int]:
    """경계 이후 `upper`(기본 `origin/main`)까지의 squash-merge PR 번호 — **오름차순**.

    🔴 **호출 시점**에 센다. 사람이 적은 목록은 작성 시점에 고정된다.
    🔴 상한은 리터럴 `HEAD` 가 아니다(회고 2026-09-16 P0). 피처 브랜치에서 돌리면 HEAD 는 그
    브랜치 끝이라, 막 main 에 머지된 PR(#1684)이 빠지고 브랜치 커밋 제목의 Issue 번호
    `(#N)` 가 PR 로 세어진다. main 의 squash 제목 끝 `(#N)` 만 PR 번호다.
    Counted at call time. The upper bound is origin/main: a feature-branch HEAD drops PRs just
    merged to main and counts Issue numbers in branch commit subjects as PRs.
    """
    out = _git(["log", "--format=%s", f"{boundary}..{upper}"])
    nums = []
    for line in out.splitlines():
        # squash 머지 제목 끝의 (#NNNN)
        if (i := line.rfind("(#")) != -1 and line.rstrip().endswith(")"):
            tail = line[i + 2:].rstrip(")").strip()
            if tail.isdigit():
                nums.append(int(tail))
    return sorted(set(nums))


def _gh_json(args: list[str]) -> object | None:
    """gh 호출 — 부재·실패·비JSON 이면 None. 호출자는 그것을 «안 쟀음» 으로 다룬다."""
    try:
        r = subprocess.run(
            ["gh", *args], cwd=_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def commit_time(ref: str) -> str | None:
    """커밋 시각(ISO 8601, 오프셋 포함) — 해석 실패면 None."""
    t = _git(["log", "-1", "--format=%cI", ref]).strip()
    return t or None


def _parse_iso(text: str) -> dt.datetime | None:
    """ISO 8601 시각을 UTC 기준 aware datetime 으로 — 해석 실패면 None.

    git 의 `%cI` 는 `+09:00` 같은 오프셋을, GitHub 의 `mergedAt` 은 `Z` 를 쓴다.
    오프셋이 없으면 UTC 로 본다.
    """
    try:
        t = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def fetch_main() -> bool:
    """`git fetch origin main` — 성공했는지만 돌려준다. 네트워크·원격이 없으면 False."""
    try:
        r = subprocess.run(
            ["git", "fetch", "--quiet", "origin", "main"], cwd=_ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


_HEAD_SHA = re.compile(r"\bhead\b[^0-9a-f]{0,12}([0-9a-f]{7,40})\b", re.I)


def report_head(retro_filename: str) -> str | None:
    """리포트가 기록한 «분석 종료 시점 HEAD» SHA — 해석되는 것만 돌려준다.

    🔴 경계 갭(#1564·#1567 이 어느 창에도 없던 사건)은 이것 없이는 **원리적으로** 못 닫는다.
    경계 커밋은 리포트가 «머지된» 시점이고, 회고의 분석은 그보다 앞에서 끝난다. 그 사이
    머지분을 가리려면 회고가 본 HEAD 를 리포트가 스스로 적어 두는 수밖에 없다.

    옛 리포트는 이 값이 없거나(미기재) squash 로 SHA 가 소멸해 해석되지 않는다 —
    그때는 None 을 돌려 호출자가 「이 축은 안 쟀다」로 다루게 한다. 날짜로 근사하지 않는다:
    실측상 리포트 날짜로 자르면 직전 창 말미가 3~7건 겹쳐 들어와 «정밀한 척» 이 된다.

    The boundary commit is when the report MERGED; the analysis ended earlier. Only a
    head SHA recorded by the report itself can close that gap — otherwise report it unmeasured.
    """
    path = _REPORTS / retro_filename
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines()[:40]:
        m = _HEAD_SHA.search(line)
        if m and resolve_ref(m.group(1)):
            return m.group(1)
    return None


def github_merged_prs(since_iso: str) -> list[int] | None:
    """창 시작 시각(`since_iso`) **뒤에** 머지된 모든 PR 번호 — gh 를 못 쓰면 None.

    🔴 base 로 거르지 않는다(회고 2026-09-16 P0). 예전 판정식 `baseRefName != "main"` 은
    base=main 인 PR 이 git log 에서 빠지는 경우(상한이 main 이 아니었다 · 원격 ref 가 낡았다)를
    원리적으로 못 봤다. git log 산출과의 **차집합**이 곧 «git log 가 못 본 것» 이다 —
    stacked PR(부모의 squash 하나로 접혀 main 제목에 `(#N)` 을 남기지 않는다)도, base=main
    탈출도 같은 식에 걸린다.

    🔴 창은 날짜가 아니라 **시각**으로 자른다. 날짜로 자르면 직전 창 말미가 겹쳐 들어오고
    (실측 3~7건), 그 과포함을 PR 번호 하한으로 막던 우회는 Grok 이 반증한 설계였다
    (회고 2026-09-16 P2-15). 검색어의 날짜는 후보를 줄이는 값싼 필터일 뿐 판정식이 아니다.

    🔴 커밋 **본문** 파싱은 처방이 아니다 — 본문의 `(#N)` 대다수가 Issue 번호라 정밀도가
    3/10 이었다(GitHub 은 Issue 와 PR 이 번호 공간을 공유한다).

    Every PR merged after the window start, regardless of base; the window is a timestamp,
    and the search date only narrows the query.
    """
    start = _parse_iso(since_iso)
    if start is None:
        return None
    # 검색 날짜는 UTC 기준 하루 앞 — 오프셋 차이로 창 앞쪽을 잘라 먹지 않게 한다.
    # Search one UTC day earlier so a timezone offset never trims the window's start.
    day = (start.astimezone(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    rows = _gh_json([
        "pr", "list", "--state", "merged", "--limit", "500",
        "--search", f"merged:>={day}", "--json", "number,mergedAt",
    ])
    if not isinstance(rows, list):
        return None
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        merged_at, number = row.get("mergedAt"), row.get("number")
        if not (isinstance(merged_at, str) and isinstance(number, int)):
            continue
        t = _parse_iso(merged_at)
        if t is not None and t > start:
            out.append(number)
    return sorted(set(out))


def resolve_ref(ref: str) -> str | None:
    """ref 를 커밋 SHA 로 해석 — 존재하지 않으면 None (조용히 넘기지 않는다)."""
    sha = _git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]).strip()
    return sha or None


def compute(since: str | None = None, fetched: bool = False) -> dict:
    """범위 산출 결과 dict — 실패도 사유와 함께 담는다.

    `fetched` 는 호출자가 직전에 `origin/main` 을 받았는지다. 받지 않았으면 원격 ref 가
    낡았을 수 있어 `unmeasured` 에 `origin-main-not-fetched` 를 싣는다.

    앵커는 두 가지이고 **리포트가 정본**이다:

    - `anchor="report"` : `docs/reports/` 의 최신 정식 회고 → 그 파일을 **추가한** 커밋이 경계.
    - `anchor="explicit"`: 리포트가 없을 때 호출자가 준 `since` 가 경계.

    🔴 **경계를 지어내지 않는다.** 리포트도 `since` 도 없으면 `ok:false` 다 —
    다만 사유에 다음 행동(`--since`)을 담는다. 종전 사유는 「정식 회고 리포트 없음」 한 줄이라
    거기서 할 수 있는 것이 없었고, 그 상태로 **3개월**이 지났다(리포트는 2026-05-25 `#643`
    에서 아카이브됐다). 그 사이 회고는 계속 돌았으므로 스킬 1단계 「범위는 기계에서 얻는다 ·
    손 조립 금지」가 원리적으로 불가능했다 — 이 함수가 그 구멍이었다.

    🔴 `since` 는 **우회가 아니다**. 경계 하나만 사람이 주고 PR 목록은 여전히 기계가 센다.
    Two anchors; the report wins. Never invents a boundary — an absent one stays ok:false,
    but the reason now carries the next action.
    """
    newest = None
    if _REPORTS.is_dir():
        newest = newest_retro(
            [p.name for p in _REPORTS.glob("*.md") if _RETRO_NAME.match(p.name)]
        )

    if newest:
        boundary = boundary_commit(newest)
        if not boundary:
            return {"ok": False, "reason": f"경계 커밋 판정 실패 / no add-commit for {newest}"}
        anchor = "report"
    elif since:
        boundary = resolve_ref(since)
        if not boundary:
            return {
                "ok": False,
                "reason": f"--since 해석 실패: {since!r} 는 이 저장소의 커밋이 아니다",
            }
        anchor = "explicit"
    else:
        return {
            "ok": False,
            "reason": (
                "정식 회고 리포트 없음 — `docs/reports/*-retrospective.md` 가 0건이다. "
                "직전 회고 경계를 알면 `--since <sha|tag>` 로 주면 그 뒤는 기계가 센다. "
                "새 회고를 마쳤다면 스킬 3단계대로 리포트를 써서 다음부터 자동 앵커가 되게 할 것."
            ),
        }

    unmeasured: list[str] = []

    # 🔴 상한 축 — 범위는 `origin/main` 까지 센다(회고 2026-09-16 P0). 원격 ref 가 없으면 HEAD 로
    #    세되 그 사실을 넘기고, 받지 않은 ref 는 낡았을 수 있다고 넘긴다.
    main_sha = resolve_ref(_MAIN_REF)
    upper = _MAIN_REF if main_sha else "HEAD"
    if not main_sha:
        unmeasured.append("origin-main-absent")
    elif not fetched:
        unmeasured.append("origin-main-not-fetched")
    # 🔴 HEAD 축 — 회고가 읽는 작업 트리가 main 끝과 다르면 미머지 커밋이나 아직 안 받은 머지가
    #    PR 목록 밖에 있다. 이것을 「일치한다」로 인쇄한 것이 P0 의 두 번째 기전이었다.
    if main_sha and resolve_ref("HEAD") != main_sha:
        unmeasured.append("head-not-main")

    # 🔴 경계 갭 축 — 리포트가 «분석 종료 HEAD» 를 적어 뒀으면 거기서부터 센다.
    #    경계 커밋은 리포트가 머지된 시점이라 그 사이 머지분이 어느 창에도 없었다(P1).
    #    적혀 있지 않으면 근사하지 않고 「안 쟀다」로 넘긴다.
    scan_from = boundary
    if newest and (rh := report_head(newest)):
        scan_from = rh
    elif anchor == "report":
        unmeasured.append("report-merge-gap")

    prs_git = merged_prs(scan_from, upper)

    # 🔴 GitHub 대조 축 — 스캔 기점 커밋 시각 뒤에 머지된 PR 전체와 git log 산출의 차집합.
    #    stacked PR 도 base=main 탈출도 이 식 하나에 걸린다.
    since_iso = commit_time(scan_from)
    gh_nums = github_merged_prs(since_iso) if since_iso else None

    if gh_nums is None:
        prs, gh_only = prs_git, []
        gh_checked = False
        # 🔴 「안 쟀음」은 「통과」가 아니다 — 이 축이 비었다는 사실을 소비자에게 넘긴다.
        unmeasured.append("github-cross-check")
    else:
        gh_only = sorted(set(gh_nums) - set(prs_git))
        prs = sorted(set(prs_git) | set(gh_only))
        gh_checked = True

    head = _git(["rev-parse", "--short", "HEAD"]).strip()
    return {
        "ok": True,
        "anchor": anchor,
        "prev_retro": newest,
        "boundary": boundary[:7],
        "head": head,
        "main_head": main_sha[:8] if main_sha else None,
        "pr_count": len(prs),
        "prs": prs,
        "range": f"#{prs[0]}~#{prs[-1]}" if prs else "(없음)",
        # 🔴 아래 셋은 소비자가 «읽어야» 의미가 있다. 워크플로 SCOPE_SCHEMA 가 이 이름을
        #    요구하도록 배선돼 있고, 그 배선을 지우면 누락이 다시 조용해진다.
        "gh_checked": gh_checked,
        "gh_only": gh_only,
        "unmeasured": unmeasured,
    }


def main() -> int:
    """CLI 진입점 — 사람이 읽는 요약 또는 `--json` 출력."""
    _make_stdout_safe()
    ap = argparse.ArgumentParser(description="회고 범위 기계 산출 / compute retro scope")
    ap.add_argument("--json", action="store_true", help="JSON 출력 (워크플로 args 용)")
    ap.add_argument(
        "--since", metavar="REF",
        help="리포트가 없을 때의 경계 커밋/태그. 리포트가 있으면 그쪽이 정본이다.",
    )
    ap.add_argument(
        "--no-fetch", action="store_true",
        help="`git fetch origin main` 을 건너뛴다(오프라인·테스트). 결과에 그 사실이 남는다.",
    )
    args = ap.parse_args()

    # 🔴 범위 상한이 origin/main 이므로 먼저 받는다 — 낡은 ref 는 막 머지된 PR 을 놓친다.
    r = compute(since=args.since, fetched=False if args.no_fetch else fetch_main())
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["ok"] else 1

    if not r["ok"]:
        print(f"❌ 범위 산출 실패: {r['reason']}")
        return 1
    print("회고 범위 (기계 산출 — 손으로 적지 말 것)")
    if r["anchor"] == "report":
        print(f"  직전 정식 회고 : {r['prev_retro']}")
    else:
        # 🔴 어떤 앵커였는지 숨기지 않는다 — 명시 경계는 사람이 준 값이라 신뢰 등급이 다르다.
        print("  직전 정식 회고 : (없음) — `--since` 로 준 명시 경계를 썼다")
    print(f"  경계 커밋      : {r['boundary']}  → origin/main {r['main_head'] or '(없음)'}")
    print(f"  작업 트리 HEAD : {r['head']}")
    print(f"  머지 PR        : {r['pr_count']}건  {r['range']}")
    print(f"  전체           : {', '.join('#' + str(n) for n in r['prs'])}")
    if r["gh_checked"]:
        if r["gh_only"]:
            print(f"  🔴 git log 가 못 본 것: {', '.join('#' + str(n) for n in r['gh_only'])}")
            print("     (stacked PR · base=main 탈출 · 리포트 머지 전 갭 — GitHub 대조로만 보인다)")
        else:
            print("  GitHub 대조    : 차집합 0 — git log 산출과 일치")
    else:
        print("  🔴 GitHub 대조 **미실행** — `gh` 를 쓸 수 없다. 이 축은 아무것도 검증하지 않았다")
        print("     (stacked PR 과 리포트 머지 전 갭은 git log 로 원리적으로 안 보인다)")
    if r["unmeasured"]:
        print(f"  🔴 안 잰 축     : {', '.join(r['unmeasured'])} — 「없다」가 아니라 「안 쟀다」")
    print()
    print("🔴 회고 착수 **직전에** 다시 실행할 것 — 그 사이 머지분이 빠지는 것이 P0 의 기전이었다.")
    if r["anchor"] == "explicit":
        print("🔴 이번 범위의 경계는 **사람이 준 값**이다. 회고를 마치면 스킬 3단계대로")
        print("   `docs/reports/YYYY-MM-DD-retrospective.md` 를 써서 다음부터 자동 앵커가 되게 할 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
