"""함정 목록의 **개수는 한 곳에서만** 산다 (traps C1 의 자기적용).

## 사고 (2026-08-13~14 — C1 을 명명한 PR 이 C1 을 재생산했다)

`.claude/traps.md` 는 *"N지점 손유지는 N−1번의 실패 기회"* 를 **C1 로 명명한 파일**이다.
그런데 그 파일을 만든 바로 그 PR(`#1345`)이 클래스 **개수**를 4개 문서에 손으로 적었고,
2026-08-14 회고 실측 결과 **세 가지 값(16·16·17·17)이 공존했으며 넷 다 틀렸다**(실제 22).
`.claude/rules/guards.md` 는 심지어 자기가 만든 **A7 을 목록에서 뺀** 채 가드 저술자에게
자동 로드됐다 — path-scoped 규칙 파일이 거짓을 가르친 것이다.

## 이 파일이 강제하는 것

1. `traps.md` 가 선언한 개수가 **자기 본문 실측과 일치**한다.
2. 다른 문서는 그 숫자를 **복제하지 않는다** — 계열(A~E)만 가리킨다.
3. 계열 선언(A n · B n …)도 실측과 일치한다(합계만 맞고 내역이 틀리는 것을 막는다).

The count lives in exactly one place; pointers name the series, never the number.
"""
from __future__ import annotations

import collections
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_TRAPS = _ROOT / ".claude" / "traps.md"

# 개수를 복제하면 안 되는 포인터 문서 — 리터럴로 못박는다(유도하면 비워도 초록이다).
_POINTERS = (
    "CLAUDE.md",
    "docs/README.md",
    ".claude/rules/guards.md",
    ".claude/rules/testing.md",
    ".claude/rules/docs.md",
)

_CLASS = re.compile(r"^### ([A-E])(\d+)\.", re.MULTILINE)


def _measured() -> collections.Counter:
    return collections.Counter(m.group(1) for m in _CLASS.finditer(_TRAPS.read_text(encoding="utf-8")))


def test_declared_total_matches_the_file_itself():
    """🔴 traps.md 가 선언한 총수 == 그 파일의 `### X<n>.` 실측."""
    body = _TRAPS.read_text(encoding="utf-8")
    measured = sum(_measured().values())

    m = re.search(r"현재\s*\**\s*(\d+)\s*클래스", body)
    assert m, "traps.md 에 `현재 **N 클래스**` 선언이 없다 — 개수의 단일 출처가 사라졌다"
    declared = int(m.group(1))

    assert declared == measured, (
        f"traps.md 선언 {declared} != 실측 {measured}. "
        "항목을 추가/삭제했으면 머리말의 숫자도 같은 커밋에서 고칠 것."
    )
    assert measured >= 10, f"클래스를 {measured}개만 찾았다 — 정규식이 깨졌는지 확인(공허 방지)"


def test_declared_series_breakdown_matches():
    """대조군 — 합계만 맞고 계열 내역이 틀리면 다음 인용이 또 갈라진다."""
    body = _TRAPS.read_text(encoding="utf-8")
    measured = _measured()

    m = re.search(r"\(A (\d+) · B (\d+) · C (\d+) · D (\d+) · E (\d+)", body)
    assert m, "계열 내역 선언이 없다"
    for i, series in enumerate("ABCDE"):
        assert int(m.group(i + 1)) == measured[series], (
            f"계열 {series}: 선언 {m.group(i + 1)} != 실측 {measured[series]}"
        )


def test_pointers_do_not_duplicate_the_number():
    """🔴 **포인터는 숫자를 복제하지 않는다** — 복제가 곧 다음 drift 다.

    2026-08-13 판은 네 문서가 각자 숫자를 적었고 세 값이 공존했다. 링크에 개수는
    아무 정보도 더하지 않는다(클릭하면 나온다) — 그래서 아예 금지한다.
    """
    pat = re.compile(r"traps\.md[^\n]{0,120}?(\d+)\s*(?:클래스|종)")
    offenders = []
    for name in _POINTERS:
        p = _ROOT / name
        if not p.exists():
            continue
        for m in pat.finditer(p.read_text(encoding="utf-8")):
            offenders.append(f"{name}: …{m.group(0)[:70]}…")

    assert not offenders, (
        "포인터 문서가 함정 개수를 복제한다 — 개수는 `.claude/traps.md` 에만 적는다:\n  "
        + "\n  ".join(offenders)
    )
