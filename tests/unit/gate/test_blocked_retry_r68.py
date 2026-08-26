"""required check 대기 중 auto-merge 가 PR 을 버리지 않는다 (backlog R68).

## 사고 기전 (2026-08-08, 사용자 확인: auto-merge 를 실제로 운용한다)

`mergeable_state="blocked"` 는 GitHub 이 **두 가지를 뭉뚱그린** 값이다:

| 경우 | 실체 | 올바른 처리 |
|---|---|---|
| (a) required check 가 아직 **도는 중** | 몇 분 뒤 풀린다 | **재시도** |
| (b) 규칙상 충족 불가(리뷰 미승인 등) | 기다려도 안 풀린다 | 종결 |

이전 계약은 `BRANCH_PROTECTION_BLOCKED` 를 `_RETRIABLE_TAGS` 에서 빼 **전부 (b)로** 처리했다.
그 결과 분석(정적 60s + AI 리뷰)이 끝난 시점에 required check 가 아직 돌고 있으면
**정상 PR 이 재시도 없이 영구 포기**됐다.

🔴 이 리포는 required check **10종** + `enforce_admins: true` 를 쓰고 그중 pytest·e2e 는
수 분이 걸린다 — (a)가 일상적으로 발생하는 구성이다.

## 이 파일이 고정하는 계약

1. `blocked` 는 **대기 가능** 태그다 (`is_retriable_tag` True)
2. 🔴 그러나 **CI 가 도는 중일 때만** 재시도로 확정된다 —
   CI 가 끝났는데도 blocked 면 그것은 (b)이고, 재시도 예산만 태운다
3. 다른 종결 태그(`dirty_conflict` 등)는 **여전히 종결**이다 — 이 변경이 게이트 전체를
   느슨하게 만들지 않았음을 대조군으로 고정한다
"""
from __future__ import annotations

import pytest

from src.gate.merge_reasons import (
    BRANCH_PROTECTION_BLOCKED,
    DIRTY_CONFLICT,
    UNSTABLE_CI,
    is_retriable_tag,
)
from src.gate.retry_policy import should_retry


# ── ① 대기 가능 태그로 승격됐다 ─────────────────────────────────────────


def test_blocked_is_now_retriable():
    """🔴 계약 변경 — 이전에는 종결이었다.

    이 한 줄이 '분석 끝났는데 체크가 아직 돌고 있어서 버려진' PR 을 살린다.
    """
    assert is_retriable_tag(BRANCH_PROTECTION_BLOCKED) is True


def test_genuinely_terminal_tags_stay_terminal():
    """🔴 대조군 — 이 변경이 게이트 전체를 느슨하게 만들지 않았는지.

    이게 없으면 위 단언은 "전부 retriable" 인 구현으로도 만족된다(가드 자살).
    """
    for tag in (DIRTY_CONFLICT, "permission_denied", "not_mergeable",
                "sensitive_path_hold", "draft_pr", "behind_base"):
        assert is_retriable_tag(tag) is False, f"{tag} 가 재시도 가능해졌다 — 과도한 완화"


# ── ② 🔴 무조건 재시도가 아니다 — CI 가 도는 중일 때만 ──────────────────


@pytest.mark.parametrize(
    ("ci_status", "expected", "why"),
    [
        ("running", True, "(a) required check 진행 중 — 몇 분 뒤 풀린다"),
        ("passed", False, "(b) CI 는 끝났는데 여전히 blocked = 규칙상 충족 불가"),
        ("failed", False, "(b) CI 실패 — 기다려도 머지되지 않는다"),
        ("unknown", False, "불명확할 때는 종결이 안전하다 — 사람이 다시 밀면 새 게이트가 돈다"),
    ],
)
def test_blocked_retries_only_while_ci_runs(ci_status: str, expected: bool, why: str):
    """🔴 (b)를 배제하는 것이 이 분기의 존재 이유다.

    `passed` 까지 재시도하면 리뷰 미승인 PR 이 max_attempts(기본 30)를 다 태운다.
    `UNSTABLE_CI` 가 `passed` 를 허용하는 것은 **merge-API lag** 때문이고 그 축은
    이미 그 태그가 담당한다 — 여기서 중복 허용할 이유가 없다.
    """
    assert should_retry(BRANCH_PROTECTION_BLOCKED, ci_status) is expected, why


def test_unstable_ci_still_allows_passed():
    """대조군 — 기존 태그의 타이밍 계약을 건드리지 않았는지(merge-API lag 허용)."""
    assert should_retry(UNSTABLE_CI, "passed") is True


def test_terminal_tag_never_retries_regardless_of_ci():
    """대조군 — 종결 태그는 CI 상태와 무관하게 재시도하지 않는다."""
    for status in ("running", "passed", "failed", "unknown"):
        assert should_retry(DIRTY_CONFLICT, status) is False


# ── ③ 예산이 무한하지 않다 ──────────────────────────────────────────────


def test_retry_budget_still_bounds_the_new_tag():
    """🔴 '재시도 가능' 이 '영원히 재시도' 는 아니다 — 예산 상한을 확인한다.

    (a)가 오래가는 병리적 상황(체크가 영영 안 끝남)에서도 `max_attempts` 와
    `max_age` 가 큐를 비운다. 그 두 상한이 실재하는지 여기서 고정한다 —
    없으면 이 변경이 **무한 재시도**를 만든다.
    """
    from src.gate import retry_policy

    source = __import__("pathlib").Path(retry_policy.__file__).read_text(encoding="utf-8")
    assert "is_expired" in source, "만료(max_age) 축이 사라졌다 — 무한 재시도 위험"
    assert "compute_next_retry_at" in source, "백오프가 사라졌다 — 즉시 재시도 폭주 위험"

# ── ④ 인용문이 코드보다 오래 산다 ─────────────────────


def test_no_gate_docstring_enumerates_a_stale_retriable_set():
    """`src/gate` 의 어떤 docstring 도 재시도 가능 집합을 **낡은 채로 열거**하지 않는다.

    R68 이 `BRANCH_PROTECTION_BLOCKED` 를 대기 가능으로 올려 집합이 3개가 됐을 때,
    그것을 이름으로 열거한 산문은 2개인 채로 남았다 — 한 곳은 정본 모듈
    `merge_reasons.is_retriable_tag` 의 docstring 자신이었다. 아무것도 red 가 되지 않았다.

    규칙: docstring 은 태그를 **한 개까지** 이름으로 들 수 있다(어떤 기전을 설명하려면
    그 태그를 불러야 한다). 두 개 이상을 들면 그것은 열거이고, `_RETRIABLE_TAGS` 와
    **정확히 일치**해야 한다. 열거하지 않는 것이 안전한 상태다.

    이 검사의 범위: `src/gate` 아래 docstring 에 나타난 **태그 상수 이름**뿐이다.
    주석·산문의 다른 주장이 참인지는 재지 못한다.

    A docstring may name at most one tag; naming two or more is an enumeration and must
    match `_RETRIABLE_TAGS` exactly. Scope: tag-constant names in src/gate docstrings.
    """
    import ast
    from pathlib import Path

    from src.gate import merge_reasons as mr

    tag_names = {
        n for n, v in vars(mr).items()
        if n.isupper() and isinstance(v, str) and not n.startswith("_")
    }
    retriable_names = {n for n in tag_names if getattr(mr, n) in mr._RETRIABLE_TAGS}
    assert retriable_names, "태그 상수를 하나도 못 찾았다 — 이 검사가 공허해졌다"

    gate_dir = Path(mr.__file__).parent
    offenders = []
    for path in sorted(gate_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        nodes = [tree] + [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        for node in nodes:
            doc = ast.get_docstring(node) or ""
            # 식별자 경계로 자른다 — UNKNOWN 이 UNKNOWN_STATE_TIMEOUT 에 걸리지 않게
            # Split on identifier boundaries so a prefix cannot match a longer constant
            words = set(
                "".join(c if (c.isalnum() or c == "_") else " " for c in doc).split()
            )
            named = tag_names & words
            if len(named) >= 2 and named != retriable_names:
                where = getattr(node, "name", "<module>")
                offenders.append(
                    f"{path.name}::{where} 가 {sorted(named)} 를 열거 "
                    f"(정본은 {sorted(retriable_names)})"
                )

    assert not offenders, (
        "재시도 가능 집합을 낡은 채로 열거한 docstring: "
        + " / ".join(offenders)
        + " — 정본은 merge_reasons._RETRIABLE_TAGS 다. 열거를 지우고 그것을 가리켜라."
    )
