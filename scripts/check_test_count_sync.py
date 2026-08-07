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


# 이월 마커 — 사유 16자 이상, PR **본문**에서만 유효.
# 🔴 백틱/따옴표로 시작하는 줄은 제외한다 — 정책 19 면제 마커가 **자기를 문서화하는 PR** 을
#    면제해 버린 실사고와 같은 클래스다(`check_claim_review_trace.py` 의 `_EXEMPT` 관용구).
_DEFERRED = re.compile(
    r"^[ \t]*(?![`'\"])STATE-sync-deferred\s*:\s*\S.{15,}", re.MULTILINE)

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
    if (total, unit) == (doc_total, doc_unit):
        print(f"✅ 테스트 수치 일치 — 전체 {total} (단위 {unit} + 통합 {integration}) == STATE")
        return 0

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
    deferral = _DEFERRED.search(os.environ.get("PR_BODY", "") or "")
    if deferral:
        reason = _LINE_BREAKS.sub(" ", deferral.group(0).strip())[:200]
        print(f"::notice title=STATE sync deferred::{reason}")
        _append_step_summary(
            "- ⏭️ **STATE 수치 동기화 이월**\n"
            f"  - {message.splitlines()[0]}\n  - 사유: {reason}\n"
        )
        print(f"⏭️  이월 마커 확인 — {message.splitlines()[0]}")
        return 0

    if advisory_drift:
        print(f"⚠️  (advisory) {message}\n   ⚠️ 이 모드는 CI 에서 더 이상 쓰이지 않는다(로컬 진단용).")
        return 0
    print(f"🔴 {message}", file=sys.stderr)
    print(
        "\n   배치-PR 이월이라 이번 PR 에서 동기화하지 않는다면 본문에 아래를 적으세요:\n"
        "     STATE-sync-deferred: <왜 이 PR 에서 안 하는가 — 16자 이상>\n"
        "   🔴 그 사용은 job summary 에 계수됩니다 — 조용한 통과가 아닙니다.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
