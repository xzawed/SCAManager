#!/usr/bin/env python3
"""owed 원장 미결 카운터 — 안전등급 미회신 건이 있으면 세션 시작 시 loud 경고.
Owed-ledger counter — warns loudly at session start when safety-tier rows await user reply.

회고 2026-07-19 P0: #1084 가 원장 파일만 만들고 **어떤 집행면에도 배선하지 않아** 기록 전용
장치가 됐다. 같은 회고가 P0 로 규정한 '문서-only 시정' 안티패턴을 같은 세션에 재생산한 것
(3회차). 안전등급 2건(#1058 SMTP·#1062 IDOR)이 4세션째 ⏳ 로 누적됐다.
Retro 2026-07-19 P0: #1084 created the ledger but wired it to no enforcement surface, making it a
record-only device — the third repetition of the doc-only remedy the same retro had just condemned.

이 카운터는 원장을 **측정 신호**로 전환한다 — SessionStart 훅에서 자동 실행(.claude/settings.json).
정책 5 NEW-P0-N: 안전등급은 매 사이클 명시 회신 의무 영역이라 미결 시 진입 전 경고한다.
This converts the ledger from cognition-dependent to measured — auto-run by the SessionStart hook.

🔴 비차단(advisory) — 항상 exit 0. 경고 배너만 출력(정책 17 안정성: 커밋/PR/세션 미간섭).
Non-blocking (advisory) — always exit 0; prints a banner only (policy 17: never blocks a session).

사용법 / Usage: python scripts/check_owed_verification.py
"""
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

_LEDGER = Path("docs/runbooks/owed-verification.md")

# ── 완전성 축 (backlog R0-2) ─────────────────────────────────────────────
#
# 🔴 이 스크립트는 **원장에 적힌 것만** 셌다. 그래서 부채를 등재하지 않는 것이 가장 싼
# 통과 경로였다 — 빈 원장이 green 이고, 파일이 없으면 아예 무음이었다. 실측된 기전:
# 창 42 PR 중 22건이 미체크 항목을 단 채 머지됐는데 세는 관측자가 0이었다.
# "옳은 일을 하면 red" 의 쌍대 — *아무것도 안 하면 초록*이다.
#
# 두 축을 추가한다. 둘 다 advisory(exit 0)이고, 둘 다 **판정 불가를 초록으로 흘리지 않는다**.
#   A. 원장 부재·읽기 실패·데이터 0행 → loud (이전엔 무음 또는 "미결 0건")
#   B. 원장이 마지막으로 갱신된 뒤 머지된 PR 수 → 임계 초과면 loud
#
# B 는 `git` 만 쓴다(`gh`·네트워크 불요) — PR 본문을 읽어 '등재 대상인가' 를 판정하는 방식은
# 산문 판정이라 오탐이 크고, 이 리포는 그 형태(`산문 가드는 양방향으로 틀린다`)를 이미
# 학습했다. 그래서 B 는 **판정이 아니라 촉구**다: "그 사이 정말 부채가 하나도 없었는가?"
#
# The old check counted only what the ledger already listed, so *not registering* debt was the
# cheapest way to pass. Axis A makes an absent/empty ledger loud; axis B (git-only) prompts when
# many PRs merged without the ledger being touched. Neither claims to know what *should* be there.
_STALE_PR_THRESHOLD = 10
_SQUASH_PR = re.compile(r"\(#\d+\)$")

# 안전/데이터 등급 섹션 마커 — 이 헤딩 이후 ~ 다음 `## ` 헤딩 전까지가 안전등급 표.
# Safety-tier section marker; rows between this heading and the next `## ` belong to it.
SAFETY_TIER_MARKER = "🔴 안전/데이터 등급"

# 표 데이터 행 — 첫 셀이 `**#NNNN**` 형태(헤더 `| PR |`·구분선 `|----|` 자동 배제).
# Table data row — first cell is `**#NNNN**` (excludes header and separator rows).
_ROW = re.compile(r"^\|\s*\*{0,2}(#\d+)\*{0,2}\s*\|")
_PENDING = "⏳"


def parse_rows(text):
    """원장 본문에서 데이터 행 목록 추출 — {pr, status, safety}.
    Extract ledger data rows as {pr, status, safety}."""
    rows = []
    in_safety = False
    for line in text.splitlines():
        if line.startswith("## "):
            # 섹션 전환 — 안전등급 헤딩이면 이후 행을 안전등급으로 분류.
            # Section switch — rows after the safety heading are safety-tier.
            in_safety = SAFETY_TIER_MARKER in line
            continue
        m = _ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append({"pr": m.group(1), "status": cells[-1] if cells else "", "safety": in_safety})
    return rows


def pending_rows(rows):
    """미결(⏳) 행만 — ✅/❌/⏭️ 는 종결(회신 완료 또는 명시 보류).
    Pending rows only; ✅/❌/⏭️ count as resolved (answered or explicitly deferred)."""
    return [r for r in rows if _PENDING in r["status"]]


def evaluate(rows):
    """(breached, message) — 안전등급 미결이 1건이라도 있으면 breached.
    Returns (breached, message); breached when any safety-tier row is still pending."""
    pending = pending_rows(rows)
    safety = [r["pr"] for r in pending if r["safety"]]
    ops = [r["pr"] for r in pending if not r["safety"]]
    if safety:
        msg = (
            f"🔴 owed 원장 안전등급 미회신 {len(safety)}건: {', '.join(safety)}"
            + (f" / 운영등급 {len(ops)}건: {', '.join(ops)}" if ops else "")
            + " — 정책 5 NEW-P0-N: 매 사이클 명시 회신 의무 (다음 사이클 진입 전 회신 요청)."
            " / Safety-tier owed verifications await user reply; request them before the next cycle."
        )
        return True, msg
    msg = (
        f"owed 원장 — 안전등급 미결 0건 / 운영등급 미결 {len(ops)}건"
        + (f": {', '.join(ops)}" if ops else "")
        + " (Phase 종료 일괄 회신 대상 — 정책 2 진화)."
    )
    return False, msg


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지(🔴) 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji-print crash on Windows local runs (UTF-8, replace on miss)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def _git(*args: str) -> str | None:
    """git 출력 또는 None(판정 불가). 네트워크·`gh` 를 쓰지 않는다."""
    try:
        proc = subprocess.run(  # nosec B603 B607
            ["git", *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def merged_prs_since_ledger() -> int | None:
    """원장이 마지막으로 갱신된 뒤 머지된 PR 수. 판정 불가면 None.

    squash 머지 제목 말미의 `(#NNNN)` 을 센다 — 이 저장소의 유일한 머지 형태다.
    🔴 **PR 본문을 읽지 않는다**: '이 PR 이 등재 대상인가' 는 산문 판정이라 오탐이 크고,
    오탐이 진탐을 넘으면 가드 자살이다(정책 17). 이 축은 판정이 아니라 **촉구**다.
    """
    sha = _git("log", "-1", "--format=%H", "--", _LEDGER.as_posix())
    if sha is None or not sha.strip():
        return None
    log = _git("log", "--format=%s", f"{sha.strip()}..HEAD")
    if log is None:
        return None
    return sum(1 for line in log.splitlines() if _SQUASH_PR.search(line.strip()))


def main():
    _make_stdout_safe()

    # ── 축 A: 원장 자체의 완전성 (R0-2) ────────────────────────────────
    # 🔴 early return **위**에 둔다. 이전에는 파일이 없으면 무음 통과였다 —
    #    "부채가 없다" 와 "원장이 없다" 가 구별되지 않았고, 후자가 더 나쁜 상태다.
    if not _LEDGER.is_file():
        print(
            f"🔴 owed 원장 파일이 없다 ({_LEDGER.as_posix()}) — **판정 불가**.\n"
            "   미결이 0건이라는 뜻이 아니다. 원장이 사라지면 부채는 추적면 밖으로 나간다.\n"
            "   Ledger missing: this is 'cannot judge', not 'nothing owed'."
        )
        return 0
    try:
        text = _LEDGER.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"🔴 owed 원장을 읽을 수 없다 — **판정 불가** ({type(exc).__name__}).")
        return 0

    rows = parse_rows(text)
    if not rows:
        print(
            "🔴 owed 원장에 항목이 **0건**이다 — '부채 없음' 과 '등재하지 않음' 이 구별되지 않는다.\n"
            "   등재하지 않는 것이 가장 싼 통과 경로가 되는 상태다(backlog R0-2).\n"
            "   An empty ledger is indistinguishable from 'nobody registered anything'."
        )
        return 0

    breached, msg = evaluate(rows)
    print(msg)
    if breached:
        print(f"   원장 / ledger: {_LEDGER.as_posix()}")

    # ── 축 B: intake 정체 (R0-2 — 실측 기전: 172 PR 동안 intake 0건) ────
    since = merged_prs_since_ledger()
    if since is None:
        print("   ⚠️ 원장 갱신 이후 머지 PR 수를 산출하지 못했다 — intake 축 **판정 불가**.")
    elif since >= _STALE_PR_THRESHOLD:
        print(
            f"🔴 원장이 마지막 갱신 이후 **{since} PR** 동안 손대지지 않았다.\n"
            "   그 사이 운영 검증이 필요한 변경이 정말 하나도 없었는지 확인할 것 —\n"
            "   이 검사는 '무엇이 빠졌는지' 는 모른다. 등재 정체만 관측한다.\n"
            f"   The ledger is untouched across {since} merged PRs; verify that is intentional."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
