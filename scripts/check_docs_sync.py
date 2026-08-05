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
# 🔴 §테스트 수 추적 이력의 **마지막 항목** (2026-08-05 신설)
# 절 제목 → 그 절의 마지막 `- ` 불릿 → 그 불릿 안의 누계/단위. 순서가 중요하다:
# 파일 전체에서 "마지막 매치" 를 찾으면 절이 통째로 사라져도 다른 곳이 매치돼 초록이 된다.
# Anchor on the section, then its last bullet — searching the whole file would stay green
# even if the section were deleted.
_STATE_HIST_HEADING = "## 테스트 수 추적 이력"
_STATE_HIST_TOTAL = re.compile(r"=\s*\*\*(\d+)\*\* 수집")
_STATE_HIST_UNIT = re.compile(r"→\s*\*\*(\d+)\*\* 단위")
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


def _history_tail(state: str) -> tuple[str | None, str | None, list[str]]:
    """§테스트 수 추적 이력의 **마지막 항목**에서 (누계, 단위) 를 뽑는다.

    🔴 `_first` 와 짝을 이룬다. 이력은 append-only 라 최신값이 **꼬리**에 있는데,
    가드가 `_first` 만 쓰면 머리(누계)만 검사하고 꼬리는 **검사 대상이 아니게** 된다 —
    실제로 꼬리만 갱신하고 머리를 빠뜨린 사고가 났다.

    🔴 **fail-closed 3층** (Grok claim-review 019fcf 적발 — 초판은 전부 fail-open 이었다):
      1. 절 자체가 없으면 red. 초판은 `None → 대조 제외` 라 **절을 통째로 지우면 초록**이었다
         ("과거 리비전 호환" 을 이유로 적었으나, 그 호환과 '운영 본문에서 절 소실 탐지' 는
         다른 요구다 — 보호 장치를 지워도 참으로 보이는 전형).
      2. 마지막 **불릿**을 앵커로 쓴다. 파일 전체에서 마지막 매치를 찾으면 절이 사라져도
         엉뚱한 곳이 매치돼 초록이 된다.
      3. 그 불릿이 형식(`= **N** 수집` · `→ **N** 단위`)을 갖추지 않으면 red. 초판은
         **패턴 없는 줄을 덧붙이면** 이전 값이 계속 last 로 잡혀 초록이었다.

    Returns (total, unit, errors). 형식 계약이 곧 append 계약이다.
    """
    errs: list[str] = []
    occurrences = state.count(_STATE_HIST_HEADING)
    if occurrences == 0:
        return None, None, [f"❌ STATE.md 에 `{_STATE_HIST_HEADING}` 절이 없다 — 이력 꼬리 검사 불가"]
    if occurrences > 1:
        # 🔴 절이 둘이면 `split(...)[1]` 이 **첫 절**만 SSOT 로 삼는다 — 두 번째 절에 무엇을
        # 적어도 무시되고, 반대로 가짜 첫 절을 끼워 넣으면 진짜 이력을 우회할 수 있다.
        # (Grok claim-review df5ed11d 적발 — 초판은 이 경로가 조용히 통과했다.)
        # Two sections would silently make the first one the SSOT and shadow the real history.
        return None, None, [
            f"❌ `{_STATE_HIST_HEADING}` 절이 {occurrences}개다 — 이력 SSOT 는 **하나**여야 한다"
        ]
    section = state.split(_STATE_HIST_HEADING, 1)[1].split("\n## ", 1)[0]
    bullets = [ln for ln in section.splitlines() if ln.startswith("- ")]
    if not bullets:
        return None, None, ["❌ 이력 절에 항목(`- `)이 하나도 없다 — 검사 범위 붕괴"]
    tail = bullets[-1]
    total = _first(_STATE_HIST_TOTAL, tail)
    unit = _first(_STATE_HIST_UNIT, tail)
    if total is None or unit is None:
        errs.append(
            "❌ 이력 마지막 항목이 형식을 갖추지 않았다 — `= **N** 수집` 과 `→ **N** 단위` 를 "
            f"모두 포함해야 한다. 실제: {tail[:90]!r}"
        )
    return total, unit, errs


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

    # 🔴 이력 **꼬리** 도 대조 대상에 넣는다 — 머리만 보면 최신 항목이 어긋나도 초록이다.
    # 절 부재·형식 붕괴는 그 자체로 red (fail-closed — `_history_tail` docstring 참조).
    hist_total, hist_unit, hist_errs = _history_tail(state)
    msgs.extend(hist_errs)
    if hist_errs:
        return False, msgs

    totals = {
        "STATE 종합(전체)": state_total[0], "STATE 추적셀(전체)": cell_total,
        "README.md(전체)": md_badge[0], "README.ko.md(전체)": ko_badge[0],
    }
    units = {
        "STATE 종합(단위)": state_total[1], "STATE 추적셀(단위)": cell_unit,
        "README.md(단위)": md_badge[1], "README.ko.md(단위)": ko_badge[1],
    }
    totals["STATE 이력 마지막(전체)"] = hist_total
    units["STATE 이력 마지막(단위)"] = hist_unit
    if len(set(totals.values())) > 1:
        msgs.append("❌ 전체 카운트 불일치: " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    if len(set(units.values())) > 1:
        msgs.append("❌ 단위 카운트 불일치: " + ", ".join(f"{k}={v}" for k, v in units.items()))

    # 🔴 **일치 ≠ 정합** — 5지점이 같은 값으로 **함께 틀릴** 수 있다(이 파일 docstring 이
    # 스스로 인정한 '사본끼리 대조' 의 한계). 전체 = 단위 + 통합 은 사본과 무관한 축이라
    # 그 합의된 오류를 잡는다.
    # Agreement is not consistency: all five copies can be wrong together. This axis is
    # independent of the copies.
    integ = _first(re.compile(r"통합 (\d+) \(현재\)"), state)
    if integ is not None and not msgs:
        if int(cell_total) != int(cell_unit) + int(integ):
            msgs.append(
                f"❌ 산술 불일치: 전체 {cell_total} ≠ 단위 {cell_unit} + 통합 {integ}"
                f" (차 {int(cell_total) - int(cell_unit) - int(integ):+})"
            )
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


def apply_fix(project_root: Path) -> tuple[bool, list[str]]:
    """이력 **마지막 항목**을 SSOT 로 삼아 파생 3지점을 다시 쓴다.

    🔴 왜 이 방향인가 (2026-08-05 문서 감사 P0-3): 같은 정수가 **5지점**에 손으로 복제돼
    있었다 — STATE 종합 · STATE 추적셀 머리 · 이력 꼬리 · README 배지 · README.ko 배지.
    **N지점 동기화 의무는 N-1 번의 실패 기회**이고, 실제로 그중 하나를 빠뜨려 가드가 red 를
    냈다. 이 함수는 그 5를 **1**로 줄인다: 작성자는 이력에 항목 한 줄만 적고 이걸 돌린다.

    파생 방향이 '이력 꼬리 → 나머지' 인 이유: 새 수치가 자연스럽게 **처음 쓰이는 곳**이
    거기다. 종합 수치를 SSOT 로 잡으면 작성자가 두 곳(종합 + 이력)을 여전히 손으로 맞춰야 한다.

    Rewrites the three derived sinks from the history tail (the single authored source),
    cutting hand-maintained copies from 5 to 1.
    """
    state_path = project_root / "docs" / "STATE.md"
    state = state_path.read_text(encoding="utf-8")
    total, unit, errs = _history_tail(state)
    if errs:
        return False, errs + ["→ 이력 마지막 항목을 먼저 올바른 형식으로 적을 것 (그것이 SSOT 다)"]

    integ = _first(re.compile(r"통합 (\d+) \(현재\)"), state)
    if integ is None:
        return False, ["❌ 추적셀에서 통합 수를 못 읽었다 — `단위 N + 통합 M (현재)` 형식 확인"]

    # 🔴 **산술 타당성** — 형식만 보고 쓰면 "형식은 맞는데 틀린 값" 을 5곳에 자동 전파한다.
    # 이 함수는 파일을 **쓰는** 코드라 그 오염이 되돌리기 어렵다. 전체 = 단위 + 통합 이
    # 성립하지 않으면 **아무것도 쓰지 않는다**. (Grok claim-review df5ed11d 적발 —
    # 초판은 이 검사가 없어 의미상 불가능한 SSOT 도 그대로 퍼뜨렸다.)
    # Arithmetic sanity: this function WRITES files, so a format-valid but wrong SSOT would be
    # propagated to five sinks. Refuse unless total == unit + integration.
    if int(total) != int(unit) + int(integ):
        return False, [
            f"❌ 이력 SSOT 가 산술적으로 불가능하다 — 전체 {total} ≠ 단위 {unit} + 통합 {integ}"
            f" (차 {int(total) - int(unit) - int(integ):+}). 아무것도 쓰지 않았다.",
            "→ 이력 마지막 항목의 수치를 먼저 실측값으로 고칠 것 (`--collect-only`).",
        ]

    changed: list[str] = []
    new_state = _STATE_TOTAL.sub(f"전체 **{total}** 수집 (단위 **{unit}**", state, count=1)
    new_state = _STATE_CELL_TOTAL.sub(f"**{total} 수집**", new_state, count=1)
    new_state = _STATE_CELL_UNIT.sub(f"단위 {unit} + 통합 {integ} (현재)", new_state, count=1)
    if new_state != state:
        state_path.write_text(new_state, encoding="utf-8", newline="\n")
        changed.append(f"✏️ docs/STATE.md — 종합 수치·추적셀 머리 → 전체 {total} / 단위 {unit}")

    badge = f"Tests-{total}%2B_total_({unit}_unit_%2B_{integ}_integration)"
    for name in ("README.md", "README.ko.md"):
        path = project_root / name
        text = path.read_text(encoding="utf-8")
        fixed = _README_BADGE.sub(badge, text, count=1)
        if fixed != text:
            path.write_text(fixed, encoding="utf-8", newline="\n")
            changed.append(f"✏️ {name} — Tests 배지 → {total} ({unit} unit)")

    return True, changed or ["(이미 일치 — 변경 없음)"]


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    if "--fix" in sys.argv:
        print("=== docs 수치 동기화 (--fix) — SSOT = §테스트 수 추적 이력 마지막 항목 ===\n")
        ok, msgs = apply_fix(project_root)
        for m in msgs:
            print(m)
        if not ok:
            return 1
        print("\n→ 재검증:")
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
        "\n해결: (수치) 손으로 고칠 곳은 STATE.md §테스트 수 추적 이력 **마지막 한 줄**뿐이다 —"
        " 그 줄을 실측값(`--collect-only`)으로 고친 뒤 `py -3 scripts/check_docs_sync.py --fix`"
        " 를 돌리면 나머지 4지점(종합 수치·추적셀 머리·README 2배지)이 파생된다."
        " (핀) requirements.txt 실핀에 맞춰 .claude/rules/deploy.md 인용과 README/README.ko"
        " FastAPI 배지를 갱신."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
