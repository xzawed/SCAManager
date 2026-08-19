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

# 형식 쌍 문법 — `_first(TOTAL)`/`_first(UNIT)` 를 따로 쓰면 불릿 안 decoy 가
# SSOT 를 조립한다 (claim-review 01a00434). 이 파일의 `_history_tail` 이 유일한 소비자.
# Single pair grammar. Independent first-matches assembled a forged SSOT.
_UNIT_OPEN = re.compile(r"\((\d+)\s*→\s*\*\*(\d+)\*\*\s*단위")
_FULL_TOTAL = re.compile(r"=\s*\*\*(\d+)\*\*\s*수집")

# STATE 종합 수치: "전체 **5196** 수집 (단위 **5042** + 통합 154)"
# 🔴 **통합 수까지 캡처한다** (2026-08-19 실측). 초판은 `단위 \*\*(\d+)\*\*` 에서 끊겼고
#    아래 치환 문자열도 거기서 끝났다 — 그래서 `+ 통합 N)` 은 도입 이래 **한 번도 갱신된
#    적이 없다**. 같은 줄의 전체·단위가 12커밋 이상 갱신되는 동안 통합만 `171` 로 얼어
#    있었고(참값 174), 그동안 이 스크립트는 「✅ 테스트 수치 일치」를 냈다.
#    다시 쓰는 줄의 숫자를 **전부** 소유하지 않으면, 안 만지는 숫자가 조용히 언다.
# Capture the integration count too: the replacement string must own every number on the
# line it rewrites, or the untouched one freezes while the guard reports agreement.
_STATE_TOTAL = re.compile(r"전체 \*\*(\d+)\*\* 수집 \(단위 \*\*(\d+)\*\* \+ 통합 (\d+)\)")
# STATE 추적셀 시작 헤더: "**5196 수집** ... 단위 5042 + 통합 154 (현재)"
_STATE_CELL_TOTAL = re.compile(r"\*\*(\d+) 수집\*\*")
_STATE_CELL_UNIT = re.compile(r"단위 (\d+) \+ 통합 \d+ \(현재\)")
# 🔴 §테스트 수 추적 이력의 **마지막 항목** (2026-08-05 신설)
# 절 제목 → 그 절의 마지막 `- ` 불릿 → 그 불릿 안의 누계/단위. 순서가 중요하다:
# 파일 전체에서 "마지막 매치" 를 찾으면 절이 통째로 사라져도 다른 곳이 매치돼 초록이 된다.
# Anchor on the section, then its last bullet — searching the whole file would stay green
# even if the section were deleted.
_STATE_HIST_HEADING = "## 테스트 수 추적 이력"
# 🔴 `_STATE_HIST_TOTAL` / `_STATE_HIST_UNIT` 은 **의도적으로 없다** (2026-08-17 삭제).
#    누계·단위를 **따로** 첫-매치하면 한 불릿 안의 decoy 쌍이 틀린 (C, B) 를 조립한다 —
#    실제로 1171 이 파생 3지점에 퍼진 사고가 났다. 그래서 읽기는 `full_pairs()` 하나로
#    통일했고, 두 정규식은 아무도 쓰지 않는 채 남아 CodeQL `py/unused-global-variable`
#    (alert 581·582) 로 잡혔다.
#    **다시 추가하지 말 것** — 되살리면 그 사고의 도구가 돌아온다. 회귀 가드가
#    `_history_tail` 이 `full_pairs` 를 쓰는지와 이 이름들의 부재를 함께 잰다:
#    `tests/unit/scripts/test_repo_integrity_checks.py::test_history_tail_uses_full_pairs_not_independent_first`
# Deliberately absent: reading total/unit independently lets a decoy pair inside one bullet
# assemble a wrong (C, B). Reading is unified on full_pairs(); do not resurrect these.
# README 배지: "Tests-5196%2B_total_(5042_unit_%2B_154_integration)"
_README_BADGE = re.compile(r"Tests-(\d+)%2B_total_\((\d+)_unit_%2B_\d+_integration\)")
# README FastAPI 배지: "FastAPI-0.141-009688" — 관례상 핀의 major.minor 만 표기
# README FastAPI badge — by convention it carries only the pin's major.minor
_FASTAPI_BADGE = re.compile(r"FastAPI-(\d+\.\d+)-")
# README FastAPI 배지가 파생되는 핀 이름
# Pin names the README FastAPI badge derives from
_DOC_PIN_NAMES = ("fastapi", "starlette")
# 버전 문자열 (PEP 440 흔한 형태 — 숫자로 시작, 이후 숫자/문자/점/하이픈)
_VERSION = r"[0-9][0-9A-Za-z.\-]*"


def _first(pattern: re.Pattern, text: str, groups: int = 1):
    """첫 매치의 그룹(들) 반환, 없으면 None. / Return first match group(s) or None."""
    m = pattern.search(text)
    if not m:
        return None
    return m.group(1) if groups == 1 else tuple(m.group(i) for i in range(1, groups + 1))


def formal_pairs(line: str) -> list[tuple[int, int, int | None]]:
    """한 줄의 형식 쌍. `_history_tail` 의 단일 읽기 규약.

    각 쌍은 `(A→**B** 단위` 로 시작한다. `= **C** 수집` 은 그 시작부터
    **다음** `(A→**B** 단위` 앞까지만 본다. 한 불릿에 decoy 쌍을 앞에
    붙여도 첫 C 와 첫 B 가 다른 쌍에서 조립되지 않는다.
    One grammar. C is scoped to the span before the next opener.
    """
    opens = list(_UNIT_OPEN.finditer(line))
    out: list[tuple[int, int, int | None]] = []
    for i, match in enumerate(opens):
        end = opens[i + 1].start() if i + 1 < len(opens) else len(line)
        segment = line[match.end() : end]
        total = _FULL_TOTAL.search(segment)
        out.append((
            int(match.group(1)),
            int(match.group(2)),
            int(total.group(1)) if total else None,
        ))
    return out


def full_pairs(line: str) -> list[tuple[int, int, int]]:
    """C 가 있는 형식 쌍만. SSOT 는 이 목록이 마지막 불릿에서 길이 1 이어야 한다.

    Full pairs only (C present). The last bullet must have exactly one.
    """
    return [(a, b, c) for a, b, c in formal_pairs(line) if c is not None]


def _exactly_one(pattern: re.Pattern, text: str, groups: int = 1):
    """매치가 정확히 1개일 때만 그룹을 돌려준다. 0 또는 2+ 는 (None, 개수).

    `_README_BADGE` 전역 첫-매치는 README 선두 decoy 에 쓴다 (claim-review 01a00434).
    개수가 1이 아니면 어느 것이 배지인지 모호하다 — 추측해서 쓰지 않는다.
    Exactly one match. 0 or 2+ is ambiguous; callers must refuse to write.
    """
    found = list(pattern.finditer(text))
    if len(found) != 1:
        return None, len(found)
    match = found[0]
    value = (
        match.group(1) if groups == 1
        else tuple(match.group(i) for i in range(1, groups + 1))
    )
    return value, 1


def _region_before_history(state: str) -> tuple[str | None, list[str]]:
    """원장 절 **밖** — `_STATE_HIST_HEADING` 앞만 돌려준다.

    🔴 `_STATE_CELL_TOTAL` 을 파일 전역에서 `_first` 하면 원장 항목
    (`**5365 수집**`)이 추적셀 머리로 잡힌다. `apply_fix` 가 그 자리에 최신
    누계를 덮어쓰고 ok=True. 영역을 못 찾으면 None — 전역 매치로 되돌아가지 않는다.
    Only the text before the append-only ledger. A global first-match rewrites a
    history item; missing the heading is fail-closed, not a fallback to the whole file.
    """
    occurrences = state.count(_STATE_HIST_HEADING)
    if occurrences == 0:
        return None, [
            f"❌ STATE.md 에 `{_STATE_HIST_HEADING}` 절이 없다 — 추적셀 영역 한정 불가"
        ]
    if occurrences > 1:
        return None, [
            f"❌ `{_STATE_HIST_HEADING}` 절이 {occurrences}개다 — 영역 한정 불가"
        ]
    return state.split(_STATE_HIST_HEADING, 1)[0], []


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
      3. 그 불릿의 **full pair** 가 정확히 1개여야 한다. `_first(TOTAL)` 과
         `_first(UNIT)` 를 따로 쓰면 불릿 안 decoy 가 틀린 C/B 를 조립한다.
         0개 = 형식 붕괴, 2+ = SSOT 모호 → 둘 다 red. 초판은 패턴 없는 줄을
         덧붙이면 이전 값이 계속 last 라 초록이었고, decoy 쌍을 앞에 붙이면
         1171 이 파생 3지점에 퍼졌다.

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
    # 🔴 불릿 *안* 첫 매치가 아니다. full pair `(A→**B** 단위 … = **C** 수집)` 가
    #    이 불릿에 정확히 1개여야 SSOT 다. 0 이면 형식 붕괴, 2+ 이면 어느 C 를
    #    쓸지 모호하므로 쓰지 않는다 (decoy 를 앞에 붙이면 1171 이 4지점에 퍼졌다).
    # Not first-match inside the bullet. Exactly one full pair, else refuse.
    found = full_pairs(tail)
    if len(found) == 0:
        errs.append(
            "❌ 이력 마지막 항목이 형식을 갖추지 않았다 — "
            "`(A→**B** 단위` 와 `= **C** 수집` 을 한 쌍으로 포함해야 한다. "
            f"실제: {tail[:90]!r}"
        )
        return None, None, errs
    if len(found) > 1:
        errs.append(
            f"❌ 이력 마지막 항목에 형식 쌍이 {len(found)}개다 — SSOT 모호, 쓰지 않는다. "
            "불릿을 나누거나 한 쌍만 남겨야 한다."
        )
        return None, None, errs
    _start, unit_n, total_n = found[0]
    return str(total_n), str(unit_n), errs


def check_consistency(project_root: Path) -> tuple[bool, list[str]]:
    """STATE/README 수치 정합을 검사해 (ok, 메시지 목록) 반환."""
    msgs: list[str] = []
    state = (project_root / "docs" / "STATE.md").read_text(encoding="utf-8")
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    readme_ko = (project_root / "README.ko.md").read_text(encoding="utf-8")

    # 🔴 추적셀 패턴은 원장 절 **밖**에서만 읽는다. 전역 첫-매치는 이력 항목을
    #    현재 값으로 오인한다 (단위 2 재현: line 253 `**5365 수집**`).
    # Tracking-cell patterns are scoped outside the ledger. A global first-match
    # treats a history item as the live cell.
    current, region_errs = _region_before_history(state)
    if region_errs:
        return False, region_errs

    state_total = _first(_STATE_TOTAL, current, 2)         # (전체, 단위) — 종합 수치
    # 🔴 종합 수치 줄의 **통합 수**도 본다 (Grok claim-review `01a019f1` G4 = BROKEN).
    #    정규식과 치환만 넓히면 `--fix` 는 그 값을 소유하지만 **검사 모드는 여전히 안 본다** —
    #    손으로 틀린 값을 넣고 `--fix` 를 안 돌리면 그대로 「✅ 수치 일치」가 나간다.
    #    실측: 이 블록을 빼고 `통합 999` 를 심으면 EXIT=0 에 초록 3줄이 나온다.
    #    그 절반짜리 상태가 정확히 이 사고의 원형이다 — 통합이 12커밋 이상 얼어 있는 동안
    #    이 스크립트는 내내 초록을 냈다. 쓰는 쪽과 **읽는 쪽을 같이** 넓혀야 닫힌다.
    # Widening the writer alone leaves the reader blind: a hand-edited wrong value still
    # prints agreement (measured: EXIT=0 with a deliberately wrong count).
    _HEAD_INTEG = re.compile(r"전체 \*\*\d+\*\* 수집 \(단위 \*\*\d+\*\* \+ 통합 (\d+)\)")
    _CELL_INTEG = re.compile(r"단위 \d+ \+ 통합 (\d+) \(현재\)")
    head_integ = _first(_HEAD_INTEG, current)
    cell_integ = _first(_CELL_INTEG, current)
    if head_integ is None:
        msgs.append("❌ STATE 종합 수치 줄에서 통합 수를 못 읽었다 — `+ 통합 N)` 형식 확인")
    elif cell_integ is not None and head_integ != cell_integ:
        msgs.append(
            f"❌ 통합 수 불일치 — 종합 수치 {head_integ} vs 추적셀 {cell_integ}. "
            "종합 쪽이 파생되지 않은 상태다 (`--fix` 로 갱신할 것)."
        )
    cell_total = _first(_STATE_CELL_TOTAL, current)         # 추적셀 시작 전체
    cell_unit = _first(_STATE_CELL_UNIT, current)           # 추적셀 시작 단위
    md_badge, md_n = _exactly_one(_README_BADGE, readme, 2)   # (전체, 단위)
    ko_badge, ko_n = _exactly_one(_README_BADGE, readme_ko, 2)

    for label, val in [
        ("STATE 종합 수치", state_total), ("STATE 추적셀 전체", cell_total),
        ("STATE 추적셀 단위", cell_unit),
    ]:
        if val is None:
            msgs.append(f"❌ {label} 패턴 미발견 (형식 변경됐는지 확인)")
    if md_badge is None:
        msgs.append(
            f"❌ README.md Tests 배지 매치 {md_n}개 — 정확히 1개여야 한다 "
            "(선두 decoy 가 첫-매치로 쓰이는 것을 막는다)"
        )
    if ko_badge is None:
        msgs.append(
            f"❌ README.ko.md Tests 배지 매치 {ko_n}개 — 정확히 1개여야 한다 "
            "(선두 decoy 가 첫-매치로 쓰이는 것을 막는다)"
        )
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
    integ = _first(re.compile(r"통합 (\d+) \(현재\)"), current)
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

    pins: dict[str, str | None] = {
        name: _first(re.compile(rf"^{name}==({_VERSION})$", re.MULTILINE), reqs)
        for name in _DOC_PIN_NAMES
    }
    for name, pin in pins.items():
        if pin is None:
            msgs.append(f"❌ requirements.txt 에 `{name}==` 핀 미발견 (핀 형식 변경됐는지 확인)")

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
    current, region_errs = _region_before_history(state)
    if region_errs:
        return False, region_errs + ["→ 원장 절 밖을 한정할 수 없으면 쓰지 않는다"]
    if _first(_STATE_CELL_TOTAL, current) is None:
        return False, [
            "❌ §현재 수치 영역에서 `**N 수집**` 을 못 찾았다 — 검사 범위 붕괴. 원장에 쓰지 않았다.",
        ]

    total, unit, errs = _history_tail(state)
    if errs:
        return False, errs + ["→ 이력 마지막 항목을 먼저 올바른 형식으로 적을 것 (그것이 SSOT 다)"]

    integ = _first(re.compile(r"통합 (\d+) \(현재\)"), current)
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
    # 🔴 치환은 현재 영역만. 전역 sub 는 원장 `**5365 수집**` 을 덮는다 (단위 2 재현).
    # Substitutions stay in the current region. A global sub rewrites a ledger item.
    new_current = _STATE_TOTAL.sub(
        f"전체 **{total}** 수집 (단위 **{unit}** + 통합 {integ})", current, count=1
    )
    new_current = _STATE_CELL_TOTAL.sub(f"**{total} 수집**", new_current, count=1)
    new_current = _STATE_CELL_UNIT.sub(
        f"단위 {unit} + 통합 {integ} (현재)", new_current, count=1
    )
    heading_and_hist = state[len(current):]
    new_state = new_current + heading_and_hist
    # 사후 단언 — 원장 바이트가 바뀌면 쓰지 않는다 (구성이 틀려도 fail-closed).
    # Post-condition: refuse to write if the ledger bytes moved.
    _, _, orig_hist = state.partition(_STATE_HIST_HEADING)
    _, _, new_hist = new_state.partition(_STATE_HIST_HEADING)
    if orig_hist != new_hist:
        return False, [
            "❌ apply_fix 가 원장 절을 바꿨다 — 쓰지 않았다. "
            "치환이 §테스트 수 추적 이력 으로 미끄러졌다.",
        ]

    badge = f"Tests-{total}%2B_total_({unit}_unit_%2B_{integ}_integration)"
    # 🔴 어떤 파일도 쓰기 전에 양쪽 배지 매치가 1개인지 본다. 2개면
    #    count=1 sub 가 선두 decoy 를 덮는다 (CLAIM 4). STATE 를 먼저
    #    쓰면 부분 기록이 남는다.
    # Check before any write — a partial STATE write plus a refused README is worse.
    for name in ("README.md", "README.ko.md"):
        path = project_root / name
        text = path.read_text(encoding="utf-8")
        _val, n = _exactly_one(_README_BADGE, text, 2)
        if n != 1:
            return False, [
                f"❌ {name} Tests 배지 매치 {n}개 — 정확히 1개가 아니면 쓰지 않는다. "
                "선두 decoy 에 최신 누계를 덮어쓰지 않기 위함이다.",
            ]

    if new_state != state:
        state_path.write_text(new_state, encoding="utf-8", newline="\n")
        changed.append(f"✏️ docs/STATE.md — 종합 수치·추적셀 머리 → 전체 {total} / 단위 {unit}")

    for name in ("README.md", "README.ko.md"):
        path = project_root / name
        text = path.read_text(encoding="utf-8")
        fixed = _README_BADGE.sub(badge, text, count=1)
        if fixed != text:
            path.write_text(fixed, encoding="utf-8", newline="\n")
            changed.append(f"✏️ {name} — Tests 배지 → {total} ({unit} unit)")

    return True, changed or ["(이미 일치 — 변경 없음)"]


# --- pylint 진리값 5지점 (문서감사 PR-4, 2026-08-12) -------------------------
# 🔴 배지·STATE 2지점·ci.yml 주석이 **10.00/10** 을 주장했으나 실측은 **9.99/10** 이었다
#    (E1136 config.py · E1125 ai_review.py · C0302 pipeline.py). 5지점 어디에도 집행자가
#    없었다 — 이 파일은 Tests·FastAPI 배지만 봤고 CI 는 리터럴 floor 만 강제했다.
# The pylint score was claimed in five places and enforced in none.
_LINT_BADGE = re.compile(r"badge/pylint-(\d+\.\d+)%2F10")
_LINT_VALUE = re.compile(r"\*\*(\d+\.\d+)/10\*\*")
_LINT_CI_COMMENT = re.compile(r"현재\s+(\d+\.\d+)/10")


def _lint_from_line(text: str, prefix: str, pattern: re.Pattern) -> float | None:
    """`prefix` 로 시작하는 **줄**에서만 값을 뽑는다.

    🔴 파일 전역 검색을 쓰지 않는다 — `docs/STATE.md` 는 과거 사이클 서사에서 `pylint 10.00`
    을 여러 번 언급하고, 그것들은 **당시 사실 기록**이라 정정 대상이 아니다(docs.md 규칙).
    Line-scoped: historical cycle notes mention old scores and must not be rewritten.
    """
    for line in text.splitlines():
        if line.startswith(prefix):
            m = pattern.search(line)
            if m:
                return float(m.group(1))
    return None


def lint_badge_sites(project_root: Path) -> list[tuple[str, float | None]]:
    """pylint 값을 주장하는 5지점을 (이름, 값) 으로 수집한다."""
    sites: list[tuple[str, float | None]] = []
    for name in ("README.md", "README.ko.md"):
        text = (project_root / name).read_text(encoding="utf-8")
        m = _LINT_BADGE.search(text)
        sites.append((name, float(m.group(1)) if m else None))

    state = (project_root / "docs" / "STATE.md").read_text(encoding="utf-8")
    sites.append(("STATE.md 종합 수치", _lint_from_line(state, "**종합 수치**", _LINT_VALUE)))
    sites.append(("STATE.md pylint 행", _lint_from_line(state, "| pylint |", _LINT_VALUE)))

    ci = (project_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    m = _LINT_CI_COMMENT.search(ci)
    sites.append(("ci.yml 주석", float(m.group(1)) if m else None))
    return sites


def check_lint_badge(project_root: Path) -> tuple[bool, list[str]]:
    """5지점이 **같은 값**을 말하는가. 하나라도 못 읽으면 fail-closed."""
    sites = lint_badge_sites(project_root)
    missing = [name for name, value in sites if value is None]
    if missing:
        return False, [f"❌ pylint 값을 읽지 못한 지점: {', '.join(missing)} (정규식 drift 의심)"]
    values = {value for _, value in sites}
    if len(values) == 1:
        return True, []
    return False, [
        "❌ pylint 값이 지점마다 다르다:",
        *[f"   {name}: {value}" for name, value in sites],
        # 🔴 리스트 안 **암묵적** 문자열 연결 금지 — 쉼표 누락과 구별되지 않아 CodeQL
        #    `py/implicit-string-concatenation-in-list` 가 잡는다(#1331 에서 실제 red).
        # Explicit `+`: implicit concatenation inside a list is indistinguishable from a typo.
        "   🔴 CI 의 --fail-under 는 README 배지에서 파생되므로, 배지가 실측보다 높으면 "
        + "그 배지가 주장하는 빌드를 그 배지가 실패시킨다.",
    ]


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
    lint_ok, lint_msgs = check_lint_badge(project_root)
    print("=== docs 수치 정합 점검 / Docs Count-Sync Check ===\n")
    if ok:
        print("✅ STATE 종합·추적셀 ↔ README.md ↔ README.ko.md 전체/단위 카운트 일치")
    if pin_ok:
        print("✅ requirements.txt 핀 ↔ README FastAPI 배지 일치")
    if lint_ok:
        sites = lint_badge_sites(project_root)
        print(f"✅ pylint 값 5지점 일치 — {sites[0][1]}/10 (CI --fail-under 가 배지에서 파생)")
    if ok and pin_ok and lint_ok:
        return 0
    for m in msgs + pin_msgs + lint_msgs:
        print(m)
    print(
        "\n해결: (수치) 손으로 고칠 곳은 STATE.md §테스트 수 추적 이력 **현재 불릿 한 줄**뿐이다 —"
        " 그 줄을 실측값(`--collect-only`)으로 고친 뒤 `py -3 scripts/check_docs_sync.py --fix`"
        " 를 돌리면 나머지 4지점(종합 수치·추적셀 머리·README 2배지)이 파생된다."
        " (핀) requirements.txt 실핀에 맞춰 README/README.ko"
        " FastAPI 배지를 갱신."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
