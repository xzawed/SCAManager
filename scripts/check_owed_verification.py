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
import sys
from pathlib import Path

_LEDGER = Path("docs/runbooks/owed-verification.md")

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


def main():
    _make_stdout_safe()
    if not _LEDGER.is_file():
        # 원장 부재 = 추적할 미결 없음(저장소 외부 실행 포함) — 무음 통과.
        # No ledger = nothing owed (incl. runs outside the repo) — pass silently.
        return 0
    rows = parse_rows(_LEDGER.read_text(encoding="utf-8", errors="replace"))
    breached, msg = evaluate(rows)
    print(msg)
    if breached:
        print(f"   원장 / ledger: {_LEDGER.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
