#!/usr/bin/env python3
"""backlog 🔴 결정 대기 카운터 — 사용자만 닫을 수 있는 항목이 방치되면 세션 시작 시 경고.
Open-decision counter — warns at session start when 🔴 rows (only the user can close them) stagnate.

## 왜 (2026-08-14 회고 P1-H → backlog R92, 사용자 결정 (a))

`docs/backlog.md` 의 상태는 셋이다: 🔴 결정 대기(사용자) · 🟡 착수 가능(Claude 자율) · ✅ 완료.
🟡 는 Claude 가 자율 착수해 **자연 소멸**한다. 🔴 은 **사용자만** 닫을 수 있는데, 그것을
사용자 앞에 다시 올리는 장치가 **하나도 없었다**.

실측 기전: `R81`·`R82` 는 P0 로 등재됐으나 **등재 세션 1회로 끝나고** 이후 6 PR 에서 한 번도
회신 요청에 재등장하지 않았다. SessionStart 훅 2종은 회고 카덴스와 owed 원장만 보고
backlog 🔴 행은 보지 않는다. 즉 **Claude 가 닫을 수 없는 유일한 클래스에만 부상 장치가
없었다** — 구조적으로 가장 정체하기 쉬운 자리에 관측자가 0이었다.

## 무엇을 재고 무엇을 안 재나 (정직 기준)

- 잰다: 🔴 행의 **개수**와, 각 행이 **몇 PR 동안 손대지 않았는지**(git 이력).
- 재지 않는다: 그 결정이 **중요한지**, 사용자가 **의도적으로 보류**한 것인지.
  산문 판정은 이 리포에서 양방향으로 틀린다(traps B5) — 그래서 이 검사는
  **판정이 아니라 촉구**다: *"이 5건이 여전히 대기 중인 게 맞는가?"*

🔴 비차단(advisory) — 항상 exit 0. 배너만 출력한다(정책 17 안정성).
Non-blocking: always exit 0; prints a banner only.

사용법 / Usage: python scripts/check_open_decisions.py
"""
from __future__ import annotations

import re
import subprocess  # nosec B404
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_BACKLOG = Path("docs/backlog.md")

# 🔴 행 형태: `| **R83** | 🔴 결정 대기 … |`
# 상태 셀 **선두**에서만 찾는다 — 본문 산문의 🔴 은 상태가 아니다(오탐 차단).
_ROW = re.compile(r"^\|\s*\*\*(R\d+)\*\*\s*\|\s*(\S)", re.MULTILINE)

# 이 수를 넘게 손대지 않았으면 정체로 본다. owed 원장 축(_STALE_PR_THRESHOLD=10)과
# 같은 크기 — 두 원장의 정체 기준이 갈라지면 어느 쪽을 믿을지 알 수 없다.
_STALE_PR_THRESHOLD = 10


def open_decisions(text: str) -> list[str]:
    """🔴 상태인 행의 ID 목록.

    🔴 **상태 셀 선두 문자로만** 판정한다. 본문에 🔴 이 흔한 리포라
    행 전체를 훑으면 거의 모든 행이 잡힌다(과교정 = 가드 자살).
    """
    return [rid for rid, state in _ROW.findall(text) if state == "🔴"]


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(  # nosec B603
            ["git", *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def merged_prs_since_backlog_touch() -> int | None:
    """backlog 가 마지막으로 바뀐 뒤 main 에 들어온 머지 커밋 수.

    ⚠️ 이것은 *"그 사이 결정이 필요했는가"* 를 모른다 — **정체만** 관측한다.
    """
    last = _git("log", "-1", "--format=%H", "--", _BACKLOG.as_posix())
    if not last or not last.strip():
        return None
    merges = _git("log", "--merges", "--oneline", f"{last.strip()}..HEAD")
    if merges is None:
        return None
    return len([ln for ln in merges.splitlines() if ln.strip()])


def main() -> int:
    # 🔴 파일 부재를 **무음 통과**로 흘리지 않는다 — "결정 0건" 과 "원장이 없다" 는 다르다.
    #    owed 카운터가 같은 클래스로 한 번 무음이었다(backlog R0-2).
    if not _BACKLOG.is_file():
        print(f"🔴 backlog 원장이 없다 ({_BACKLOG.as_posix()}) — **판정 불가**.")
        print("   결정 대기가 0건이라는 뜻이 아니다.")
        return 0

    try:
        text = _BACKLOG.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"🔴 backlog 를 읽을 수 없다 — **판정 불가** ({type(exc).__name__}).")
        return 0

    rows = _ROW.findall(text)
    if not rows:
        print("🔴 backlog 표에서 행을 **0건** 찾았다 — 파서 확인(빈 범위 위의 초록은 fail-open).")
        return 0

    pending = open_decisions(text)
    if not pending:
        print(f"✅ backlog 🔴 결정 대기 **0건** (전체 {len(rows)}행).")
        return 0

    print(f"🔴 **사용자 결정 대기 {len(pending)}건** — Claude 가 닫을 수 없는 클래스다: "
          f"{' · '.join(pending)}")
    print(f"   원장 / ledger: {_BACKLOG.as_posix()}")

    since = merged_prs_since_backlog_touch()
    if since is None:
        print("   ⚠️ backlog 갱신 이후 머지 수를 산출하지 못했다 — 정체 축 **판정 불가**.")
    elif since >= _STALE_PR_THRESHOLD:
        print(f"   🔴 backlog 가 마지막 갱신 이후 **{since} 머지** 동안 손대지지 않았다 — "
              "그 사이 이 결정들이 한 번도 재론되지 않았다는 뜻이다.")

    print("   ⚠️ 이 검사는 **중요도·의도적 보류를 판정하지 않는다** — 촉구일 뿐이다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
