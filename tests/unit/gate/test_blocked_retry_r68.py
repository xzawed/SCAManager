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
`src/gate/sensitive_paths.py:18~20` 이 이미 그 성질을 실측으로 기록해 뒀다:
*"오히려 자동 머지를 죽인다 … 이 태그는 `_RETRIABLE_TAGS` 에 없다(실측) → 종결 실패"*.

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
