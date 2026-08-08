#!/usr/bin/env python3
"""e2e 검사 범위 가드 — 수집 건수가 baseline 미만이면 실패 (backlog R58).

## 왜 필요한가 (2026-08-06 5+1 회고 P1)

e2e 초록에는 **두 가지 공허화 경로**가 있었다.

1. **전건 skip** — `live_server` 가 `/health` 폴링에 실패하면 `pytest.skip` 을 던져
   121건이 전부 skip 되고 pytest 는 exit 0 을 낸다. 🔴 **앱이 부팅조차 못 해도 CI 가
   초록이고 배지도 초록**이다(뮤테이션 실측: `121 skipped … exit=0`).
   → `e2e/conftest.py` 에서 skip 을 `RuntimeError` 로 바꿔 닫았다.
2. **검사 범위 축소** — 테스트를 지우거나 조건부로 빼면 남은 것만 통과하고 job 은
   초록이다. skip 을 실패로 바꿔도 이 축은 그대로 열려 있다.
   → **이 스크립트**가 커밋된 기대값과 대조해 닫는다.

이 리포는 같은 창에서 `lint-js`·의존성 핀·STATE 이력 절 **3 표면에 '범위 비면 fail'**
을 이미 적용해 두고, **자기가 방금 초록으로 만든 e2e 에만** 적용하지 않았다.

## 계약

- baseline = `e2e/EXPECTED_COUNT` (커밋된 정수 한 줄).
- **미만이면 실패**. 초과는 통과한다 — 테스트 추가를 막을 이유가 없다.
  다만 크게 늘면 baseline 갱신을 권고 출력한다(차단 아님).
- 수집 자체가 실패하거나 숫자를 못 읽으면 **실패**(fail-closed). 파싱 실패를
  "0건이지만 통과" 로 흘려보내면 이 가드 자신이 공허해진다.

E2E scope guard: fails when collection drops below the committed baseline.
"""
from __future__ import annotations

import io
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[1]
_BASELINE = _ROOT / "e2e" / "EXPECTED_COUNT"
# pytest `--collect-only -q` 마지막 줄: "121 tests collected in 0.04s"
_COLLECTED = re.compile(r"(\d+)\s+tests?\s+collected")
# 수집 오류 동반 표기 — "N tests collected, M errors" / "errors during collection"
_COLLECT_ERROR = re.compile(r"errors?", re.IGNORECASE)


def read_baseline(path: Path = _BASELINE) -> int | None:
    """baseline 정수. 파일이 없거나 정수가 아니면 None (호출부가 fail-closed 처리)."""
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def parse_collected(output: str) -> int | None:
    """`--collect-only -q` 출력에서 수집 건수. **마지막** 매치를 쓴다.

    앞부분은 nodeid 덤프라 첫 매치는 위험하다(`check_test_count_sync` 와 같은 관용구).

    🔴 **collection error 가 섞이면 None**(fail-closed) — Grok claim-review `71bd2d6c` 적발.
    초판은 `2 tests collected, 1 error` 에서 **2 를 뽑아** 그 수가 baseline 이상이면
    통과시켰다. 즉 *일부 모듈이 import 실패했는데 나머지로 범위를 채우면* 초록이었다.
    A partial collection with errors must not be treated as a valid count.
    """
    if _COLLECT_ERROR.search(output):
        return None
    matches = _COLLECTED.findall(output)
    return int(matches[-1]) if matches else None


# `docs/STATE.md` 가 적어 둔 내역 표기 — `= 121 collected (110 표준 + 11 perf)`.
_DOC_SPLIT = re.compile(r"=\s*(\d+)\s+collected\s*\(\s*(\d+)\s*표준\s*\+\s*(\d+)\s*perf\s*\)")


# 🔴 `-m` 로 좁히면 pytest 는 **다른 형식**을 쓴다: `11/121 tests collected (110 deselected)`.
# `parse_collected` 의 패턴은 " tests collected" 바로 앞 숫자를 잡으므로 **분모(121)**를
# 가져온다 — 필터가 안 걸린 것처럼 보인다(실측으로 발견). 전용 파서가 필요하다.
# Filtered runs print `selected/total`; the general parser grabs the total, not the selection.
_SELECTED = re.compile(r"(\d+)\s*/\s*\d+\s+tests?\s+collected")


def _collect_count(marker: str) -> int | None:
    """`-m <marker>` 로 좁힌 e2e 수집 건수. 실패는 None (호출부 fail-closed)."""
    proc = subprocess.run(  # nosec B603 B607
        [sys.executable, "-m", "pytest", "e2e/", "--collect-only", "-q",
         "-p", "no:asyncio", "-m", marker],
        cwd=_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        return None
    out = proc.stdout or ""
    if _COLLECT_ERROR.search(out):
        return None
    if (m := _SELECTED.search(out)) is not None:
        return int(m.group(1))
    # 전부 선택되면 pytest 는 `selected/total` 대신 `N tests collected` 를 쓴다.
    return parse_collected(out)


def _check_documented_split(actual_total: int) -> int:
    """`docs/STATE.md` 의 `(N 표준 + M perf)` 내역을 **실측과 성분별로** 대조한다.

    🔴 합계만 보면 안 된다 — 합이 맞는 거짓 쌍은 무한히 많고, 실제로 그 형태로 틀렸다
    (`109 + 12 = 121` 인데 진실은 `110 + 11`). 성분을 각각 잰다.
    """
    state = _ROOT / "docs" / "STATE.md"
    try:
        match = _DOC_SPLIT.search(state.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"\n❌ STATE.md 를 읽지 못했다: {exc}")
        return 1
    if match is None:
        print("\n❌ STATE.md 에서 `= N collected (A 표준 + B perf)` 표기를 찾지 못했다.")
        print("   → 표기를 바꿨다면 이 가드의 패턴도 함께 갱신할 것. **미매치는 통과가 아니다**.")
        return 1

    doc_total, doc_std, doc_perf = (int(g) for g in match.groups())
    perf = _collect_count("perf")
    standard = _collect_count("not perf")
    if perf is None or standard is None:
        print("\n❌ perf/표준 분리 수집에 실패했다 — 내역을 신뢰할 수 없다(fail-closed).")
        return 1

    problems = []
    if doc_total != actual_total:
        problems.append(f"총계 {doc_total} ≠ 실측 {actual_total}")
    if doc_perf != perf:
        problems.append(f"perf {doc_perf} ≠ 실측 {perf}")
    if doc_std != standard:
        problems.append(f"표준 {doc_std} ≠ 실측 {standard}")
    if problems:
        print("\n❌ STATE.md 의 e2e 내역이 실측과 다르다: " + " · ".join(problems))
        print(f"   실측: {actual_total} = {standard} 표준 + {perf} perf")
        print("   → `docs/STATE.md` §테스트 유형 표의 E2E 셀을 실측값으로 고칠 것.")
        return 1

    print(f"✅ 내역 일치 — {actual_total} = {standard} 표준 + {perf} perf")
    return 0


def main() -> int:
    print("=== e2e 검사 범위 점검 / E2E Scope Check ===\n")
    expected = read_baseline()
    if expected is None:
        print(f"❌ baseline 을 읽을 수 없다: {_BASELINE}")
        print("   → 정수 한 줄을 담은 파일이어야 한다. 없는 상태로 통과시키면 가드가 공허해진다.")
        return 1

    proc = subprocess.run(  # nosec B603 B607
        [sys.executable, "-m", "pytest", "e2e/", "--collect-only", "-q", "-p", "no:asyncio"],
        cwd=_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        # 🔴 수집이 non-zero 로 끝났으면 숫자가 보여도 신뢰할 수 없다(fail-closed).
        print(f"❌ 수집 프로세스가 실패했다 (exit={proc.returncode}) — 숫자를 신뢰하지 않는다.")
        print((proc.stdout or "")[-800:])
        return 1

    actual = parse_collected(proc.stdout or "")
    if actual is None:
        print("❌ 수집 건수를 파싱하지 못했다 — 수집 자체가 실패했을 수 있다(fail-closed).")
        print((proc.stdout or "")[-800:])
        print((proc.stderr or "")[-400:])
        return 1

    print(f"baseline {expected} · 실측 {actual}")
    if actual < expected:
        print(f"\n❌ e2e 수집 건수가 baseline 미만 ({actual} < {expected}) — **검사 범위 축소**")
        print("   → 테스트를 의도적으로 줄였다면 `e2e/EXPECTED_COUNT` 를 **같은 PR 에서** 갱신할 것.")
        print("   → 의도치 않았다면 수집 오류(import 실패·조건부 skip)를 먼저 확인할 것.")
        return 1

    # 🔴 문서가 적어 둔 **내역**(표준 + perf)도 실측과 대조한다 (2026-08-08 적대 검증 P0).
    #    사고: `#1316` 이 이 셀의 총계를 122→121 로 고치면서 내역을 `109 표준 + 12 perf` 로
    #    적었는데 실측은 **110 + 11** 이었다 — 두 성분 다 거짓. 그리고 같은 커밋이 만든
    #    전용 집행자(`test_e2e_count_has_one_source.py`)는 `총계 == 표준 + perf` 만 봐서
    #    **초록인 채로 거짓을 지켰다**. 합이 맞는 거짓 쌍은 무한히 많다.
    # 🔴 이 검사가 **여기** 있는 이유: e2e 수집은 playwright 환경이 필요해 단위 테스트 job
    #    에서는 돌릴 수 없다. 이 스크립트는 이미 e2e 를 수집하는 유일한 CI 지점이다.
    # The documented split is verified where e2e can actually be collected — a unit test
    # cannot, and a sum-only assertion keeps any wrong-but-consistent pair green.
    if (rc := _check_documented_split(actual)) != 0:
        return rc

    if actual > expected:
        print(f"\n✅ 통과 (baseline 초과 +{actual - expected}) — 여유가 커지면 baseline 갱신 권고")
    else:
        print("\n✅ 통과 — 검사 범위 유지")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
