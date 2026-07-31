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
- 모드: 기본 = drift 시 exit 1 (main push 용). `--advisory-drift` = drift 시 loud 경고 + exit 0
  (PR 용 — PR 마다 STATE 수정을 강제하면 병렬 PR STATE 충돌을 배치 이월 규칙이 막으려던 그대로
  재생산하므로, PR 은 신호만 주고 main 에서 빨간다).

## 🔴 이 가드가 증명하지 않는 것 (정직 기준)

- **브랜치 보호 부재(R2-b)라 red 는 머지를 물리적으로 막지 못한다** — red 가 어디 보이느냐를
  바꿀 뿐이다. "기계적 종결" 이 아니라 **프로세스 신호**다.
- plugin/순서 불변성은 **현재 핀 상대적**이다(pytest 9.x 고정 · deselect 훅 0 · randomly 미설치
  실측). 수집을 바꾸는 플러그인이 들어오면 이 축은 이유를 모른 채 흔들린다.
- CI(ubuntu, requirements-dev 설치)가 **권위 표면**이다 — 로컬 pytest 버전 차이는 참고용.

Ground-truth axis: compares live `--collect-only` counts against docs/STATE.md. Fail-closed on any
tool/parse failure in BOTH modes; only the drift verdict is advisory on PRs. Red does not physically
block merges (no branch protection) — this moves where red appears, nothing more.
"""
from __future__ import annotations

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
    if advisory_drift:
        print(f"⚠️  (advisory) {message}\n   PR 은 통과시킨다 — main push 에서 enforce 된다.")
        return 0
    print(f"🔴 {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
