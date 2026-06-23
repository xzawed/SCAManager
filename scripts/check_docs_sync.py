#!/usr/bin/env python3
"""
docs 수치 정합 점검 — STATE.md 종합 수치 ↔ STATE 추적셀 시작 헤더 ↔ README/README.ko 배지.
docs count-sync checker — STATE.md totals ↔ STATE tracking-cell header ↔ README/README.ko badges.

STATE.md 갱신 시 다지점(헤더 종합 수치 + 추적셀 시작 헤더) 및 README.md/README.ko.md Tests 배지가
서로 어긋나는 drift(과거 #931/#933 Codex 적발)를 turn-0(pre-commit)에서 차단한다. repo 내부 파일만
읽어 CI-safe. 단위/전체 카운트가 4 지점에서 모두 일치하면 exit 0.

NOTE: 절대 카운트(pytest --collect-only)와의 대조는 비포함 — 본 체커는 '문서 간 일치'만 검증
(pre-commit 속도 보존). pytest 실측 카운트 갱신은 작업자 책임(STATE 추적셀 trail).
"""
import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# STATE 종합 수치: "전체 **5196** 수집 (단위 **5042** + 통합 154)"
_STATE_TOTAL = re.compile(r"전체 \*\*(\d+)\*\* 수집 \(단위 \*\*(\d+)\*\*")
# STATE 추적셀 시작 헤더: "**5196 수집** ... 단위 5042 + 통합 154 (현재)"
_STATE_CELL_TOTAL = re.compile(r"\*\*(\d+) 수집\*\*")
_STATE_CELL_UNIT = re.compile(r"단위 (\d+) \+ 통합 \d+ \(현재\)")
# README 배지: "Tests-5196%2B_total_(5042_unit_%2B_154_integration)"
_README_BADGE = re.compile(r"Tests-(\d+)%2B_total_\((\d+)_unit_%2B_\d+_integration\)")


def _first(pattern: re.Pattern, text: str, groups: int = 1):
    """첫 매치의 그룹(들) 반환, 없으면 None. / Return first match group(s) or None."""
    m = pattern.search(text)
    if not m:
        return None
    return m.group(1) if groups == 1 else tuple(m.group(i) for i in range(1, groups + 1))


def check_consistency(project_root: Path) -> tuple[bool, list[str]]:
    """STATE/README 수치 정합을 검사해 (ok, 메시지 목록) 반환."""
    msgs: list[str] = []
    state = (project_root / "docs" / "STATE.md").read_text(encoding="utf-8")
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    readme_ko = (project_root / "README.ko.md").read_text(encoding="utf-8")

    state_total = _first(_STATE_TOTAL, state, 2)         # (전체, 단위) — 종합 수치
    cell_total = _first(_STATE_CELL_TOTAL, state)         # 추적셀 시작 전체
    cell_unit = _first(_STATE_CELL_UNIT, state)           # 추적셀 시작 단위
    md_badge = _first(_README_BADGE, readme, 2)           # (전체, 단위)
    ko_badge = _first(_README_BADGE, readme_ko, 2)        # (전체, 단위)

    for label, val in [
        ("STATE 종합 수치", state_total), ("STATE 추적셀 전체", cell_total),
        ("STATE 추적셀 단위", cell_unit), ("README.md 배지", md_badge),
        ("README.ko.md 배지", ko_badge),
    ]:
        if val is None:
            msgs.append(f"❌ {label} 패턴 미발견 (형식 변경됐는지 확인)")
    if msgs:
        return False, msgs

    totals = {
        "STATE 종합(전체)": state_total[0], "STATE 추적셀(전체)": cell_total,
        "README.md(전체)": md_badge[0], "README.ko.md(전체)": ko_badge[0],
    }
    units = {
        "STATE 종합(단위)": state_total[1], "STATE 추적셀(단위)": cell_unit,
        "README.md(단위)": md_badge[1], "README.ko.md(단위)": ko_badge[1],
    }
    if len(set(totals.values())) > 1:
        msgs.append("❌ 전체 카운트 불일치: " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    if len(set(units.values())) > 1:
        msgs.append("❌ 단위 카운트 불일치: " + ", ".join(f"{k}={v}" for k, v in units.items()))
    return (not msgs), msgs


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    ok, msgs = check_consistency(project_root)
    print("=== docs 수치 정합 점검 / Docs Count-Sync Check ===\n")
    if ok:
        print("✅ STATE 종합·추적셀 ↔ README.md ↔ README.ko.md 전체/단위 카운트 일치")
        return 0
    for m in msgs:
        print(m)
    print("\n해결: STATE.md 종합 수치 + 추적셀 시작 헤더 + README.md/README.ko.md Tests 배지를 동일 값으로 동기화.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
