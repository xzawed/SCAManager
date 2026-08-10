#!/usr/bin/env python3
"""테스트 수치 ground-truth 축 — `--collect-only` 실측 ↔ `docs/STATE.md` 대조 (회고 P0-D · R25).

## 왜 만드나 (2026-07-31 실측)

`check_docs_sync.py` 는 **문서 사본끼리만** 대조한다(그 파일 스스로 명시). 그래서 STATE 종합수치 ·
추적셀 · README 배지 2곳이 **같은 틀린 값(6205)으로 합의**하면 원리적으로 GREEN 이다 — 실측은
6269(단위 6099 + 통합 170)였다. 창 마지막 PR(#1247)이 6-step ⑤ 를 건너뛰자 아무것도 발화하지
않았고, 이후 4 PR 이 더 머지되며 drift 는 커져만 갔다. 이 스크립트가 그 **실측 대조 축**이다.

## 동작 계약 (Grok claim-review 019fb930 반영)

- 수집: `pytest <경로> --collect-only -q` 를 실행해 **마지막** `N tests collected` 매치를 파싱한다
  (`-q` 출력 앞부분은 nodeid 덤프라 첫 매치는 위험 — Grok 지적).
- 🔴 **fail-closed 는 모드 무관**: collect 프로세스 non-zero(수집 오류·"no tests collected") ·
  파싱 미검출 · STATE 정규식 미매치 → **항상 exit 1**. 이것이 `|| true` 와의 경계다 —
  advisory 가 되는 것은 **drift 판정뿐**이다.
- 모드: **기본 = drift 시 exit 1** — PR·main push 양쪽 모두 차단한다.
  `--advisory-drift` 는 남겨 두되 **CI 에서는 더 이상 쓰지 않는다**(로컬 진단용).

🔴 **2026-08-07 — PR advisory 를 걷어냈다 (P2).** 이전에는 PR 에서 exit 0 이라
드리프트가 통과했고 main push 에서만 enforce 돼 **막을 수 없는 곳에서만** 빨개졌다.
실제 사고: 오판독한 정수 하나가 `--fix` 로 4지점에 전파돼 사본은 완벽히 일치했고
(`check_docs_sync` ✅) PR 을 통과해 머지된 뒤 **main CI 가 2연속 red** 였다.

배치-PR 이월은 없애지 않고 **명시 면제**로 승격했다 — PR 본문에
`STATE-sync-deferred: <사유 16자 이상>` 을 적으면 통과하되 job summary 에 계수된다.
조용한 통과가 아니라 **보이는 결정**이 되는 것이 차이다.

## 🔴 이 가드가 증명하지 않는 것 (정직 기준)

- 🔴 **정정(2026-08-07)**: 이전 판에는 `"브랜치 보호 부재라 red 는 머지를 막지 못한다"`
  는 서술이 있었고, **그것이 PR advisory 를 유지하는 근거로 쓰였다**. 그 서술은 이미
  거짓이다 — required **10종** + `enforce_admins: true` 가 살아 있다(API 실측).
  red 는 실제로 머지를 막는다.
  (구 서술은 인용 부호 안에 둔다 — 회귀 가드가 **따옴표 밖 맨 주장**만 위반으로 본다.)
- plugin/순서 불변성은 **현재 핀 상대적**이다(pytest 9.x 고정 · deselect 훅 0 · randomly 미설치
  실측). 수집을 바꾸는 플러그인이 들어오면 이 축은 이유를 모른 채 흔들린다.
- CI(ubuntu, requirements-dev 설치)가 **권위 표면**이다 — 로컬 pytest 버전 차이는 참고용.

Ground-truth axis: compares live `--collect-only` counts against docs/STATE.md. Fail-closed on any
tool/parse failure. Drift now BLOCKS on PRs too (2026-08-07); the batch-carry escape became an
explicit, counted `STATE-sync-deferred:` marker. Branch protection is live (10 required checks +
enforce_admins), so red does physically block merges.
"""
from __future__ import annotations

import os
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

# Windows cp949 stdout 에서 한글/이모지 크래시 방지 (guards.md 관용구)
# Prevent cp949 crashes on Korean/emoji output (guards.md idiom).
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[1]

# 🔴 PR 본문은 **단일 리더**를 통해서만 읽는다 — 원문을 정규식에 넘기면 HTML 주석 안
# 마커가 "리뷰어 비가시 + 게이트 통과" 를 성립시킨다(회고 N-P0-1 · backlog R20 결함 1).
# 스크립트 간 공유 관용구는 `retro_scope.py:34` 선례를 따른다(standalone 실행이라
# sys.path 조작이 필요하다). 단일성 강제: `tests/unit/scripts/test_pr_body_single_reader.py`.
# Read the PR body only through the single hardened reader; see the guard test.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_claim_review_trace import (  # noqa: E402  # pylint: disable=wrong-import-position
    read_pr_body,
)


# 🔴 check_docs_sync._STATE_TOTAL 과 **동일 패턴 유지 의무** (PARITY GUARD — testing.md 패턴).
#   runtime import 결합 대신 사본 + 동등성 테스트(test_check_test_count_sync.py)로 drift 차단.
# Must stay identical to check_docs_sync._STATE_TOTAL; parity is test-enforced, not import-coupled.
_STATE_TOTAL = re.compile(r"전체 \*\*(\d+)\*\* 수집 \(단위 \*\*(\d+)\*\*")

# 마지막 매치 사용 + 단수형 허용 ("1 test collected") — Grok 계약.
# Use the LAST match; tolerate the singular form.
_COLLECTED = re.compile(r"(\d+) tests? collected")


def parse_collected(output: str) -> int | None:
    """`--collect-only -q` 출력에서 수집 수 — **마지막** 매치, 미검출 시 None.
    Last match of the collected-count line; None when absent (caller must fail closed)."""
    matches = _COLLECTED.findall(output)
    return int(matches[-1]) if matches else None


def collect_count(test_path: str) -> int:
    """실측 수집 — 실패는 **어떤 모드에서도** 예외로 전파한다(fail-closed).
    Run the real collection; any failure raises (fail-closed in every mode)."""
    proc = subprocess.run(  # nosec B603
        [sys.executable, "-m", "pytest", test_path, "--collect-only", "-q"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600, cwd=str(_ROOT), check=False,
    )
    # exit 5 = 수집 0건, exit 2 = 수집 오류 — 둘 다 "count 를 신뢰할 수 없음" 이다.
    # Exit 5 (nothing collected) and 2 (collection errors) both mean the count is untrustworthy.
    if proc.returncode != 0:
        raise RuntimeError(
            f"pytest collect 실패 (exit {proc.returncode}) — {test_path}\n"
            f"{(proc.stdout or '')[-500:]}\n{(proc.stderr or '')[-300:]}"
        )
    count = parse_collected(proc.stdout)
    if count is None:
        raise RuntimeError(
            f"'N tests collected' 라인을 찾지 못했다 — {test_path} (포맷 drift = 축 소멸이므로 실패)"
        )
    return count


def state_counts(state_text: str) -> tuple[int, int] | None:
    """STATE 종합수치의 (전체, 단위). 미매치 = None (호출자가 fail-closed).
    (total, unit) from STATE; None when the regex misses."""
    m = _STATE_TOTAL.search(state_text)
    return (int(m.group(1)), int(m.group(2))) if m else None


# 이월 마커 — 사유 16자 이상, **커밋 메시지**에서만 유효(아래 `deferral_carriers` 참조).
# 🔴 백틱/따옴표로 시작하는 줄은 제외한다 — 정책 19 면제 마커가 **자기를 문서화하는 PR** 을
#    면제해 버린 실사고와 같은 클래스다(`check_claim_review_trace.py` 의 `_EXEMPT` 관용구).
# 🔴 **`* ` 접두를 허용한다** (2026-08-08 적대 검증 F1 — 실측 반례).
#    GitHub squash 는 커밋이 **2건 이상**이면 각 커밋 제목에 `* ` 를 붙인다
#    (`b1eb7110`·`4d0a8dda`·`1991cfed` 실물 확인). 이월 흐름은 마커 커밋을 하나 더하므로
#    **구조적으로 항상 ≥2** 다. 그래서 마커를 커밋 **제목**에 쓰면:
#      PR 단계  : `git log --format=%B` → `STATE-sync-deferred: …` (col 0) → PASS
#      push 단계: squash 본문         → `* STATE-sync-deferred: …`      → **FAIL**
#    운반체는 살아남았는데 **표기가 바뀌어** 관측자가 못 읽는 것 — Grok `019fe026` 이
#    반증한 것과 정확히 같은 클래스다. 목록 접두(`* `/`- `)를 흡수해 닫는다.
# GitHub's squash body prefixes each commit subject with `* ` when the PR has 2+ commits.
_DEFERRED = re.compile(
    r"^[ \t]*(?:[*-][ \t]+)?(?![`'\"])STATE-sync-deferred\s*:\s*\S.{15,}", re.MULTILINE)

# 🔴 마커를 **설명하는** 문장은 마커가 아니다 (F3 — fail-open 실측).
#    커밋 메시지에 사용법을 적기만 해도 면제가 발급됐다. 백틱 배제(`(?![`'\"])`)는
#    산문 인용을 못 막는다 — 안내문은 보통 백틱 없이 쓰인다.
#    설명문의 표지: 사유 자리에 **꺾쇠 플레이스홀더**가 오거나, 같은 줄에 사용법 동사가 붙는다.
# A line that merely documents the marker must not issue an exemption.
_DEFERRED_PROSE = re.compile(
    r"STATE-sync-deferred\s*:\s*(?:<|&lt;|\[)"          # `: <사유>` 형태의 플레이스홀더
    r"|(?:형식|형태|처럼|예시|적는다|적으세요|쓰세요|사용법)[^\n]*STATE-sync-deferred",
    re.MULTILINE,
)


def is_real_deferral(text: str):
    """실제 이월 선언만 돌려준다 — 설명·인용은 제외 (F3).

    🔴 매치를 **줄 단위로** 재검사한다: 같은 커밋 메시지 안에 안내문과 실제 선언이
    함께 있을 수 있고, 그때 실제 선언은 살아야 한다(과교정 방지).
    """
    for match in _DEFERRED.finditer(text):
        line = match.group(0)
        if _DEFERRED_PROSE.search(line):
            continue
        # 안내문이 **바로 윗줄**에 있는 형태(`… 적는다:` 다음 줄에 마커)도 설명으로 본다.
        head = text[: match.start()].rsplit("\n", 2)[-2:]
        if any(_DEFERRED_PROSE.search(h) or h.rstrip().endswith(("적는다:", "적으세요:", "형식:"))
               for h in head):
            continue
        return match
    return None


def _git_text(*args: str) -> str:
    """리포 자신의 git 출력. 실패는 빈 문자열 — 호출자가 fail-closed 로 처리한다."""
    try:
        return subprocess.run(  # nosec B603 B607
            ["git", *args], cwd=str(_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60, check=False,
        ).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def deferral_carriers() -> tuple[str, str]:
    """(마커가 **유효한** 곳, 마커가 **함정인** 곳) = (커밋 메시지, PR 본문).

    ## 왜 PR 본문이 아니라 커밋 메시지인가 (2026-08-08 회고 N-P0-2)

    이월 마커의 초판은 PR 본문에서만 읽혔다. 그런데 CI 는 **두 이벤트**에서 이 게이트를 돌린다:

    | 이벤트 | `PR_BODY` | 결과 |
    |---|---|---|
    | `pull_request` | 있음 | 마커 인식 → PR 통과 |
    | `push` (머지 후 main) | **없음** | 마커 소멸 → **main red** |

    🔴 즉 마커를 처음 쓰는 사람이 **main 을 빨갛게 만든다** — 이 마커가 없애려던 사고를
    마커 자신이 재생산하는 구조였다. 사용 0건이라 아직 발현하지 않았을 뿐이다.

    고치는 방향은 "push 에도 PR 본문을 흘려보내기" 가 아니라 **머지 후에도 남는 곳에만
    마커를 인정하기** 다. 이월은 *"지금은 안 하고 나중에 한다"* 는 약속이고, 약속은
    머지 뒤에도 읽혀야 한다. 커밋 메시지는 squash 후에도 남는다.
    CLAUDE.md 6-step ⑤ 이월 분기가 이미 *"commit body 에 카운트 delta 를 기록"* 하라고
    적어 둔 것과도 일치한다 — 규약을 새로 만드는 게 아니라 집행면을 맞추는 것이다.

    🔴 **양쪽 다 "범위" 로 읽는다 — `git log -1` 은 틀린 답이었다** (Grok claim-review
    `019fe026` 가 초판을 BROKEN 으로 반증). 이 리포는 `allow_merge_commit` 과
    `allow_rebase_merge` 가 **둘 다 켜져 있다**(API 실측). 머지 커밋으로 머지하면 tip 은
    *"Merge pull request #N …"* 이라 마커가 없고, rebase-merge 로 여러 커밋이 올라가면
    마커가 tip 이 아닌 커밋에 있을 수 있다. 두 경우 다 **PR 초록 → main red** 로,
    이 함수가 없애려던 바로 그 비대칭이 그대로 재현된다.

    그래서 push 에서도 **그 push 가 실제로 들여온 커밋 전부**(`before..after`)를 본다.
    이러면 squash·merge-commit·rebase-merge 셋 다 마커를 보존한다.
    `before` 가 all-zero(새 브랜치)이거나 범위 조회가 실패하면 직전 커밋으로 물러난다 —
    그 경우 마커가 안 보이면 드리프트가 차단되므로 fail-closed 다.

    Both events read a *range*: the PR's commits, or the commits the push actually
    introduced. `git log -1` was wrong — merge commits and rebase-merges hide the marker.
    """
    base = os.environ.get("PR_BASE_SHA", "")
    head = os.environ.get("PR_HEAD_SHA", "")
    if not (base and head):
        # push 이벤트 — `github.event.before` .. `github.sha`
        base = os.environ.get("PUSH_BEFORE_SHA", "")
        head = os.environ.get("PUSH_AFTER_SHA", "")
        if set(base) <= {"0"}:  # 새 브랜치의 all-zero sentinel / new-branch sentinel
            base = ""

    commits = _git_text("log", "--format=%B", f"{base}..{head}") if base and head else ""
    return commits or _git_text("log", "-1", "--format=%B"), read_pr_body()

# 개행류 제어문자 — Actions 워크플로 커맨드 위조 차단(`\r` 이 남으면 줄이 갈라진다).
_LINE_BREAKS = re.compile(r"\s+")


def _append_step_summary(markdown: str) -> None:
    """GitHub Actions job summary 에 한 줄 추가 (없으면 무시 — 로컬 실행).

    🔴 `::notice` 는 Actions **로그 안쪽**이라 사실상 아무도 보지 않는다. 이월 남용은
    한 건씩 보면 정상이고 **추세로만** 드러나므로 사람이 실제로 여는 자리에 누적돼야 한다.
    이 저장소가 반복해 고쳐 온 "관측은 하는데 아무도 안 보는" 클래스다.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown)
    except OSError:
        pass  # 기록 실패가 판정을 바꾸면 안 된다 / logging must never change the verdict


# 🔴 본문 수치 주장 — 6-step ② 의 집행 가능한 형태 (backlog R48).
#
# 회고 권고(2026-08-08): *"전체 테스트를 돌렸는가"* 는 자기 신고라 기계가 진위를 못 잰다.
# 질문을 *"본문에 적힌 수가 실측 수집값에서 파생됐는가"* 로 바꾸면 **잴 수 있다**.
#
# 형식 2종이 실재한다(2026-08-10, 최근 20 PR 실측) — 둘 다 받아야 한다:
#   · 화살표 `pytest tests/unit  →  6841 passed / 9 skipped / EXIT=0`        (#1304~#1314)
#   · 표     `| `pytest tests/unit` 전체 | **6985 passed / 9 skipped / …** |` (#1316~#1320)
# 화살표만 지원하면 이 축은 **현행 관행에서 영원히 미실행**이 된다.
#
# `pytest tests/unit` 앵커가 뮤테이션 표(`**2 failed** / 3 passed`)를 배제한다 —
# 그 행들은 전체 스위트 주장이 아니라 개별 뮤테이션 결과다.
# Two real body formats; the `pytest tests/unit` anchor excludes per-mutation rows.
_BODY_CLAIM = re.compile(
    r"pytest[`'\"\s]*tests/unit\b[^\n]*?(\d+)\s*passed[^\n]*?(\d+)\s*skipped",
    re.IGNORECASE,
)


def parse_body_claim(body: str) -> tuple[int, int] | None:
    """PR 본문이 주장하는 `(passed, skipped)`. 미검출은 None (빈 값과 구별한다).

    마지막 매치를 쓴다 — `parse_collected` 와 같은 관용구다(앞쪽은 인용일 수 있다).
    """
    matches = list(_BODY_CLAIM.finditer(body or ""))
    if not matches:
        return None
    last = matches[-1]
    return int(last.group(1)), int(last.group(2))


def check_body_claim(body: str, unit: int) -> int:
    """본문 수치 ↔ 실측 수집값 대조. 0 = 일치 또는 미실행 / 1 = 불일치.

    🔴 **미검출을 초록으로 위장하지 않는다** — 수치 라인이 없으면 이 축은 아무것도
    검증하지 않은 것이므로 *"미실행"* 을 명시 출력한다. 빈 범위 위의 ✅ 는 이 리포가
    반복해 온 fail-open 이다(`check_lint_js_nonvacuous` 가 같은 이유로 범위 붕괴를 red 로 본다).

    🔴 **이 축이 증명하지 않는 것 (정직 기준)**: 수치를 **아예 안 적으면** 축이 돌지 않는다.
    그 우회로를 닫으려면 수치 라인을 의무화해야 하는데, 그러면 본문을 기계가 만드는
    dependabot·봇 PR 이 전부 red 가 된다 — 별도 결정 영역이라 여기서 닫지 않는다.
    A missing claim means the axis did not run; it is announced, never rendered as green.
    """
    claim = parse_body_claim(body)
    if claim is None:
        print(
            "⚠️  본문 수치 축 **미실행** — 본문에서 "
            "`pytest tests/unit … N passed / M skipped` 를 찾지 못했다.\n"
            "    이 축은 아무것도 검증하지 않았다(초록이 아니라 '안 쟀음')."
        )
        return 0
    passed, skipped = claim
    if passed + skipped == unit:
        print(
            f"✅ 본문 수치 축 일치 — 본문 {passed}+{skipped}={passed + skipped} "
            f"== 실측 단위 {unit}"
        )
        return 0
    print(
        f"🔴 본문 수치가 실측과 다르다 — 본문 {passed} passed + {skipped} skipped "
        f"= {passed + skipped} vs 실측 수집 {unit} (차 {passed + skipped - unit:+d})\n"
        "   → 6-step ② 가 요구하는 것은 '돌렸다는 말' 이 아니라 **기계값에서 파생된 수**다.\n"
        "   `py -3 -m pytest tests/unit -q` 를 다시 돌려 본문 수치를 그 출력으로 갱신하세요.\n"
        "   🔴 실측 4건이 이 형태였다(#1305 −10 · #1310 −1 · #1312 −16) — base 가 앞서간\n"
        "      탓이 아니라 본문이 틀린 것이었다(브랜치 tip 재측정으로 배제).",
        file=sys.stderr,
    )
    _append_step_summary(
        f"- 🔴 **본문 수치 불일치** — 본문 {passed + skipped} vs 실측 {unit}\n"
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    advisory_drift = "--advisory-drift" in argv

    state_file = _ROOT / "docs" / "STATE.md"
    if not state_file.is_file():
        print("🔴 docs/STATE.md 부재 — 대조 대상이 없다 (fail-closed)", file=sys.stderr)
        return 1
    documented = state_counts(state_file.read_text(encoding="utf-8"))
    if documented is None:
        print(
            "🔴 STATE 종합수치 정규식 미매치 — 형식이 바뀌면 이 축은 조용히 죽는다 (fail-closed).\n"
            "   기대 형식: 전체 **N** 수집 (단위 **N** …",
            file=sys.stderr,
        )
        return 1
    doc_total, doc_unit = documented

    try:
        unit = collect_count("tests/unit")
        integration = collect_count("tests/integration")
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        # 🔴 도구 실패는 advisory 모드에서도 실패다 — 여기서 삼키면 `|| true` 와 같다.
        # Tool failure is a failure even in advisory mode; swallowing it here would be `|| true`.
        print(f"🔴 실측 수집 실패 (모드 무관 fail-closed): {exc}", file=sys.stderr)
        return 1

    total = unit + integration

    # 🔴 본문 수치 축은 **STATE 축과 독립**이다 (R48) — STATE 가 맞아도 본문이 틀릴 수 있고,
    #    실제로 #1310 이 정확히 그 형태였다(사본 전부 일치 · 본문만 −1). 그래서 STATE 축의
    #    조기 return 앞에서 먼저 계산하고, 모든 통과 경로가 이 결과를 함께 들고 나간다.
    #    이월 마커(`STATE-sync-deferred`)도 이 축을 면제하지 않는다 — 이월은 *"STATE 갱신을
    #    나중에 한다"* 는 약속이지 *"본문에 틀린 수를 적어도 된다"* 가 아니다.
    # The body-claim axis is independent of the STATE axis and no escape hatch covers it.
    commits, pr_body = deferral_carriers()
    claim_rc = check_body_claim(pr_body, unit)

    if (total, unit) == (doc_total, doc_unit):
        print(f"✅ 테스트 수치 일치 — 전체 {total} (단위 {unit} + 통합 {integration}) == STATE")
        return claim_rc

    message = (
        f"테스트 수치 drift — 실측 전체 {total} (단위 {unit} + 통합 {integration}) "
        f"vs STATE 전체 {doc_total} (단위 {doc_unit})\n"
        "   → docs/STATE.md 종합수치 + 추적셀 + README 배지 2곳(6-step ⑤) 동기화 필요.\n"
        "   trailing sync PR 로 갱신하라 — 이 신호가 배치 이월의 종결 신호다."
    )
    # 🔴 배치-PR 이월은 없애지 않고 **명시 면제**로 승격한다 (P2, 2026-08-07).
    #    이전에는 `--advisory-drift` 가 **모든** 드리프트를 조용히 통과시켰고, 그 결과
    #    오판독한 정수가 4지점으로 전파돼 머지됐으며 main 이 2연속 red 였다.
    #    이제 이월하려면 PR 본문에 그 의도를 **적어야** 하고, 그 사용은 계수된다.
    # The batch-carry escape is now an explicit, counted marker instead of a silent pass.
    deferral = is_real_deferral(commits)
    if deferral:
        reason = _LINE_BREAKS.sub(" ", deferral.group(0).strip())[:200]
        print(f"::notice title=STATE sync deferred::{reason}")
        _append_step_summary(
            "- ⏭️ **STATE 수치 동기화 이월**\n"
            f"  - {message.splitlines()[0]}\n  - 사유: {reason}\n"
        )
        print(f"⏭️  이월 마커 확인 — {message.splitlines()[0]}")
        return claim_rc

    # 🔴 마커가 PR 본문에만 있으면 **여기서** 실패시킨다 — 통과시켜 놓고 머지 후 main 에서
    #    빨개지게 두면, 이 마커가 없애려던 사고를 마커가 재생산한다(회고 N-P0-2).
    #    "조용히 무시" 도 답이 아니다: 저자는 면제를 적었다고 믿고 떠난다.
    # A body-only marker fails here rather than after the merge, where it cannot be fixed cheaply.
    if is_real_deferral(pr_body):
        print(
            f"🔴 {message}\n\n"
            "   이월 마커가 **PR 본문에만** 있습니다 — 머지 후 push 이벤트에는 PR 본문이\n"
            "   전달되지 않아 그대로 main 이 빨개집니다. 마커를 **커밋 메시지**로 옮기세요:\n"
            '     git commit --allow-empty -m "chore: STATE 동기화 이월" '
            '-m "STATE-sync-deferred: <왜 이 PR 에서 안 하는가 — 16자 이상>"',
            file=sys.stderr,
        )
        return 1

    if advisory_drift:
        print(f"⚠️  (advisory) {message}\n   ⚠️ 이 모드는 CI 에서 더 이상 쓰이지 않는다(로컬 진단용).")
        return 0
    print(f"🔴 {message}", file=sys.stderr)
    print(
        "\n   배치-PR 이월이라 이번 PR 에서 동기화하지 않는다면 **커밋 메시지**에 적으세요:\n"
        '     git commit --allow-empty -m "chore: STATE 동기화 이월" '
        '-m "STATE-sync-deferred: <왜 이 PR 에서 안 하는가 — 16자 이상>"\n'
        "   🔴 PR 본문이 아니라 커밋 메시지입니다 — 본문은 머지 후 push 이벤트에 전달되지\n"
        "      않아 main 이 빨개집니다(회고 N-P0-2).\n"
        "   🔴 그 사용은 job summary 에 계수됩니다 — 조용한 통과가 아닙니다.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
