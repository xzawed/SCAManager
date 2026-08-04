#!/usr/bin/env python3
"""
docs 수치 정합 점검 — STATE.md 종합 수치 ↔ STATE 추적셀 시작 헤더 ↔ README/README.ko 배지.
docs count-sync checker — STATE.md totals ↔ STATE tracking-cell header ↔ README/README.ko badges.

STATE.md 갱신 시 다지점(헤더 종합 수치 + 추적셀 시작 헤더) 및 README.md/README.ko.md Tests 배지가
서로 어긋나는 drift(과거 #931/#933 Codex 적발)를 turn-0(pre-commit)에서 차단한다. repo 내부 파일만
읽어 CI-safe. 단위/전체 카운트가 4 지점에서 모두 일치하면 exit 0.

NOTE: 절대 카운트(pytest --collect-only)와의 대조는 비포함 — 본 체커는 '문서 간 일치'만 검증
(pre-commit 속도 보존). pytest 실측 카운트 갱신은 작업자 책임(STATE 추적셀 trail).

🔴 두 번째 축 = 의존성 핀 정합(check_dependency_pins) — 이쪽은 **ground truth 대조**다.
문서끼리가 아니라 `requirements.txt` 실핀과 대조하므로, 문서 사본이 함께 틀려도 적발된다
(backlog R25 가 지적한 '사본끼리 대조' 한계의 보완축 / backlog R15 재발 차단).
Second axis = dependency-pin sync, compared against requirements.txt (ground truth) rather
than doc-to-doc, so it still fails when every doc copy drifts together.
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
# README FastAPI 배지: "FastAPI-0.141-009688" — 관례상 핀의 major.minor 만 표기
# README FastAPI badge — by convention it carries only the pin's major.minor
_FASTAPI_BADGE = re.compile(r"FastAPI-(\d+\.\d+)-")
# 산문이 인용하는 핀 이름 — `.claude/rules/deploy.md` 가 `name==X` 형태로 적는 것들
# Dependency names quoted as `name==X` in .claude/rules/deploy.md
_DOC_PIN_NAMES = ("fastapi", "starlette")
# 버전 문자열 (PEP 440 흔한 형태 — 숫자로 시작, 이후 숫자/문자/점/하이픈)
_VERSION = r"[0-9][0-9A-Za-z.\-]*"


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


def check_dependency_pins(project_root: Path) -> tuple[bool, list[str]]:
    """requirements.txt 실핀 ↔ 문서 인용·배지 정합을 검사해 (ok, 메시지 목록) 반환.

    기대값을 `requirements.txt`(ground truth)에서 유도하므로 문서 사본이 함께 틀려도 red 다.
    인용이 0건이면 '검사 범위 붕괴' 로 실패시킨다 — 빈 범위 위의 ✅ 가 fail-open 이기 때문.
    Expectations come from requirements.txt; an empty citation scope fails rather than passes.
    """
    msgs: list[str] = []
    reqs = (project_root / "requirements.txt").read_text(encoding="utf-8")
    deploy = (project_root / ".claude" / "rules" / "deploy.md").read_text(encoding="utf-8")

    pins: dict[str, str | None] = {
        name: _first(re.compile(rf"^{name}==({_VERSION})$", re.MULTILINE), reqs)
        for name in _DOC_PIN_NAMES
    }
    for name, pin in pins.items():
        if pin is None:
            msgs.append(f"❌ requirements.txt 에 `{name}==` 핀 미발견 (핀 형식 변경됐는지 확인)")
            continue
        quoted = re.findall(rf"\b{name}==({_VERSION})", deploy)
        if not quoted:
            msgs.append(f"❌ .claude/rules/deploy.md 의 `{name}==` 인용 0건 — 검사 범위 붕괴")
        msgs += [
            f"❌ deploy.md `{name}=={got}` ↔ requirements.txt `{name}=={pin}` 불일치"
            for got in dict.fromkeys(v for v in quoted if v != pin)
        ]

    fastapi_pin = pins["fastapi"]
    if fastapi_pin is not None:
        want = ".".join(fastapi_pin.split(".")[:2])   # 배지는 major.minor 만 표기
        for fname in ("README.md", "README.ko.md"):
            badge = _first(_FASTAPI_BADGE, (project_root / fname).read_text(encoding="utf-8"))
            if badge is None:
                msgs.append(f"❌ {fname} FastAPI 배지 패턴 미발견 (형식 변경됐는지 확인)")
            elif badge != want:
                msgs.append(
                    f"❌ {fname} FastAPI 배지 {badge} ↔ 핀 {fastapi_pin} (기대 {want}) 불일치"
                )
    return (not msgs), msgs


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    ok, msgs = check_consistency(project_root)
    pin_ok, pin_msgs = check_dependency_pins(project_root)
    print("=== docs 수치 정합 점검 / Docs Count-Sync Check ===\n")
    if ok:
        print("✅ STATE 종합·추적셀 ↔ README.md ↔ README.ko.md 전체/단위 카운트 일치")
    if pin_ok:
        print("✅ requirements.txt 핀 ↔ deploy.md 인용 ↔ README FastAPI 배지 일치")
    if ok and pin_ok:
        return 0
    for m in msgs + pin_msgs:
        print(m)
    print(
        "\n해결: (수치) STATE.md 종합 수치 + 추적셀 시작 헤더 + README.md/README.ko.md Tests 배지를"
        " 동일 값으로 동기화. (핀) requirements.txt 실핀에 맞춰 .claude/rules/deploy.md 인용과"
        " README/README.ko FastAPI 배지를 갱신."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
