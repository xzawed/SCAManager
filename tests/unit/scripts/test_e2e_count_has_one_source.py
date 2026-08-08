"""E2E 테스트 수는 **한 곳에서만 온다** — 문서 사본이 조용히 갈라지지 않게 (회고 N-P0-4).

## 사고 (2026-08-08 회고 실측)

`docs/STATE.md` 안에서 **같은 파일이 자기 자신과 모순**이었다:

| 지점 | 값 |
|---|---|
| STATE 종합 수치 | 121 |
| STATE §테스트 유형 표 `E2E 테스트` 셀 | 🔴 **122** |
| `e2e/EXPECTED_COUNT` (기계 baseline) | 121 |
| README.md · README.ko.md 배지 | 121 · 121 |

`#1291` 이 중복 1건을 제거할 때 종합 수치는 따라왔고 그 셀만 뒤처졌다. 🔴 **1년 가까이
아무도 못 잡은 이유는 단순하다 — 이 축에는 기계 대조가 없었다.**
`check_docs_sync` 는 단위/통합만 보고, `check_test_count_sync` 도 `tests/unit`+`tests/integration`
만 세며, `check_e2e_scope` 는 `EXPECTED_COUNT` 하나만 본다. 셋 다 E2E **문서 사본**은 안 본다.

🔴 이것이 그 회고의 가장 깨끗한 대조 실험이었다 — **같은 문서, 같은 세션에서 집행자가
붙은 숫자는 100% 정확했고 안 붙은 숫자는 8곳이 틀렸다.** 문제는 문서의 *양*이 아니라
*집행 여부*다.

## 이 파일이 강제하는 것

`e2e/EXPECTED_COUNT` 를 **단일 출처**로 삼아 STATE 2지점 + README 2배지를 대조한다.
기대값을 손으로 적지 않는다 — baseline 파일에서 읽는다.

One source of truth for the E2E count; every doc copy is compared against it.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_BASELINE = _ROOT / "e2e" / "EXPECTED_COUNT"


def expected_count() -> int:
    """기계 baseline. 이 파일이 없거나 깨지면 **여기서 먼저** 실패해야 한다."""
    assert _BASELINE.exists(), f"{_BASELINE} 이 없다 — 이 가드의 단일 출처가 사라졌다"
    raw = _BASELINE.read_text(encoding="utf-8").strip()
    assert raw.isdigit(), f"baseline 이 정수가 아니다: {raw!r}"
    return int(raw)


def test_baseline_is_sane():
    """🔴 대조군 — baseline 이 0 이면 아래 단언이 전부 무의미해진다."""
    assert expected_count() > 0, "E2E baseline 이 0 — 빈 값 위의 ✅ 는 fail-open"


@pytest.mark.parametrize(
    ("doc", "pattern", "what"),
    [
        ("docs/STATE.md", r"E2E \*\*(\d+)\*\* \(`#1291`", "STATE 종합 수치"),
        ("docs/STATE.md", r"\| E2E 테스트 \| \*\*(\d+)개\*\* \|", "STATE 테스트 유형 표"),
        ("README.md", r"E2E-(\d+)_in_CI", "README.md 배지"),
        ("README.ko.md", r"E2E-(\d+)_CI", "README.ko.md 배지"),
    ],
)
def test_every_doc_copy_matches_the_baseline(doc: str, pattern: str, what: str):
    """🔴 봉인 — 사본 하나가 갈라지면 여기서 깨진다.

    실측 사고: STATE 테스트 유형 표만 122 로 남아 같은 파일 종합 수치(121)와 모순이었다.
    """
    text = (_ROOT / doc).read_text(encoding="utf-8")
    match = re.search(pattern, text)

    assert match, (
        f"{doc} 에서 {what} 수치를 찾지 못했다 (패턴 `{pattern}`).\n"
        "→ 표기를 바꿨다면 이 가드의 패턴도 함께 갱신할 것. **패턴 미매치는 통과가 아니다** — "
        "찾지 못하면 이 축이 조용히 사라진다."
    )
    assert int(match.group(1)) == expected_count(), (
        f"{doc} 의 {what} = {match.group(1)} ≠ `e2e/EXPECTED_COUNT` = {expected_count()}\n"
        "→ E2E 수가 바뀌면 baseline 과 문서 4지점을 **같은 PR 에서** 맞출 것."
    )


def test_the_collected_cell_breakdown_adds_up():
    """`= N collected (a 표준 + b perf)` 의 **합계** 축만 본다 — 성분은 여기서 못 잰다.

    🔴 **초판은 이 한계를 모른 채 "내역을 지킨다" 고 적었고, 그래서 거짓을 초록으로
    지켰다** (2026-08-08 적대 검증 P0). `#1316` 이 총계를 122→121 로 고치며 내역을
    `109 표준 + 12 perf` 로 적었는데 실측은 **110 + 11** — 두 성분 다 거짓이었다.
    합이 121 로 맞으니 이 테스트는 통과했다. **합이 맞는 거짓 쌍은 무한히 많다.**

    성분을 실제로 재려면 `-m perf` / `-m "not perf"` 로 e2e 를 수집해야 하는데, 그건
    playwright 환경이 필요해 **단위 테스트 job 에서 돌릴 수 없다**. 그래서 그 축은
    `scripts/check_e2e_scope.py::_check_documented_split` 으로 옮겼다 — 이미 e2e 를
    수집하는 유일한 CI 지점이다. 아래 배선 테스트가 그 이관을 고정한다.
    A sum-only check cannot catch a wrong-but-consistent pair; the component axis lives
    where e2e can actually be collected.
    """
    text = (_ROOT / "docs" / "STATE.md").read_text(encoding="utf-8")
    match = re.search(r"= (\d+) collected \((\d+) 표준 \+ (\d+) perf\)", text)

    assert match, "E2E collected 내역 표기를 찾지 못했다 — 이 축이 사라졌다"
    total, standard, perf = (int(g) for g in match.groups())
    assert total == standard + perf, f"내역 합이 안 맞는다: {standard} + {perf} ≠ {total}"
    assert total == expected_count(), f"내역 합계 {total} ≠ baseline {expected_count()}"


def test_the_component_axis_is_actually_enforced_somewhere():
    """🔴 배선 — 위 테스트가 못 보는 축을 **누군가는** 실제로 재는지.

    이 단언이 없으면 "성분은 다른 데서 잰다" 는 위 docstring 이 **검증되지 않은 산문**이
    된다. 이 리포가 반복해 고쳐 온 형태다(관측은 넘겼는데 받는 쪽이 없다).
    """
    scope = (_ROOT / "scripts" / "check_e2e_scope.py").read_text(encoding="utf-8")
    tree = ast.parse(scope)

    checker = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == "_check_documented_split"),
        None,
    )
    assert checker is not None, (
        "check_e2e_scope.py 에 성분 대조가 없다 — E2E 내역이 다시 무집행이 된다"
    )

    body = ast.unparse(checker)
    assert "표준" in body and "perf" in body, "성분 이름을 읽지 않는다 — 대조가 공허하다"

    called = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_check_documented_split"
        for n in ast.walk(tree)
    )
    assert called, "성분 대조를 정의만 하고 **부르지 않는다** — 정의 ≠ 배선"
