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

🔴 **배너는 자기 계수를 증명하지 못한다** (2026-08-14 Grok `019fffde` 반례 (a) 잔여).
`open_decisions()` 를 통째로 죽이면 *"결정 대기 없음"* 이 인쇄되고, 그것은 진짜 0건과
**같은 문구**다 — 계수 함수 자신이 계수의 유일한 근거이므로 원리적으로 그렇다.
파서 파손(행 0개)만 다른 문구로 구별된다. 이 축의 실제 관측자는
`tests/unit/scripts/test_open_decisions.py` 이며, 계수를 죽이면 **8건이 red** 다.
배너를 계수 건강의 증거로 읽지 말 것.

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

# 원장 행: `| **R83** | 🔴 결정 대기 … |`
#
# 🔴 **ID 를 `R\d+` 로 좁히면 위음성이 난다** (2026-08-14 Grok `019fffde` 반례 (e)).
#    초판은 `R\d+` 만 봐서 실원장의 `R0-2` · `B6-b` · `B2` · `H2` 를 **한 번도 세지 않았다**.
#    이 카운터에서 거짓 음성은 거짓 양성보다 나쁘다 — 안 보이면 영원히 정체한다.
_ROW = re.compile(r"^\|\s*\*{0,2}([A-Z][0-9A-Za-z.\-]*)\*{0,2}\s*\|([^|]*)\|", re.MULTILINE)

# 상태 셀 선두의 마커. 셀이 `**🔴 결정 대기**` 처럼 볼드일 수 있다(반례 (e) 위음성).
_BOLD = re.compile(r"^\**\s*")

# 🔴 이 원장에는 **섹션 소속으로만** 결정 대기인 행이 있다 — `## 🔴 사용자 결정 대기`
#    아래 표는 상태 셀에 🔴 이 없다(B6-b·B7 등). 상태 셀만 보면 그 전부가 위음성이다.
_SECTION = re.compile(r"^##\s+(.*)$", re.MULTILINE)

# 요약이 "현재 창" 과 "역사" 를 구분하므로 카운터도 구분한다 — 한 숫자로 뭉개면
# `test_backlog_shape.current_window()` 와 갈라진다(반례 (f)).
_HISTORY_MARK = "(역사)"

# 이 수를 넘게 손대지 않았으면 정체로 본다. owed 원장 축(_STALE_PR_THRESHOLD=10)과
# 같은 크기 — 두 원장의 정체 기준이 갈라지면 어느 쪽을 믿을지 알 수 없다.
_STALE_PR_THRESHOLD = 10


def _sections(text: str) -> list[tuple[int, str]]:
    """(오프셋, 헤딩) — 각 행이 어느 섹션에 속하는지 판정하는 데 쓴다."""
    return [(m.start(), m.group(1)) for m in _SECTION.finditer(text)]


def _section_of(pos: int, sections: list[tuple[int, str]]) -> str:
    head = ""
    for off, title in sections:
        if off > pos:
            break
        head = title
    return head


def open_decisions(text: str) -> list[tuple[str, str]]:
    """결정 대기 행 — `(ID, 구역)` 목록. 구역은 `현재` 또는 `역사`.

    ## 두 가지 형태를 **둘 다** 센다 (2026-08-14 Grok 반례 (e)(f))

    1. **상태 셀 선두가 🔴** — `| **R48** | 🔴 결정 대기 | …`
    2. **`## 🔴 …` 섹션 소속** — 그 표의 행은 상태 셀에 마커가 없다(`B6-b`·`B7`).
       초판은 1만 봐서 2를 통째로 놓쳤다.

    🔴 **상태 셀 선두로만** 판정하는 원칙은 유지한다 — 본문 산문에 🔴 이 흔한 리포라
    행 전체를 훑으면 거의 모든 행이 잡힌다(과교정 = 가드 자살). 볼드(`**🔴 …**`)는 벗긴다.

    Counts both status-cell rows and rows that are open purely by section membership;
    narrowing the ID pattern or ignoring sections produced silent false negatives.
    """
    sections = _sections(text)
    out: list[tuple[str, str]] = []
    for m in _ROW.finditer(text):
        rid, cell = m.group(1), m.group(2)
        head = _section_of(m.start(), sections)
        zone = "역사" if _HISTORY_MARK in head else "현재"
        by_cell = _BOLD.sub("", cell.strip()).startswith("🔴")
        by_section = head.strip().startswith("🔴")
        if by_cell or by_section:
            out.append((rid, zone))
    return out


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
        # 🔴 **파서 파손과 '진짜 0건' 을 문구로 구별한다** (2026-08-14 Grok 반례 (a)(b)).
        #    초판은 둘 다 «0건» 을 인쇄해 사람이 배너만 보고는 구별할 수 없었다 —
        #    계수 함수를 죽여도 건강한 상태와 같아 보였다(observer-lie).
        #    행은 찾았는데 대기가 0이면 그 사실을 **행 수와 함께** 말한다.
        print(f"✅ 결정 대기 **없음** — 원장 {len(rows)}행을 읽었고 그중 🔴 은 0건이다.")
        return 0

    now = [r for r, z in pending if z == "현재"]
    past = [r for r, z in pending if z == "역사"]
    print(f"🔴 **사용자 결정 대기 {len(pending)}건** — Claude 가 닫을 수 없는 클래스다.")
    if now:
        print(f"   현재 창 {len(now)}건: {' · '.join(now)}")
    # 역사 섹션은 원장 요약이 카운트에서 제외하는 구역이다. 그래도 **결정은 열려 있다** —
    # 한 숫자로 뭉개면 `test_backlog_shape.current_window()` 와 갈라지므로 나눠 인쇄한다.
    if past:
        print(f"   역사 구역 {len(past)}건(요약 카운트 제외분): {' · '.join(past)}")
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
