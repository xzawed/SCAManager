"""PR 워크플로가 base 브랜치와 무관하게 발화하는지 — 게이트 우회 차단 (#1432).

## 왜 (2026-08-17 실측)

`on.pull_request.branches: [main]` 이면 base 가 **다른 feature 브랜치**인 PR 에서
워크플로가 **아예 발화하지 않는다**. 그 PR 은 CI 0건 · claim-review 0건으로 머지된다.

이 리포에서 실제로 그렇게 머지된 PR (`gh pr list --state merged` 실측):

    #1402 base=docs/final-cleanup           checks=no checks reported
    #1399 base=docs/retire-owed-and-history checks=no checks reported
    #1398 base=docs/retire-owed-and-history checks=no checks reported
    #1389 base=docs/melt-state-ledger       checks=no checks reported

## 🔴 이 가드가 닫는 것과 **닫지 못하는 것** (정직 기준)

닫는다 — **관측**. 스택 PR 에서도 CI 가 돌아 저자와 리뷰어가 red 를 본다.

**닫지 못한다** — **집행**. 머지를 막는 것은 branch protection / ruleset 인데 둘 다
`refs/heads/main` 만 대상으로 한다(2026-08-17 실측):

    gh api .../branches/main/protection/required_status_checks  → main 전용 10종
    gh api .../rulesets/17144307 → conditions.ref_name.include = ["refs/heads/main"]

즉 feature 브랜치를 base 로 한 PR 은 **check 가 0건이라 통과한 게 아니라, 애초에 규칙이
적용되지 않는다.** 집행까지 원하면 ruleset 의 `ref_name.include` 를 넓혀야 하고 그것은
리포 설정 변경이라 이 리포의 가드가 볼 수 없다. 여기서는 그 사실을 **적어만 둔다** —
이 테스트가 초록이라고 「스택 PR 이 막힌다」로 읽히면 새 observer-lie 다.

Ensures PR-triggered workflows are not scoped to a single base branch, so stacked PRs still
run CI. Note this buys visibility, not enforcement: branch protection targets main only.
"""
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOWS = _ROOT / ".github" / "workflows"

# `on:` 블록 안의 `pull_request:` 다음에 오는 `branches:` 목록.
# 들여쓰기 2칸 = `on:` 직속 이벤트, 4칸 = 그 이벤트의 필터.
_PR_BRANCHES = re.compile(
    r"^\s{2}pull_request(?:_target)?:\s*$\n(?:^\s{4}\w[^\n]*$\n)*?^\s{4}branches:\s*(?P<v>[^\n]+)$",
    re.MULTILINE,
)


def _pr_workflows() -> list[Path]:
    """`pull_request` 로 발화하는 워크플로 파일들."""
    found = [
        p for p in sorted(_WORKFLOWS.glob("*.yml"))
        if re.search(r"^\s{2}pull_request(?:_target)?:", p.read_text(encoding="utf-8"), re.M)
    ]
    # 🔴 공허화 차단 — 분모가 비면 이 테스트는 아무것도 재지 않는다.
    # Vacuity guard: an empty denominator would make every assertion below trivially true.
    assert found, ".github/workflows 에 pull_request 워크플로가 0건 — 이 테스트가 공허하다"
    return found


@pytest.mark.parametrize("wf", _pr_workflows(), ids=lambda p: p.name)
def test_pr_workflow_is_not_scoped_to_a_single_base_branch(wf: Path):
    """`on.pull_request.branches` 로 base 를 좁히면 스택 PR 이 CI 0건으로 머지된다 (#1432)."""
    text = wf.read_text(encoding="utf-8")
    hit = _PR_BRANCHES.search(text)
    assert hit is None, (
        f"{wf.name}: `on.pull_request` 가 base 를 {hit.group('v').strip() if hit else ''} 로 "
        "제한한다 — base 가 그 밖인 PR 은 워크플로가 발화하지 않아 CI 0건으로 머지된다.\n"
        "→ `branches:` 줄을 지워 모든 base 에서 발화시킨다 (#1432 옵션 A).\n"
        "⚠️ 이것은 관측을 되살릴 뿐 머지를 막지는 않는다 — branch protection 은 main 전용이다."
    )


def test_guard_regex_actually_matches_the_shape_it_forbids():
    """🔴 정규식 자기검증 — 금지 형태를 실제로 잡는가.

    이 단언이 없으면 `_PR_BRANCHES` 가 무엇도 매칭하지 못하게 망가져도 위 테스트는
    영원히 초록이다(가드가 자기 눈을 잃는 형태). 합성 문자열로 눈이 살아 있음을 고정한다.
    Self-check: a regex that matches nothing would make the guard above permanently green.
    """
    forbidden = "on:\n  push:\n    branches: [main]\n  pull_request:\n    branches: [main]\n"
    assert _PR_BRANCHES.search(forbidden) is not None, "가드 정규식이 금지 형태를 놓친다"

    allowed = "on:\n  push:\n    branches: [main]\n  pull_request:\n    types: [edited]\n"
    assert _PR_BRANCHES.search(allowed) is None, "가드 정규식이 허용 형태를 오탐한다"

    # `push:` 의 `branches:` 는 잡으면 안 된다 — main push 한정은 정당하다.
    push_only = "on:\n  push:\n    branches: [main]\n"
    assert _PR_BRANCHES.search(push_only) is None, "push 의 branches 를 pull_request 로 오인한다"
