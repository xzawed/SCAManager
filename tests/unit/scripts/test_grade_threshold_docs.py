"""문서의 등급 임계값 ↔ `src/constants.py::GRADE_THRESHOLDS` 대조.

## 사고 (2026-08-01 문서 감사)

`docs/design/brief/00-service-overview.md` 와 `03-design-direction.md` 가 등급 임계값을
**A 90 / B 80 / C 70 / D 60 / F <60** 이라 적고 있었다. 실제 정본
(`src/constants.py::GRADE_THRESHOLDS`)은 **A 90 / B 75 / C 60 / D 45 / F <45** 다.

🔴 **행동 영향**: 이 브리프는 UI 색상 체계와 서비스 설명의 근거 문서다. 여기서 임계값을 읽고
작업하면 대시보드 색상 경계·문구·테스트 기대값이 전부 어긋난다. 그리고 **두 문서가 같은
오류를 공유**했다 — 한쪽만 고치면 다른 쪽이 남는 전형이다.

## 이 파일이 강제하는 것

기대값을 손으로 적지 않고 **`src/constants.py` 에서 파싱**한다. 임계값이 바뀌면 문서도
따라와야 하고, 안 따라오면 여기서 깨진다. 🔴 문서에 수치를 박는 것 자체가 drift 원인이므로,
새 문서는 가급적 `scoring.md` 를 링크하고 수치를 복제하지 않는 편이 낫다.

Cross-checks grade thresholds written in docs against the single source in constants.py.
"""
import ast
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_CONSTANTS = _ROOT / "src" / "constants.py"

# 임계값을 문장으로 적는 문서들 (등급 문자 + 숫자 패턴이 나타나는 곳).
_DOCS = (
    "docs/design/brief/00-service-overview.md",
    "docs/design/brief/03-design-direction.md",
)

# `A(90+)` · `A (90+)` · `A 90` 형태를 모두 잡는다.
_GRADE_IN_DOC = re.compile(r"\b([ABCD])\s*\(?\s*(\d{2})\s*\+?\s*\)?")


def canonical_thresholds() -> dict:
    """`GRADE_THRESHOLDS` 를 AST 로 읽는다 — import 부작용 없이."""
    tree = ast.parse(_CONSTANTS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
        if target == "GRADE_THRESHOLDS" and node.value is not None:
            return ast.literal_eval(node.value)
    raise AssertionError("constants.py 에서 GRADE_THRESHOLDS 를 못 찾았다")


def test_canonical_source_is_parseable():
    """🔴 대조군 — 정본을 못 읽으면 아래 단언이 공허하다."""
    t = canonical_thresholds()
    assert set(t) == {"A", "B", "C", "D"}, f"등급 집합이 바뀌었다: {t}"
    assert t["A"] > t["B"] > t["C"] > t["D"], f"단조 감소가 깨졌다: {t}"


@pytest.mark.parametrize("doc", _DOCS)
def test_doc_thresholds_match_constants(doc):
    """🔴 문서에 적힌 등급 임계값이 정본과 일치해야 한다."""
    canon = canonical_thresholds()
    path = _ROOT / doc
    assert path.exists(), f"{doc} 가 없다 — 목록 갱신 필요"

    wrong = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for grade, value in _GRADE_IN_DOC.findall(line):
            if int(value) != canon[grade]:
                wrong.append(f"{doc}:{lineno} — {grade}={value} (정본 {canon[grade]}) :: {line.strip()[:90]}")
    assert not wrong, (
        "문서의 등급 임계값이 `src/constants.py::GRADE_THRESHOLDS` 와 다르다:\n  "
        + "\n  ".join(wrong)
        + "\n→ 문서를 고치거나, 아예 수치를 빼고 `docs/reference/scoring.md` 를 링크할 것."
    )


def test_detector_would_catch_a_wrong_value():
    """🔴 판정기가 공허하지 않은지 — 틀린 값을 실제로 잡는가."""
    canon = canonical_thresholds()
    found = _GRADE_IN_DOC.findall(f"- A({canon['A']}+) / B({canon['B'] + 5}+)")
    assert ("B", str(canon["B"] + 5)) in found, "패턴이 등급-숫자 쌍을 못 뽑는다"
